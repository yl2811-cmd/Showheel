# Reproduce this local terrain study

The accepted terrain in `maps/archeon-atlas/terrain` is read-only input. The original terrain files are deliberately not duplicated here. The model checks the input height fingerprint before running.

Use Python 3.12 with numpy 2.5.3, scipy 1.18.1, rasterio 1.5.1, pyproj 3.8.0, numba 0.67.0, Pillow 12.3.0. Task-isolated dependencies are currently under `review/foundation-20260914/deps`.

1. Preserve `seeds/frozen-geography.json` as `review/foundation-20260914/geography.json`.
2. Run `src/foundation-prepare.py`, `src/foundation-references.py`, `src/foundation-satellite.py`.
3. Run `src/foundation-model.py`, then `src/foundation-export.py`.
4. Run `node src/foundation-world.cjs`.
5. Run `review/foundation-20260914/verify-numerical.py`, then `write-findings.py` and `browser-check.cjs`.

The six AI inputs are already saved in `foundation/seeds`; image generation is not rerun during the build. Reproducibility uses these saved bytes and seed 5210914. Full downloaded radar tiles stay under review/references; the compact numerical samples and 3DEP clips are delivered with the seeds.

No build step mutates the formal terrain, named settlement data, routes or manuscript. Full aeolian, glacial, stratigraphic and mantle simulation are NOT implemented in this pilot. The shipped water/sediment component is a custom finite-volume prototype, not the Landlab SPACE implementation.
