using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Options;

namespace Showheel.Services.Ai;

/// <summary>
/// Thin client for OpenAI-compatible providers. Handles chat completions and
/// embeddings. The API key is attached per-request from server-side config and
/// never leaves the server. All external content returned here is treated as
/// untrusted and is not executed.
/// </summary>
public sealed class OpenAiCompatibleClient
{
    private readonly HttpClient _http;
    private readonly ILogger<OpenAiCompatibleClient> _logger;
    private readonly AiResponseCache _cache;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public OpenAiCompatibleClient(HttpClient http, AiResponseCache cache, ILogger<OpenAiCompatibleClient> logger)
    {
        _http = http;
        _cache = cache;
        _logger = logger;
    }

    /// <summary>Runs a chat completion against the given provider.</summary>
    public async Task<string> ChatAsync(
        ProviderOptions provider,
        IReadOnlyList<ChatMessage> messages,
        double temperature = 0.4,
        ThinkingLevel thinking = ThinkingLevel.Normal,
        CancellationToken ct = default)
    {
        if (!provider.IsConfigured)
            throw new InvalidOperationException("AI provider is not configured.");

        // Cache on the full request shape: identical prompts return the cached reply,
        // avoiding a paid round-trip. Temperature is part of the key so different
        // sampling settings don't collide.
        var key = AiResponseCache.Key("chat", provider.Model, temperature, thinking.ToString(),
            messages.Select(m => new { m.Role, m.Content }));

        return await _cache.GetOrAddChatAsync(key, async () =>
        {
            var payload = BuildChatPayload(
                provider,
                messages.Select(m => new { role = m.Role, content = (object)m.Content }),
                temperature,
                thinking);

            using var req = BuildRequest(provider, "chat/completions", payload);
            using var res = await _http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);
            await EnsureSuccess(res, ct);

            var body = await res.Content.ReadFromJsonAsync<ChatResponse>(JsonOpts, ct);
            return body?.Choices?.FirstOrDefault()?.Message?.Content?.Trim() ?? "";
        });
    }

    /// <summary>Chat completion that accepts multimodal messages (text + images) for vision models.</summary>
    public async Task<string> ChatMultimodalAsync(
        ProviderOptions provider,
        IReadOnlyList<MultimodalMessage> messages,
        double temperature = 0.4,
        ThinkingLevel thinking = ThinkingLevel.Normal,
        CancellationToken ct = default)
    {
        if (!provider.IsConfigured)
            throw new InvalidOperationException("AI provider is not configured.");

        var key = AiResponseCache.Key("chat-mm", provider.Model, temperature, thinking.ToString(),
            messages.Select(m => new { m.Role, m.Text, m.ImageUrls }));

        return await _cache.GetOrAddChatAsync(key, async () =>
        {
            var payload = BuildChatPayload(
                provider,
                messages.Select(m => new { role = m.Role, content = m.ToContentParts() }),
                temperature,
                thinking);

            using var req = BuildRequest(provider, "chat/completions", payload);
            using var res = await _http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);
            await EnsureSuccess(res, ct);

            var body = await res.Content.ReadFromJsonAsync<ChatResponse>(JsonOpts, ct);
            return body?.Choices?.FirstOrDefault()?.Message?.Content?.Trim() ?? "";
        });
    }

    /// <summary>
    /// Builds the chat payload as a dictionary so optional fields (reasoning_effort,
    /// max_tokens) are only sent when set. Providers ignore unknown fields.
    /// </summary>
    private static Dictionary<string, object?> BuildChatPayload(
        ProviderOptions provider, object messages, double temperature, ThinkingLevel thinking)
    {
        var payload = new Dictionary<string, object?>
        {
            ["model"] = provider.Model,
            ["temperature"] = temperature,
            ["messages"] = messages
        };
        if (thinking != ThinkingLevel.Normal)
            payload["reasoning_effort"] = thinking.ToApiValue();
        var maxTokens = thinking.MaxTokens();
        if (maxTokens is not null)
            payload["max_tokens"] = maxTokens.Value;
        return payload;
    }

    /// <summary>Embeds a batch of texts. Returns one vector per input, in order.</summary>
    public async Task<List<float[]>> EmbedAsync(
        ProviderOptions provider,
        IReadOnlyList<string> inputs,
        CancellationToken ct = default)
    {
        if (!provider.IsConfigured)
            throw new InvalidOperationException("Embedding provider is not configured.");
        if (inputs.Count == 0) return new();

        // Embeddings are deterministic for a given model+input, so caching the batch
        // eliminates repeated re-embedding of the same RAG query / chunk text.
        var key = AiResponseCache.Key("embed", provider.Model, inputs);

        return await _cache.GetOrAddEmbeddingsAsync(key, async () =>
        {
            using var req = BuildRequest(provider, "embeddings", new
            {
                model = provider.Model,
                input = inputs
            });

            using var res = await _http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);
            await EnsureSuccess(res, ct);

            var body = await res.Content.ReadFromJsonAsync<EmbeddingResponse>(JsonOpts, ct);
            return body?.Data?
                .OrderBy(d => d.Index)
                .Select(d => d.Embedding ?? Array.Empty<float>())
                .ToList() ?? new();
        });
    }

    private static HttpRequestMessage BuildRequest(ProviderOptions p, string path, object payload)
    {
        var baseUrl = p.BaseUrl.TrimEnd('/');
        var req = new HttpRequestMessage(HttpMethod.Post, $"{baseUrl}/{path}")
        {
            Content = JsonContent.Create(payload, options: JsonOpts)
        };
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", p.ApiKey);
        return req;
    }

    private async Task EnsureSuccess(HttpResponseMessage res, CancellationToken ct)
    {
        if (res.IsSuccessStatusCode) return;
        var text = await res.Content.ReadAsStringAsync(ct);
        // Log details server-side; surface a redacted message to callers.
        _logger.LogWarning("AI provider returned {Status}: {Body}", (int)res.StatusCode, text);
        throw new AiProviderException($"AI provider returned {(int)res.StatusCode} ({res.ReasonPhrase}).");
    }

    // --- wire types ---

    private sealed class ChatResponse
    {
        [JsonPropertyName("choices")] public List<Choice>? Choices { get; set; }
    }
    private sealed class Choice
    {
        [JsonPropertyName("message")] public ChatMessage? Message { get; set; }
    }
    private sealed class EmbeddingResponse
    {
        [JsonPropertyName("data")] public List<EmbeddingDatum>? Data { get; set; }
    }
    private sealed class EmbeddingDatum
    {
        [JsonPropertyName("index")] public int Index { get; set; }
        [JsonPropertyName("embedding")] public float[]? Embedding { get; set; }
    }
}

public sealed class ChatMessage
{
    [JsonPropertyName("role")] public string Role { get; set; } = "user";
    [JsonPropertyName("content")] public string Content { get; set; } = "";

    public static ChatMessage System(string c) => new() { Role = "system", Content = c };
    public static ChatMessage User(string c) => new() { Role = "user", Content = c };
    public static ChatMessage Assistant(string c) => new() { Role = "assistant", Content = c };
}

public sealed class AiProviderException : Exception
{
    public AiProviderException(string message) : base(message) { }
}
