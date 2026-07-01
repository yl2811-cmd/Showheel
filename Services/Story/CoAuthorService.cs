using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Options;
using Showheel.Services.Ai;

namespace Showheel.Services.Story;

/// <summary>
/// The "main brain" co-author. It answers questions and proposes edits to the story
/// tree, always grounded in RAG-retrieved global context so it sees the whole book
/// (avoiding duplicate content, contradictions, and stale/expired info).
///
/// Editing is patch-based: instead of many per-edit tool calls, the brain returns a
/// single <see cref="StoryPatch"/> changeset that the human reviews and applies in one
/// pass — far cheaper on tokens.
/// </summary>
public sealed partial class CoAuthorService
{
    private readonly OpenAiCompatibleClient _ai;
    private readonly RagService _rag;
    private readonly ConversationMemory _memory;
    private readonly StoryStore _store;
    private readonly IOptionsMonitor<AiOptions> _options;

    public CoAuthorService(
        OpenAiCompatibleClient ai,
        RagService rag,
        ConversationMemory memory,
        StoryStore store,
        IOptionsMonitor<AiOptions> options)
    {
        _ai = ai;
        _rag = rag;
        _memory = memory;
        _store = store;
        _options = options;
    }

    public bool IsConfigured => _options.CurrentValue.CoAuthor.IsConfigured;

    /// <summary>
    /// Chat turn grounded in whole-book RAG context, with on-demand retrieval, memory
    /// summarization of older turns, optional image attachments, and a thinking level.
    /// Returns the assistant reply plus the citations (section paths) used as context.
    /// </summary>
    public async Task<(string reply, List<string> citations)> ChatAsync(
        string userMessage,
        IReadOnlyList<ChatMessage> history,
        IReadOnlyList<string>? imageDataUrls = null,
        ThinkingLevel thinking = ThinkingLevel.Normal,
        CancellationToken ct = default)
    {
        var provider = _options.CurrentValue.CoAuthor;

        // 1) On-demand retrieval: only look up the book when the message needs it.
        var retrieved = new List<VectorChunk>();
        if (_memory.ShouldRetrieve(userMessage))
            retrieved = await _rag.RetrieveAsync(userMessage, topK: 8, ct);
        var context = RagService.FormatContext(retrieved);

        // 2) Memory: summarize older turns, keep recent turns verbatim.
        var (summary, recent) = await _memory.CompressAsync(history, thinking, ct);

        var system = BuildSystemPrompt(context, summary, patchMode: false);

        // 3) Multimodal only when images are attached; otherwise plain text (widest support).
        if (imageDataUrls is { Count: > 0 })
        {
            var mm = new List<MultimodalMessage> { MultimodalMessage.System(system) };
            foreach (var m in recent)
                mm.Add(m.Role == "assistant" ? MultimodalMessage.Assistant(m.Content) : MultimodalMessage.User(m.Content));
            mm.Add(new MultimodalMessage { Role = "user", Text = userMessage, ImageUrls = imageDataUrls.ToList() });

            var mmReply = await _ai.ChatMultimodalAsync(provider, mm, temperature: 0.5, thinking, ct);
            return (mmReply, retrieved.Select(c => c.Path).Distinct().ToList());
        }

        var messages = new List<ChatMessage> { ChatMessage.System(system) };
        messages.AddRange(recent);
        messages.Add(ChatMessage.User(userMessage));

        var reply = await _ai.ChatAsync(provider, messages, temperature: 0.5, thinking, ct);
        return (reply, retrieved.Select(c => c.Path).Distinct().ToList());
    }

    /// <summary>
    /// Asks the brain to produce a reviewable <see cref="StoryPatch"/> for an instruction,
    /// optionally incorporating an uploaded draft (text) and/or images. The patch is NOT
    /// applied here — the caller reviews it first.
    /// </summary>
    public async Task<StoryPatch> ProposePatchAsync(
        string instruction,
        string? draftText = null,
        IReadOnlyList<string>? imageDataUrls = null,
        ThinkingLevel thinking = ThinkingLevel.High,
        CancellationToken ct = default)
    {
        var provider = _options.CurrentValue.CoAuthor;

        // Retrieve global context so placement avoids duplication/contradiction, and
        // give the model the current node ids it can target.
        var query = instruction + (draftText is null ? "" : "\n" + Truncate(draftText, 1500));
        var retrieved = await _rag.RetrieveAsync(query, topK: 10, ct);
        var context = RagService.FormatContext(retrieved);
        var idMap = await BuildIdMapAsync(ct);

        var system = BuildSystemPrompt(context, memory: "", patchMode: true) +
                     "\n\n=== 当前树的节点 id（用于 targetId/parentId）===\n" + idMap;

        var userText = new StringBuilder(instruction);
        if (!string.IsNullOrWhiteSpace(draftText))
            userText.Append("\n\n=== 待归位的稿件（可能是旧英文稿）===\n").Append(draftText);

        string raw;
        if (imageDataUrls is { Count: > 0 })
        {
            var mm = new List<MultimodalMessage>
            {
                MultimodalMessage.System(system),
                new() { Role = "user", Text = userText.ToString(), ImageUrls = imageDataUrls.ToList() }
            };
            raw = await _ai.ChatMultimodalAsync(provider, mm, temperature: 0.3, thinking, ct);
        }
        else
        {
            var messages = new List<ChatMessage>
            {
                ChatMessage.System(system),
                ChatMessage.User(userText.ToString())
            };
            raw = await _ai.ChatAsync(provider, messages, temperature: 0.3, thinking, ct);
        }

        return ParsePatch(raw);
    }

