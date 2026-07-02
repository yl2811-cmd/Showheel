using System.Security.Cryptography;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using Showheel.Services.Ai;
using Showheel.Services.Story;

namespace Showheel.Controllers;

/// <summary>
/// Backend API for the Story Studio. The browser never sees API keys — it calls
/// these endpoints, which call the configured AI providers server-side.
///
/// Authentication: a session-based password gate. The AI-touching endpoints
/// (chat / audit / patch-propose / translate) additionally require ownership of the
/// single AI slot (see <see cref="AiSlotService"/>), so only one person can drive the
/// main brain at a time. The entry password lives in config and is compared server-side.
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
    private readonly MainBrainTelemetry _telemetry;
    private readonly AiSlotService _slot;
    private readonly IOptionsMonitor<StudioOptions> _studio;

    public StoryApiController(
        StoryTreeService tree,
        RagService rag,
        CoAuthorService coauthor,
        TranslationService translator,
        StoryPatchService patch,
        UploadService uploads,
        AiResponseCache cache,
        MainBrainTelemetry telemetry,
        AiSlotService slot,
        IOptionsMonitor<StudioOptions> studio)
    {
        _tree = tree;
        _rag = rag;
        _coauthor = coauthor;
        _translator = translator;
        _patch = patch;
        _uploads = uploads;
        _cache = cache;
        _telemetry = telemetry;
        _slot = slot;
        _studio = studio;
    }

    // ---- Auth + slot (session-based password gate) ----

    private const string AuthSessionKey = "studio.authed";
    private const string OwnerSessionKey = "studio.owner";

    /// <summary>True when the gate is disabled (no password configured) or the session is authed.</summary>
    private bool IsAuthed()
        => string.IsNullOrEmpty(_studio.CurrentValue.Password) ||
           HttpContext.Session.GetInt32(AuthSessionKey) == 1;

    /// <summary>The stable per-session owner id, or null when not authenticated.</summary>
    private string? OwnerId() => IsAuthed() ? HttpContext.Session.GetString(OwnerSessionKey) : null;

    /// <summary>401 if the session hasn't passed the gate. Call at the top of protected endpoints.</summary>
    private IActionResult? RequireAuth()
        => IsAuthed() ? null : Unauthorized(new { error = "Password required.", requiresAuth = true });

    /// <summary>
    /// Guards an AI-driving endpoint: requires auth, then requires that this session owns
    /// the AI slot. If the slot is free it is claimed (lazily) for this caller; if it is
    /// held by another session, returns 409. Returns 401 when not authenticated.
    /// </summary>
    private IActionResult? RequireSlot()
    {
        var authFail = RequireAuth();
        if (authFail is not null) return authFail;
        var owner = HttpContext.Session.GetString(OwnerSessionKey);
        if (owner is null) return Unauthorized(new { error = "Password required.", requiresAuth = true });
        // TryClaim is atomic: succeeds when free / held-by-me / expired; fails only when
        // another unexpired session holds the slot. Calling it per request both checks and
        // renews ownership, so two free-slot users can't race past the gate.
        return _slot.TryClaim(owner) ? null : Conflict(new { error = "AI busy: another session is using the co-author.", busy = true, status = _slot.Status() });
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
        var auth = RequireAuth();
        if (auth is not null) return auth;
        var tree = await _tree.DecomposeAsync(req?.SourceFile, authorityBuckets: true, ct);
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

    // ---- Auth + slot (entry gate + single-writer AI lock) ----

    /// <summary>Whether a password is configured and the current session is unlocked.</summary>
    [HttpGet("auth/status")]
    public IActionResult AuthStatus()
        => Ok(new { authed = IsAuthed(), requiresPassword = !string.IsNullOrEmpty(_studio.CurrentValue.Password) });

    /// <summary>Verify the studio entry password and unlock this session.</summary>
    [HttpPost("auth/login")]
    public IActionResult AuthLogin([FromBody] LoginRequest? req)
    {
        var password = _studio.CurrentValue.Password ?? "";
        if (password.Length == 0)
        {
            // Gate disabled: auto-auth and mint an owner id.
            EnsureOwner();
            HttpContext.Session.SetInt32(AuthSessionKey, 1);
            return Ok(new { authed = true });
        }
        if (req is null || !FixedTimeEquals(req.Password ?? "", password))
            return Unauthorized(new { error = "Wrong password.", requiresAuth = true });

        EnsureOwner();
        HttpContext.Session.SetInt32(AuthSessionKey, 1);
        return Ok(new { authed = true });
    }

    /// <summary>The single AI conversation slot: who holds it right now.</summary>
    [HttpGet("slot/status")]
    public IActionResult SlotStatus() => Ok(_slot.Status());

    /// <summary>Claim the AI slot for this session (fails 409 if held by another).</summary>
    [HttpPost("slot/claim")]
    public IActionResult SlotClaim()
    {
        var fail = RequireAuth();
        if (fail is not null) return fail;
        var owner = EnsureOwner();
        var claimed = _slot.TryClaim(owner);
        return claimed ? Ok(new { claimed = true, status = _slot.Status() })
                       : Conflict(new { claimed = false, busy = true, error = "AI busy: another session holds the slot.", status = _slot.Status() });
    }

    /// <summary>Renew this session's hold on the AI slot (heartbeat).</summary>
    [HttpPost("slot/heartbeat")]
    public IActionResult SlotHeartbeat()
    {
        var fail = RequireAuth();
        if (fail is not null) return fail;
        var owner = HttpContext.Session.GetString(OwnerSessionKey);
        return Ok(new { renewed = owner is not null && _slot.Renew(owner ?? ""), status = _slot.Status() });
    }

    /// <summary>Release the AI slot so another session can take over immediately.</summary>
    [HttpPost("slot/release")]
    public IActionResult SlotRelease()
    {
        var owner = HttpContext.Session.GetString(OwnerSessionKey);
        if (owner is not null) _slot.Release(owner);
        return Ok(new { released = true, status = _slot.Status() });
    }

    // ---- Main-brain telemetry (token usage + context window) ----

    /// <summary>Cumulative + last-turn token usage for the co-author, and context-window occupancy.</summary>
    [HttpGet("telemetry")]
    public IActionResult Telemetry() => Ok(_telemetry.Snapshot());

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
        var gate = RequireSlot();
        if (gate is not null) return gate;
        var providerError = TryBuildProvider(req.Provider, out var provider);
        if (providerError is not null) return BadRequest(new { error = providerError });
        if (provider is null && !_coauthor.IsConfigured)
            return BadRequest(new { error = "Co-author provider not configured. Configure a model provider to chat." });
        if (string.IsNullOrWhiteSpace(req.Message))
            return BadRequest(new { error = "Message is required." });

        var history = (req.History ?? new())
            .Where(m => !string.IsNullOrWhiteSpace(m.Content))
            .Select(m => new ChatMessage { Role = m.Role == "assistant" ? "assistant" : "user", Content = m.Content })
            .ToList();

        var thinking = ThinkingLevelExtensions.Parse(req.Thinking);
        var images = await ResolveImagesAsync(req.ImageDataUrls, req.NodeAssetIds, ct);
        var (reply, citations) = await _coauthor.ChatAsync(req.Message, history, images, thinking, provider, ct);
        return Ok(new { reply, citations, telemetry = _telemetry.Snapshot() });
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
        var gate = RequireSlot();
        if (gate is not null) return gate;
        var tree = await _tree.GetTreeAsync(ct);
        if (tree is null) return BadRequest(new { error = "Decompose the story first." });
        var providerError = TryBuildProvider(req?.Provider, out var provider);
        if (providerError is not null) return BadRequest(new { error = providerError });
        if (provider is null && !_coauthor.IsConfigured)
            return BadRequest(new { error = "Co-author provider not configured. Configure a model provider to run this check." });
        var thinking = ThinkingLevelExtensions.Parse(req?.Thinking);
        return Ok(new { report = await _coauthor.AuditAsync(tree, thinking, provider, ct), telemetry = _telemetry.Snapshot() });
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
        var gate = RequireSlot();
        if (gate is not null) return gate;
        var providerError = TryBuildProvider(req.Provider, out var provider);
        if (providerError is not null) return BadRequest(new { error = providerError });
        if (provider is null && !_coauthor.IsConfigured)
            return BadRequest(new { error = "Co-author provider not configured. Configure a model provider to propose patches." });
        if (string.IsNullOrWhiteSpace(req.Instruction))
            return BadRequest(new { error = "Instruction is required." });

        var thinking = ThinkingLevelExtensions.Parse(req.Thinking ?? "high");
        var patch = await _coauthor.ProposePatchAsync(req.Instruction, req.DraftText, req.ImageDataUrls, thinking, provider, ct);
        var validation = await _patch.ValidateAsync(patch, ct);
        return Ok(new { patch, valid = validation.Success, errors = validation.Errors, telemetry = _telemetry.Snapshot() });
    }

    /// <summary>
    /// Parses a pasted plain-text patch document (e.g. written by an external "main
    /// brain" over a long chat) into a reviewable changeset. Sections target nodes by
    /// outline path — no ids. Nothing is applied; the response carries the parsed patch
    /// (path references resolved), per-section previews, and any errors.
    /// No AI call happens here, so the AI slot is not required.
    /// </summary>
    [HttpPost("patch/parse")]
    public async Task<IActionResult> ParsePatchDoc([FromBody] ParsePatchRequest? req, CancellationToken ct)
    {
        var auth = RequireAuth();
        if (auth is not null) return auth;
        if (req is null || string.IsNullOrWhiteSpace(req.Text))
            return BadRequest(new { error = "Patch document text is required." });

        StoryPatch patch;
        var parseErrors = new List<string>();
        if (StoryPatchTextParser.LooksLikeTextPatch(req.Text))
            patch = StoryPatchTextParser.Parse(req.Text, out parseErrors);
        else
            patch = CoAuthorService.ParsePatch(req.Text); // tolerate pasted JSON too

        var validation = await _patch.ValidateAsync(patch, ct);
        var errors = parseErrors.Concat(validation.Errors).ToList();

        // Per-section preview with resolved display paths for the review UI.
        var tree = await _tree.GetTreeAsync(ct);
        var sections = patch.Ops.Select(op =>
        {
            var target = op.TargetId is not null ? tree?.Find(op.TargetId) : null;
            var parent = op.ParentId is not null ? tree?.Find(op.ParentId) : null;
            return new
            {
                op = op.Op,
                targetPath = target is not null && tree is not null ? StoryPath.DisplayPath(tree, target) : op.TargetPath,
                parentPath = parent is not null && tree is not null ? StoryPath.DisplayPath(tree, parent) : op.ParentPath,
                title = op.Title,
                number = op.Number,
                reason = op.Reason,
                contentChars = op.Content?.Length ?? 0,
                currentChars = target?.Content?.Length ?? 0,
            };
        }).ToList();

        return Ok(new { patch, valid = errors.Count == 0 && validation.Success, errors, sections });
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
        var gate = RequireSlot();
        if (gate is not null) return gate;
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
    public sealed record ChatRequest(string Message, List<ChatTurn>? History, List<string>? ImageDataUrls, List<AssetRef>? NodeAssetIds, string? Thinking, ProviderRequest? Provider);
    public sealed record ChatTurn(string Role, string Content);
    public sealed record ProviderRequest(string? BaseUrl, string? ApiKey, string? Model, int? MaxContextTokens);
    public sealed record AuditRequest(string? Thinking, ProviderRequest? Provider);
    public sealed record ProposePatchRequest(string Instruction, string? DraftText, List<string>? ImageDataUrls, string? Thinking, ProviderRequest? Provider);
    public sealed record ParsePatchRequest(string? Text);
    public sealed record TranslateRequest(string? Text, string? TargetLang);
    public sealed record LoginRequest(string? Password);

    // ---- helpers ----

    /// <summary>Mints (once per session) a stable owner id used for AI-slot ownership.</summary>
    private string EnsureOwner()
    {
        var owner = HttpContext.Session.GetString(OwnerSessionKey);
        if (string.IsNullOrEmpty(owner))
        {
            owner = Guid.NewGuid().ToString("N");
            HttpContext.Session.SetString(OwnerSessionKey, owner);
        }
        return owner;
    }

    private static string? TryBuildProvider(ProviderRequest? provider, out ProviderOptions? result)
    {
        result = null;
        if (provider is null) return null;
        var any =
            !string.IsNullOrWhiteSpace(provider.BaseUrl) ||
            !string.IsNullOrWhiteSpace(provider.ApiKey) ||
            !string.IsNullOrWhiteSpace(provider.Model) ||
            provider.MaxContextTokens is not null;
        if (!any) return null;

        if (string.IsNullOrWhiteSpace(provider.BaseUrl) ||
            string.IsNullOrWhiteSpace(provider.ApiKey) ||
            string.IsNullOrWhiteSpace(provider.Model))
            return "Model provider requires Base URL, API key, and model.";
        if (provider.MaxContextTokens is not null && provider.MaxContextTokens <= 0)
            return "Model provider max context tokens must be greater than zero.";

        result = new ProviderOptions
        {
            BaseUrl = provider.BaseUrl.Trim(),
            ApiKey = provider.ApiKey.Trim(),
            Model = provider.Model.Trim(),
            MaxContextTokens = provider.MaxContextTokens
        };
        return null;
    }

    /// <summary>Constant-time string compare to avoid leaking the password length via timing.</summary>
    private static bool FixedTimeEquals(string a, string b)
    {
        var aa = System.Text.Encoding.UTF8.GetBytes(a ?? "");
        var bb = System.Text.Encoding.UTF8.GetBytes(b ?? "");
        return aa.Length == bb.Length && CryptographicOperations.FixedTimeEquals(aa, bb);
    }

    // ---- helpers ----

    private static string SafeFileName(string raw)
    {
        var invalid = System.IO.Path.GetInvalidFileNameChars();
        var cleaned = new string(raw.Select(c => invalid.Contains(c) ? '-' : c).ToArray()).Trim();
        cleaned = System.Text.RegularExpressions.Regex.Replace(cleaned, @"\s+", "-");
        return string.IsNullOrEmpty(cleaned) ? "section" : (cleaned.Length > 80 ? cleaned[..80] : cleaned);
    }
}
