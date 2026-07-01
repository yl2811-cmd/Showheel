namespace Showheel.Services.Ai;

/// <summary>
/// Resolves the maximum context window (in tokens) for a given model name.
///
/// The "AI context amount takes the model's max" requirement: big models (Gemini,
/// GPT-4.1, Claude Sonnet/Opus long-context) expose ~1M tokens; others fall back to
/// their own known ceiling; unknown models get a conservative default.
///
/// Resolution order (first match wins):
///   1. explicit <see cref="ProviderOptions.MaxContextTokens"/> on the provider,
///   2. an exact/substring match in the caller-supplied overrides (from appsettings),
///   3. the built-in substring table below,
///   4. <see cref="DefaultLimit"/>.
/// </summary>
public static class ModelContextLimits
{
    /// <summary>Fallback when a model can't be matched. A safe modern baseline.</summary>
    public const int DefaultLimit = 128_000;

    private const int OneMillion = 1_000_000;
    private const int TwoMillion = 2_000_000;

    // Ordered longest-first so more specific names win over shorter prefixes.
    private static readonly (string needle, int limit)[] Table =
    {
        // Google Gemini — 1M–2M context.
        ("gemini-1.5-pro", TwoMillion),
        ("gemini-2.5-pro", OneMillion),
        ("gemini-2.0", OneMillion),
        ("gemini-1.5", OneMillion),
        ("gemini", OneMillion),

        // OpenAI GPT-4.1 family — 1M context.
        ("gpt-4.1", OneMillion),
        // OpenAI o-series / GPT-4o — 128k–200k.
        ("o4", 200_000),
        ("o3", 200_000),
        ("o1", 200_000),
        ("gpt-4o", 128_000),
        ("gpt-4-turbo", 128_000),
        ("gpt-4-32k", 32_768),
        ("gpt-4", 8_192),
        ("gpt-3.5-turbo-16k", 16_384),
        ("gpt-3.5", 16_384),

        // Anthropic Claude — 200k (some 1M beta).
        ("claude-3-5-sonnet", 200_000),
        ("claude-3-7", 200_000),
        ("claude-sonnet-4", OneMillion),
        ("claude-opus-4", 200_000),
        ("claude-3", 200_000),
        ("claude", 200_000),

        // DeepSeek — 64k–128k.
        ("deepseek-reasoner", 64_000),
        ("deepseek-chat", 64_000),
        ("deepseek", 64_000),

        // Qwen — up to 1M on long-context variants.
        ("qwen-long", OneMillion),
        ("qwen2.5", 128_000),
        ("qwen", 32_768),

        // Moonshot / Kimi — long context.
        ("kimi", 200_000),
        ("moonshot-v1-128k", 128_000),
        ("moonshot", 128_000),

        // Mistral / Mixtral.
        ("mistral-large", 128_000),
        ("mixtral", 32_768),
        ("mistral", 32_768),

        // Meta Llama 3.x — 128k.
        ("llama-3", 128_000),
        ("llama3", 128_000),

        // GLM / Zhipu.
        ("glm-4", 128_000),
        ("glm", 128_000),
    };

    /// <summary>
    /// Resolves the max context tokens for <paramref name="model"/>, honoring the
    /// explicit provider override, then caller overrides, then the built-in table.
    /// </summary>
    public static int Resolve(string? model, int? explicitOverride, IReadOnlyDictionary<string, int>? overrides)
    {
        if (explicitOverride is > 0) return explicitOverride.Value;

        var name = (model ?? "").Trim().ToLowerInvariant();
        if (name.Length == 0) return DefaultLimit;

        if (overrides is not null)
        {
            // Longest-key-first so a specific override beats a broad one.
            foreach (var kv in overrides.OrderByDescending(k => k.Key.Length))
            {
                if (kv.Value > 0 && name.Contains(kv.Key.Trim().ToLowerInvariant()))
                    return kv.Value;
            }
        }

        foreach (var (needle, limit) in Table)
            if (name.Contains(needle)) return limit;

        return DefaultLimit;
    }
}
