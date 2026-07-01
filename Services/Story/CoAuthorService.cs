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
    private readonly MainBrainTelemetry _telemetry;

    public CoAuthorService(
        OpenAiCompatibleClient ai,
        RagService rag,
        ConversationMemory memory,
        StoryStore store,
        IOptionsMonitor<AiOptions> options,
        MainBrainTelemetry telemetry)
    {
        _ai = ai;
        _rag = rag;
        _memory = memory;
        _store = store;
        _options = options;
        _telemetry = telemetry;
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

            var mmResult = await _ai.ChatMultimodalWithUsageAsync(provider, mm, temperature: 0.5, thinking, ct);
            _telemetry.Record(mmResult.Usage);
            return (mmResult.Content, retrieved.Select(c => c.Path).Distinct().ToList());
        }

        var messages = new List<ChatMessage> { ChatMessage.System(system) };
        messages.AddRange(recent);
        messages.Add(ChatMessage.User(userMessage));

        var result = await _ai.ChatWithUsageAsync(provider, messages, temperature: 0.5, thinking, ct);
        _telemetry.Record(result.Usage);
        return (result.Content, retrieved.Select(c => c.Path).Distinct().ToList());
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

    // The "knowing what you don't know" scaffold: every retrieval-based co-author must
    // treat the repo as the only source of canon, never its own pretraining / chat memory.
    // Appended to the base system prompt so it applies to both chat and patch modes.
    private const string ScaffoldPrompt = """
        === AI 如何知道自己不知道（⌂ 脚手架）===

        适用对象：所有检索式 AI co-author（Fable 5 及任何后续模型），每个 session 全程生效。
        本文档与 ai-coauthor-protocol.md 互补：协议管"读什么"，本文档管"没读过的东西不许装读过"。

        公理：印象不是出处。
        检索式 AI 对本世界的默认状态是"不知道"——预训练里没有 Archeon，聊天记忆会过期，
        specimen 会污染印象。任何 canon 断言的唯一合法来源是本仓库 status: canon 的文件原文。

        一、断言三态制（核心机制）
        AI 给出的每一个世界事实，必须归入三态之一，且只许按对应方式处理：
        - 可溯源：我读过原文，能当场给出文件路径，且文件 status 为 canon → 直接使用。
        - 待查：库里可能有，我说不出路径，但 INDEX/CANON_MAP/GLOSSARY 提示存在 → 先查后写：
          grep 全库 / 读目标文件。查到→升为可溯源；查无→降为真空白。
        - 真空白：库里没有，grep 与 INDEX 均无 → 见 §四。禁止脑补填平。
        判定只有一句话："我能给出路径吗？"给不出路径=没读过=待查，没有第四态。

        二、写前自检（每次动笔 / 动设定前过一遍）
        - 涉及的每个专名（人/地/物/事件），我是否逐一在 GLOSSARY 见过拼写、在 canon 文件见过定义？
        - 涉及角色的年龄、性别、家庭关系、生死状态，我是否有 10-canon/characters/ 的明文出处？
          不知道就去查，查不到就问，不许编，可拒答。
        - 我引用的事实，来自 canon 文件，还是来自我对历史对话的印象？后者必须回库验证。
        - 我是否读过相关 specimen？若是，警惕标本污染：印象里的细节可能来自废案而非 canon。
        - 我即将使用的条款是 canon 还是 proposed？proposed 一律注明"待裁决"，不得当事实铺陈。

        三、机械验证手段（怀疑时的最低成本动作）
        - 专名是否存在/如何拼写：grep -ri "<名词>" --include="*.md" 全库。
        - 文件是否存在：查 10-canon/INDEX.md 与 CANON_MAP.md。
        - 时序事实：唯一权威是 10-canon/history/master-timeline.md 与 10-canon/world/calendar.md。

        四、真空白的处理路径（空白即资产）
        发现库里真没有时，按影响面三选一，任何一条都不允许"顺手编一个填进正文"：
        - 局部小空白（如某配角的口头禅）：正文中绕开，或以 proposed 形态显式提案并标【※】。
        - 结构性空白（如某地点的季节事实、某角色的关键过往）：挂入 30-design/open-questions.md。
        - 作者意图级空白（如主题取舍、硬日期）：直接问作者，等一句话裁决。宁可产出减半，不可埋矛盾。

        五、禁令清单
        - 禁止用预训练知识补本世界设定（地球通识可用于物理/气象等现实机制，Archeon 专有事实必须有库内出处）。
        - 禁止从聊天记忆直接引 canon——记忆只用于"知道该去读哪个文件"。
        - 禁止以"合理推断"名义把推断写成事实；推断必须显式标注为推断或【※】。
        - 禁止在不确定时选择"更流畅的那个版本"——流畅是编造的伪装色。不确定时停下来，查，或问。
        - 禁止默写专名拼写；一律对 GLOSSARY。

        六、session 末的无知申报
        收割清单末尾追加一节"本次发现的不知道"：列出本 session 遇到的待查项与真空白及其处置
        （已查清/已挂账/已问作者）。空白被登记，下一个 session 的 AI 才不会在同一个坑里重新开始猜。

        知道自己不知道，是检索式接班人唯一可靠的美德。
        """;

    private static string BuildSystemPrompt(string context, string memory, bool patchMode)
    {
        var sb = new StringBuilder()
            .AppendLine("你是《Skies Beyond the Star》的 AI 联合作者（主脑）。")
            .AppendLine("你面对的是整本书的树形结构：世界观 / 世界地图 / 童年篇 / Arc 计划 / 账本 / 裁决 / 设计原则 / 品味层。")
            .AppendLine("依据下面的全局 RAG 检索上下文作答，保持全局一致性：")
            .AppendLine("- 不要重复已存在的设定；不要与既有 canon 矛盾；")
            .AppendLine("- 指出过期/失效的信息并建议删除；引用来源时用〔章节路径〕标注。")
            .AppendLine()
            .AppendLine(ScaffoldPrompt);

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
