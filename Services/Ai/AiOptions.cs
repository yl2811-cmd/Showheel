namespace Showheel.Services.Ai;

/// <summary>
/// Configuration for the AI providers. Bound from configuration section "Ai".
/// Keys are server-side only (appsettings / user-secrets / env vars) and are never
/// sent to the browser. There are three logical roles:
///   - CoAuthor: the "main brain" that restructures/edits the story tree.
///   - Embeddings: builds the RAG index for whole-book awareness.
///   - Translator: a *separate* model used only for on-demand translation of a
///     browsing region (kept apart from the co-author on purpose).
/// All three speak the OpenAI-compatible protocol (base URL + key + model), which
/// covers OpenAI, DeepSeek, OpenRouter, local Ollama, and most Chinese providers.
/// </summary>
public sealed class AiOptions
{
    public const string SectionName = "Ai";

    public ProviderOptions CoAuthor { get; set; } = new();
    public ProviderOptions Embeddings { get; set; } = new();
    public ProviderOptions Translator { get; set; } = new();

    /// <summary>
    /// Optional model-name → max context window (tokens) overrides. Matched
    /// case-insensitively as a substring of the model name, so "gpt-4o" covers
    /// "gpt-4o-mini" etc. Overrides the built-in defaults in <see cref="ModelContextLimits"/>.
    /// </summary>
    public Dictionary<string, int> ModelContextLimits { get; set; } = new();
}

public sealed class ProviderOptions
{
    /// <summary>e.g. https://api.openai.com/v1 or https://api.deepseek.com/v1 . No trailing slash needed.</summary>
    public string BaseUrl { get; set; } = "";

    /// <summary>Secret API key. Keep in user-secrets or environment, not in committed appsettings.</summary>
    public string ApiKey { get; set; } = "";

    /// <summary>Model name, e.g. gpt-4o-mini, deepseek-chat, text-embedding-3-small.</summary>
    public string Model { get; set; } = "";

    /// <summary>
    /// Optional explicit max context window (tokens) for this provider's model. When set,
    /// it wins over the name-based lookup — useful when a provider serves a large-context
    /// variant the built-in map can't infer from the name alone.
    /// </summary>
    public int? MaxContextTokens { get; set; }

    public bool IsConfigured =>
        !string.IsNullOrWhiteSpace(BaseUrl) &&
        !string.IsNullOrWhiteSpace(ApiKey) &&
        !string.IsNullOrWhiteSpace(Model);
}
