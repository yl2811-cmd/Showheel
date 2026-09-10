using System.Text.Json;
using Microsoft.AspNetCore.StaticFiles;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddRazorPages();
var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();

// This marker is emitted only into an optimized publish, never into the authoring site.
var routeFile = Path.Combine(app.Environment.ContentRootPath, "showheel-web-routes.json");
if (File.Exists(routeFile))
{
    using var manifest = JsonDocument.Parse(File.ReadAllText(routeFile));
    var routes = manifest.RootElement.GetProperty("routes").EnumerateObject()
        .ToDictionary(p => p.Name, p => p.Value.GetString()!, StringComparer.OrdinalIgnoreCase);
    var packed = manifest.RootElement.GetProperty("packed").EnumerateObject()
        .ToDictionary(p => p.Name, p => (
            File: p.Value.GetProperty("file").GetString()!,
            ContentType: p.Value.GetProperty("contentType").GetString()!), StringComparer.OrdinalIgnoreCase);
    var webRoot = Path.GetFullPath(app.Environment.WebRootPath) + Path.DirectorySeparatorChar;
    string AssetPath(string relative)
    {
        var full = Path.GetFullPath(Path.Combine(webRoot, relative.TrimStart('/')));
        if (!full.StartsWith(webRoot, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Invalid published asset path");
        return full;
    }
    foreach (var target in routes.Values) _ = AssetPath(target);
    foreach (var target in packed.Values) _ = AssetPath(target.File);
    app.Use(async (context, next) =>
    {
        if (HttpMethods.IsGet(context.Request.Method) || HttpMethods.IsHead(context.Request.Method))
        {
            var requestPath = context.Request.Path.Value ?? "/";
            if (packed.TryGetValue(requestPath, out var asset))
            {
                var file = AssetPath(asset.File);
                context.Response.ContentType = asset.ContentType;
                context.Response.Headers.ContentEncoding = "gzip";
                context.Response.Headers.CacheControl = "no-cache";
                context.Response.ContentLength = new FileInfo(file).Length;
                if (!HttpMethods.IsHead(context.Request.Method)) await context.Response.SendFileAsync(file);
                return;
            }
            if (routes.TryGetValue(requestPath.Length > 1 ? requestPath.TrimEnd('/') : requestPath, out var destination)) context.Request.Path = destination;
        }
        await next();
    });
}

var contentTypes = new FileExtensionContentTypeProvider();
contentTypes.Mappings[".pack"] = "application/octet-stream";
app.UseStaticFiles(new StaticFileOptions
{
    ContentTypeProvider = contentTypes,
    OnPrepareResponse = context =>
    {
        if (context.Context.Request.Path.StartsWithSegments("/_packed") && context.File.Name.EndsWith(".pack", StringComparison.Ordinal))
            context.Context.Response.Headers.CacheControl = "public, max-age=31536000, immutable";
    }
});
app.UseRouting();
app.UseAuthorization();
app.MapRazorPages();
app.Run();
