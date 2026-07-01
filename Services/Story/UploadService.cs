using System.Text;

namespace Showheel.Services.Story;

/// <summary>Metadata + extracted payload for an uploaded file.</summary>
public sealed class UploadedFile
{
    public string Id { get; set; } = Guid.NewGuid().ToString("n");
    public string FileName { get; set; } = "";
    public string ContentType { get; set; } = "";
    public long Size { get; set; }

    /// <summary>text | image | other — how the co-author should treat it.</summary>
    public string Kind { get; set; } = "other";

    /// <summary>Extracted UTF-8 text for text files (old drafts, notes). Empty otherwise.</summary>
    public string? Text { get; set; }

    /// <summary>data: URL for images, so a vision model can read them. Null otherwise.</summary>
    public string? DataUrl { get; set; }

    public DateTimeOffset UploadedAt { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>
/// Accepts chat attachments (txt drafts, images, other media), stores the raw file
/// under App_Data/story/uploads/, and extracts a usable payload: text for .txt/.md,
/// a base64 data URL for images. File content is treated as untrusted data and is
/// never executed. Size/type limits guard against abuse.
/// </summary>
public sealed class UploadService
{
    private readonly string _uploadDir;
    private readonly ILogger<UploadService> _logger;

    private const long MaxBytes = 12 * 1024 * 1024; // 12 MB per file
    private const long MaxTextBytes = 2 * 1024 * 1024; // extract text up to 2 MB

    private static readonly HashSet<string> TextExtensions = new(StringComparer.OrdinalIgnoreCase)
    { ".txt", ".md", ".markdown", ".text" };

    private static readonly Dictionary<string, string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        [".png"] = "image/png",
        [".jpg"] = "image/jpeg",
        [".jpeg"] = "image/jpeg",
        [".gif"] = "image/gif",
        [".webp"] = "image/webp"
    };

    public UploadService(IWebHostEnvironment env, ILogger<UploadService> logger)
    {
        _logger = logger;
        _uploadDir = Path.Combine(env.ContentRootPath, "App_Data", "story", "uploads");
        Directory.CreateDirectory(_uploadDir);
    }

    public async Task<UploadedFile> SaveAsync(IFormFile file, CancellationToken ct = default)
    {
        if (file.Length <= 0) throw new InvalidOperationException("Empty file.");
        if (file.Length > MaxBytes) throw new InvalidOperationException($"File too large (>{MaxBytes / (1024 * 1024)} MB).");

        // Sanitize the name; never trust client-provided paths.
        var safeName = Path.GetFileName(file.FileName);
        var ext = Path.GetExtension(safeName);
        var record = new UploadedFile
        {
            FileName = safeName,
            ContentType = file.ContentType ?? "application/octet-stream",
            Size = file.Length
        };

        // Persist raw bytes under a generated id (no path traversal risk).
        var storedPath = Path.Combine(_uploadDir, record.Id + ext);
        await using (var fs = File.Create(storedPath))
            await file.CopyToAsync(fs, ct);

        if (TextExtensions.Contains(ext))
        {
            record.Kind = "text";
            if (file.Length <= MaxTextBytes)
                record.Text = await File.ReadAllTextAsync(storedPath, Encoding.UTF8, ct);
            else
                record.Text = "(file too large to extract inline)";
        }
        else if (ImageExtensions.TryGetValue(ext, out var mime))
        {
            record.Kind = "image";
            var bytes = await File.ReadAllBytesAsync(storedPath, ct);
            record.DataUrl = $"data:{mime};base64,{Convert.ToBase64String(bytes)}";
        }
        else
        {
            record.Kind = "other";
        }

        _logger.LogInformation("Stored upload {Name} ({Kind}, {Size} bytes)", safeName, record.Kind, file.Length);
        return record;
    }

    /// <summary>The on-disk file name for an upload id + extension (e.g. "&lt;id&gt;.png").</summary>
    private static string StoredName(string id, string ext) => id + ext;

    /// <summary>
    /// Builds a persistable <see cref="NodeAsset"/> from an uploaded file and returns the
    /// stored file name so it can be re-read later (e.g. to re-serve an image to the AI).
    /// </summary>
    public NodeAsset ToNodeAsset(UploadedFile upload)
    {
        // The stored name is "&lt;id&gt;&lt;ext&gt;"; recover the extension from the original name.
        var ext = Path.GetExtension(upload.FileName);
        return new NodeAsset
        {
            Id = upload.Id,
            FileName = upload.FileName,
            Kind = upload.Kind,
            ContentType = upload.ContentType,
            Size = upload.Size,
            StoredName = StoredName(upload.Id, ext),
        };
    }

    /// <summary>Resolves the absolute path of a stored asset, guarding against path traversal.</summary>
    public string? ResolvePath(string storedName)
    {
        var safe = Path.GetFileName(storedName ?? "");
        if (string.IsNullOrEmpty(safe)) return null;
        var full = Path.Combine(_uploadDir, safe);
        // Ensure the resolved path stays inside the uploads directory.
        var root = Path.GetFullPath(_uploadDir);
        var target = Path.GetFullPath(full);
        if (!target.StartsWith(root, StringComparison.Ordinal)) return null;
        return File.Exists(target) ? target : null;
    }

    /// <summary>Reads an image asset back as a base64 data URL so a vision model can see it.</summary>
    public async Task<string?> ReadImageDataUrlAsync(NodeAsset asset, CancellationToken ct = default)
    {
        if (asset.Kind != "image") return null;
        var path = ResolvePath(asset.StoredName);
        if (path is null) return null;
        var ext = Path.GetExtension(path);
        if (!ImageExtensions.TryGetValue(ext, out var mime)) return null;
        var bytes = await File.ReadAllBytesAsync(path, ct);
        return $"data:{mime};base64,{Convert.ToBase64String(bytes)}";
    }
}
