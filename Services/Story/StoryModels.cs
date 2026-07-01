using System.Text.Json.Serialization;

namespace Showheel.Services.Story;

/// <summary>
/// A single node in the story tree. The whole "Part 1 — Skies Beyond the Star"
/// book is represented as a tree of these: worldview -> childhood arc -> later arcs,
/// each section/subsection/entry being a node. AI co-author edits mutate this tree.
/// </summary>
public sealed class StoryNode
{
    /// <summary>Stable unique id (guid string). Used for edits, RAG citations, links.</summary>
    public string Id { get; set; } = Guid.NewGuid().ToString("n");

    /// <summary>Outline number as it appears in the source, e.g. "1", "1.1", "1.7". May repeat in source; kept as a label.</summary>
    public string Number { get; set; } = "";

    /// <summary>Primary (Chinese) title of the section.</summary>
    public string Title { get; set; } = "";

    /// <summary>Optional English title, filled by the translation pass.</summary>
    public string? TitleEn { get; set; }

    /// <summary>Body text for this node (the prose/tables that belong directly under this heading).</summary>
    public string Content { get; set; } = "";

    /// <summary>Optional English translation of <see cref="Content"/>, produced by the translator AI (separate from the co-author).</summary>
    public string? ContentEn { get; set; }

    /// <summary>Depth in the tree (0 = top level like "1. Worldview").</summary>
    public int Depth { get; set; }

    /// <summary>Ordering among siblings.</summary>
    public int Order { get; set; }

    /// <summary>Child nodes.</summary>
    public List<StoryNode> Children { get; set; } = new();

    [JsonIgnore]
    public int WordCount => Content?.Length ?? 0;

    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>Root container persisted to tree.json.</summary>
public sealed class StoryTree
{
    public string Title { get; set; } = "Skies Beyond the Star";

    /// <summary>Schema version so future migrations are detectable.</summary>
    public int Version { get; set; } = 1;

    /// <summary>Top-level nodes (0 Global Index, 1 Worldview, 2 World Map, ...).</summary>
    public List<StoryNode> Nodes { get; set; } = new();

    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;

    /// <summary>Flattens the tree depth-first into (node, parent) pairs.</summary>
    public IEnumerable<StoryNode> Flatten()
    {
        IEnumerable<StoryNode> Walk(IEnumerable<StoryNode> nodes)
        {
            foreach (var n in nodes)
            {
                yield return n;
                foreach (var c in Walk(n.Children))
                    yield return c;
            }
        }
        return Walk(Nodes);
    }

    /// <summary>Finds a node by id anywhere in the tree.</summary>
    public StoryNode? Find(string id) => Flatten().FirstOrDefault(n => n.Id == id);

    /// <summary>Finds the parent of a node (null if it is top-level or missing).</summary>
    public StoryNode? FindParent(string childId)
    {
        StoryNode? Search(IEnumerable<StoryNode> nodes, StoryNode? parent)
        {
            foreach (var n in nodes)
            {
                if (n.Id == childId) return parent;
                var hit = Search(n.Children, n);
                if (hit is not null) return hit;
            }
            return null;
        }
        return Search(Nodes, null);
    }

    /// <summary>Removes a node by id. Returns true if removed.</summary>
    public bool Remove(string id)
    {
        bool RemoveFrom(List<StoryNode> list)
        {
            var idx = list.FindIndex(n => n.Id == id);
            if (idx >= 0) { list.RemoveAt(idx); return true; }
            foreach (var n in list)
                if (RemoveFrom(n.Children)) return true;
            return false;
        }
        return RemoveFrom(Nodes);
    }
}
