using System.Text;
using System.Text.RegularExpressions;

namespace Showheel.Services.Story;

/// <summary>
/// Human/model-friendly node addressing. The co-author never sees GUIDs — it targets
/// nodes by outline number ("1.7"), title ("气候与季节"), "number title", or a
/// slash-separated path ("10 · Canon 正典 / 1 世界观 / 1.7"). This class resolves those
/// references back to tree nodes server-side and renders the clean outline the model
/// sees as its whole-book skeleton.
/// </summary>
public static partial class StoryPath
{
    /// <summary>Result of resolving a path reference: a node, or an error with candidates.</summary>
    public sealed record Resolution(StoryNode? Node, string? Error)
    {
        public bool Success => Node is not null;
    }

    /// <summary>"Number Title" label for one node, e.g. "1.7 气候与季节".</summary>
    public static string Label(StoryNode node)
        => $"{node.Number} {node.Title}".Trim();

    /// <summary>Full display path from root, e.g. "10 · Canon 正典 / 1 世界观 / 1.7 气候".</summary>
    public static string DisplayPath(StoryTree tree, StoryNode node)
    {
        var chain = new List<string>();
        if (BuildChain(tree.Nodes, node.Id, chain)) chain.Reverse();
        return string.Join(" / ", chain);
    }

    private static bool BuildChain(List<StoryNode> nodes, string id, List<string> chain)
    {
        foreach (var n in nodes)
        {
            if (n.Id == id) { chain.Add(Label(n)); return true; }
            if (BuildChain(n.Children, id, chain)) { chain.Add(Label(n)); return true; }
        }
        return false;
    }

    /// <summary>
    /// The clean outline the model sees: indentation + number + title + content size.
    /// No ids, no timestamps, no JSON noise — just the book's skeleton.
    /// </summary>
    public static string BuildOutline(StoryTree tree)
    {
        var sb = new StringBuilder();
        foreach (var n in tree.Flatten())
        {
            sb.Append(new string(' ', n.Depth * 2)).Append(Label(n));
            if (n.WordCount > 0) sb.Append("  〔").Append(n.WordCount).Append(" 字〕");
            sb.Append('\n');
        }
        return sb.ToString().TrimEnd();
    }

    /// <summary>
    /// Resolves a reference to a node. Accepts a raw node id (legacy), a number ("1.7"),
    /// a title, "number title", or a path with "/" or "›" separators. Ambiguity and
    /// misses return an error listing the closest candidates.
    /// </summary>
    public static Resolution Resolve(StoryTree tree, string? reference)
    {
        var raw = (reference ?? "").Trim();
        if (raw.Length == 0) return new Resolution(null, "空路径。");

        // Legacy: exact node id.
        var byId = tree.Find(raw);
        if (byId is not null) return new Resolution(byId, null);

        var segments = SeparatorRegex().Split(raw)
            .Select(s => Normalize(s))
            .Where(s => s.Length > 0)
            .ToList();
        if (segments.Count == 0) return new Resolution(null, "空路径。");

        // First segment: search the whole tree. Later segments: search within candidates.
        var candidates = MatchSegment(tree.Flatten(), segments[0]);
        for (int i = 1; i < segments.Count && candidates.Count > 0; i++)
        {
            var next = new List<StoryNode>();
            foreach (var c in candidates)
            {
                // Prefer direct children; fall back to any descendant.
                var direct = MatchSegment(c.Children, segments[i]);
                next.AddRange(direct.Count > 0 ? direct : MatchSegment(Descendants(c), segments[i]));
            }
            candidates = next.DistinctBy(n => n.Id).ToList();
        }

        if (candidates.Count == 1) return new Resolution(candidates[0], null);
        if (candidates.Count == 0)
            return new Resolution(null, $"找不到章节「{raw}」。");

        var listing = string.Join("；", candidates.Take(5).Select(c => DisplayPath(tree, c)));
        return new Resolution(null, $"「{raw}」有 {candidates.Count} 个匹配，请写更完整的路径。候选：{listing}");
    }

    private static IEnumerable<StoryNode> Descendants(StoryNode node)
    {
        foreach (var c in node.Children)
        {
            yield return c;
            foreach (var d in Descendants(c)) yield return d;
        }
    }

    /// <summary>Exact matches first (number / title / "number title" / bucket); contains-fallback second.</summary>
    private static List<StoryNode> MatchSegment(IEnumerable<StoryNode> pool, string segment)
    {
        var nodes = pool as IList<StoryNode> ?? pool.ToList();
        var exact = nodes.Where(n =>
                Eq(n.Number, segment) ||
                Eq(n.Title, segment) ||
                Eq(Label(n), segment) ||
                Eq(n.Bucket, segment))
            .ToList();
        if (exact.Count > 0) return exact;

        if (segment.Length >= 2)
            return nodes.Where(n => Normalize(n.Title).Contains(segment, StringComparison.OrdinalIgnoreCase) ||
                                    Normalize(Label(n)).Contains(segment, StringComparison.OrdinalIgnoreCase))
                        .ToList();
        return new List<StoryNode>();
    }

    private static bool Eq(string? a, string b)
        => a is not null && string.Equals(Normalize(a), b, StringComparison.OrdinalIgnoreCase);

    private static string Normalize(string s)
        => WhitespaceRegex().Replace(s.Trim(), " ");

    [GeneratedRegex(@"\s*(?:/|›|>)\s*")]
    private static partial Regex SeparatorRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex WhitespaceRegex();
}
