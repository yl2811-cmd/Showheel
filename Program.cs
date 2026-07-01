using Showheel.Services.Ai;
using Showheel.Services.Story;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorPages();
builder.Services.AddControllers();

// AI provider config (base URL + key + model per role). Keys stay server-side.
// Put real keys in user-secrets or environment variables, never in committed appsettings.
builder.Services.Configure<AiOptions>(builder.Configuration.GetSection(AiOptions.SectionName));

// In-memory cache for AI calls (chat + embeddings), keyed by request hash. Cuts paid
// round-trips for identical prompts / repeated embeddings and reports hit/miss stats.
builder.Services.AddSingleton<AiResponseCache>();

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

app.UseAuthorization();

app.MapRazorPages();
app.MapControllers();

app.Run();
