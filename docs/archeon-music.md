# Archeon cover, reading width and soundtrack

The cover uses `images/anna1.png` at its original 1875:664 aspect ratio, with no parallax enlargement or cropping, so all four panels remain visible. Archeon prose now fills the reader with responsive side margins; standalone readers retain their narrower width.

The fixed upper-right soundtrack controls play `images/archeonvibe1.mp3` through `archeonvibe9.mp3` in order. These ten media files were copied without modification from `origin/main` at `0fe2b77e540d44717c24508e83a465c70c4162f5`.

Entering Archeon attempts audible playback of track 1. Browser autoplay restrictions are respected: when blocked, the control displays Play and a subsequent user interaction can start playback. Explicit pauses are never overridden by later general page interactions.

Natural completion waits 10 seconds before the next track; track 9 wraps to track 1. Previous/next buttons switch immediately and start playback, including from a paused state. Pausing during the gap freezes its remaining time; resuming finishes that remaining gap. Playback errors stop progression and allow retry or manual skipping. Page exit cancels timers and pauses audio.

Only Archeon receives the extra navigation spacing. At narrow widths, navigation sits below the music controls so the player does not cover the reader's language buttons.

## Verification — 2026-09-06

- .NET build succeeded with 0 warnings/errors; Visual Studio launch settings were not changed.
- `node scripts/verify-archeon-music.cjs`: deterministic tests cover 10-second timing, paused gaps, manual skips, both wrap directions, autoplay rejection/recovery, stale play promises and timer cleanup.
- `node scripts/verify-archeon-music-browser.cjs [base-url]`: real background Chromium decoded and played all nine MP3s, verified an actual 10.003-second gap from track 9 to track 1, pause/previous controls, and autoplay-blocked recovery. No JavaScript errors occurred.
- At 1440 px viewport width, the prose text area measured approximately 1081 px. Desktop and 390 px mobile screenshots were inspected; the page has no horizontal overflow, and the desktop cover displays all four panels.
- Browser checks use `PLAYWRIGHT_MODULE`/`CHROME_PATH` when supplied and save screenshots and JSON to the temporary `showheel-music-qa` folder, or `MUSIC_QA_OUTPUT`. Chromium is headless and muted for verification.
