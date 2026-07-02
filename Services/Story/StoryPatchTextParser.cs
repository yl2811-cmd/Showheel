using System.Text;
using System.Text.RegularExpressions;

namespace Showheel.Services.Story;

/// <summary>
/// Parses the plain-text patch document format — the robust alternative to JSON for
/// long-form Chinese prose. A patch doc can be tens of thousands of characters: the
/// body of each section sits between headers verbatim, with zero escaping, so nothing
/// gets mangled. Sections are parsed independently: one malformed header only fails
/// that section, never the whole document.
///
/// Format:
/// <code>
/// # summary: 一句话概述
/// === update 1.7 ===
/// reason: 修正雨季设定矛盾
/// ---
/// （该节的新正文全文……可几万字）
/// === append 10-canon / 1 世界观 / 1.2 ===
/// ---
/// （要追加的正文）
/// === add under 2 世界地图 ===
/// number: 2.5
/// title: 新章节标题
/// ---
/// （新章节正文）
/// === delete 4.1 ===
/// reason: 已过期
/// === move 5.3 -> 2 世界地图 ===
/// position: 0
/// </code>
/// Targets use outline numbers / titles / slash paths (see <see cref="StoryPath"/>) —
/// never GUIDs.
/// </summary>
public static partial class StoryPatchTextParser
{
    /// <summary>True when the text contains at least one recognizable section header.</summary>
    public static bool LooksLikeTextPatch(string? text)
        => !string.IsNullOrWhiteSpace(text) && HeaderRegex().IsMatch(text);

    /// <summary>
    /// Parses a patch document. Per-section errors are collected in
    /// <paramref name="errors"/>; well-formed sections still make it into the patch.
    /// </summary>
    public static StoryPatch Parse(string text, out List<string> errors)
    {
        errors = new List<string>();
        var patch = new StoryPatch();
        var lines = text.Replace("\r\n", "\n").Split('\n');

        // Preamble: pick up "# summary: …" / "summary: …" before the first header.
        int i = 0;
        for (; i < lines.Length && !HeaderRegex().IsMatch(lines[i]); i++)
        {
            var m = SummaryRegex().Match(lines[i]);
            if (m.Success && patch.Summary.Length == 0)
                patch.Summary = m.Groups[1].Value.Trim();
        }

        while (i < lines.Length)
        {
            var header = HeaderRegex().Match(lines[i]);
            if (!header.Success) { i++; continue; }

            var headerLineNo = i + 1;
            var opKind = header.Groups["op"].Value.ToLowerInvariant();
            var rest = header.Groups["rest"].Value.Trim();
            i++;

            // Collect this section's lines (metadata + body) up to the next header.
            var start = i;
            while (i < lines.Length && !HeaderRegex().IsMatch(lines[i])) i++;
            var section = lines[start..i];

            var op = BuildOp(opKind, rest, section, headerLineNo, errors);
            if (op is not null) patch.Ops.Add(op);
        }

        if (patch.Ops.Count == 0 && errors.Count == 0)
            errors.Add("文档中没有找到任何 `=== <op> … ===` 小节。");
        return patch;
    }

    private static PatchOp? BuildOp(string opKind, string rest, string[] section, int lineNo, List<string> errors)
    {
        var op = new PatchOp { Op = opKind };

        switch (opKind)
        {
            case "add":
                // "add under <parentPath>" or bare "add" (top level).
                var under = AddUnderRegex().Match(rest);
                if (under.Success) op.ParentPath = under.Groups[1].Value.Trim();
                else if (rest.Length > 0) op.ParentPath = rest; // tolerate "add <parentPath>"
                break;

            case "move":
                var arrow = MoveRegex().Match(rest);
                if (!arrow.Success)
                {
                    errors.Add($"第 {lineNo} 行：move 需要 `=== move <路径> -> <新父路径|top> ===`。");
                    return null;
                }
                op.TargetPath = arrow.Groups[1].Value.Trim();
                var dest = arrow.Groups[2].Value.Trim();
                op.ParentPath = dest.Equals("top", StringComparison.OrdinalIgnoreCase) ? null : dest;
                break;

            default: // update / append / delete
                if (rest.Length == 0)
                {
                    errors.Add($"第 {lineNo} 行：{opKind} 缺少目标路径。");
                    return null;
                }
                op.TargetPath = rest;
                break;
        }

        // Metadata lines run until a "---" separator, a blank line, or a non-metadata line.
        int b = 0;
        for (; b < section.Length; b++)
        {
            var line = section[b];
            if (line.Trim() == "---") { b++; break; }
            var meta = MetaRegex().Match(line);
            if (!meta.Success)
            {
                if (line.Trim().Length == 0) { b++; }
                break;
            }
            ApplyMeta(op, meta.Groups[1].Value.ToLowerInvariant(), meta.Groups[2].Value.Trim());
        }

        var body = string.Join("\n", section[b..]).Trim('\n', '\r');
        if (body.Trim().Length > 0) op.Content = body;

        if (opKind is "update" or "append" && op.Content is null && op.Title is null)
            errors.Add($"第 {lineNo} 行：{opKind}「{op.TargetPath}」没有正文也没有新标题。");
        if (opKind == "add" && op.Title is null && string.IsNullOrWhiteSpace(op.Content))
            errors.Add($"第 {lineNo} 行：add 需要 title 或正文。");

        return op;
    }

    private static void ApplyMeta(PatchOp op, string key, string value)
    {
        switch (key)
        {
            case "reason": op.Reason = value; break;
            case "title": op.Title = value; break;
            case "number": op.Number = value; break;
            case "target": op.TargetPath ??= value; break;
            case "parent": op.ParentPath ??= value; break;
            case "position":
                if (int.TryParse(value, out var p)) op.Position = p;
                break;
        }
    }

    [GeneratedRegex(@"^===\s*(?<op>add|update|append|delete|move)\b(?<rest>[^=]*)===\s*$",
        RegexOptions.IgnoreCase | RegexOptions.Multiline)]
    private static partial Regex HeaderRegex();

    [GeneratedRegex(@"^#?\s*summary\s*[:：]\s*(.+)$", RegexOptions.IgnoreCase)]
    private static partial Regex SummaryRegex();

    [GeneratedRegex(@"^under\s+(.+)$", RegexOptions.IgnoreCase)]
    private static partial Regex AddUnderRegex();

    [GeneratedRegex(@"^(.*?)\s*(?:->|→)\s*(.+)$")]
    private static partial Regex MoveRegex();

    [GeneratedRegex(@"^(reason|title|number|position|target|parent)\s*[:：]\s*(.*)$", RegexOptions.IgnoreCase)]
    private static partial Regex MetaRegex();
}
