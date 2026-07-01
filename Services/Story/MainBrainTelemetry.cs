using Microsoft.Extensions.Options;
using Showheel.Services.Ai;

namespace Showheel.Services.Story;

/// <summary>
/// Process-wide telemetry for the "main brain" co-author: cumulative and last-turn
/// token usage plus a snapshot of the current context-window occupancy. Surfaced to the
/// Story Studio header so the operator can watch input/output token spend and how full
/// the model's context window is.
///
/// Registered as a singleton (like <see cref="Showheel.Services.Ai.AiResponseCache"/>)
/// so counters are shared across requests. Counters are process-global and reset only on
/// restart. Cache hits spend no provider tokens, so they are recorded separately and do
/// not inflate the cumulative in/out totals.
/// </summary>
public sealed class MainBrainTelemetry
{
    private readonly IOptionsMonitor<AiOptions> _options;
    private readonly object _gate = new();

    private long _cumulativeInput;
    private long _cumulativeOutput;
    private long _turns;
    private long _cacheHits;

    private int _lastInput;
    private int _lastOutput;
    private int _lastCached;
    private bool _lastFromCache;
    private DateTimeOffset? _lastAt;

    public MainBrainTelemetry(IOptionsMonitor<AiOptions> options) => _options = options;

    /// <summary>
    /// Records one co-author turn. On a cache hit <paramref name="usage"/> is null
    /// (no provider tokens spent): the turn is counted as a cache hit and the last-turn
    /// figures show 0 in/out.
    /// </summary>
    public void Record(TokenUsage? usage)
    {
        lock (_gate)
        {
            _turns++;
            _lastAt = DateTimeOffset.UtcNow;
            if (usage is null)
            {
                _cacheHits++;
                _lastFromCache = true;
                _lastInput = _lastOutput = _lastCached = 0;
                return;
            }
            _lastFromCache = false;
            _lastInput = usage.PromptTokens;
            _lastOutput = usage.CompletionTokens;
            _lastCached = usage.CachedTokens;
            _cumulativeInput += usage.PromptTokens;
            _cumulativeOutput += usage.CompletionTokens;
        }
    }

    /// <summary>The max context window (tokens) for the currently-configured co-author model.</summary>
    public int MaxContextTokens()
    {
        var p = _options.CurrentValue.CoAuthor;
        return ModelContextLimits.Resolve(p.Model, p.MaxContextTokens, _options.CurrentValue.ModelContextLimits);
    }

    /// <summary>A snapshot for the UI. "Context used" approximates the last turn's total tokens.</summary>
    public object Snapshot()
    {
        lock (_gate)
        {
            var provider = _options.CurrentValue.CoAuthor;
            var maxContext = MaxContextTokens();
            var lastTotal = _lastInput + _lastOutput;
            double ctxPct = maxContext > 0 ? Math.Round(100.0 * lastTotal / maxContext, 2) : 0;
            return new
            {
                model = provider.Model,
                configured = provider.IsConfigured,
                maxContextTokens = maxContext,
                turns = _turns,
                cacheHits = _cacheHits,
                last = new
                {
                    input = _lastInput,
                    output = _lastOutput,
                    cached = _lastCached,
                    total = lastTotal,
                    fromCache = _lastFromCache,
                    at = _lastAt,
                },
                cumulative = new
                {
                    input = _cumulativeInput,
                    output = _cumulativeOutput,
                    total = _cumulativeInput + _cumulativeOutput,
                },
                context = new
                {
                    used = lastTotal,
                    max = maxContext,
                    percent = ctxPct,
                },
            };
        }
    }
}
