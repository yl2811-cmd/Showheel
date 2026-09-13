# Current website baseline and bake storage audit

The accepted baseline is Showheel commit `28a144b`, with Atheria city 0.68, field 0.07–0.10, height power 4.0, natural canopy 1.7, cliff whiteness 38. The source remains `D:/SKBS/maps/archeon-atlas`; the verified compressed preview remains `D:/SKBS/review/atheria-sparse-release-20260913/compressed-verified`.

## Old versions

Inactive, unreferenced version directories and two superseded compressed previews were moved to `D:/SKBS/archives/pending-manual-delete-20260913`. No file was permanently deleted. `archive-plan.json` records exact original and destination paths and SHA-256 hashes. The archive contains its own `restore-manifest.json`. Restore a directory by moving its `to` path back to its `from` path only when that original path is absent.

Active canopy-v13, sparse-v1, Orun landforms-v3, surface-v8-r2, water-v8-r3, windward-v8-r3, and AI input assets remain in place. canopy-v8 remains because the viewer still names it as a fallback. Prior audit records and editable source generators remain available.

The old folders were already excluded by the publication asset manifest. Their removal from the working website does not reduce the current compressed deployment. Git history retains earlier files; this cleanup does not rewrite that history.

## Website storage, measured from the compressed release

All MB here are decimal, 1 MB = 1,000,000 bytes. Current package: **916.50 MB**. Against a conservative **1,000 MB** cap, remaining space is **83.50 MB**. The earlier build report used 1 GiB (1,073.74 MB), with a 90% internal budget of 966.37 MB; these units must not be confused.

| Content that a finished viewer-only bake could replace | Current compressed MB |
| --- | ---: |
| Selected editor and Orun simulation code | 0.32 |
| Orun input, landform, surface, water and climate datasets | 326.82 |
| Atheria house editing metadata | 18.40 |
| Atheria canopy field and exclusions | 18.09 |
| Sparse canopy controls/data | 0.05 |
| Scene editing JSON data | 1.07 |
| Candidate replacement envelope | **364.75** |

Removing programs alone saves almost nothing. Source generators in `src` and build scripts are already outside the deployed site. Some `.js` files are geometry or atlas data and cannot be removed as though they were unused programs. Three.js and viewer, streaming, interaction and animation code must remain.

Conditional accounting: **final package = 551.75 MB + baked replacement assets and retained data**. For example, if the complete replacement costs 100 MB compressed, the package would be about 651.75 MB, saving 264.75 MB. This is an illustrative input to the formula, not a measured bake size or a forecast. The 364.75 MB figure is a replacement envelope, not guaranteed net savings; shared packed files and retained supporting data must be reconciled in the actual export.

## Feasible workflow

1. Keep the full simulation, terrain and settlement adjustment tools locally, saving parameters and seeds.
2. Export the accepted terrain, house and canopy surfaces into spatial chunks with appropriate LODs, fixed material attributes, and simplified data for picking and movement.
3. Keep water, cloud and other movement as separate runtime layers; those systems still require viewer code and suitable reduced inputs.
4. Publish the viewer and compressed baked chunks; omit only data proven unnecessary for that viewer. Keep authoring source recoverable locally or in a separate private/source repository if desired.
5. Compare fixed viewpoints and chunk boundaries to the accepted baseline, then measure the actual package and browser RAM/GPU use.

Orun already generates exposed faces rather than six faces for every voxel. Baking does not automatically offer an additional hidden-face reduction. Atheria already loads baked base geometry, but applies editable house patches and canopy changes at runtime. Both need a dedicated export/loader path to bake the accepted final result; simply hiding controls or dropping worker scripts breaks functionality.

Three.js describes exposed-face voxel geometry at https://threejs.org/manual/en/voxel-geometry and GPU resource disposal at https://threejs.org/manual/en/cleanup.html. Deployment size is separate from runtime memory. No RAM or GPU saving is claimed by this storage audit.

## Browser inspection

The verified compressed package was opened in the in-app browser at `http://127.0.0.1:8777/archeon-atlas/`. Atheria neighbourhood rendered with the accepted sparse defaults and a displayed coverage integral of 127.78 km². Orun rendered after its initial mesh-generation phase; one settled default view showed 137,377 columns and 60 fps. These are observations for this desktop and view, not performance guarantees.

No warning/error entries were captured during the initial Atheria-to-Orun inspection. A minor existing navigation issue was observed: entering Orun from Atheria retains the Atheria document title and an unrelated `focus=neighbourhood` URL parameter; Orun preset buttons also leave that URL parameter unchanged. This audit preserves baseline runtime code and records the issue rather than changing the accepted rendering.

`storage-audit.json`, `archive-verification.json`, and `browser-verification.json` contain the measured evidence. The full static asset verifier and compressed decode verifier are rerun after moving inactive files. No production deployment or completed baking implementation is implied.

## Follow-up: original colour switch

During the user's own live adjustment, DOM state reported `materialMode:0`, `busy:true`, `errors:[]`, while the last completed mesh statistics still belonged to geomorphic-v1. The current worker had not returned a completed legacy mesh after repeated observations several minutes apart. JavaScript heap readings were approximately 1.33–1.38 GB in that tab (not total process RAM or GPU memory).

`orun-controller.js` updates the requested slider label immediately and calls `applyMaterials`. `orun-view.js` then posts a full mesh job and retains the last committed mesh until a new worker result arrives. `orun-mesh.js` switches from the precomputed geomorphic material sampler to the legacy `orun-material-lod.js` sampler, which integrates a 64 m material lattice over the terrain. This is a costly recomputation, not a simple palette uniform change. No missing-resource or JavaScript exception was captured; no claim is made that this pending computation is complete or repaired.

The two controls have different purposes: `materialMode` selects the old material algorithm; `paletteStyle` selects warm white versus the original grey-blue within the newer geomorphic material algorithm. The latter is handled through the current palette uniforms. A robust follow-up should distinguish requested from displayed state and provide a cancellable/progressive legacy bake or cache, rather than presenting an unfinished change as applied.
