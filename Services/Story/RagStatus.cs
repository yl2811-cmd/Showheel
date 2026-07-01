namespace Showheel.Services.Story;

/// <summary>Health/progress of the RAG index, surfaced to the UI for notifications.</summary>
public sealed class RagStatus
{
    public RagState State { get; set; } = RagState.Unknown;

    /// <summary>Short human message, e.g. "Index ready · 214 chunks".</summary>
    public string Message { get; set; } = "";

    /// <summary>0-100 while indexing.</summary>
    public int Progress { get; set; }

    public int ChunkCount { get; set; }
    public string EmbeddingModel { get; set; } = "";
    public DateTimeOffset? IndexedAt { get; set; }

    /// <summary>True when embeddings are configured and an index is loaded and usable.</summary>
    public bool Healthy => State == RagState.Ready && ChunkCount > 0;
}

public enum RagState
{
    Unknown,        // not checked yet
    NotConfigured,  // no embedding provider set
    Empty,          // configured but no index built
    Indexing,       // build in progress
    Ready,          // index loaded and usable
    Error           // last operation failed
}
