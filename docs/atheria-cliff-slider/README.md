# Atheria cliff whiteness

The Atheria sidebar now controls the three cliff faces with a single 0–100 slider. Zero exactly preserves the accepted colours. The linked warm-white albedo curve retains the original rock variation and does not change lighting, geometry, buildings, fields, vegetation or water.

The default remains 0 until the author reports a preferred value. The Copy parameters action includes the value and baseline revision. Promote a confirmed value by updating defaultValue and baselineRevision in the source cliff-look.json, rebuilding its metadata with build-atheria-cliff-look.cjs and repeating import and verification. Keep the numeric scale and original binary colours unchanged. Old browser trials are ignored after a baseline revision changes.

Ownership masks are generated for all four regional LODs and the Eyrie terrain/collar, and are loaded as sidecars. The existing regional builder refreshes ownership at each output exit. The compressed site loads these files through the established packed-asset loader.

Source verification confirms 3,124 original binary assets and the Chinese manuscript were unchanged. Browser verification covers zero equivalence, resetting, all LODs, near detail, light modes, clipboard, refresh, baseline invalidation, capture and responsive controls.
