/*!
 * Showheel — vfx-reel.js
 * Plays the clips of a [data-vfx-reel] back to back on a loop. Two stacked <video> elements take
 * turns: while one plays, the other buffers the next clip, then they crossfade on "ended".
 *
 * MARKUP CONTRACT (styles in sections.css, "VFX: looping clip reel")
 *   .vfx-reel-video ×2        The first one carries the opening clip's src and .is-active.
 *   button[data-reel-clip]    One per clip, in play order; clicking jumps to that clip.
 *     .vfx-reel-bar > i       Progress bar (scaleX 0 → 1).  .vfx-reel-name  "01 · Title".
 *   [data-reel-play]          Pause / Play.     [data-reel-sound]  Unmute / Mute.
 *   [data-reel-count] [data-reel-title]   HUD readout of the current clip.
 * Pauses while offscreen or in a background tab; starts paused with prefers-reduced-motion.
 */
(() => {
    'use strict';

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const pad2 = (n) => String(n).padStart(2, '0');
    const FADE_MS = 450; // matches the .vfx-reel-video opacity transition

    document.querySelectorAll('[data-vfx-reel]').forEach((reel) => {
        const videos = Array.from(reel.querySelectorAll('.vfx-reel-video'));
        const clips = Array.from(reel.querySelectorAll('[data-reel-clip]'));
        const bars = clips.map((btn) => btn.querySelector('.vfx-reel-bar i'));
        const playBtn = reel.querySelector('[data-reel-play]');
        const soundBtn = reel.querySelector('[data-reel-sound]');
        const countEl = reel.querySelector('[data-reel-count]');
        const titleEl = reel.querySelector('[data-reel-title]');
        if (videos.length < 2 || !clips.length) return;

        let index = 0;
        let active = videos.find((v) => v.classList.contains('is-active')) || videos[0];
        let userPaused = reduceMotion;
        let onScreen = !('IntersectionObserver' in window);
        let frame = 0;
        let switchId = 0; // a newer switch cancels a pending one

        const other = () => videos.find((v) => v !== active);
        const titleOf = (i) => clips[i].querySelector('.vfx-reel-name').textContent.replace(/^\d+\s*·\s*/, '');

        const load = (video, i) => {
            const url = new URL(clips[i].dataset.reelClip, location.href).href;
            if (video.src !== url) {
                video.src = url;
                video.load();
            }
        };

        const whenReady = (video) => new Promise((resolve) => {
            if (video.readyState >= 3) resolve();
            else video.addEventListener('canplay', resolve, { once: true });
        });

        const paintProgress = () => {
            const t = active.duration ? active.currentTime / active.duration : 0;
            bars.forEach((bar, i) => {
                const p = i < index ? 1 : i > index ? 0 : t;
                bar.style.transform = `scaleX(${Math.min(1, Math.max(0, p))})`;
            });
        };

        const tick = () => {
            paintProgress();
            frame = active.paused ? 0 : requestAnimationFrame(tick);
        };

        const render = () => {
            reel.classList.toggle('is-paused', userPaused);
            if (playBtn) playBtn.textContent = userPaused ? 'Play' : 'Pause';
            if (soundBtn) soundBtn.textContent = active.muted ? 'Unmute' : 'Mute';
            clips.forEach((btn, i) => {
                if (i === index) btn.setAttribute('aria-current', 'true');
                else btn.removeAttribute('aria-current');
            });
            if (countEl) countEl.textContent = pad2(index + 1);
            if (titleEl) titleEl.textContent = titleOf(index);
            paintProgress();
        };

        const sync = () => {
            if (!userPaused && onScreen && !document.hidden) {
                const p = active.play();
                // Autoplay refused (e.g. data saver): fall back to a paused reel with a Play button.
                if (p && p.catch) p.catch(() => { userPaused = true; render(); });
            } else {
                active.pause();
            }
            render();
        };

        const show = async (i) => {
            const id = ++switchId;
            const next = other();
            load(next, i);
            await whenReady(next);
            if (id !== switchId) return;

            const prev = active;
            next.currentTime = 0;
            active = next;
            index = i;
            next.classList.add('is-active');
            prev.classList.remove('is-active');
            sync();

            // After the crossfade, the idle element starts buffering the clip after this one.
            setTimeout(() => {
                if (id !== switchId) return;
                prev.pause();
                load(prev, (i + 1) % clips.length);
            }, FADE_MS);
        };

        videos.forEach((v) => {
            v.muted = true;
            v.addEventListener('ended', () => { if (v === active) show((index + 1) % clips.length); });
            v.addEventListener('play', () => { if (v === active && !frame) frame = requestAnimationFrame(tick); });
            v.addEventListener('timeupdate', () => { if (v === active && v.paused) paintProgress(); });
        });

        clips.forEach((btn, i) => {
            btn.addEventListener('click', () => {
                userPaused = false;
                if (i === index) {
                    active.currentTime = 0;
                    sync();
                } else {
                    show(i);
                }
            });
        });

        if (playBtn) {
            playBtn.addEventListener('click', () => {
                userPaused = !userPaused;
                sync();
            });
        }

        if (soundBtn) {
            soundBtn.addEventListener('click', () => {
                const muted = !active.muted;
                videos.forEach((v) => { v.muted = muted; });
                render();
            });
        }

        if (!onScreen) {
            new IntersectionObserver((entries) => {
                onScreen = entries[entries.length - 1].isIntersecting;
                sync();
            }, { threshold: 0.25 }).observe(reel);
        }
        document.addEventListener('visibilitychange', sync);

        load(other(), (index + 1) % clips.length);
        sync();
    });
})();
