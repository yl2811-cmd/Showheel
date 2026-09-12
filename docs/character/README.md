# 06 · Character in Archeon Atlas

Character is the sixth tab in the Atlas navigation row, immediately after 05 Federation. Clicking it replaces the map content area with Anna Freedman, Lia Redwood and Kassia Ashcroft. The Atlas header and six tabs remain visible. The misplaced home card and above-map link were removed.

The portraits, three Chinese paragraphs per character, English prose and approximate measurements are shared with /Character. The Atlas panel loads that existing page once and mounts only its character content, without another iframe or duplicated biographies. Character content is excluded from the atlas automatic translation pass; the shared component follows the Atlas language selection in both directions and preserves the current reading block.

The panel uses the Atlas paper and dark-green palette, hides map-only controls while active, retains its scroll position on reopening, and releases star/3D scene resources through the existing navigation lifecycle. All original geography and astronomy tabs remain available. Direct link: /archeon-atlas/index.html#view=character.

## Import ownership

scripts/atlas-character-adapter.cjs adds the website tab and navigation handling to fresh source exports. scripts/atlas-character contains the website-owned panel assets. The importer includes these in the asset manifest, and the verifier checks their shared character CSS/JavaScript dependencies. The authoring atlas source and all manuscript prose remain unchanged.

An isolated full source import reproduced the four Character integration files byte-for-byte. Its separate source-model validation found 11 Eyrie bundle hashes inconsistent with the source detail manifest. These unrelated source changes were not imported into the live checkout. The website's existing map assets passed verification. Details are preserved in atlas-tab-verification.json.

## Verification and publication

- Seven integrated browser checks passed, including the exact tab order/location, synchronized languages, reading position, all five existing tab types, rapid transitions, mobile layout and retry after a failed content request. No page errors or failed local resources.
- Eleven shared-reader checks passed, including character facts, complete image proportions, 320/390 px widths, keyboard operation and no-script reading.
- Website atlas verification passed for 4,509 files. Static build and compressed delivery checks passed for 10 pages and 4637 resources.
- Chinese Timelapse remains byte-identical to D:/SKBS; the English long manuscript is unchanged.
- Compressed full-site output is 543.02 MB. The local build has no confirmed Azure quota and exceeds its default 225 MB budget. No hosting settings are changed.

Run scripts/verify-character-atlas.cjs with a preview base URL and screenshot directory to check the embedded tab; scripts/verify-character.cjs checks the shared standalone reader. Both accept PLAYWRIGHT_MODULE and CHROME_PATH as in the existing browser checks. Source and compressed-overlay updates are archived under docs/updates. The earlier verification.json records the original standalone layout; atlas-tab-verification.json records this corrected placement.
