namespace Showheel.Services.Story;

/// <summary>
/// Loads/creates the story tree. On first run it decomposes wwwroot/story.md
/// (the flat plain-text book) into the tree via <see cref="StoryParser"/> and
/// persists it. Afterwards the persisted tree.json is the source of truth and
/// AI edits mutate it.
/// </summary>
public sealed class StoryTreeService
{
    private readonly StoryStore _store;
    private readonly StoryParser _parser;
    private readonly IWebHostEnvironment _env;
    private readonly ILogger<StoryTreeService> _logger;

    public StoryTreeService(StoryStore store, StoryParser parser, IWebHostEnvironment env, ILogger<StoryTreeService> logger)
    {
        _store = store;
        _parser = parser;
        _env = env;
        _logger = logger;
    }

    /// <summary>Returns the persisted tree, or null if it hasn't been decomposed yet.</summary>
    public Task<StoryTree?> GetTreeAsync(CancellationToken ct = default) => _store.LoadTreeAsync(ct);

    /// <summary>
    /// Parses the source markdown into a tree and persists it, replacing any existing tree.
    /// This is the "decompose plain text into tree structure" action.
    /// </summary>
    public async Task<StoryTree> DecomposeAsync(string? sourceFile = null, CancellationToken ct = default)
    {
        var path = ResolveSource(sourceFile);
        if (!File.Exists(path))
            throw new FileNotFoundException($"Story source not found: {path}");

        var markdown = await File.ReadAllTextAsync(path, ct);
        var tree = _parser.Parse(markdown);
        await _store.SaveTreeAsync(tree, ct);
        _logger.LogInformation("Decomposed {Path} into {Count} nodes", path, tree.Flatten().Count());
        return tree;
    }

    /// <summary>Persists an externally-modified tree.</summary>
    public Task SaveAsync(StoryTree tree, CancellationToken ct = default) => _store.SaveTreeAsync(tree, ct);

    /// <summary>Adds a child node under a parent (or top-level when parentId is null).</summary>
    public async Task<StoryNode?> AddNodeAsync(string? parentId, string title, string content, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var node = new StoryNode { Title = title, Content = content };

        if (string.IsNullOrEmpty(parentId))
        {
            node.Depth = 0;
            node.Order = tree.Nodes.Count;
            tree.Nodes.Add(node);
        }
        else
        {
            var parent = tree.Find(parentId);
            if (parent is null) return null;
            node.Depth = parent.Depth + 1;
            node.Order = parent.Children.Count;
            parent.Children.Add(node);
        }
        await _store.SaveTreeAsync(tree, ct);
        return node;
    }

    /// <summary>Updates title/content of a node.</summary>
    public async Task<StoryNode?> UpdateNodeAsync(string id, string? title, string? content, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var node = tree.Find(id);
        if (node is null) return null;
        if (title is not null) node.Title = title;
        if (content is not null) node.Content = content;
        node.UpdatedAt = DateTimeOffset.UtcNow;
        await _store.SaveTreeAsync(tree, ct);
        return node;
    }

    /// <summary>Prunes (deletes) a node and its subtree — used to remove stale content.</summary>
    public async Task<bool> DeleteNodeAsync(string id, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var removed = tree.Remove(id);
        if (removed) await _store.SaveTreeAsync(tree, ct);
        return removed;
    }

    private string ResolveSource(string? sourceFile)
    {
        var name = string.IsNullOrWhiteSpace(sourceFile) ? "story.md" : Path.GetFileName(sourceFile);
        return Path.Combine(_env.WebRootPath, name);
    }
}
