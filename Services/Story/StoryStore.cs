using System.Text.Json;

namespace Showheel.Services.Story;

/// <summary>
/// Persists the story tree and the RAG vector index as JSON files on disk
/// (App_Data/story/). File-backed so edits are git-visible and there is no DB dependency.
/// A simple lock serializes writes; this is a single-author authoring tool.
/// </summary>
public sealed class StoryStore
{
    private readonly string _dir;
    private readonly string _treePath;
    private readonly string _vectorsPath;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly ILogger<StoryStore> _logger;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    public StoryStore(IWebHostEnvironment env, ILogger<StoryStore> logger)
    {
        _logger = logger;
        _dir = Path.Combine(env.ContentRootPath, "App_Data", "story");
        Directory.CreateDirectory(_dir);
        _treePath = Path.Combine(_dir, "tree.json");
        _vectorsPath = Path.Combine(_dir, "vectors.json");
    }

    public bool TreeExists => File.Exists(_treePath);
    public bool VectorsExist => File.Exists(_vectorsPath);
    public string TreePath => _treePath;

    // ---- Tree ----

    public async Task<StoryTree?> LoadTreeAsync(CancellationToken ct = default)
    {
        if (!File.Exists(_treePath)) return null;
        await _gate.WaitAsync(ct);
        try
        {
            await using var fs = File.OpenRead(_treePath);
            return await JsonSerializer.DeserializeAsync<StoryTree>(fs, JsonOpts, ct);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load story tree from {Path}", _treePath);
            return null;
        }
        finally { _gate.Release(); }
    }

    public async Task SaveTreeAsync(StoryTree tree, CancellationToken ct = default)
    {
        tree.UpdatedAt = DateTimeOffset.UtcNow;
        await _gate.WaitAsync(ct);
        try
        {
            // Write to a temp file then move, so a crash mid-write can't corrupt tree.json.
            var tmp = _treePath + ".tmp";
            await using (var fs = File.Create(tmp))
                await JsonSerializer.SerializeAsync(fs, tree, JsonOpts, ct);
            File.Copy(tmp, _treePath, overwrite: true);
            File.Delete(tmp);
        }
        finally { _gate.Release(); }
    }

    // ---- Vectors ----

    public async Task<VectorIndex?> LoadVectorsAsync(CancellationToken ct = default)
    {
        if (!File.Exists(_vectorsPath)) return null;
        await _gate.WaitAsync(ct);
        try
        {
            await using var fs = File.OpenRead(_vectorsPath);
            return await JsonSerializer.DeserializeAsync<VectorIndex>(fs, JsonOpts, ct);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load vector index from {Path}", _vectorsPath);
            return null;
        }
        finally { _gate.Release(); }
    }

    public async Task SaveVectorsAsync(VectorIndex index, CancellationToken ct = default)
    {
        index.UpdatedAt = DateTimeOffset.UtcNow;
        await _gate.WaitAsync(ct);
        try
        {
            var tmp = _vectorsPath + ".tmp";
            await using (var fs = File.Create(tmp))
                await JsonSerializer.SerializeAsync(fs, index, JsonOpts, ct);
            File.Copy(tmp, _vectorsPath, overwrite: true);
            File.Delete(tmp);
        }
        finally { _gate.Release(); }
    }
}
