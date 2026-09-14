# Orun loam appearance — 2026-09-13

The user's screenshot is the new pigment-weight baseline: sand gold 2.55, pale silt 2.10, warm grey brown 1.00, ochre 2.00, flax loam 0.45, rose grey 1.00, mauve grey 1.00, cool blue grey 1.55. Original rock mode remains the default. Existing browser drafts are retained.

The terracotta family now uses muted flax tones (#B4A17D, #C2B08B, #A49476, #BAA884). Its persisted parameter key remains `terracottaAmount`, so exported parameters and saved drafts still load. Pale sediment, warm grey brown, ochre and exposed oxide tones are adjusted to complement it. The special high-elevation terracotta bonus is removed and the weathered-parent pigment preference is balanced toward sand and grey brown.

Both rock modes receive the same bounded wet-soil finish over their bare fraction. Existing moisture and retained surface materials determine the finish; dry ground and fresh exposed rock receive none. The finish mixes #95866A toward #6B6451 as moisture increases. It is an appearance treatment, not a new nutrient, organic-carbon or soil-chemistry simulation. Plant and water weights are not tinted or recalculated.

The finish is applied after the existing six-coefficient material integration. The stored terrain, hydrology, pigment basis and ecological integration arrays remain valid. No additional full-map arrays or shader attributes are required. The CPU output and GPU palette reconstruction agree in the check.

## Validation

- 81 sites: existing ecology weights identical, nonnegative coverage with total no greater than one; dry ground and bare bedrock do not receive wet-soil finish.
- 148,168 fixture vertices across both rock modes: positions, normals, indices and canopy unchanged from the archived previous implementation; colour attributes finite.
- Final evolved terrain SHA256: `8f9d9db64626054cc4b9f2ec01b75d71de6de3d875cabe386d943ea2a8778fbe`.
- Physical water SHA256: `4efeedad739b90492cdab7a0604d87dcf56c831b63f7a5f8759305468e2f89e9`.
- Existing control/cancellation/order/cloud checks: six groups passed.
- Precomputed startup check: climate, terrain, hydrology and material data do not recompute.
- Showheel atlas: 4,606 resource hashes and five geographic dependency graphs passed; 4,603 imported resources unchanged in this update.
- Compressed output: 3,144 packed and 1,590 copied resources, 10 pages, decoded source and reader hashes verified.

## Local delivery

Canonical compressed directory: `D:/SKBS/review/orun-loam-20260913/compressed`.
Size: **916,527,689 bytes**. Target: 950,000,000 bytes; hard cap: 1,000,000,000 bytes. Increase from previous package: 901 bytes. This is disk/package size, not browser RAM.

Source preview: http://127.0.0.1:8780/?version=loam-v1#view=orun&focus=weeps

Compressed preview: http://127.0.0.1:8781/archeon-atlas/#view=orun&focus=weeps

The existing compressed preview directory retains old packed files for already-open clients. Its disk total is not the package total; use the canonical clean directory for delivery.

Previous source modules and metadata are retained under `D:/SKBS/archives/pending-manual-delete-20260913/orun-before-loam`. Physical assets remain in their existing active locations. Chinese Timelapse is synchronized byte-for-byte to Showheel; the English manuscript is preserved. No GitHub push or production deployment was performed.
