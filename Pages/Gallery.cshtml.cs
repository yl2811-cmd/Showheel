using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Showheel.Pages
{
    public class GalleryModel : PageModel
    {
        private static readonly string[] AllowedExtensions =
            new[] { ".png", ".jpg", ".jpeg", ".webp", ".gif" };

        private readonly IWebHostEnvironment _env;

        public GalleryModel(IWebHostEnvironment env)
        {
            _env = env;
        }

        public List<string> Images { get; private set; } = new();

        public void OnGet()
        {
            var imagesDir = Path.Combine(_env.WebRootPath, "images");
            if (!Directory.Exists(imagesDir))
            {
                return;
            }

            Images = Directory
                .EnumerateFiles(imagesDir)
                .Where(p => AllowedExtensions.Contains(Path.GetExtension(p).ToLowerInvariant()))
                .Select(p => Path.GetFileName(p) ?? string.Empty)
                .Where(n => !string.IsNullOrEmpty(n))
                .OrderBy(n => n, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }
    }
}
