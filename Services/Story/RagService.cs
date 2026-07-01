using System.Text;
using Microsoft.Extensions.Options;
using Showheel.Services.Ai;

namespace Showheel.Services.Story;

/// <summary>
/// Retrieval-Augmented Generation service. Builds a global embedding index over the
/// whole story tree and retrieves the most relevant chunks for a query, so the
/// co-author AI reasons with whole-book awareness instead of a narrow window.
/// This is what guards against duplicate content, contradictions, and stale info.
/// </summary>
public sealed class RagService
{
    private readonly StoryStore _store;
    private readonly OpenAiCompatibleClient _ai;
    private readonly IOptionsMonitor<AiOptions> _options;
    private readonly ILogger<RagService> _logger;

    private readonly SemaphoreSlim _indexGate = new(1, 1);
    private volatile RagStatus _status = new() { State = RagState.Unknown, Message = "Not checked yet" };

    // Chunking: keep chunks small enough to be specific but large enough to carry context.
    private const int MaxChunkChars = 900;
    private const int EmbedBatchSize = 32;

    public RagService(
        StoryStore store,
        OpenAiCompatibleClient ai,
        IOptionsMonitor<AiOptions> options,
        ILogger<RagService> logger)
    {
        _store = store;
        _ai = ai;
        _options = options;
        _logger = logger;
    }

    public RagStatus Status => _status;

    /// <summary>Refreshes status from disk + config without rebuilding. Cheap; safe to poll.</summary>
    public async Task<RagStatus> RefreshStatusAsync(CancellationToken ct = default)
    {
        var embed = _options.CurrentValue.Embeddings;
        if (!embed.IsConfigured)
        {
            return _status = new RagStatus
            {
                State = RagState.NotConfigured,
                Message = "Embedding provider not configured — RAG offline."
            };
        }

        // Don't clobber an in-progress build.
        if (_status.State == RagState.Indexing) return _status;

        var index = await _store.LoadVectorsAsync(ct);
        if (index is null || index.Chunks.Count == 0)
        {
            return _status = new RagStatus
            {
                State = RagState.Empty,
                Message = "No index yet — decompose the story to enable RAG.",
                EmbeddingModel = embed.Model
            };
        }

        return _status = new RagStatus
        {
            State = RagState.Ready,
            Message = $"Index ready · {index.Chunks.Count} chunks",
            ChunkCount = index.Chunks.Count,
            EmbeddingModel = index.EmbeddingModel,
            IndexedAt = index.UpdatedAt,
            Progress = 100
        };
    }

