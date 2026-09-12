# Atheria cliff whiteness

The Atheria sidebar now controls the three cliff faces with a single 0–100 slider. Zero exactly preserves the accepted colours. The linked warm-white albedo curve retains the original rock variation and does not change lighting, geometry, buildings, fields, vegetation or water.

The default remains 0 until the author reports a preferred value. The Copy parameters action includes the value and baseline revision. Promote a confirmed value by updating defaultValue and baselineRevision in the source cliff-look.json, rebuilding its metadata with build-atheria-cliff-look.cjs and repeating import and verification. Keep the numeric scale and original binary colours unchanged. Old browser trials are ignored after a baseline revision changes.

Ownership masks are generated for all four regional LODs only, and are loaded as sidecars. The existing regional builder refreshes ownership at each output exit. The compressed site loads these files through the established packed-asset loader.

Source verification confirms 3,124 original binary assets and the Chinese manuscript were unchanged. Browser verification covers zero equivalence, resetting, all LODs, near detail, light modes, clipboard, refresh, baseline invalidation, capture and responsive controls.

## Eyrie exclusion, 2026-09-12

The author restricted this control to the three regional cliff faces. Eyrie high-detail terrain, all its objects, the collar and proxies retain their original materials and colours. No cliff masks or shader hooks are attached to those meshes. The regional masks, curve, scalar default and persisted trial values are unchanged. See eyrie-exclusion-source.json and eyrie-exclusion-browser.json for the updated verification.
