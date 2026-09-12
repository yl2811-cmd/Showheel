# 06 · Character

The home page and Archeon page now link to /Character, presenting Anna Freedman, Lia Redwood and Kassia Ashcroft with the current artwork, approximate height and weight, and age at the start of the main story. Each introduction has three Chinese paragraphs and a matching English version. Major plot outcomes are omitted.

Chinese is the initial language. The page remembers a language selection when browser storage is available, preserves the nearest visible reading block during a switch, and leaves all Chinese prose accessible without JavaScript. Portraits retain their full aspect ratios. The existing shared layout accepts a per-page HTML language and otherwise remains English.

## Content boundaries

- Anna: 19, approximately 168 cm / 58 kg; Lia: 14, approximately 149 cm / 44 kg; Kassia: 21, approximately 172 cm / 60 kg.
- Kassia Ashcroft is the full name requested for this website page. No additional birthplace or family history was introduced into the source manuscript.
- Chinese Timelapse is byte-identical to the current D:/SKBS source (814837 bytes). The English long manuscript is unchanged.
- Existing artwork was reused. Lossless WebP copies are produced by the established build; source PNGs remain intact.

## Verification

- Static export and integrity checks passed: 10 pages and 4635 assets, including /Character routing and image names containing spaces.
- Eleven browser checks passed on the final compressed output: entry links, both languages and facts, persistence, reading position, keyboard focus, 390/320 px mobile layout, image aspect ratios, no-script reading and unavailable storage. No page errors or failed local resources.
- The source manuscript, 3D asset contents and English reader content were preserved. See verification.json for exact hashes and image sizes.

Run scripts/build-web.cjs with a new --output directory and --report path, then scripts/verify-web.cjs with the source root, output directory and report. Serve the output with scripts/serve-web.cjs. Run scripts/verify-character.cjs with the local base URL and a screenshot output directory; it supports the same PLAYWRIGHT_MODULE and CHROME_PATH environment variables as the existing browser verifier.

## Publication

The requested destination is the current codex/archeon-atlas branch. The update archive includes changed source files, the compressed character assets/pages, and the synchronized Chinese manuscript as a scoped overlay for the existing site.

The full generated site is 543.99 MB. The local report has no confirmed Azure quota and exceeds its default 225 MB budget; the budget check does not pass. A GitHub branch push is not a confirmed website deployment. The checked workflow triggers on main or pull requests targeting main; deployment settings and main were not changed.
