namespace Showheel.Services.Ai;

/// <summary>
/// Thinking / reasoning depth for a chat completion. Mapped to the OpenAI-compatible
/// "reasoning_effort" field plus an escalating output-token budget. Providers that do
/// not support reasoning simply ignore the extra field.
/// </summary>
public enum ThinkingLevel
{
    /// <summary>No reasoning hint — fastest, cheapest.</summary>
    Normal = 0,
    /// <summary>reasoning_effort=high.</summary>
    High = 1,
    /// <summary>reasoning_effort=high with a larger token budget.</summary>
    XHigh = 2,
    /// <summary>reasoning_effort=high with the largest token budget.</summary>
    Max = 3
}

public static class ThinkingLevelExtensions
{
    /// <summary>The reasoning_effort string sent to the provider.</summary>
    public static string ToApiValue(this ThinkingLevel level) => level switch
    {
        ThinkingLevel.Normal => "medium",
        _ => "high" // High / XHigh / Max all use the highest reasoning tier.
    };

    /// <summary>
    /// Output-token budget that escalates with the level, so xhigh/max get more room
    /// for long chains of thought even when the provider ignores reasoning_effort.
    /// </summary>
    public static int? MaxTokens(this ThinkingLevel level) => level switch
    {
        ThinkingLevel.Normal => null,   // provider default
        ThinkingLevel.High => 4096,
        ThinkingLevel.XHigh => 8192,
        ThinkingLevel.Max => 16384,
        _ => null
    };

    /// <summary>Parses a UI value ("normal"/"high"/"xhigh"/"max") into the enum.</summary>
    public static ThinkingLevel Parse(string? value) => (value ?? "").Trim().ToLowerInvariant() switch
    {
        "high" => ThinkingLevel.High,
        "xhigh" => ThinkingLevel.XHigh,
        "max" => ThinkingLevel.Max,
        _ => ThinkingLevel.Normal
    };
}
