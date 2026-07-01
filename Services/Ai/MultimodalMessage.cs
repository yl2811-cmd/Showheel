namespace Showheel.Services.Ai;

/// <summary>
/// A chat message that can carry text and/or images, for vision-capable providers.
/// Serialized to the OpenAI-compatible "content parts" array. When a message has only
/// text, callers may still use the simpler <see cref="ChatMessage"/>.
/// </summary>
public sealed class MultimodalMessage
{
    public string Role { get; set; } = "user";
    public string? Text { get; set; }

    /// <summary>Image references as data URLs (e.g. "data:image/png;base64,....") or http(s) URLs.</summary>
    public List<string> ImageUrls { get; set; } = new();

    public static MultimodalMessage System(string text) => new() { Role = "system", Text = text };
    public static MultimodalMessage Assistant(string text) => new() { Role = "assistant", Text = text };
    public static MultimodalMessage User(string text) => new() { Role = "user", Text = text };

    /// <summary>
    /// Builds the provider payload for this message. If there are no images we emit a
    /// plain string content (widest compatibility); otherwise a parts array.
    /// </summary>
    public object ToContentParts()
    {
        if (ImageUrls.Count == 0)
            return Text ?? "";

        var parts = new List<object>();
        if (!string.IsNullOrEmpty(Text))
            parts.Add(new { type = "text", text = Text });
        foreach (var url in ImageUrls)
            parts.Add(new { type = "image_url", image_url = new { url } });
        return parts;
    }
}
