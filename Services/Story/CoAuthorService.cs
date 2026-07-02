using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Options;
using Showheel.Services.Ai;

namespace Showheel.Services.Story;

/// <summary>
/// The "main brain" co-author. It answers questions and proposes edits to the story
/// tree with whole-book awareness (avoiding duplicate content, contradictions, and
/// stale/expired info).
///
/// Prompt layout is deliberately cache-friendly for long multi-turn discussions:
///  - the system prompt is STATIC (identity + rules + patch format — never varies),
///  - the clean book outline follows it and only changes when the tree changes,
///  - conversation history is append-only (memory compaction happens at quantized
///    milestones, not every turn),
///  - per-turn RAG context is injected into the FINAL user message only.
/// So the provider's prompt-prefix cache hits on everything except the newest message.
///
/// The model's view is a clean tree: outline numbers + titles only — no GUIDs, no JSON
/// plumbing. Edits are patch-based: one plain-text patch document (git-style, reviewable,
/// robust for tens of thousands of characters) applied in a single pass after approval.
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
    /// Chat turn with whole-book awareness: stable prefix (static system prompt + book
    /// outline + verbatim history), per-turn retrieval in the final user message, and a
    /// single-round 【查:关键词】 verification loop when the model asks to see canon text.
    /// Returns the assistant reply plus the citations (section paths) used as context.
    /// </summary>
    public async Task<(string reply, List<string> citations)> ChatAsync(
        string userMessage,
        IReadOnlyList<ChatMessage> history,
        IReadOnlyList<string>? imageDataUrls = null,
        ThinkingLevel thinking = ThinkingLevel.Normal,
        ProviderOptions? providerOverride = null,
        CancellationToken ct = default)
    {
        var provider = providerOverride ?? _options.CurrentValue.CoAuthor;

        // 1) On-demand retrieval: only look up the book when the message needs it.
        var retrieved = new List<VectorChunk>();
        if (_memory.ShouldRetrieve(userMessage))
            retrieved = await _rag.RetrieveAsync(userMessage, topK: 8, ct);
        var citations = retrieved.Select(c => c.Path).Distinct().ToList();

        // 2) Memory: milestone compaction of old turns; recent turns stay verbatim.
        var (summary, recent) = await _memory.CompressAsync(history, thinking, provider, ct);

        // 3) Stable prefix: static system prompt + clean outline (changes only with the tree).
        var system = await BuildSystemPromptAsync(ct);

        // 4) Per-turn variability lives only in the FINAL user message.
        var finalUser = ComposeFinalUserMessage(userMessage, retrieved);

        var messages = new List<ChatMessage> { ChatMessage.System(system) };
        AppendMemory(messages, summary);
        messages.AddRange(recent);

        string reply;
        if (imageDataUrls is { Count: > 0 })
        {
            var mm = messages
                .Select(m => m.Role switch
                {
                    "system" => MultimodalMessage.System(m.Content),
                    "assistant" => MultimodalMessage.Assistant(m.Content),
                    _ => MultimodalMessage.User(m.Content)
                })
                .ToList();
            mm.Add(new MultimodalMessage { Role = "user", Text = finalUser, ImageUrls = imageDataUrls.ToList() });

            var mmResult = await _ai.ChatMultimodalWithUsageAsync(provider, mm, temperature: 0.5, thinking, ct);
            _telemetry.Record(mmResult.Usage);
            reply = mmResult.Content;

            // Verification loop (multimodal path): one extra round, images not re-sent.
            reply = await RunLookupLoopAsync(provider, messages, finalUser, reply, thinking, citations, ct);
            return (reply, citations);
        }

        messages.Add(ChatMessage.User(finalUser));

        var result = await _ai.ChatWithUsageAsync(provider, messages, temperature: 0.5, thinking, ct);
        _telemetry.Record(result.Usage);
        reply = result.Content;

        reply = await RunLookupLoopAsync(provider, messages, finalUser, reply, thinking, citations, ct);
        return (reply, citations);
    }

    /// <summary>
    /// Asks the brain to produce a reviewable <see cref="StoryPatch"/> for an instruction,
    /// optionally incorporating an uploaded draft (text) and/or images. The model writes a
    /// plain-text patch document (never JSON) targeting sections by outline path — no
    /// GUIDs anywhere in its view. The patch is NOT applied here; the caller reviews it.
    /// </summary>
    public async Task<StoryPatch> ProposePatchAsync(
        string instruction,
        string? draftText = null,
        IReadOnlyList<string>? imageDataUrls = null,
        ThinkingLevel thinking = ThinkingLevel.High,
        ProviderOptions? providerOverride = null,
        CancellationToken ct = default)
    {
        var provider = providerOverride ?? _options.CurrentValue.CoAuthor;

        // Retrieve global context so placement avoids duplication/contradiction.
        var query = instruction + (draftText is null ? "" : "\n" + Truncate(draftText, 1500));
        var retrieved = await _rag.RetrieveAsync(query, topK: 10, ct);

        // Same stable prefix as chat mode — patch and chat calls share the cached prefix.
        var system = await BuildSystemPromptAsync(ct);

        var userText = new StringBuilder();
        userText.AppendLine("请针对下面的指令，输出一份 patch 文档（严格按系统提示中的 patch 文档格式，只输出文档本身，不要解释）。");
        AppendRetrievedBlock(userText, retrieved);
        userText.AppendLine().AppendLine("=== 指令 ===").Append(instruction);
        if (!string.IsNullOrWhiteSpace(draftText))
            userText.AppendLine().AppendLine().AppendLine("=== 待归位的稿件（可能是旧英文稿）===").Append(draftText);

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
    public async Task<string> AuditAsync(
        StoryTree tree,
        ThinkingLevel thinking = ThinkingLevel.High,
        ProviderOptions? providerOverride = null,
        CancellationToken ct = default)
    {
        var provider = providerOverride ?? _options.CurrentValue.CoAuthor;

        var system = "你是《Skies Beyond the Star》的一致性审计员。基于给出的目录结构，指出：" +
                     "(1) 疑似重复的章节；(2) 可能矛盾的设定；(3) 可能过期需删除的内容。用简洁的中文条列，" +
                     "每条给出涉及的〔章节路径〕。";

        var messages = new List<ChatMessage>
        {
            ChatMessage.System(system),
            ChatMessage.User("当前书籍结构：\n" + StoryPath.BuildOutline(tree))
        };
        return await _ai.ChatAsync(provider, messages, temperature: 0.3, thinking, ct);
    }

    // --- prompt assembly ---

    /// <summary>
    /// STATIC system prompt — identical for every call and every mode, so the provider's
    /// prompt cache always hits on it. Anything that varies (outline, retrieval, memory)
    /// is appended after it or lives in later messages.
    /// </summary>
    private const string BaseSystemPrompt = """
        你是《Skies Beyond the Star》的 AI 联合作者（主脑）。
        你面对的是整本书的树形结构：世界观 / 世界地图 / 童年篇 / Arc 计划 / 账本 / 裁决 / 设计原则 / 品味层。
        本消息末尾附有全书目录（骨架）；每轮对话中检索到的原文片段会附在当轮用户消息里，来源以〔章节路径〕标注。
        原则：
        - 不要重复已存在的设定；不要与既有 canon 矛盾；
        - 指出过期/失效的信息并建议删除；引用来源时用〔章节路径〕标注。

        === 如何查证细节（唯一手段）===
        当你需要确认某个专名、设定、时序等原文细节而当轮检索片段不够时，在回复中写入
        【查:关键词】（最多 3 个，每个不超过 20 字），系统会对全书做精确检索并把命中的
        原文片段发回给你，然后你给出最终回答。除此之外你没有任何读取全书的手段——
        不要假装 grep 过、读过某个文件。

        === AI 如何知道自己不知道（⌂ 脚手架）===

        适用对象：所有检索式 AI co-author（Fable 5 及任何后续模型），每个 session 全程生效。

        公理：印象不是出处。
        检索式 AI 对本世界的默认状态是"不知道"——预训练里没有 Archeon，聊天记忆会过期，
        specimen 会污染印象。任何 canon 断言的唯一合法来源是本书树中的原文。

        一、断言三态制（核心机制）
        AI 给出的每一个世界事实，必须归入三态之一，且只许按对应方式处理：
        - 可溯源：我在本次对话收到的检索片段/查证结果里读过原文，能给出〔章节路径〕 → 直接使用。
        - 待查：目录显示可能存在，但我没读过原文 → 先写【查:关键词】拿到原文再下笔。
          查到→升为可溯源；查无→降为真空白。
        - 真空白：查证也没有 → 见 §三。禁止脑补填平。
        判定只有一句话："我能给出〔章节路径〕吗？"给不出=没读过=待查，没有第四态。

        二、写前自检（每次动笔 / 动设定前过一遍）
        - 涉及的每个专名（人/地/物/事件），我是否在检索片段中见过拼写与定义？
        - 涉及角色的年龄、性别、家庭关系、生死状态，我是否有原文出处？不知道就【查:】，
          查不到就问，不许编，可拒答。
        - 我引用的事实，来自原文片段，还是来自我对历史对话的印象？后者必须【查:】验证。
        - 我即将使用的条款是 canon 还是 proposed？proposed 一律注明"待裁决"，不得当事实铺陈。

        三、真空白的处理路径（空白即资产）
        发现书里真没有时，按影响面三选一，任何一条都不允许"顺手编一个填进正文"：
        - 局部小空白（如某配角的口头禅）：正文中绕开，或以 proposed 形态显式提案并标【※】。
        - 结构性空白（如某地点的季节事实、某角色的关键过往）：建议挂入设计原则/悬而未决章节。
        - 作者意图级空白（如主题取舍、硬日期）：直接问作者，等一句话裁决。宁可产出减半，不可埋矛盾。

        四、禁令清单
        - 禁止用预训练知识补本世界设定（地球通识可用于物理/气象等现实机制，Archeon 专有事实必须有书内出处）。
        - 禁止从聊天记忆直接引 canon——记忆只用于"知道该去查哪个章节"。
        - 禁止以"合理推断"名义把推断写成事实；推断必须显式标注为推断或【※】。
        - 禁止在不确定时选择"更流畅的那个版本"——流畅是编造的伪装色。不确定时停下来，【查:】，或问。
        - 禁止默写专名拼写；一律以检索片段为准。

        知道自己不知道，是检索式接班人唯一可靠的美德。

        === Patch 文档格式（当被要求提出修改时使用）===
        用一份纯文本 patch 文档表达全部改动（git 式一次性 changeset，人审核后程序化应用）。
        只输出文档本身。格式：

        # summary: 一句话概述
        === update 1.7 ===
        reason: 简短理由
        ---
        （该节的新正文全文，可以很长）
        === append 1 世界观 / 1.2 ===
        ---
        （要追加到该节末尾的正文）
        === add under 2 世界地图 ===
        number: 2.5
        title: 新章节标题
        ---
        （新章节正文）
        === delete 4.1 ===
        reason: 为何删除
        === move 5.3 -> 2 世界地图 ===
        position: 0

        规则：
        - 定位章节一律用目录中的编号（如 1.7）或「编号 标题」；同名/同号时用 / 写出层级路径消歧。
          绝不使用任何内部 id。move 到顶层写 `-> top`。
        - 把长稿拆到最合适的既有章节下（优先 append/update），只有确实缺章节时才 add；
          发现过期内容用 delete；结构错位用 move。
        - reason/title/number/position 等元数据行紧跟小节头；正文放在 `---` 之后，直到下一个小节头。
        """;

    /// <summary>Static prompt + the clean book outline (outline changes only when the tree does).</summary>
    private async Task<string> BuildSystemPromptAsync(CancellationToken ct)
    {
        var tree = await _store.LoadTreeAsync(ct);
        var outline = tree is null ? "（树未初始化。）" : StoryPath.BuildOutline(tree);
        return BaseSystemPrompt + "\n\n=== 全书目录（骨架：编号 标题 〔字数〕）===\n" + outline;
    }

    /// <summary>Injects the milestone memory summary as an append-only history preamble.</summary>
    private static void AppendMemory(List<ChatMessage> messages, string summary)
    {
        if (string.IsNullOrWhiteSpace(summary)) return;
        messages.Add(ChatMessage.User("【早期对话要点（系统压缩，非原文）】\n" + summary));
        messages.Add(ChatMessage.Assistant("（已了解早期讨论要点。）"));
    }

    /// <summary>
    /// The only per-turn variable content: retrieval context + the user's message,
    /// composed into the final message so everything before it stays cache-stable.
    /// </summary>
    private static string ComposeFinalUserMessage(string userMessage, List<VectorChunk> retrieved)
    {
        if (retrieved.Count == 0) return userMessage;
        var sb = new StringBuilder();
        AppendRetrievedBlock(sb, retrieved);
        sb.AppendLine().Append(userMessage);
        return sb.ToString();
    }

    private static void AppendRetrievedBlock(StringBuilder sb, List<VectorChunk> retrieved)
    {
        if (retrieved.Count == 0) return;
        sb.AppendLine("【本轮检索到的原文片段（仅当轮参考）】");
        sb.AppendLine(RagService.FormatContext(retrieved));
    }

    // --- verification loop ---

    /// <summary>
    /// If the reply contains 【查:关键词】 markers, runs ONE round of exact keyword
    /// retrieval, feeds the hits back, and asks for the final answer. Capped at a single
    /// extra call so cost stays bounded.
    /// </summary>
    private async Task<string> RunLookupLoopAsync(
        ProviderOptions provider,
        List<ChatMessage> messages,
        string finalUser,
        string reply,
        ThinkingLevel thinking,
        List<string> citations,
        CancellationToken ct)
    {
        var terms = LookupRegex().Matches(reply)
            .Select(m => m.Groups[1].Value.Trim())
            .Where(t => t.Length is >= 1 and <= 20)
            .Distinct()
            .Take(3)
            .ToList();
        if (terms.Count == 0) return reply;

        var found = new List<VectorChunk>();
        foreach (var term in terms)
        {
            var hits = await _rag.SearchKeywordAsync(term, topK: 3, ct);
            foreach (var h in hits)
                if (!found.Any(f => f.NodeId == h.NodeId && f.Text == h.Text))
                    found.Add(h);
        }

        var resultBlock = found.Count == 0
            ? "（查证无结果：全书没有命中这些关键词。按「真空白」处理，不要编造。）"
            : RagService.FormatContext(found);
        citations.AddRange(found.Select(f => f.Path).Where(p => !citations.Contains(p)));

        // Continue the same conversation: prior messages stay byte-identical (prefix
        // cache hit), we only append the draft reply and the lookup results.
        var followUp = new List<ChatMessage>(messages);
        if (followUp.Count == 0 || followUp[^1].Content != finalUser)
            followUp.Add(ChatMessage.User(finalUser));
        followUp.Add(ChatMessage.Assistant(reply));
        followUp.Add(ChatMessage.User("【查证结果】\n" + resultBlock +
                                      "\n\n请基于以上原文给出修订后的完整最终回答；不要再输出【查:】标记。"));

        var result = await _ai.ChatWithUsageAsync(provider, followUp, temperature: 0.5, thinking, ct);
        _telemetry.Record(result.Usage);
        return result.Content;
    }

    // --- patch parsing ---

    /// <summary>
    /// Parses model output into a patch. Prefers the plain-text patch document format
    /// (robust for very long prose); falls back to legacy JSON, tolerating code fences.
    /// </summary>
    public static StoryPatch ParsePatch(string raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
            return new StoryPatch { Summary = "(empty)" };

        var unfenced = Unfence(raw);
        if (StoryPatchTextParser.LooksLikeTextPatch(unfenced))
        {
            var patch = StoryPatchTextParser.Parse(unfenced, out var errors);
            if (patch.Summary.Length == 0 && errors.Count > 0)
                patch.Summary = "解析警告：" + string.Join("；", errors);
            return patch;
        }

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
            return new StoryPatch { Summary = "解析失败：模型未返回有效的 patch 文档或 JSON。" };
        }
    }

    private static string Unfence(string raw)
    {
        var fence = FenceRegex().Match(raw);
        return fence.Success ? fence.Groups[1].Value.Trim() : raw.Trim();
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

    [GeneratedRegex(@"```(?:json|text|patch)?\s*([\s\S]*?)```", RegexOptions.IgnoreCase)]
    private static partial Regex FenceRegex();

    [GeneratedRegex(@"【查[:：]\s*([^】]{1,40})】")]
    private static partial Regex LookupRegex();
}
