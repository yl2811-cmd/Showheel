using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Showheel.Services.Ai;

/// <summary>
/// A small, in-memory cache for AI provider calls (chat completions + embeddings),
/// keyed by a stable hash of the request (model + messages/inputs + params).
///
/// Why this exists: the co-author and RAG make many identical or near-identical calls
/// (e.g. re-embedding the same query, re-asking with the same grounded context). Those
/// providers are paid per token, so a cache hit is a direct cost/latency saving. The
/// hit/miss counters are surfaced to the UI so the operator can see cache utilization.
///
/// Scope: process memory only (thread-safe). Entries expire by TTL and the store is
/// bounded so it can't grow without limit. Not shared across instances — this is an
/// authoring tool, not a distributed system.
/// </summary>
public sealed class AiResponseCache
{
    private sealed record Entry(string Kind, object Value, DateTimeOffset ExpiresAt);

    private readonly ConcurrentDictionary<string, Entry> _store = new();
    private readonly TimeSpan _ttl;
    private readonly int _maxEntries;
    private readonly ILogger<AiResponseCache> _logger;

    private long _chatHits, _chatMisses, _embedHits, _embedMisses, _evictions;

    public AiResponseCache(ILogger<AiResponseCache> logger)
    {
        _logger = logger;
        _ttl = TimeSpan.FromHours(6);
        _maxEntries = 512;
    }

    private static readonly JsonSerializerOptions KeyJson = new() { PropertyNamingPolicy = null };

    /// <summary>Stable SHA-256 key over an arbitrary request shape.</summary>
    public static string Key(string kind, params object?[] parts)
    {
        var sb = new StringBuilder(kind).Append('|');
        foreach (var p in parts)
            sb.Append(p is null ? "∅" : JsonSerializer.Serialize(p, KeyJson)).Append('|');
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(sb.ToString()));
        return Convert.ToHexString(bytes);
    }

    /// <summary>Gets a cached chat reply, or runs <paramref name="factory"/> and caches it.</summary>
    public async Task<string> GetOrAddChatAsync(string key, Func<Task<string>> factory)
    {
        if (TryGet(key, out string? cached) && cached is not null)
        {
            Interlocked.Increment(ref _chatHits);
            return cached;
        }
        Interlocked.Increment(ref _chatMisses);
        var value = await factory();
        Set(key, "chat", value);
        return value;
    }

    /// <summary>Gets a cached embedding batch, or runs <paramref name="factory"/> and caches it.</summary>
    public async Task<List<float[]>> GetOrAddEmbeddingsAsync(string key, Func<Task<List<float[]>>> factory)
    {
        if (TryGet(key, out List<float[]>? cached) && cached is not null)
        {
            Interlocked.Increment(ref _embedHits);
            return cached;
        }
        Interlocked.Increment(ref _embedMisses);
        var value = await factory();
        Set(key, "embed", value);
        return value;
    }

    private bool TryGet<T>(string key, out T? value) where T : class
    {
        value = null;
        if (!_store.TryGetValue(key, out var entry)) return false;
        if (entry.ExpiresAt <= DateTimeOffset.UtcNow)
        {
            _store.TryRemove(key, out _);
            return false;
        }
        value = entry.Value as T;
        return value is not null;
    }

    private void Set(string key, string kind, object value)
    {
        // Cheap bound: if we're over budget, drop the oldest-expiring entries.
        if (_store.Count >= _maxEntries)
        {
            foreach (var stale in _store.OrderBy(kv => kv.Value.ExpiresAt).Take(_maxEntries / 8))
            {
                if (_store.TryRemove(stale.Key, out _)) Interlocked.Increment(ref _evictions);
            }
        }
        _store[key] = new Entry(kind, value, DateTimeOffset.UtcNow.Add(_ttl));
    }

    /// <summary>Clears the cache. Returns the number of entries removed.</summary>
    public int Clear()
    {
        var n = _store.Count;
        _store.Clear();
        _logger.LogInformation("AI response cache cleared ({Count} entries)", n);
        return n;
    }

    /// <summary>A snapshot of cache utilization for the UI.</summary>
    public object Stats()
    {
        long ch = Interlocked.Read(ref _chatHits), cm = Interlocked.Read(ref _chatMisses);
        long eh = Interlocked.Read(ref _embedHits), em = Interlocked.Read(ref _embedMisses);
        long hits = ch + eh, misses = cm + em, total = hits + misses;
        double Rate(long h, long t) => t == 0 ? 0 : Math.Round(100.0 * h / t, 1);
        return new
        {
            entries = _store.Count,
            maxEntries = _maxEntries,
            ttlHours = _ttl.TotalHours,
            evictions = Interlocked.Read(ref _evictions),
            chat = new { hits = ch, misses = cm, hitRate = Rate(ch, ch + cm) },
            embeddings = new { hits = eh, misses = em, hitRate = Rate(eh, eh + em) },
            overall = new { hits, misses, total, hitRate = Rate(hits, total) },
        };
    }
}
