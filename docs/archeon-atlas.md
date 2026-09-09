# Archeon Atlas integration

The website uses the accepted v6 atlas from `D:/SKBS/maps/archeon-atlas`.
The source directory is external to this repository and is never modified by the import.

## Refreshing browser assets

Run `node scripts/import-archeon-atlas.cjs [source-directory]` from this repository.
The importer copies the five map scripts, atlas data, tile metadata, referenced terrain previews/clouds/mist, PNG terrain tiles, JavaScript contour blocks, and the local D3 distribution with its license.
It checks source and destination SHA-256 hashes and writes `docs/archeon-atlas-assets.json`.
The web-only adaptations remove SVG/PNG export controls and link to `about.html`.
Review the manifest diff on every refresh; the importer does not delete files.

`wwwroot/archeon-atlas/index.html` is the public map entry. `/world-atlas.html` redirects there to preserve old links. No legacy atlas content is published.
`about.html` is the website help page. Geographic descriptions, map geometry, coordinates and layers are copied without alteration.

The imported runtime is approximately 524 MiB including the Eyrie scene. Editable terrain arrays, source-generation scripts, historical versions, QA output and standalone map exports remain outside the website. JSON geography downloads are retained.
This integration does not change the deployment workflow or enable Git LFS.

## Validation

### Atheria regional refresh — 2026-09-09

Imported the source Atheria regional viewer and manifest-referenced binary geometry, plus updated Eyrie geometry, materials, batches and wind/life runtime. The importer and verifier now follow the regional manifest and controller dependencies. The old source physics audit is missing; its previously published copy is retained and explicitly recorded in the asset manifest.

All 4,860 resource hashes and JavaScript syntax checks, five map dependency graphs, and 4,861 HTTP resource checks passed. The isolated .NET build passed with zero warnings and errors. Imported assets total 999,085,314 bytes. Interactive 3D browser behavior was not rechecked for this refresh.

### Eyrie and bilingual refresh — 2026-09-09

Imported the latest Eyrie geometry, scene assets and runtime changes, together with the bilingual catalogue, content and interface resources. All 1,745 resource hashes, JavaScript syntax checks, five map dependency graphs and 1,746 HTTP resource checks passed. The isolated .NET build passed with zero warnings or errors. Interactive browser behavior was not rechecked for this refresh.

### Terrain, rivers and Eyrie refresh — 2026-09-08

Imported updated terrain tiles, contours, atlas data and map scripts, plus viewport-loaded river detail and the Eyrie scene, materials, motion, walking controls and navigation. The importer includes hydrology JavaScript blocks and the scene's browser dependencies.

The source `eyrie-assets/geometry.js` exceeds the Git file size limit. The importer converts it into seven scripts of at most 32 MiB and adapts the Eyrie controller to await them in order. All 789 geometry entries were compared with the source and are identical; the manifest records the source file hash for each generated part. The source directory is unchanged.

All 1,741 asset hashes, JavaScript syntax checks, five map dependency graphs and 1,742 HTTP resource checks passed, including the Razor and legacy entry points. The isolated .NET build passed with zero warnings or errors. Browser rendering and interactive behavior were not rechecked for this refresh.

### Colonization research refresh — 2026-09-07

Imported the updated map entry and space controller with the source colonization UI, renderer, model, input data, star catalogue, provenance, sensitivity results and Federation registry. The importer now includes these dependencies, and verification checks the UI's dynamically loaded scripts as well as the space controller's scripts.

All 1,600 asset hashes, JavaScript syntax checks, five map dependency graphs and 1,601 HTTP resource checks passed, including the Razor and legacy entry points. The isolated .NET build passed with no warnings or errors. Interactive browser behavior was not rechecked for this refresh.

### Living atlas refresh — 2026-09-07

The subsequent refresh includes settlement-display.js, revised living and astronomy data, and Federation documentation. All 1,587 resource hashes and 1,588 HTTP resource checks passed. The reader suite passed across five geographic views; both system and Federation views reached ready state without page errors. The isolated .NET build passed with no warnings or errors.

Imported the latest living overlay and its JSON/JavaScript data alongside the updated map and space controllers. The importer supports the source's world-living export names while retaining the website's existing download adaptations. Verified 1,585 resource hashes, 1,586 HTTP resources, all five map views, and a browser world view exposing 243 community sites and 26 routes without JavaScript errors. The isolated .NET build passed with no warnings or errors.

Use an isolated .NET artifacts directory for the build, because the starting commit tracks historical `bin` and `obj` files. Do not include generated artifact changes in this feature.
Serve the application with its repository content root and verify `/Archeon`, the old map URL, and all five atlas views.
Check search, detail links, layers, scenic mode, zoom/pan, terrain and contour loading, error retry, JSON downloads, and a 390 px mobile viewport.
Browser map requests must be local, with no missing assets or JavaScript errors.

Run `node scripts/verify-archeon-atlas.cjs http://127.0.0.1:5276` against the preview server to check hashes, JavaScript syntax, tile/contour references, HTTP responses, and the Razor/legacy entry points.

### Terrain refresh verified on 2026-09-07

- Imported the finished source revision `2026-09-07 naturalized valleys and bounded contour generalization`, including terrain imagery, tiles, contours, river geometry and geographic data.
- All 1,563 imported resources match the source SHA-256 hashes after the documented web adaptations; five map dependency graphs and 1,564 HTTP resource checks passed.
- Isolated .NET build passed with 0 warnings and 0 errors; `/Archeon` and the legacy map entry passed HTTP verification.
- Parsed geography comparison confirms routes, settlements, coastlines, lakes and other existing non-river sections are unchanged. Rivers and tributaries retain their counts; the source adds terrain-naturalization metadata. The smaller JSON is minified upstream.
- The source retains three documented pre-existing hydrology connection exceptions; this refresh preserves the source data.
- The interaction checks below describe the earlier integration verification; this refresh rechecked asset integrity, references, syntax, build and HTTP delivery.

### Initial integration verified on 2026-09-06

- .NET build: 0 warnings, 0 errors; artifacts directed to a temporary directory.
- Asset verification: 1,563 hashes and 1,564 HTTP resource checks passed; no missing tile or contour references.
- In-app browser: all five views rendered; Chinese search for 北境湖海 and English search for Atheria opened the correct details; Atheria's detail link opened its local map.
- Route visibility, scenic-mode restoration, zoom and drag panning passed. At 410% zoom, Aethelgard displayed 42 loaded terrain tiles and 28 detailed contour blocks.
- At 390 × 844, page width remained 390 px; mobile layers could be expanded and collapsed.
- The legacy URL redirected to the new atlas, the help page returned to the map, and the main browser tab reported no warnings or errors.
- A temporary localhost QA proxy deliberately returned HTTP 503 for the first Rimstone map request. The error message appeared and “重新展开” successfully loaded Rimstone on retry. The proxy is not part of the website.
