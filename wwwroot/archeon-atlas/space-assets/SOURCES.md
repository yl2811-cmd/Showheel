# Astronomy assets and provenance

The HYG 4.1 catalogue is by **David Nash / Astronexus**, adapted here under **CC BY-SA 4.0**. Its upstream combines Hipparcos, Yale Bright Star and Gliese data; see [upstream field documentation](source/HYG-DATA-README.md) and [licence](source/HYG-LICENSE.md). The frozen source CSV is retained locally.

- Commit: `c7f7f883fe678cc7680169a50ccd7dcc49b060ce`.
- Source SHA256: `d9f69fd86bbf90a4e4d52b4c5c53eacfa6dfc0bfdef85bfd94f095e0bebe4ebd`.
- Fixed source: https://raw.githubusercontent.com/astronexus/HYG-Database/c7f7f883fe678cc7680169a50ccd7dcc49b060ce/hyg/CURRENT/hygdata_v41.csv
- Adaptation: retain 0 < distance ≤ 600 ly; convert parsecs to light-years; encode Cartesian position, absolute magnitude and B−V colour as little-endian float32; keep names/identifiers for search.
- 51833 source records pass the distance filter. Remove HIP 27989 from the real-star renderer because the story supplies exactly one Betelgeuse node at its canonical 531 ly. 51832 catalogue points remain. Sol is a separate scene origin.
- Epoch/equinox remains J2000.0. The two story dates do not simulate stellar proper motion. The catalogue is incomplete; 600 ly is a viewing limit, never a political sphere.
- Missing B−V defaults to 0.65 for display only (1224 records). Every displayed record retains its HYG identifier.
- The CC BY-SA terms apply to the adapted catalogue in data/stars-hyg41.js as well. Fictional node data, prose and original map artwork have separate authorship and are not relicensed by this notice.

## Fictional placement

The Earth–Archeon–Betelgeuse triangle is solved from 530 / 531 / 10 ly. The Betelgeuse direction comes from HYG. The Archeon azimuth around that direction, colony sky positions, four numbered intermediate nodes, unspecified orbital angles and outer-planet size are declared cartographic assumptions. Fixed distances and documented phases/populations remain separate.

Historical event time, local first-light time and carried knowledge are separate data fields. The 3094 Archeon status is what Federation can know; the geographic atlas gives the author's contemporary surface view. A 2 ly luminous remnant does not imply a 2 ly lethal sphere or a 15 ly physical cloud.

## Rebuilding

Run `node src/build-space-data.cjs` using the frozen source files, then `node src/build-space-textures.cjs`. Both commands only write new astronomy assets and QA. The texture builder samples original world-surface.rgba through the current D3 Equal Earth projection, then writes a 4096 × 2048 equirectangular image and a data URL. It never stretches the atlas export or changes geographic data.

Numerical checks are in qa/space-data-audit.json. They are geometry and two-body sanity checks, not a complete physical simulation.

## Host stars, visual photometry and terraform visits

Every fictional colony now has a separate hostStar and terraformPlanet. The host is the luminous object at the existing system coordinate; the colony ring is an annotation. The real HYG point cloud is unchanged. The eight additional FGK hosts, planets and their procedural surfaces are explicitly inferred additions, not actual exoplanet detections. Archeon keeps its accepted primary, geography and moons.

Absolute magnitude and colour come from the retained HYG V / B−V fields for real stars. The renderer must calculate the apparent magnitude from the moving camera distance, so nearby red dwarfs can fade at distance while intrinsically luminous giants remain visible much farther away. The example display limit of V=12 is an exposure choice, not the naked-eye threshold.

Sol uses the NASA Sun Fact Sheet reference M_V=4.83 and T_eff=5772K with B−V rounded to 0.65; the original HYG values 4.85 and 0.656 remain in catalogReference. NASA source: https://nssdc.gsfc.nasa.gov/planetary/factsheet/sunfact.html

The original HYG HIP27989 record gives Betelgeuse M_V=-5.469 and B−V=1.5. Its fixed novel distance is still 531 ly. This photometry is a **precursor reference**; it must not resurrect the star after the 2563 collapse in a simultaneous historical view. HYG visual luminosity is not bolometric luminosity. The supplied precursor mass, radius and temperature are individually marked model assumptions.

Fictional host bolometric luminosity is derived from the assumed radius and temperature by L/L_sun=(R/R_sun)^2 (T/5772)^4. The V-band magnitude uses an explicit approximate bolometric correction. These values support consistent display, not a verified atmospheric or climate model. The terraform radii, orbital radii, day lengths, terrain, cloud and ocean fractions are working illustrations. Core gravity values retain the manuscript; intermediate gravity is explicitly inferred. Planet periods satisfy the two-body Kepler relation.

## Nearby nebulae

Four sourced nearby cloud entries are now included: Pleiades reflection dust, Taurus L1495, Rho Ophiuchi and the in-range portion of Coalsack. Positions, distance choices, infrared-versus-optical limits and the inferred three-dimensional shapes are documented in [NEBULAE.md](NEBULAE.md). Betelgeuse remains the separate canonical remnant.
