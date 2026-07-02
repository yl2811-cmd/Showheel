using System.Text.Json.Serialization;

namespace Showheel.Services.Story;

/// <summary>
/// A single edit operation the co-author proposes against the story tree.
/// The main brain returns a whole <see cref="StoryPatch"/> (many ops) in ONE reply,
/// so we apply a coherent changeset in a single pass instead of many tool-call round
/// trips. Nothing is applied until the human approves the patch.
/// </summary>
public sealed class PatchOp
{
    /// <summary>add | update | append | delete | move</summary>
    [JsonPropertyName("op")]
    public string Op { get; set; } = "";

    /// <summary>Existing node id this op targets (update/append/delete/move).</summary>
    [JsonPropertyName("targetId")]
    public string? TargetId { get; set; }

    /// <summary>
    /// Human/model-friendly target reference (update/append/delete/move): outline number
    /// ("1.7"), title, or slash path ("1 世界观 / 1.7"). Resolved server-side to
    /// <see cref="TargetId"/> so the model never handles GUIDs.
    /// </summary>
    [JsonPropertyName("targetPath")]
    public string? TargetPath { get; set; }

    /// <summary>Parent node id for add/move (null/empty = top level).</summary>
    [JsonPropertyName("parentId")]
    public string? ParentId { get; set; }

    /// <summary>Human/model-friendly parent reference for add/move (null/empty/"top" = top level).</summary>
    [JsonPropertyName("parentPath")]
    public string? ParentPath { get; set; }

    /// <summary>Outline number for a new node, e.g. "1.8" (optional).</summary>
    [JsonPropertyName("number")]
    public string? Number { get; set; }

    /// <summary>Title for add/update.</summary>
    [JsonPropertyName("title")]
    public string? Title { get; set; }

    /// <summary>Content for add/update/append.</summary>
    [JsonPropertyName("content")]
    public string? Content { get; set; }

    /// <summary>Insert position among siblings for add/move (optional; appends if null).</summary>
    [JsonPropertyName("position")]
    public int? Position { get; set; }

    /// <summary>Short human-readable reason, shown in the review UI.</summary>
    [JsonPropertyName("reason")]
    public string? Reason { get; set; }
}

/// <summary>A reviewable changeset the co-author proposes for the story tree.</summary>
public sealed class StoryPatch
{
    /// <summary>One-line summary of the whole change, for the review header.</summary>
    [JsonPropertyName("summary")]
    public string Summary { get; set; } = "";

    [JsonPropertyName("ops")]
    public List<PatchOp> Ops { get; set; } = new();
}

/// <summary>Result of validating/applying a patch.</summary>
public sealed class PatchResult
{
    public bool Success { get; set; }
    public List<string> Errors { get; set; } = new();
    public List<string> Applied { get; set; } = new();
}
