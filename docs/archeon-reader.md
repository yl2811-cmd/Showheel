# Embedded atlas and bilingual reader

`/Archeon` keeps the cover, navigation and city background. Its former media grid is now a full-width iframe containing the existing atlas; the image wall is replaced by an independently scrolling reader. Switching reader languages does not navigate or reload the map.

The Chinese manuscript is a byte-for-byte snapshot of `D:/SKBS/timelapse-skies_beyond_the_star.txt`, including worldbuilding and story sections. The English manuscript remains unchanged. Source/previous Chinese/English hashes and dependency provenance are recorded in `archeon-reader-content.json`. No images or source manuscript files were deleted.

The reader and both standalone reader URLs share `story-reader.js` and `story-reader.css`. Chinese is the default on Archeon; the standalone English URL defaults to English. Each language retains its scroll offset for the current page session. A generation counter rejects stale responses, successful renderings are cached, and failed requests can be retried.

Marked 18.0.11 and DOMPurify 3.4.15 are vendored with licenses. npm tarballs were checked against their SHA-512 integrity values before extracting browser bundles. Markdown uses GFM and line breaks; HTML is sanitized before insertion. Only the render input adapts equals-delimited chapter headings, leaving the source bytes and fenced code intact.

## Visual Studio

Use the existing `Showheel` startup project and launch profile, then navigate to `/Archeon`. No project, launch-profile or deployment configuration changes are needed. Existing `bin/obj` changes from local development are excluded from the feature commit.

## Verification — 2026-09-06

- .NET build succeeded with 0 warnings and 0 errors using a temporary artifacts directory.
- Background Chromium tests passed for all five embedded map views, full Chinese ending, both language defaults, independent scroll restoration, keyboard PageDown, and unchanged iframe loading count during language switches.
- The 390 × 844 mobile viewport had no page overflow; desktop/mobile screenshots were inspected.
- Both existing standalone URLs work. A mocked 503 was recoverable; a delayed Chinese request did not overwrite a later English selection.
- Markdown fixtures verified tables, fenced code, adapted headings and sanitization of scripts, event handlers and JavaScript links. No page errors or missing local resources were reported on the real content pages.

Run `node scripts/verify-archeon-reader.cjs http://127.0.0.1:5280` against a running preview. The script uses `playwright`, or the module path supplied in `PLAYWRIGHT_MODULE`; `CHROME_PATH` optionally selects an installed Chromium executable. Screenshots and verification JSON default to the temporary `showheel-reader-qa` directory, overridable by `READER_QA_OUTPUT`.
