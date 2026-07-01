using Microsoft.AspNetCore.Mvc;
using Showheel.Services.Ai;
using Showheel.Services.Story;

namespace Showheel.Controllers;

/// <summary>
/// Backend API for the Story Studio. The browser never sees API keys — it calls
/// these endpoints, which call the configured AI providers server-side.
///
/// NOTE: this API is currently unauthenticated. Because it proxies to paid AI
/// providers using a server-held key, add authentication + rate limiting before
/// exposing it publicly (see README / Program.cs comments).
/// </summary>
[ApiController]
[Route("api/story")]
public sealed class StoryApiController : ControllerBase
{
    private readonly StoryTreeService _tree;
    private readonly RagService _rag;
    private readonly CoAuthorService _coauthor;
    private readonly TranslationService _translator;
    private readonly StoryPatchService _patch;
    private readonly UploadService _uploads;
    private readonly AiResponseCache _cache;

    public StoryApiController(
        StoryTreeService tree,
        RagService rag,
        CoAuthorService coauthor,
        TranslationService translator,
        StoryPatchService patch,
        UploadService uploads,
        AiResponseCache cache)
    {
        _tree = tree;
        _rag = rag;
        _coauthor = coauthor;
        _translator = translator;
        _patch = patch;
        _uploads = uploads;
        _cache = cache;
    }

    // ---- Tree ----

    [HttpGet("tree")]
    public async Task<IActionResult> GetTree(CancellationToken ct)
    {
        var tree = await _tree.GetTreeAsync(ct);
        return Ok(new { exists = tree is not null, tree });
    }

    /// <summary>Decompose the flat plain-text story into the tree structure.</summary>
    [HttpPost("decompose")]
    public async Task<IActionResult> Decompose([FromBody] DecomposeRequest? req, CancellationToken ct)
    {
        var tree = await _tree.DecomposeAsync(req?.SourceFile, ct);
        return Ok(new { nodeCount = tree.Flatten().Count(), tree });
    }

    [HttpPost("node")]
    public async Task<IActionResult> AddNode([FromBody] AddNodeRequest req, CancellationToken ct)
    {
        var node = await _tree.AddNodeAsync(req.ParentId, req.Title ?? "", req.Content ?? "", ct);
        return node is null ? NotFound(new { error = "Parent not found." }) : Ok(node);
    }

    [HttpPut("node/{id}")]
    public async Task<IActionResult> UpdateNode(string id, [FromBody] UpdateNodeRequest req, CancellationToken ct)
    {
        var node = await _tree.UpdateNodeAsync(id, req.Title, req.Content, ct);
        return node is null ? NotFound(new { error = "Node not found." }) : Ok(node);
    }

    [HttpDelete("node/{id}")]
    public async Task<IActionResult> DeleteNode(string id, CancellationToken ct)
    {
        var ok = await _tree.DeleteNodeAsync(id, ct);
        return ok ? Ok(new { deleted = true }) : NotFound(new { error = "Node not found." });
    }

    // ---- Per-node content export / import ----

    /// <summary>Download a node's raw text content as a .txt attachment.</summary>
    [HttpGet("node/{id}/export")]
    public async Task<IActionResult> ExportNode(string id, CancellationToken ct)
    {
        var tree = await _tree.GetTreeAsync(ct);
        var node = tree?.Find(id);
        if (node is null) return NotFound(new { error = "Node not found." });
        var name = SafeFileName($"{node.Number}-{node.Title}") + ".txt";
        return File(System.Text.Encoding.UTF8.GetBytes(node.Content ?? ""), "text/plain; charset=utf-8", name);
    }

    /// <summary>Overwrite a node's content from uploaded text (the "upload to overwrite" flow).</summary>
    [HttpPut("node/{id}/content")]
    public async Task<IActionResult> SetNodeContent(string id, [FromBody] SetContentRequest req, CancellationToken ct)
    {
        var node = await _tree.SetContentAsync(id, req.Content ?? "", ct);
        return node is null ? NotFound(new { error = "Node not found." }) : Ok(node);
    }