    /// <summary>
    /// Rebuilds the whole embedding index from the current tree and persists it.
    /// Progress is reflected in <see cref="Status"/> so the UI can show notifications.
    /// </summary>
    public async Task<RagStatus> RebuildAsync(StoryTree tree, CancellationToken ct = default)
    {
        var embed = _options.CurrentValue.Embeddings;
        if (!embed.IsConfigured)
            return _status = new RagStatus { State = RagState.NotConfigured, Message = "Embedding provider not configured." };

        await _indexGate.WaitAsync(ct);
        try
        {
            _status = new RagStatus { State = RagState.Indexing, Message = "Building index…", Progress = 0, EmbeddingModel = embed.Model };

            var chunks = BuildChunks(tree);
            if (chunks.Count == 0)
                return _status = new RagStatus { State = RagState.Empty, Message = "Nothing to index." };

            var index = new VectorIndex { EmbeddingModel = embed.Model };

            for (int i = 0; i < chunks.Count; i += EmbedBatchSize)
            {
                ct.ThrowIfCancellationRequested();
                var batch = chunks.Skip(i).Take(EmbedBatchSize).ToList();
                var vectors = await _ai.EmbedAsync(embed, batch.Select(c => c.Text).ToList(), ct);

                for (int j = 0; j < batch.Count && j < vectors.Count; j++)
                {
                    batch[j].Embedding = vectors[j];
                    index.Chunks.Add(batch[j]);
                }

                _status = new RagStatus
                {
                    State = RagState.Indexing,
                    Message = $"Embedding… {Math.Min(i + EmbedBatchSize, chunks.Count)}/{chunks.Count}",
                    Progress = (int)((double)Math.Min(i + EmbedBatchSize, chunks.Count) / chunks.Count * 100),
                    EmbeddingModel = embed.Model
                };
            }

            index.Dimensions = index.Chunks.FirstOrDefault()?.Embedding.Length ?? 0;
            await _store.SaveVectorsAsync(index, ct);

            return _status = new RagStatus
            {
                State = RagState.Ready,
                Message = $"Index ready · {index.Chunks.Count} chunks",
                ChunkCount = index.Chunks.Count,
                EmbeddingModel = index.EmbeddingModel,
                IndexedAt = index.UpdatedAt,
                Progress = 100
            };
        }
        catch (OperationCanceledException)
        {
            _status = new RagStatus { State = RagState.Error, Message = "Indexing cancelled." };
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "RAG rebuild failed");
            return _status = new RagStatus { State = RagState.Error, Message = "Indexing failed — see server logs." };
        }
        finally { _indexGate.Release(); }
    }

    /// <summary>Retrieves the top-K most relevant chunks for a query.</summary>
    public async Task<List<VectorChunk>> RetrieveAsync(string query, int topK = 6, CancellationToken ct = default)
    {
        var embed = _options.CurrentValue.Embeddings;
        if (!embed.IsConfigured) return new();

        var index = await _store.LoadVectorsAsync(ct);
        if (index is null || index.Chunks.Count == 0) return new();

        var qv = (await _ai.EmbedAsync(embed, new[] { query }, ct)).FirstOrDefault();
        if (qv is null || qv.Length == 0) return new();

        return index.Chunks
            .Select(c => (chunk: c, score: Cosine(qv, c.Embedding)))
            .OrderByDescending(x => x.score)
            .Take(topK)
            .Select(x => x.chunk)
            .ToList();
    }

    /// <summary>Formats retrieved chunks as a context block for a prompt.</summary>
    public static string FormatContext(IEnumerable<VectorChunk> chunks)
    {
        var sb = new StringBuilder();
        foreach (var c in chunks)
        {
            // Show the full structural lineage so the model sees WHERE this sits in the book.
            var header = string.IsNullOrWhiteSpace(c.AncestorPath) ? c.Path : c.AncestorPath;
            sb.Append("〔").Append(header).Append("〕\n");
            sb.Append(c.Text.Trim()).Append("\n\n");
        }
        return sb.ToString().Trim();
    }

    // --- internals ---

    private static List<VectorChunk> BuildChunks(StoryTree tree)
    {
        var chunks = new List<VectorChunk>();

        void Walk(IEnumerable<StoryNode> nodes, List<string> ancestors)
        {
            foreach (var node in nodes)
            {
                var label = $"{node.Number} {node.Title}".Trim();
                var chain = new List<string>(ancestors) { label };
                var ancestorPath = string.Join(" › ", chain);

                var content = node.Content?.Trim() ?? "";
                if (content.Length > 0)
                {
                    foreach (var piece in SplitByLength(content, MaxChunkChars))
                    {
                        chunks.Add(new VectorChunk
                        {
                            NodeId = node.Id,
                            Path = label,
                            AncestorPath = ancestorPath,
                            // Embed the full lineage so the vector carries structural identity,
                            // not just the isolated fragment.
                            Text = $"{ancestorPath}\n{piece}"
                        });
                    }
                }

                Walk(node.Children, chain);
            }
        }

        Walk(tree.Nodes, new List<string>());
        return chunks;
    }

    private static IEnumerable<string> SplitByLength(string text, int max)
    {
        // Prefer paragraph boundaries; fall back to hard splits for very long paragraphs.
        var paras = text.Split(new[] { "\n\n" }, StringSplitOptions.RemoveEmptyEntries);
        var buffer = new StringBuilder();
        foreach (var para in paras)
        {
            if (para.Length > max)
            {
                if (buffer.Length > 0) { yield return buffer.ToString(); buffer.Clear(); }
                for (int i = 0; i < para.Length; i += max)
                    yield return para.Substring(i, Math.Min(max, para.Length - i));
                continue;
            }
            if (buffer.Length + para.Length + 2 > max && buffer.Length > 0)
            {
                yield return buffer.ToString();
                buffer.Clear();
            }
            if (buffer.Length > 0) buffer.Append("\n\n");
            buffer.Append(para);
        }
        if (buffer.Length > 0) yield return buffer.ToString();
    }

    private static float Cosine(float[] a, float[] b)
    {
        if (a.Length == 0 || b.Length == 0 || a.Length != b.Length) return 0f;
        float dot = 0, na = 0, nb = 0;
        for (int i = 0; i < a.Length; i++)
        {
            dot += a[i] * b[i];
            na += a[i] * a[i];
            nb += b[i] * b[i];
        }
        if (na == 0 || nb == 0) return 0f;
        return dot / (MathF.Sqrt(na) * MathF.Sqrt(nb));
    }
}
