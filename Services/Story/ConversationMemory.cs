using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Options;
using Showheel.Services.Ai;

namespace Showheel.Services.Story;

/// <summary>
/// Two lightweight "smart context" helpers for the co-author:
///  1) On-demand retrieval — decide whether a message actually needs a RAG lookup
///     (chit-chat / meta questions skip it, canon questions trigger it), so we don't
///     burn an embedding call on every turn.
///  2) Memory summarization — compress older chat turns into a compact memory string
///     so long conversations don't get hard-truncated and lose earlier intent.
/// </summary>
public sealed partial class ConversationMemory
{
    private readonly OpenAiCompatibleClient _ai;
    private readonly IOptionsMonitor<AiOptions> _options;

    /// <summary>Always keep at least this many most-recent turns verbatim.</summary>
    private const int VerbatimTurns = 8;

    /// <summary>
    /// Compression happens in blocks of this size: the summarized prefix only grows in
    /// steps of 16 turns, so for 16 consecutive turns the "older transcript" is byte-
    /// identical → the summarization call hits <see cref="Showheel.Services.Ai.AiResponseCache"/>
    /// (zero provider tokens) and the prompt prefix stays stable for provider-side
    /// prompt caching. This is the milestone/quantized alternative to re-summarizing
    /// every turn.
    /// </summary>
    private const int CompressBlock = 16;

    public ConversationMemory(OpenAiCompatibleClient ai, IOptionsMonitor<AiOptions> options)
    {
        _ai = ai;
        _options = options;
    }

    /// <summary>
    /// Heuristic gate for whether to run retrieval. Cheap and provider-free: retrieval
    /// is skipped for short greetings/meta and used whenever the message references
    /// story content, entities, or asks to add/change/check something.
    /// </summary>
    public bool ShouldRetrieve(string message)
    {
        var m = (message ?? "").Trim();
        if (m.Length == 0) return false;

        // Very short messages that are clearly greetings/acks: skip.
        if (m.Length <= 6 && GreetingRegex().IsMatch(m)) return false;

        // Anything that mentions editing, checking, or story structure: retrieve.
        if (StoryIntentRegex().IsMatch(m)) return true;

        // Contains an entity code (P-01, M-26, Ep7, FED-1) or CJK content: retrieve.
        if (EntityCodeRegex().IsMatch(m)) return true;
        if (m.Any(ch => ch >= 0x4E00 && ch <= 0x9FFF)) return true;

        // Default: retrieve for substantive questions, skip for tiny ones.
        return m.Length > 12;
    }

    /// <summary>
    /// Splits history into (summary of older turns, recent verbatim turns). If history
    /// is short, summary is empty and all turns are returned verbatim. The split point
    /// is quantized to <see cref="CompressBlock"/>-turn milestones so both the summary
    /// input and the verbatim window are append-only between milestones — that keeps
    /// the prompt prefix stable (provider cache hits) and lets the summarization call
    /// itself hit the local response cache.
    /// </summary>
    public async Task<(string summary, List<ChatMessage> recent)> CompressAsync(
        IReadOnlyList<ChatMessage> history,
        ThinkingLevel thinking = ThinkingLevel.Normal,
        ProviderOptions? providerOverride = null,
        CancellationToken ct = default)
    {
        // Quantize: only whole blocks get summarized, and only once at least one full
        // block sits behind the verbatim window.
        var olderCount = (history.Count - VerbatimTurns) / CompressBlock * CompressBlock;
        if (olderCount <= 0)
            return ("", history.ToList());

        var older = history.Take(olderCount).ToList();
        var recent = history.Skip(olderCount).ToList();

        var provider = providerOverride ?? _options.CurrentValue.CoAuthor;
        if (!provider.IsConfigured)
            return ("", recent); // can't summarize without a provider; just keep recent.

        var transcript = new StringBuilder();
        foreach (var m in older)
            transcript.Append(m.Role == "assistant" ? "AI: " : "作者: ").Append(m.Content).Append('\n');

        var messages = new List<ChatMessage>
        {
            ChatMessage.System("把下面这段《Skies Beyond the Star》创作对话压缩成要点记忆，" +
                               "保留：已达成的决定、待办、涉及的章节/角色、用户偏好。用简洁中文条列，不要展开。"),
            ChatMessage.User(transcript.ToString())
        };

        var summary = await _ai.ChatAsync(provider, messages, temperature: 0.2, ThinkingLevel.Normal, ct);
        return (summary, recent);
    }

    [GeneratedRegex(@"^(hi|hey|ok|好|嗯|谢谢|thanks?)\b", RegexOptions.IgnoreCase)]
    private static partial Regex GreetingRegex();

    [GeneratedRegex(@"(add|append|update|change|edit|delete|prune|move|check|audit|contradict|duplicate|stale|" +
                    @"添加|修改|新增|删除|修剪|移动|检查|矛盾|重复|过期|一致|章节|角色|设定|世界观|arc)", RegexOptions.IgnoreCase)]
    private static partial Regex StoryIntentRegex();

    [GeneratedRegex(@"\b(P-\d+|M-\d+|Ep\d+|FED-\d+)\b", RegexOptions.IgnoreCase)]
    private static partial Regex EntityCodeRegex();
}
