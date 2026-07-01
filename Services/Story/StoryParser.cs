using System.Text;
using System.Text.RegularExpressions;

namespace Showheel.Services.Story;

/// <summary>
/// Turns the flat plain-text book (wwwroot/story.md) into a <see cref="StoryTree"/>.
///
/// The source has no Markdown "#" headings. Instead it keeps its own numbered
/// Table of Contents that mirrors the body:
///     1. 世界观 Worldview          (level 1)
///       1.1 Cosmos · 主星与天空     (level 2)
/// We parse the TOC to get the authoritative ordered outline, then walk the body
/// and slice the prose between consecutive headings into each node's content.
/// </summary>
public sealed partial class StoryParser
{
    // "1. 世界观 Worldview"  -> number has a trailing dot and no second number.
    [GeneratedRegex(@"^(?<num>\d+)\.\s+(?<title>\S.*)$")]
    private static partial Regex Level1();

    // "1.1 Cosmos · 主星与天空" / "1.4a ..." -> N.M(optional letter) then title.
    [GeneratedRegex(@"^(?<num>\d+\.\d+[a-z]?)\s+(?<title>\S.*)$")]
    private static partial Regex Level2();

    private sealed record Entry(int Level, string Number, string Title);

    public StoryTree Parse(string markdown)
    {
        var lines = markdown.Replace("\r\n", "\n").Split('\n');

        var tocStart = Array.FindIndex(lines, l => l.Contains("Table of Contents"));
        if (tocStart < 0) tocStart = Array.FindIndex(lines, l => l.TrimStart().StartsWith("目录"));

        var (entries, bodyStart) = ParseToc(lines, tocStart < 0 ? 0 : tocStart);

        // Fallback: if the TOC couldn't be read, treat the whole document as one node.
        if (entries.Count == 0)
        {
            var root = new StoryTree();
            root.Nodes.Add(new StoryNode { Number = "0", Title = "Story", Content = markdown.Trim(), Depth = 0, Order = 0 });
            return root;
        }

        // Locate each heading's line in the body, in order (forward-only scan).
        var headingLine = new int[entries.Count];
        var search = bodyStart;
        for (int i = 0; i < entries.Count; i++)
        {
            headingLine[i] = FindHeading(lines, entries[i], search);
            if (headingLine[i] >= 0) search = headingLine[i] + 1;
        }

        // Slice content: each heading owns the prose up to the next *found* heading.
        var contents = new string[entries.Count];
        for (int i = 0; i < entries.Count; i++)
        {
            if (headingLine[i] < 0) { contents[i] = ""; continue; }
            var from = headingLine[i] + 1;
            var to = lines.Length;
            for (int j = i + 1; j < entries.Count; j++)
                if (headingLine[j] >= 0) { to = headingLine[j]; break; }
            contents[i] = Slice(lines, from, to);
        }

        return BuildTree(entries, contents);
    }

    private static (List<Entry> entries, int bodyStart) ParseToc(string[] lines, int tocStart)
    {
        var entries = new List<Entry>();
        var seenTopNumbers = new HashSet<string>();
        int bodyStart = tocStart;

        for (int i = tocStart + 1; i < lines.Length; i++)
        {
            var line = lines[i].Trim();
            if (line.Length == 0) continue;

            var m1 = Level1().Match(line);
            if (m1.Success)
            {
                var num = m1.Groups["num"].Value;
                // The body repeats the numbered sections. The first time we see a
                // top-level number we've already recorded, the TOC is over.
                if (seenTopNumbers.Contains(num)) { bodyStart = i; break; }
                seenTopNumbers.Add(num);
                entries.Add(new Entry(1, num, StripToc(m1.Groups["title"].Value)));
                continue;
            }

            var m2 = Level2().Match(line);
            if (m2.Success)
            {
                entries.Add(new Entry(2, m2.Groups["num"].Value, StripToc(m2.Groups["title"].Value)));
                continue;
            }
            // Any other prose line inside the TOC region is ignored.
        }

        return (entries, bodyStart);
    }

    private static int FindHeading(string[] lines, Entry e, int from)
    {
        var wanted = Normalize(e.Number + " " + e.Title);
        for (int i = from; i < lines.Length; i++)
        {
            var line = lines[i].Trim();
            if (line.Length == 0) continue;
            var norm = Normalize(line);
            if (norm == wanted || norm.StartsWith(wanted, StringComparison.Ordinal))
                return i;
        }
        return -1;
    }

    private static StoryTree BuildTree(List<Entry> entries, string[] contents)
    {
        var tree = new StoryTree();
        StoryNode? current = null;
        int topOrder = 0;

        for (int i = 0; i < entries.Count; i++)
        {
            var e = entries[i];
            var node = new StoryNode
            {
                Number = e.Number,
                Title = e.Title,
                TitleEn = ExtractEnglish(e.Title),
                Content = contents[i],
                Depth = e.Level - 1
            };

            if (e.Level == 1)
            {
                node.Order = topOrder++;
                tree.Nodes.Add(node);
                current = node;
            }
            else if (current is not null)
            {
                node.Order = current.Children.Count;
                current.Children.Add(node);
            }
            else
            {
                node.Depth = 0;
                node.Order = topOrder++;
                tree.Nodes.Add(node);
            }
        }
        return tree;
    }

    // --- helpers ---

    private static string Slice(string[] lines, int from, int to)
    {
        var sb = new StringBuilder();
        for (int i = from; i < to && i < lines.Length; i++)
            sb.Append(lines[i]).Append('\n');
        return sb.ToString().Trim();
    }

    /// <summary>Removes a trailing full-width parenthetical, used in TOC entries only.</summary>
    private static string StripToc(string title)
    {
        var idx = title.IndexOf('（');
        return (idx > 0 ? title[..idx] : title).Trim();
    }

    /// <summary>Collapses whitespace so body/TOC headings compare reliably.</summary>
    private static string Normalize(string s)
    {
        var stripped = StripToc(s);
        return WhitespaceRegex().Replace(stripped, "").Trim();
    }

    /// <summary>Best-effort English label from a mixed "Cosmos · 主星与天空" style title.</summary>
    private static string? ExtractEnglish(string title)
    {
        var latin = LatinRegex().Match(title);
        return latin.Success ? latin.Value.Trim() : null;
    }

    [GeneratedRegex(@"\s+")]
    private static partial Regex WhitespaceRegex();

    [GeneratedRegex(@"[A-Za-z][A-Za-z0-9 '\-]*")]
    private static partial Regex LatinRegex();
}
