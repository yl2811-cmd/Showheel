namespace Showheel.Services.Story;

/// <summary>
/// Validates and applies a <see cref="StoryPatch"/> to the story tree in a single
/// atomic pass, then persists once and triggers one RAG reindex. This is the
/// token-efficient alternative to many per-edit tool calls: the co-author proposes a
/// whole changeset, the human approves, and we apply it here.
/// </summary>
public sealed class StoryPatchService
{
    private readonly StoryStore _store;
    private readonly RagService _rag;
    private readonly ILogger<StoryPatchService> _logger;

    public StoryPatchService(StoryStore store, RagService rag, ILogger<StoryPatchService> logger)
    {
        _store = store;
        _rag = rag;
        _logger = logger;
    }

    /// <summary>Validates a patch against the current tree without changing anything.</summary>
    public async Task<PatchResult> ValidateAsync(StoryPatch patch, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct);
        if (tree is null)
            return new PatchResult { Success = false, Errors = { "Tree not initialized — decompose the story first." } };
        return Validate(patch, tree);
    }

    /// <summary>
    /// Applies the patch atomically: validates all ops first; if anything is invalid,
    /// nothing is written. On success, persists the tree once and rebuilds the RAG index.
    /// </summary>
    public async Task<PatchResult> ApplyAsync(StoryPatch patch, bool reindex = true, CancellationToken ct = default)
    {
        var tree = await _store.LoadTreeAsync(ct);
        if (tree is null)
            return new PatchResult { Success = false, Errors = { "Tree not initialized — decompose the story first." } };

        var validation = Validate(patch, tree);
        if (!validation.Success) return validation;

        var applied = new List<string>();
        foreach (var op in patch.Ops)
        {
            switch (op.Op.Trim().ToLowerInvariant())
            {
                case "add":
                    ApplyAdd(tree, op, applied);
                    break;
                case "update":
                    ApplyUpdate(tree, op, applied);
                    break;
                case "append":
                    ApplyAppend(tree, op, applied);
                    break;
                case "delete":
                    ApplyDelete(tree, op, applied);
                    break;
                case "move":
                    ApplyMove(tree, op, applied);
                    break;
            }
        }

        await _store.SaveTreeAsync(tree, ct);
        _logger.LogInformation("Applied patch '{Summary}' with {Count} ops", patch.Summary, applied.Count);

        if (reindex)
        {
            // One reindex for the whole changeset (not per edit).
            try { await _rag.RebuildAsync(tree, ct); }
            catch (Exception ex) { _logger.LogWarning(ex, "Reindex after patch failed; index may be stale."); }
        }

        return new PatchResult { Success = true, Applied = applied };
    }

    // --- validation ---

    /// <summary>
    /// Resolves human/model-friendly path references (targetPath/parentPath) to node ids
    /// in place, so the rest of the pipeline works on ids while the model never sees a
    /// GUID. Resolution failures become validation errors.
    /// </summary>
    private static void ResolvePaths(StoryPatch patch, StoryTree tree, PatchResult result)
    {
        foreach (var op in patch.Ops)
        {
            if (string.IsNullOrEmpty(op.TargetId) && !string.IsNullOrWhiteSpace(op.TargetPath))
            {
                var r = StoryPath.Resolve(tree, op.TargetPath);
                if (r.Success) op.TargetId = r.Node!.Id;
                else result.Errors.Add($"{op.Op}: {r.Error}");
            }
            if (string.IsNullOrEmpty(op.ParentId) && !string.IsNullOrWhiteSpace(op.ParentPath))
            {
                var r = StoryPath.Resolve(tree, op.ParentPath);
                if (r.Success) op.ParentId = r.Node!.Id;
                else result.Errors.Add($"{op.Op}: {r.Error}");
            }
        }
    }

    private static PatchResult Validate(StoryPatch patch, StoryTree tree)
    {
        var result = new PatchResult { Success = true };
        if (patch.Ops.Count == 0)
        {
            result.Success = false;
            result.Errors.Add("Patch has no operations.");
            return result;
        }

        ResolvePaths(patch, tree, result);

        foreach (var op in patch.Ops)
        {
            var kind = op.Op.Trim().ToLowerInvariant();
            var targetRef = op.TargetPath ?? op.TargetId;
            var parentRef = op.ParentPath ?? op.ParentId;
            // A path that failed to resolve already produced an error in ResolvePaths;
            // don't double-report it here.
            var targetUnresolved = string.IsNullOrEmpty(op.TargetId) && !string.IsNullOrWhiteSpace(op.TargetPath);
            var parentUnresolved = string.IsNullOrEmpty(op.ParentId) && !string.IsNullOrWhiteSpace(op.ParentPath);
            switch (kind)
            {
                case "add":
                    if (!parentUnresolved && !string.IsNullOrEmpty(op.ParentId) && tree.Find(op.ParentId) is null)
                        result.Errors.Add($"add: parent '{parentRef}' not found.");
                    if (string.IsNullOrWhiteSpace(op.Title) && string.IsNullOrWhiteSpace(op.Content))
                        result.Errors.Add("add: needs a title or content.");
                    break;
                case "update":
                case "append":
                case "delete":
                    if (!targetUnresolved && (string.IsNullOrEmpty(op.TargetId) || tree.Find(op.TargetId) is null))
                        result.Errors.Add($"{kind}: target '{targetRef}' not found.");
                    break;
                case "move":
                    if (!targetUnresolved && (string.IsNullOrEmpty(op.TargetId) || tree.Find(op.TargetId) is null))
                        result.Errors.Add($"move: target '{targetRef}' not found.");
                    if (!parentUnresolved && !string.IsNullOrEmpty(op.ParentId) && tree.Find(op.ParentId) is null)
                        result.Errors.Add($"move: parent '{parentRef}' not found.");
                    if (!string.IsNullOrEmpty(op.TargetId) && op.TargetId == op.ParentId)
                        result.Errors.Add("move: a node cannot be its own parent.");
                    break;
                default:
                    result.Errors.Add($"Unknown op '{op.Op}'.");
                    break;
            }
        }

        result.Success = result.Errors.Count == 0;
        return result;
    }

    // --- apply helpers ---

    private static void ApplyAdd(StoryTree tree, PatchOp op, List<string> applied)
    {
        var node = new StoryNode
        {
            Number = op.Number ?? "",
            Title = op.Title ?? "",
            Content = op.Content ?? ""
        };
        if (string.IsNullOrEmpty(op.ParentId))
        {
            node.Depth = 0;
            InsertAt(tree.Nodes, node, op.Position);
        }
        else
        {
            var parent = tree.Find(op.ParentId)!;
            node.Depth = parent.Depth + 1;
            InsertAt(parent.Children, node, op.Position);
        }
        Renumber(tree);
        applied.Add($"add “{node.Title}”");
    }

    private static void ApplyUpdate(StoryTree tree, PatchOp op, List<string> applied)
    {
        var node = tree.Find(op.TargetId!)!;
        if (op.Title is not null) node.Title = op.Title;
        if (op.Content is not null) node.Content = op.Content;
        if (op.Number is not null) node.Number = op.Number;
        node.UpdatedAt = DateTimeOffset.UtcNow;
        applied.Add($"update “{node.Title}”");
    }

    private static void ApplyAppend(StoryTree tree, PatchOp op, List<string> applied)
    {
        var node = tree.Find(op.TargetId!)!;
        var addition = op.Content ?? "";
        node.Content = string.IsNullOrEmpty(node.Content)
            ? addition
            : node.Content.TrimEnd() + "\n\n" + addition;
        node.UpdatedAt = DateTimeOffset.UtcNow;
        applied.Add($"append to “{node.Title}”");
    }

    private static void ApplyDelete(StoryTree tree, PatchOp op, List<string> applied)
    {
        var node = tree.Find(op.TargetId!);
        var title = node?.Title ?? op.TargetId!;
        if (tree.Remove(op.TargetId!))
        {
            Renumber(tree);
            applied.Add($"delete “{title}”");
        }
    }

    private static void ApplyMove(StoryTree tree, PatchOp op, List<string> applied)
    {
        var node = tree.Find(op.TargetId!)!;
        var title = node.Title;

        // Detach without losing the subtree.
        tree.Remove(op.TargetId!);

        if (string.IsNullOrEmpty(op.ParentId))
        {
            node.Depth = 0;
            InsertAt(tree.Nodes, node, op.Position);
        }
        else
        {
            var parent = tree.Find(op.ParentId!)!;
            node.Depth = parent.Depth + 1;
            InsertAt(parent.Children, node, op.Position);
        }
        FixDepth(node);
        Renumber(tree);
        applied.Add($"move “{title}”");
    }

    private static void InsertAt(List<StoryNode> list, StoryNode node, int? position)
    {
        if (position is int p && p >= 0 && p <= list.Count) list.Insert(p, node);
        else list.Add(node);
    }

    private static void FixDepth(StoryNode node)
    {
        foreach (var child in node.Children)
        {
            child.Depth = node.Depth + 1;
            FixDepth(child);
        }
    }

    /// <summary>Recomputes sibling Order across the whole tree after structural edits.</summary>
    private static void Renumber(StoryTree tree)
    {
        void Walk(List<StoryNode> nodes)
        {
            for (int i = 0; i < nodes.Count; i++)
            {
                nodes[i].Order = i;
                Walk(nodes[i].Children);
            }
        }
        Walk(tree.Nodes);
    }
}
