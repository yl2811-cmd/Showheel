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

    public StoryApiController(
        StoryTreeService tree,
        RagService rag,
        CoAuthorService coauthor,
        TranslationService translator,
        StoryPatchService patch,
        UploadService uploads)
    {
        _tree = tree;
        _rag = rag;
        _coauthor = coauthor;
        _translator = translator;
        _patch = patch;
        _uploads = uploads;
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
        var (reply, citations) = await _coauthor.ChatAsync(req.Message, history, req.ImageDataUrls, thinking, ct);
        return Ok(new { reply, citations });
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
    public sealed record ChatRequest(string Message, List<ChatTurn>? History, List<string>? ImageDataUrls, string? Thinking);
    public sealed record ChatTurn(string Role, string Content);
    public sealed record AuditRequest(string? Thinking);
    public sealed record ProposePatchRequest(string Instruction, string? DraftText, List<string>? ImageDataUrls, string? Thinking);
    public sealed record TranslateRequest(string? Text, string? TargetLang);
}
