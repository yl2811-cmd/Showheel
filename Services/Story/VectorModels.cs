namespace Showheel.Services.Story;

/// <summary>
/// One embedded chunk of story content. A chunk maps back to the StoryNode it came
/// from so RAG results can cite the exact section and the co-author can edit it.
/// </summary>
public sealed class VectorChunk
{
    public string Id { get; set; } = Guid.NewGuid().ToString("n");

    /// <summary>Id of the <see cref="StoryNode"/> this chunk was derived from.</summary>
    public string NodeId { get; set; } = "";

    /// <summary>Human-readable path like "1.7 Characters · Anna 档案" for citations.</summary>
    public string Path { get; set; } = "";

    /// <summary>
    /// Full ancestor chain from the top-level section down to this node, e.g.
    /// "1 世界观 › 1.7 Characters › Anna 档案". Gives the model structural context
    /// (where a fact sits in the book), not just an isolated fragment.
    /// </summary>
    public string AncestorPath { get; set; } = "";

    /// <summary>The raw text that was embedded.</summary>
    public string Text { get; set; } = "";

    /// <summary>The embedding vector.</summary>
    public float[] Embedding { get; set; } = Array.Empty<float>();
}

/// <summary>Persisted RAG index (vectors.json). Global — gives the AI whole-book awareness.</summary>
public sealed class VectorIndex
{
    public int Version { get; set; } = 1;

    /// <summary>Model used to build the embeddings; a mismatch means the index must be rebuilt.</summary>
    public string EmbeddingModel { get; set; } = "";

    /// <summary>Dimensionality of the vectors (for a fast sanity check).</summary>
    public int Dimensions { get; set; }

    public List<VectorChunk> Chunks { get; set; } = new();

    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}