    /// <summary>Save a translation for a node under a language code (e.g. "en", "ja").</summary>
    [HttpPut("node/{id}/translation")]
    public async Task<IActionResult> SetNodeTranslation(string id, [FromBody] SetTranslationRequest req, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(req.Lang)) return BadRequest(new { error = "Language code required." });
        var node = await _tree.SetTranslationAsync(id, req.Lang, req.Text ?? "", ct);
        return node is null ? NotFound(new { error = "Node not found." }) : Ok(node);
    }

    /// <summary>Download the whole tree as a single structured .txt outline.</summary>
    [HttpGet("export")]
    public async Task<IActionResult> ExportTree(CancellationToken ct)
    {
        var tree = await _tree.GetTreeAsync(ct);
        if (tree is null) return NotFound(new { error = "Decompose the story first." });
        var sb = new System.Text.StringBuilder();
        sb.Append(tree.Title).Append("\n\n");
        foreach (var n in tree.Nodes) AppendNode(sb, n);
        var bytes = System.Text.Encoding.UTF8.GetBytes(sb.ToString());
        return File(bytes, "text/plain; charset=utf-8", "skies-beyond-the-star-tree.txt");
    }

    private static void AppendNode(System.Text.StringBuilder sb, StoryNode n)
    {
        var indent = new string(' ', Math.Max(0, n.Depth) * 2);
        sb.Append(indent).Append(n.Number).Append(' ').Append(n.Title).Append('\n');
        if (!string.IsNullOrWhiteSpace(n.Content))
            foreach (var line in n.Content.Replace("\r\n", "\n").Split('\n'))
                sb.Append(indent).Append("  ").Append(line).Append('\n');
        sb.Append('\n');
        foreach (var c in n.Children) AppendNode(sb, c);
    }

    // ---- Node assets (files attached to a node, saved server-side) ----

    /// <summary>Upload a file and attach it to a node. Images become visible to the co-author.</summary>
    [HttpPost("node/{id}/asset")]
    [RequestSizeLimit(16 * 1024 * 1024)]
    public async Task<IActionResult> AddNodeAsset(string id, [FromForm] IFormFile file, CancellationToken ct)
    {
        if (file is null) return BadRequest(new { error = "No file." });
        try
        {
            var upload = await _uploads.SaveAsync(file, ct);
            var asset = _uploads.ToNodeAsset(upload);
            var saved = await _tree.AddAssetAsync(id, asset, ct);
            return saved is null ? NotFound(new { error = "Node not found." }) : Ok(saved);
        }
        catch (Exception ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// <summary>Detach an asset from a node (bytes are retained on disk).</summary>
    [HttpDelete("node/{id}/asset/{assetId}")]
    public async Task<IActionResult> RemoveNodeAsset(string id, string assetId, CancellationToken ct)
    {
        var ok = await _tree.RemoveAssetAsync(id, assetId, ct);
        return ok ? Ok(new { removed = true }) : NotFound(new { error = "Asset not found." });
    }

    /// <summary>Serve a node asset's raw bytes (used for image thumbnails in the UI).</summary>
    [HttpGet("node/{id}/asset/{assetId}")]
    public async Task<IActionResult> GetNodeAsset(string id, string assetId, CancellationToken ct)
    {
        var tree = await _tree.GetTreeAsync(ct);
        var node = tree?.Find(id);
        var asset = node?.Assets.FirstOrDefault(a => a.Id == assetId);
        if (asset is null) return NotFound();
        var path = _uploads.ResolvePath(asset.StoredName);
        if (path is null) return NotFound();
        var bytes = await System.IO.File.ReadAllBytesAsync(path, ct);
        return File(bytes, string.IsNullOrEmpty(asset.ContentType) ? "application/octet-stream" : asset.ContentType);
    }

    // ---- RAG ----

    [HttpGet("rag/status")]
    public async Task<IActionResult> RagStatus(CancellationToken ct)
        => Ok(await _rag.RefreshStatusAsync(ct));

    [HttpPost("rag/rebuild")]
    public async Task<IActionResult> RagRebuild(CancellationToken ct)
    {
        var tree = await _tree.GetTreeAsync(ct);
        if (tree is null) return BadRequest(new { error = "Decompose the story first." });
        var status = await _rag.RebuildAsync(tree, ct);
        return Ok(status);
    }

    // ---- AI call cache utilization ----

    /// <summary>Report hit/miss utilization of the AI response + embedding cache.</summary>
    [HttpGet("cache/stats")]
    public IActionResult CacheStats() => Ok(_cache.Stats());

    /// <summary>Clear the AI response cache.</summary>
    [HttpPost("cache/clear")]
    public IActionResult CacheClear() => Ok(new { cleared = _cache.Clear() });

    // ---- Co-author (main brain) ----

    [HttpPost("chat")]
    public async Task<IActionResult> Chat([FromBody] ChatRequest req, CancellationToken ct)
    {
        if (!_coauthor.IsConfigured)
            return BadRequest(new { error = "Co-author provider not configured." });
        if (string.IsNullOrWhiteSpace(req.Message))
            return BadRequest(new { error = "Message is required." });

        var history = (req.History ?? new())
            .Where(m => !string.IsNullOrWhiteSpace(m.Content))
            .Select(m => new ChatMessage { Role = m.Role == "assistant" ? "assistant" : "user", Content = m.Content })
            .ToList();

        var thinking = ThinkingLevelExtensions.Parse(req.Thinking);
        var images = await ResolveImagesAsync(req.ImageDataUrls, req.NodeAssetIds, ct);
        var (reply, citations) = await _coauthor.ChatAsync(req.Message, history, images, thinking, ct);
        return Ok(new { reply, citations });
    }

    /// <summary>
    /// Merges transient chat image data URLs with images pulled from node-attached assets,
    /// so the co-author sees images the user saved onto the tree (server-side), not just
    /// files staged in the current message.
    /// </summary>
    private async Task<List<string>?> ResolveImagesAsync(List<string>? dataUrls, List<AssetRef>? assetRefs, CancellationToken ct)
    {
        var images = new List<string>();
        if (dataUrls is not null) images.AddRange(dataUrls.Where(u => !string.IsNullOrWhiteSpace(u)));

        if (assetRefs is not null && assetRefs.Count > 0)
        {
            var tree = await _tree.GetTreeAsync(ct);
            if (tree is not null)
            {
                foreach (var r in assetRefs)
                {
                    var node = tree.Find(r.NodeId);
                    var asset = node?.Assets.FirstOrDefault(a => a.Id == r.AssetId);
                    if (asset is null) continue;
                    var url = await _uploads.ReadImageDataUrlAsync(asset, ct);
                    if (url is not null) images.Add(url);
                }
            }
        }
        return images.Count == 0 ? null : images;
    }

    [HttpPost("audit")]
    public async Task<IActionResult> Audit([FromBody] AuditRequest? req, CancellationToken ct)
    {
        var tree = await _tree.GetTreeAsync(ct);
        if (tree is null) return BadRequest(new { error = "Decompose the story first." });
        if (!_coauthor.IsConfigured) return BadRequest(new { error = "Co-author provider not configured." });
        var thinking = ThinkingLevelExtensions.Parse(req?.Thinking);
        return Ok(new { report = await _coauthor.AuditAsync(tree, thinking, ct) });
    }

    // ---- Uploads (txt drafts, images) ----

    [HttpPost("upload")]
    [RequestSizeLimit(16 * 1024 * 1024)]
    public async Task<IActionResult> Upload([FromForm] IFormFile file, CancellationToken ct)
    {
        if (file is null) return BadRequest(new { error = "No file." });
        try
        {
            var record = await _uploads.SaveAsync(file, ct);
            // Do not echo full image data URLs back in the list response; keep payload lean.
            return Ok(new
            {
                record.Id,
                record.FileName,
                record.Kind,
                record.Size,
                textPreview = record.Text is null ? null : (record.Text.Length > 400 ? record.Text[..400] + "…" : record.Text),
                record.Text,
                record.DataUrl
            });
        }
        catch (Exception ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    // ---- Patch (propose / apply) ----

    /// <summary>Ask the co-author to propose a reviewable changeset. Nothing is applied.</summary>
    [HttpPost("patch/propose")]
    public async Task<IActionResult> ProposePatch([FromBody] ProposePatchRequest req, CancellationToken ct)
    {
        if (!_coauthor.IsConfigured)
            return BadRequest(new { error = "Co-author provider not configured." });
        if (string.IsNullOrWhiteSpace(req.Instruction))
            return BadRequest(new { error = "Instruction is required." });

        var thinking = ThinkingLevelExtensions.Parse(req.Thinking ?? "high");
        var patch = await _coauthor.ProposePatchAsync(req.Instruction, req.DraftText, req.ImageDataUrls, thinking, ct);
        var validation = await _patch.ValidateAsync(patch, ct);
        return Ok(new { patch, valid = validation.Success, errors = validation.Errors });
    }

    /// <summary>Apply a reviewed changeset atomically, then reindex once.</summary>
    [HttpPost("patch/apply")]
    public async Task<IActionResult> ApplyPatch([FromBody] StoryPatch patch, CancellationToken ct)
    {
        var result = await _patch.ApplyAsync(patch, reindex: true, ct);
        if (!result.Success) return BadRequest(new { errors = result.Errors });
        var tree = await _tree.GetTreeAsync(ct);
        return Ok(new { applied = result.Applied, tree });
    }

    // ---- Translation (separate model) ----

    [HttpPost("translate")]
    public async Task<IActionResult> Translate([FromBody] TranslateRequest req, CancellationToken ct)
    {
        if (!_translator.IsConfigured)
            return BadRequest(new { error = "Translator provider not configured." });
        var result = await _translator.TranslateAsync(req.Text ?? "", req.TargetLang ?? "English", ct);
        return Ok(new { translation = result });
    }

    // ---- request DTOs ----

    public sealed record DecomposeRequest(string? SourceFile);
    public sealed record AddNodeRequest(string? ParentId, string? Title, string? Content);
    public sealed record UpdateNodeRequest(string? Title, string? Content);
    public sealed record SetContentRequest(string? Content);
    public sealed record SetTranslationRequest(string? Lang, string? Text);
    public sealed record AssetRef(string NodeId, string AssetId);
    public sealed record ChatRequest(string Message, List<ChatTurn>? History, List<string>? ImageDataUrls, List<AssetRef>? NodeAssetIds, string? Thinking);
    public sealed record ChatTurn(string Role, string Content);
    public sealed record AuditRequest(string? Thinking);
    public sealed record ProposePatchRequest(string Instruction, string? DraftText, List<string>? ImageDataUrls, string? Thinking);
    public sealed record TranslateRequest(string? Text, string? TargetLang);

    // ---- helpers ----

    private static string SafeFileName(string raw)
    {
        var invalid = System.IO.Path.GetInvalidFileNameChars();
        var cleaned = new string(raw.Select(c => invalid.Contains(c) ? '-' : c).ToArray()).Trim();
        cleaned = System.Text.RegularExpressions.Regex.Replace(cleaned, @"\s+", "-");
        return string.IsNullOrEmpty(cleaned) ? "section" : (cleaned.Length > 80 ? cleaned[..80] : cleaned);
    }
}
