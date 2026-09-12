# Atheria cliff whiteness

The author-approved default is **38/100**, baseline revision **atheria-cliff-white-2**. Reset returns to 38. Zero still means the original, unmodified colours, and the numeric scale and warm-rock-1 curve are unchanged. A previous baseline's trial value is ignored on reload.

Only regional cliff rock receives the shader adjustment. Eyrie high-detail terrain, its buildings, the collar and architecture proxies keep their original materials and colours.

## Central distant cliff coverage

The regional terrain previously excluded the central 256 m square even when high detail was not loaded. This left an untinted block at a distance. The regional ownership mask now includes this terrain across all four LODs. The viewer's existing Eyrie visibility clipping hides it when the separate high-detail scene is shown; no high-detail material hooks or masks are added.

The fix adds 5,140 regional vertices and preserves all prior ownership, binary model files and original colours. Browser checks target the omitted block at every actual visible LOD, verify that the old trial value becomes 38, and confirm pixel-identical high-detail renders at slider values 0 and 100. Updated evidence is in baseline38-*.json; older verification files document the preceding revisions.

To promote a future author-approved value, update defaultValue and baselineRevision in the source cliff-look.json, regenerate sidecar metadata using build-atheria-cliff-look.cjs, then import, validate, compress and push the current branch. Do not bake another colour gain into the original models or change the slider's scale.
