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
    /// When <paramref name="authorityBuckets"/> is true (default) the parsed sections are
    /// reorganized under the 8 authority-level folders that mirror the canon repo
    /// (00-meta … 90-archive), so both humans and the AI read the structure the same way.
    /// </summary>
    public async Task<StoryTree> DecomposeAsync(string? sourceFile = null, bool authorityBuckets = true, CancellationToken ct = default)
    {
        var path = ResolveSource(sourceFile);
        if (!File.Exists(path))
            throw new FileNotFoundException($"Story source not found: {path}");

        var markdown = await File.ReadAllTextAsync(path, ct);
        var tree = _parser.Parse(markdown);
        if (authorityBuckets) tree = ReorganizeIntoBuckets(tree);
        await _store.SaveTreeAsync(tree, ct);
        _logger.LogInformation("Decomposed {Path} into {Count} nodes", path, tree.Flatten().Count());
        return tree;
    }

    /// <summary>The 8 authority buckets, in override order (lower number wins on conflict).</summary>
    private static readonly (string Bucket, string Title, string Blurb)[] Buckets =
    {
        ("00-meta",       "00 · Meta 元层",        "How the repo runs — index / glossary / codes / conventions"),
        ("10-canon",      "10 · Canon 正典",        "What the world is — worldview / map / characters / history"),
        ("20-craft",      "20 · Craft 工艺",        "What counts as written right — the writing constitution"),
        ("30-design",     "30 · Design 设计",       "How the story is built — arcs / modules / ledgers / principles"),
        ("40-manuscript", "40 · Manuscript 正文",   "The work itself — English prose (drafts)"),
        ("50-assets",     "50 · Assets 资产",       "What the world looks like — uploaded images & references"),
        ("60-taste",      "60 · Taste 品味",        "What the world should feel like — paired samples & rulings"),
        ("90-archive",    "90 · Archive 归档",      "What failure looks like — specimens (never a source of fact)"),
    };

    /// <summary>Maps a parsed top-level section number (0–9) to its dominant authority bucket.</summary>
    private static string BucketForSection(string number) => number switch
    {
        "0" => "00-meta",       // 全局索引 / 纪年表 / GLOSSARY / 代号词典
        "1" => "10-canon",      // 世界观
        "2" => "10-canon",      // 世界地图
        "3" => "20-craft",      // 童年篇（宪法 + 骨架 + 模块库）
        "4" => "30-design",     // Arc 计划
        "5" => "30-design",     // 账本
        "6" => "00-meta",       // 裁决与规约
        "7" => "30-design",     // 设计原则与悬而未决
        "8" => "30-design",     // Arc 1 逐集明细
        "9" => "60-taste",      // 品味层
        _   => "10-canon",
    };

    /// <summary>
    /// Wraps the flat top-level sections produced by the parser under the 8 authority
    /// buckets. Lossless: each section keeps its title/content/children and is nested
    /// whole under its dominant bucket. Empty buckets are still emitted so the structure
    /// is visible and the AI/user can populate them (e.g. drop images into 50-assets).
    /// </summary>
    private static StoryTree ReorganizeIntoBuckets(StoryTree parsed)
    {
        var tree = new StoryTree { Title = parsed.Title };

        // Create the 8 bucket nodes up front, preserving order.
        var byBucket = new Dictionary<string, StoryNode>(StringComparer.Ordinal);
        for (int i = 0; i < Buckets.Length; i++)
        {
            var (bucket, title, blurb) = Buckets[i];
            var node = new StoryNode
            {
                Number = bucket,
                Title = title,
                Content = blurb,
                Bucket = bucket,
                Depth = 0,
                Order = i,
            };
            byBucket[bucket] = node;
            tree.Nodes.Add(node);
        }

        // Re-parent each parsed top-level section under its bucket, deepening the subtree by 1.
        foreach (var section in parsed.Nodes)
        {
            var bucketKey = BucketForSection(section.Number);
            var bucket = byBucket[bucketKey];
            Deepen(section, bucket.Depth + 1);
            section.Order = bucket.Children.Count;
            bucket.Children.Add(section);
        }

        return tree;
    }

    /// <summary>Recomputes Depth for a node and its subtree starting at <paramref name="depth"/>.</summary>
    private static void Deepen(StoryNode node, int depth)
    {
        node.Depth = depth;
        foreach (var c in node.Children) Deepen(c, depth + 1);
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

    /// <summary>Overwrites a node's content wholesale (used by the "upload text to overwrite" flow).</summary>
    public async Task<StoryNode?> SetContentAsync(string id, string content, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var node = tree.Find(id);
        if (node is null) return null;
        node.Content = content;
        node.UpdatedAt = DateTimeOffset.UtcNow;
        await _store.SaveTreeAsync(tree, ct);
        return node;
    }

    /// <summary>Saves a single translation for a node under the given language code.</summary>
    public async Task<StoryNode?> SetTranslationAsync(string id, string lang, string text, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var node = tree.Find(id);
        if (node is null) return null;
        var code = lang.Trim().ToLowerInvariant();
        if (string.IsNullOrEmpty(code)) return node;
        node.Translations[code] = text;
        if (code == "en") node.ContentEn = text; // keep the legacy field in sync
        node.UpdatedAt = DateTimeOffset.UtcNow;
        await _store.SaveTreeAsync(tree, ct);
        return node;
    }

    /// <summary>Attaches an already-uploaded asset (image/txt/other) to a node.</summary>
    public async Task<NodeAsset?> AddAssetAsync(string nodeId, NodeAsset asset, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var node = tree.Find(nodeId);
        if (node is null) return null;
        node.Assets.Add(asset);
        node.UpdatedAt = DateTimeOffset.UtcNow;
        await _store.SaveTreeAsync(tree, ct);
        return asset;
    }

    /// <summary>Detaches an asset from a node. Returns true if it was present. Does not delete bytes.</summary>
    public async Task<bool> RemoveAssetAsync(string nodeId, string assetId, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct) ?? throw new InvalidOperationException("Tree not initialized.");
        var node = tree.Find(nodeId);
        if (node is null) return false;
        var removed = node.Assets.RemoveAll(a => a.Id == assetId) > 0;
        if (removed) { node.UpdatedAt = DateTimeOffset.UtcNow; await _store.SaveTreeAsync(tree, ct); }
        return removed;
    }

    private string ResolveSource(string? sourceFile)
    {
        var name = string.IsNullOrWhiteSpace(sourceFile) ? "story.md" : Path.GetFileName(sourceFile);
        return Path.Combine(_env.WebRootPath, name);
    }
}
