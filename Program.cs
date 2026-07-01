using Showheel.Services.Ai;
using Showheel.Services.Story;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorPages();
builder.Services.AddControllers();

// In-process session for the Story Studio password gate + AI slot ownership. The session
// cookie carries only an opaque id; the auth flag + slot owner id live server-side.
builder.Services.AddDistributedMemoryCache();
builder.Services.AddSession(o =>
{
    o.IdleTimeout = TimeSpan.FromHours(8);
    o.Cookie.HttpOnly = true;
    o.Cookie.IsEssential = true;
    o.Cookie.SameSite = SameSiteMode.Lax;
});

// AI provider config (base URL + key + model per role). Keys stay server-side.
// Put real keys in user-secrets or environment variables, never in committed appsettings.
builder.Services.Configure<AiOptions>(builder.Configuration.GetSection(AiOptions.SectionName));

// Studio entry password (bound from "Studio" section). Empty disables the gate.
builder.Services.Configure<StudioOptions>(builder.Configuration.GetSection(StudioOptions.SectionName));

// In-memory cache for AI calls (chat + embeddings), keyed by request hash. Cuts paid
// round-trips for identical prompts / repeated embeddings and reports hit/miss stats.
builder.Services.AddSingleton<AiResponseCache>();

// Process-wide telemetry + occupancy lock for the main-brain co-author. Singletons so the
// counters/owner are shared across all requests in the process.
builder.Services.AddSingleton<MainBrainTelemetry>();
builder.Services.AddSingleton<AiSlotService>();

// Single HttpClient for all OpenAI-compatible provider calls.
builder.Services.AddHttpClient<OpenAiCompatibleClient>(c =>
{
    c.Timeout = TimeSpan.FromSeconds(120);
});

// Story tree + RAG services.
builder.Services.AddSingleton<StoryParser>();
builder.Services.AddSingleton<StoryStore>();
builder.Services.AddSingleton<RagService>();
builder.Services.AddSingleton<UploadService>();
builder.Services.AddScoped<ConversationMemory>();
builder.Services.AddScoped<StoryTreeService>();
builder.Services.AddScoped<StoryPatchService>();
builder.Services.AddScoped<CoAuthorService>();
builder.Services.AddScoped<TranslationService>();

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();

app.UseRouting();

// Session must be acquired before authorization so [Authorize]/auth checks can read it.
app.UseSession();

app.UseAuthorization();

app.MapRazorPages();
app.MapControllers();

app.Run();
