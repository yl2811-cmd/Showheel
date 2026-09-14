# Orun spring ground and stable controls

Implemented locally on the accepted Atheria/Orun baseline. GitHub publication is disabled for this run by the user's latest instruction.

## Result

Latest user preference: default to original rock colours (`materialMode=0`) in code, the asset manifest and future spring builds. Existing manual drafts remain separate.

- Preview defaults: terracotta 1.0, top vegetation 0.80, side vegetation 0.90, habitat response 1.15, seep response 1.20. Other pigments, erosion and river controls retain the accepted values.
- Vegetation occupies its ecological fraction first; rock pigments occupy only the remaining bare fraction. Both rock rendering modes use the same ecology. Herbaceous cover and moss increase while the sampled woodland footprint remains exactly unchanged.
- Habitat response is separate from the conserved hydrology computation. Physical water arrays, routes, ledger and final terrain height are preserved. New vegetation caches use the final evolved terrain and the current water fields.
- Automatic request replacement no longer invokes the user cancellation/reset path. One active computation and one replaceable latest request are retained; duplicate requests are coalesced. Stale responses cannot install a superseded scene. Explicit cancellation or failure retains the draft.
- Saved drafts use an independent local key. Reopening presents a saved draft as unapplied rather than silently replacing it with a new default or claiming it is rendered.
- Original-rock and geomorphic chunks have separate bounded caches. The first uncached original-rock computation can still take time; the page identifies requested and displayed material separately and reports chunk progress.
- Cloud bodies use a continuous density field with smooth height changes and shear, retaining 200 m cubes and terrain clearance. Optical-depth crossfading avoids doubling opacity between generations. Default connected vertical stacks remain at most 600 m in the tests.
- Orun navigation validates focus names and writes its own page title and preset URL.

## Verification

`unit-verification.json` records six passing groups: compact asset-reference input, approved defaults/physical-water key, habitat mass/tree/water preservation, rock/vegetation composition, queued/cancelled/failed/out-of-order requests, and coherent-cloud geometry.

`geometry-verification.json` compares 74,084 actual generated vertices / 37,042 triangles between both material modes: positions, normals, indices and canopy statistics match; all colour attributes are finite. All four fixture chunks were reused on switching back.

`coverage.json` samples 775 locations from the current final terrain. Mean top-surface vegetation changed from 39.0% to 50.5% in the low band, 52.6% to 67.3% in the middle band, and 15.4% to 20.5% in the high band. The 88 suitable moist/soil-supported samples averaged 84.98%; 88.64% were in the 70–90% target range. These are model weights at sampled locations, not screenshot pixel percentages or real-world measurements. Maximum tree-coverage delta is zero.

`build-verification.json` preserves the physical water hash `4efeedad739b90492cdab7a0604d87dcf56c831b63f7a5f8759305468e2f89e9` and final height hash `8f9d9db64626054cc4b9f2ec01b75d71de6de3d875cabe386d943ea2a8778fbe`. The precomputed verifier confirms climate, terrain, hydrology and material fields do not require recomputation at startup.

The full atlas verifier passed 4,606 hashes and five geographic dependency graphs. The final compressed verifier passed 3,144 packed and 1,590 copied resources, with 10 exported pages. Unaffected imported resources: 4,580. Chinese Timelapse matches its source byte-for-byte; English remains unchanged.

Browser inspection covered the new The Weeps scene and successful original-rock application. No captured browser warnings/errors occurred in those observations. The user continued adjusting the open previews; those drafts remain separate from release defaults. Runtime timing and heap samples are observational and vary with concurrent previews and cache state. The source scene recorded a settled 60 fps sample and approximately 9.6 s for one mesh job; another compressed cold job recorded about 77.8 s with multiple previews active. No general performance guarantee or total RAM/GPU memory claim is made.

## Package and local previews

Final package: **916,526,788 bytes (916.53 MB)**. Hard cap: **1,000,000,000 bytes**. Enforced target: **950,000,000 bytes**. Hard-cap headroom: **83,473,212 bytes**. The builder now supports an explicit `--budget-mb` while preserving its existing 90% default for other invocations.

- Authoring preview: http://127.0.0.1:8780/#view=orun&focus=weeps
- Compressed preview: http://127.0.0.1:8781/archeon-atlas/#view=orun&focus=weeps
- Final package directory: `D:/SKBS/review/orun-spring-20260913/compressed-original-default`
- Authoring generator: `D:/SKBS/maps/archeon-atlas/src/build-orun-spring.cjs`

The first test package accidentally included temporary arrays in the JSON input. This was corrected, the input returned to 12,710 bytes, and a regression check prevents recurrence. Only `compressed-original-default` is the verified final package. Earlier experimental packages remain local and are not the deliverable.

This is an authoring/runtime refinement, not the separate full viewer-only baking project. No GitHub push or production deployment was performed.