    /// <summary>
    /// Reviews the whole tree for global-consistency issues: duplication,
    /// contradiction, and stale content. Returns a plain-text report.
    /// </summary>
    public async Task<string> AuditAsync(StoryTree tree, ThinkingLevel thinking = ThinkingLevel.High, CancellationToken ct = default)
    {
        var provider = _options.CurrentValue.CoAuthor;

        var outline = new StringBuilder();
        foreach (var n in tree.Flatten())
            outline.Append(new string(' ', n.Depth * 2))
                   .Append(n.Number).Append(' ').Append(n.Title)
                   .Append("  (").Append(n.WordCount).Append(" chars)\n");

        var system = "你是《Skies Beyond the Star》的一致性审计员。基于给出的目录结构，指出：" +
                     "(1) 疑似重复的章节；(2) 可能矛盾的设定；(3) 可能过期需删除的内容。用简洁的中文条列，" +
                     "每条给出涉及的〔章节路径〕。";

        var messages = new List<ChatMessage>
        {
            ChatMessage.System(system),
            ChatMessage.User("当前书籍结构：\n" + outline)
        };
        return await _ai.ChatAsync(provider, messages, temperature: 0.3, thinking, ct);
    }

    // --- internals ---

    private static string BuildSystemPrompt(string context, string memory, bool patchMode)
    {
        var sb = new StringBuilder()
            .AppendLine("你是《Skies Beyond the Star》的 AI 联合作者（主脑）。")
            .AppendLine("你面对的是整本书的树形结构：世界观 / 世界地图 / 童年篇 / Arc 计划 / 账本 / 裁决 / 设计原则 / 品味层。")
            .AppendLine("依据下面的全局 RAG 检索上下文作答，保持全局一致性：")
            .AppendLine("- 不要重复已存在的设定；不要与既有 canon 矛盾；")
            .AppendLine("- 指出过期/失效的信息并建议删除；引用来源时用〔章节路径〕标注。");

        if (!string.IsNullOrWhiteSpace(memory))
            sb.AppendLine().AppendLine("=== 早期对话记忆（摘要）===").AppendLine(memory);

        sb.AppendLine().AppendLine("=== 全局检索上下文 ===")
          .AppendLine(string.IsNullOrWhiteSpace(context) ? "（本轮未检索或无结果。）" : context);

        if (patchMode)
        {
            sb.AppendLine()
              .AppendLine("=== 输出要求：只返回一个 JSON 补丁，不要任何解释 ===")
              .AppendLine("用一次性 changeset 表达全部改动（不要逐条对话）。JSON 结构：")
              .AppendLine("{\"summary\":\"一句话概述\",\"ops\":[{\"op\":\"add|update|append|delete|move\",")
              .AppendLine("\"targetId\":\"现有节点id(update/append/delete/move)\",\"parentId\":\"父节点id(add/move,顶层留空)\",")
              .AppendLine("\"number\":\"如1.8\",\"title\":\"标题\",\"content\":\"正文\",\"position\":0,\"reason\":\"简短理由\"}]}")
              .AppendLine("规则：把长稿拆到最合适的既有节点下（优先 append/update），只有确实缺章节时才 add；")
              .AppendLine("发现过期内容用 delete；结构错位用 move。只输出 JSON。");
        }

        return sb.ToString();
    }

    private async Task<string> BuildIdMapAsync(CancellationToken ct)
    {
        var tree = await _store.LoadTreeAsync(ct);
        if (tree is null) return "（树未初始化）";
        var sb = new StringBuilder();
        foreach (var n in tree.Flatten())
            sb.Append(new string(' ', n.Depth * 2))
              .Append(n.Id).Append("  ")
              .Append(n.Number).Append(' ').Append(n.Title).Append('\n');
        return sb.ToString();
    }

    /// <summary>Parses the model output into a patch, tolerating code fences / stray prose.</summary>
    public static StoryPatch ParsePatch(string raw)
    {
        var json = ExtractJson(raw);
        try
        {
            var patch = JsonSerializer.Deserialize<StoryPatch>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
            return patch ?? new StoryPatch { Summary = "(empty)" };
        }
        catch
        {
            return new StoryPatch { Summary = "解析失败：模型未返回有效 JSON。" };
        }
    }

    private static string ExtractJson(string raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) return "{}";
        var fence = FenceRegex().Match(raw);
        if (fence.Success) return fence.Groups[1].Value.Trim();
        var start = raw.IndexOf('{');
        var end = raw.LastIndexOf('}');
        if (start >= 0 && end > start) return raw.Substring(start, end - start + 1);
        return raw.Trim();
    }

    private static string Truncate(string s, int max) => s.Length <= max ? s : s[..max] + "…";

    [GeneratedRegex(@"```(?:json)?\s*([\s\S]*?)```", RegexOptions.IgnoreCase)]
    private static partial Regex FenceRegex();
}
