using Microsoft.Extensions.Options;
using Showheel.Services.Ai;

namespace Showheel.Services.Story;

/// <summary>
/// Standalone translator. Deliberately separate from the co-author "main brain":
/// every browsing region can offer on-demand translation via its own AI provider,
/// without touching the canon or the RAG index.
/// </summary>
public sealed class TranslationService
{
    private readonly OpenAiCompatibleClient _ai;
    private readonly IOptionsMonitor<AiOptions> _options;

    public TranslationService(OpenAiCompatibleClient ai, IOptionsMonitor<AiOptions> options)
    {
        _ai = ai;
        _options = options;
    }

    public bool IsConfigured => _options.CurrentValue.Translator.IsConfigured;

    /// <summary>Translates a block of story text to the target language.</summary>
    public async Task<string> TranslateAsync(string text, string targetLang = "English", CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(text)) return "";
        var provider = _options.CurrentValue.Translator;

        var system =
            $"You are a literary translator for the novel \"Skies Beyond the Star\". " +
            $"Translate the user's text into {targetLang}. Preserve meaning, tone, and any " +
            $"proper nouns/code names (e.g. Anna, Sky Fire, P-01, M-26) exactly. " +
            $"Return only the translation, no commentary.";

        var messages = new List<ChatMessage>
        {
            ChatMessage.System(system),
            ChatMessage.User(text)
        };
        return await _ai.ChatAsync(provider, messages, temperature: 0.2, ct: ct);
    }
}
