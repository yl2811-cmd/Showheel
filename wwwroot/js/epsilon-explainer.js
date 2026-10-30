/*!
 * Showheel — epsilon-explainer.js
 * Animated explainers for the Epsilon boss AI (VibeCode, section #epsilon).
 * Vanilla JS, no dependencies. Each <figure data-ep="NAME"> is set up by the matching
 * init function below.
 *
 * - Animations run only while their figure is on screen (IntersectionObserver) and the
 *   tab is visible.
 * - With prefers-reduced-motion every figure draws a complete, static diagram instead;
 *   step buttons, "Replay" and the distance slider still work, without tweening.
 * - Every number used here comes from the mod sources in
 *   D:\w2\src\main\java\net\mcreator\jujutukaisencheat (see the comment above each
 *   explainer and the "Source" line under each figure). Scenery (walls, positions) is
 *   made up for illustration; the rules applied to it are the mod's.
 */
(() => {
    'use strict';
    if (window.__epExplainerInit) return;
    window.__epExplainerInit = true;

    const NS = 'http://www.w3.org/2000/svg';
    const TAU = Math.PI * 2;
    const DEG = Math.PI / 180;
    const mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reduced = mqReduce.matches;

    const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
    const lerp = (a, b, t) => a + (b - a) * t;
    const smooth = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
    const fix = (v, d) => (Math.abs(v) < 0.5 * Math.pow(10, -d) ? 0 : v).toFixed(d);

    function svgEl(tag, attrs, parent) {
        const n = document.createElementNS(NS, tag);
        if (attrs) setAttrs(n, attrs);
        if (parent) parent.appendChild(n);
        return n;
    }
    function setAttrs(n, attrs) {
        for (const k in attrs) {
            const v = attrs[k];
            if (v === null || v === undefined) n.removeAttribute(k);
            else n.setAttribute(k, v);
        }
        return n;
    }
    function text(parent, x, y, str, cls, extra) {
        const t = svgEl('text', Object.assign({ x, y, class: cls || 't-label' }, extra || {}), parent);
        t.textContent = str;
        return t;
    }
    function show(n, on) { n.style.display = on ? '' : 'none'; }
    // Small seeded PRNG so "random" scenery is reproducible.
    function rng(seed) {
        let a = seed >>> 0;
        return () => {
            a = (a + 0x6D2B79F5) >>> 0;
            let t = a;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }
    // Arrow helper: a line plus a filled head, updated in place.
    function makeArrow(parent, cls, headCls) {
        const g = svgEl('g', null, parent);
        const line = svgEl('line', { class: cls }, g);
        const head = svgEl('polygon', { class: headCls || '' }, g);
        return {
            g,
            set(x1, y1, x2, y2, size) {
                const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy);
                if (len < 1) { show(g, false); return; }
                show(g, true);
                const ux = dx / len, uy = dy / len, s = size || 9;
                const bx = x2 - ux * s, by = y2 - uy * s;
                setAttrs(line, { x1, y1, x2: bx, y2: by });
                setAttrs(head, { points: `${x2},${y2} ${bx - uy * s * 0.55},${by + ux * s * 0.55} ${bx + uy * s * 0.55},${by - ux * s * 0.55}` });
            },
            hide() { show(g, false); },
        };
    }
    function diamond(parent, cls, r) {
        return svgEl('polygon', { class: cls, points: `0,${-r} ${r},0 0,${r} ${-r},0` }, parent);
    }
    // Segment / axis-aligned rectangle intersection: returns the entry distance t (0..1) or null.
    function segRect(x1, y1, x2, y2, r) {
        let t0 = 0, t1 = 1;
        const dx = x2 - x1, dy = y2 - y1;
        const p = [-dx, dx, -dy, dy];
        const q = [x1 - r.x, r.x + r.w - x1, y1 - r.y, r.y + r.h - y1];
        for (let i = 0; i < 4; i++) {
            if (p[i] === 0) { if (q[i] < 0) return null; continue; }
            const t = q[i] / p[i];
            if (p[i] < 0) { if (t > t1) return null; if (t > t0) t0 = t; }
            else { if (t < t0) return null; if (t < t1) t1 = t; }
        }
        return t0;
    }
    function rectEls(parent, rects, cls) {
        rects.forEach((r) => svgEl('rect', { x: r.x, y: r.y, width: r.w, height: r.h, rx: 3, class: cls || 'p-rock' }, parent));
    }

    /* ─── Runner: play while visible, static under reduced motion ───────────── */

    const runners = [];
    function register(fig, api) {
        const r = { fig, api, visible: false, running: false, last: 0, raf: 0 };
        runners.push(r);
        if (reduced) api.still();
        else if (api.frame) api.frame(0);
        return r;
    }
    function tickRunner(r, ts) {
        if (!r.running) return;
        const dt = r.last ? Math.min(0.1, (ts - r.last) / 1000) : 0;
        r.last = ts;
        try {
            r.api.frame(dt);
        } catch (err) {
            console.error('[epsilon-explainer] ' + (r.fig.dataset.ep || '?') + ' frame failed', err);
            stopRunner(r);
            return;
        }
        r.raf = requestAnimationFrame((t) => tickRunner(r, t));
    }
    function startRunner(r) {
        if (r.running || reduced || document.hidden || !r.visible || !r.api.frame) return;
        r.running = true;
        r.last = 0;
        r.raf = requestAnimationFrame((t) => tickRunner(r, t));
    }
    function stopRunner(r) {
        r.running = false;
        cancelAnimationFrame(r.raf);
    }

    function wireRunners() {
        if ('IntersectionObserver' in window) {
            const io = new IntersectionObserver((entries) => {
                entries.forEach((e) => {
                    const r = runners.find((x) => x.fig === e.target);
                    if (!r) return;
                    r.visible = e.isIntersecting;
                    if (r.visible) startRunner(r); else stopRunner(r);
                });
            }, { rootMargin: '80px 0px', threshold: 0.05 });
            runners.forEach((r) => io.observe(r.fig));
        } else {
            runners.forEach((r) => { r.visible = true; startRunner(r); });
        }
        document.addEventListener('visibilitychange', () => {
            runners.forEach((r) => (document.hidden ? stopRunner(r) : startRunner(r)));
        });
        const onReduce = () => {
            reduced = mqReduce.matches;
            runners.forEach((r) => {
                if (reduced) { stopRunner(r); r.api.still(); }
                else { if (r.api.resume) r.api.resume(); startRunner(r); }
            });
        };
        if (mqReduce.addEventListener) mqReduce.addEventListener('change', onReduce);
        else if (mqReduce.addListener) mqReduce.addListener(onReduce);
    }

    /* Generic timeline explainer: render(t) for t in [0, duration]; loops. */
    function timeline(fig, duration, render, opts) {
        let t = 0;
        const api = {
            frame(dt) {
                t += dt;
                if (t > duration) { t = 0; if (opts && opts.onLoop) opts.onLoop(); }
                render(t, false);
            },
            still() { render(duration, true); },
            resume() { t = 0; },
            replay() {
                if (opts && opts.onLoop) opts.onLoop();
                t = 0;
                if (reduced) render(duration, true); else render(0, false);
            },
        };
        const btn = fig.querySelector('[data-ep-replay]');
        if (btn) btn.addEventListener('click', () => api.replay());
        return api;
    }

    /* ─── 01 · One tick, in order ─────────────────────────────────────────────
       Demo2Procedure.execute, lines 114–231: counters/effects → CommonenemylockProcedure (167)
       → DamageThreatUtil.refreshProjectileThreats (170) → CommontargetProcedure (173)
       → CommonskillProcedure (217) → CommonflashProcedure (224, only while stunlevelfly < 30)
       → updateFlyscoreKickoff (231; 5-tick burst, 110-tick cooldown, lines 69–71). */
    function initTick(fig, opts) {
        const items = Array.from(fig.querySelectorAll('.ep-tick-list li'));
        const counter = fig.querySelector('[data-ep-tickno]');
        const STEP = (opts && opts.step) || 0.5;
        const PAUSE = (opts && opts.pause) || 0.6;
        const label = (opts && opts.label) || ((n, cycle) => 'tick ' + n + ' · slowed ×' + Math.round(cycle * 20));
        const cycle = items.length * STEP + PAUSE;
        let t = 0;
        let tickNo = 1;
        const mark = (i) => items.forEach((li, k) => li.classList.toggle('is-active', k === i));
        return {
            frame(dt) {
                t += dt;
                if (t >= cycle) { t -= cycle; tickNo += 1; }
                const i = Math.floor(t / STEP);
                mark(i < items.length ? i : -1);
                if (counter) counter.textContent = label(tickNo, cycle);
            },
            still() { mark(-1); if (counter) counter.textContent = ''; },
        };
    }

    /* ─── 02 · How far it wants to be ─────────────────────────────────────────
       CommonflashProcedure:
         hold distance ("orbit" block, 556–577): push = clamp((d − 24) / 6 × 0.03, ±0.12) ×
           horizontalRangeStrength(d) (1094–1096: clamp(0.1 + (40 − d) / 24 × 0.9, 0.1, 1));
           d < 12 → fixed −0.1. Positive = toward the target. Only while d < 64 (434) and not
           while a far flashdrive owns flight (662–663).
         near flashdrive: strength 1 at ≤ 12 m → 0 at 28 m (54–55, 3115–3122); goal distance
           clamp(d + 12, 14, 32) (60–62, 3579–3585), with line of sight (3494–3501).
         far flashdrive chase: d > 62 m with clear sight (158, 431). */
    function initDistance(fig) {
        const s = fig.querySelector('svg');
        const range = fig.querySelector('[data-ep-range]');
        const autoBtn = fig.querySelector('[data-ep-auto]');
        const read = {};
        fig.querySelectorAll('[data-ep-readout] > div').forEach((d) => { read[d.dataset.r] = { box: d, dd: d.querySelector('dd') }; });

        const X0 = 50, PX = 7, AY = 118;
        const x = (d) => X0 + d * PX;
        const defs = svgEl('defs', null, s);
        const grad = svgEl('linearGradient', { id: 'ep-near-grad', x1: '0', x2: '1', y1: '0', y2: '0' }, defs);
        svgEl('stop', { offset: '0', 'stop-color': '#ffb02e', 'stop-opacity': '0.55' }, grad);
        svgEl('stop', { offset: String(12 / 28), 'stop-color': '#ffb02e', 'stop-opacity': '0.55' }, grad);
        svgEl('stop', { offset: '1', 'stop-color': '#ffb02e', 'stop-opacity': '0' }, grad);

        // Bands
        svgEl('rect', { x: x(0), y: 46, width: 28 * PX, height: 16, rx: 3, fill: 'url(#ep-near-grad)' }, s);
        text(s, x(0), 38, 'near flashdrive ≤ 28 m', 't-small t-boss');
        svgEl('rect', { x: x(62), y: 46, width: 18 * PX, height: 16, rx: 3, class: 'p-ray-fill' }, s);
        text(s, x(80), 38, 'chase > 62 m', 't-small t-ray', { 'text-anchor': 'end' });
        // Hold point
        svgEl('line', { x1: x(24), y1: 70, x2: x(24), y2: 160, class: 'p-guide' }, s);
        text(s, x(24) + 6, 80, 'hold 24 m', 't-small', { 'text-anchor': 'start' });
        // Axis + ticks
        svgEl('line', { x1: x(0), y1: AY, x2: x(80), y2: AY, class: 'p-axis' }, s);
        [0, 12, 24, 28, 62, 80].forEach((d) => {
            svgEl('line', { x1: x(d), y1: AY - 5, x2: x(d), y2: AY + 5, class: 'p-tick' }, s);
            text(s, x(d), 184, String(d), 't-small', { 'text-anchor': 'middle' });
        });
        // Target
        svgEl('circle', { cx: x(0), cy: AY, r: 13, class: 'p-target-ring' }, s);
        svgEl('circle', { cx: x(0), cy: AY, r: 7, class: 'p-target' }, s);
        text(s, x(0), AY - 20, 'target', 't-small', { 'text-anchor': 'middle' });

        // Dynamic layer
        const chase = makeArrow(s, 'p-ray', 'p-ray-head');
        chase.g.querySelector('polygon').setAttribute('fill', '#6fb1ff');
        const hold = makeArrow(s, 'p-boss-line', '');
        hold.g.querySelector('polygon').setAttribute('fill', '#ffb02e');
        const goalG = svgEl('g', null, s);
        svgEl('line', { x1: 0, y1: AY - 14, x2: 0, y2: AY + 14, stroke: '#ffb02e', 'stroke-width': 2, 'stroke-dasharray': '3 3' }, goalG);
        const goalText = text(goalG, 0, AY - 20, 'goal', 't-small t-boss', { 'text-anchor': 'middle' });
        const boss = svgEl('g', null, s);
        diamond(boss, 'p-boss', 10);
        text(boss, 0, 46, 'Epsilon', 't-small t-boss', { 'text-anchor': 'middle' });

        const rangeStrength = (d) => clamp(0.1 + (40 - d) / 24 * 0.9, 0.1, 1.0);
        const holdAccel = (d) => {
            if (d > 62) return null;          // a far flashdrive owns flight
            if (d < 12) return -0.1;
            return clamp((d - 24) / 6 * 0.03, -0.12, 0.12) * rangeStrength(d);
        };
        const nearStrength = (d) => (d <= 12 ? 1 : d >= 28 ? 0 : (28 - d) / 16);
        const nearGoal = (d) => clamp(d + 12, 14, 32);

        let d = 30;
        let auto = !reduced;
        let t = 0;
        function setRead(key, str, cls) {
            const r = read[key];
            if (!r) return;
            r.dd.textContent = str;
            r.box.classList.toggle('is-on', cls === 'on');
            r.box.classList.toggle('is-on-blue', cls === 'blue');
        }
        function render() {
            const bx = x(d);
            boss.setAttribute('transform', `translate(${bx},${AY})`);
            const a = holdAccel(d);
            if (a === null || Math.abs(a) < 0.0005) hold.hide();
            else {
                const len = Math.abs(a) / 0.12 * 80;
                const dir = a > 0 ? -1 : 1; // positive pulls toward the target (left)
                hold.set(bx, AY + 22, bx + dir * Math.max(len, 12), AY + 22, 8);
            }
            const ns = nearStrength(d);
            if (ns > 0) {
                show(goalG, true);
                goalG.setAttribute('transform', `translate(${x(nearGoal(d))},0)`);
                goalG.style.opacity = String(0.35 + 0.65 * ns);
                goalText.textContent = 'goal ' + Math.round(nearGoal(d)) + ' m';
            } else show(goalG, false);
            if (d > 62) chase.set(bx - 14, AY - 26, bx - 120, AY - 26, 9); else chase.hide();

            setRead('dist', Math.round(d) + ' m');
            if (a === null) setRead('hold', 'off (the chase has the controls)');
            else if (d < 12) setRead('hold', 'hard push out · 0.100', 'on');
            else if (Math.abs(a) < 0.0005) setRead('hold', 'balanced at 24 m', 'on');
            else setRead('hold', (a > 0 ? 'pull in · ' : 'push out · ') + fix(Math.abs(a), 3), 'on');
            if (ns > 0) setRead('near', Math.round(ns * 100) + '% · goal at ' + Math.round(nearGoal(d)) + ' m', 'on');
            else setRead('near', 'off');
            setRead('far', d > 62 ? 'on · up to 1.25 blocks/tick' : 'off', d > 62 ? 'blue' : '');
        }
        function setAuto(on) {
            auto = on && !reduced;
            if (autoBtn) {
                autoBtn.setAttribute('aria-pressed', auto ? 'true' : 'false');
                autoBtn.classList.toggle('is-active', auto);
            }
        }
        range.addEventListener('input', () => { setAuto(false); d = Number(range.value); render(); });
        if (autoBtn) {
            if (reduced) show(autoBtn, false);
            autoBtn.addEventListener('click', () => { setAuto(!auto); if (auto) t = Math.asin(clamp((d - 42) / 37, -1, 1)) / TAU * 16; });
        }
        setAuto(auto);
        render();
        return {
            frame(dt) {
                if (!auto) return;
                t += dt;
                d = 42 + 37 * Math.sin(TAU * t / 16);
                range.value = String(Math.round(d));
                render();
            },
            still() { setAuto(false); if (autoBtn) show(autoBtn, false); render(); },
            resume() { if (autoBtn) show(autoBtn, true); },
        };
    }

    /* ─── 03 · Flashdrive burst and detour ────────────────────────────────────
       CommonflashProcedure: FLASHDRIVE_SPEED_STEP 0.2, FLASHDRIVE_SPEED_CAP 1.25 (51–53);
       start sets flashdrive2 = 10, which counts down once per tick; the burst runs while it is
       ≥ 0 (724–725, 733, Demo2 139). If the straight route hits a solid within the lookahead
       (≤ 10 m, 5350–5357) it uses the second-brain path2 heading (709–721).
       CommontargetProcedure.runProbeBrain: 600 probes in a 3–30 m shell (29–31), sweep-clear only,
       ≥ 8 m from self, ≥ 12 m from the target, beyond 64 m only within 45° of the aim,
       +36 for line of sight (902–957). Speed: steerFlashdriveVelocity (3718–3752). */
    function initFlashdrive(fig) {
        const s = fig.querySelector('svg');
        const status = fig.querySelector('[data-ep-status]');
        const PX = 7;
        const B = { x: 84, y: 150 };
        const T = { x: B.x + 65 * PX, y: 150 };
        // A long wall just below Epsilon's line: a straight burst would scrape along it.
        const pillar = { x: 96, y: 152, w: 234, h: 160 };
        const BODY = 7; // half the body box, px (1 m)
        // Second-brain samples (golden-angle spiral, area-uniform radius 3..30 m)
        const wedge = svgEl('path', { class: 'p-ray-fill', d: '' }, s);
        const dotsG = svgEl('g', null, s);
        rectEls(s, [pillar]);
        wedge.style.opacity = '0.6';
        const N = 120, GA = Math.PI * (3 - Math.sqrt(5));
        const dots = [];
        let best = null;
        for (let i = 0; i < N; i++) {
            const u = (i + 0.5) / N;
            const rm = Math.sqrt(lerp(9, 900, (i * 37 % N + 0.5) / N));
            const ang = i * GA + u * 0.0001;
            const px = B.x + Math.cos(ang) * rm * PX, py = B.y + Math.sin(ang) * rm * PX;
            let a = Math.atan2(py - B.y, px - B.x);
            const inWedge = Math.abs(a) <= 45 * DEG;
            const insidePillar = px >= pillar.x - BODY && px <= pillar.x + pillar.w + BODY && py >= pillar.y - BODY && py <= pillar.y + pillar.h + BODY;
            const blocked = insidePillar || segRect(B.x, B.y, px, py, { x: pillar.x - BODY, y: pillar.y - BODY, w: pillar.w + 2 * BODY, h: pillar.h + 2 * BODY }) !== null;
            const ok = inWedge && !blocked && rm >= 8;
            const c = svgEl('circle', { cx: px.toFixed(1), cy: py.toFixed(1), r: ok ? 3.2 : 2.2, fill: ok ? '#6fb1ff' : 'rgba(255,255,255,0.22)' }, dotsG);
            dots.push({ c, ok, px, py, a, rm });
            // Illustrative pick: the clear candidate closest to the aim line, at least 20 m out.
            if (ok && rm >= 20 && (!best || Math.abs(a) < Math.abs(best.a))) best = { px, py, a, rm };
        }
        if (!best) best = dots.find((o) => o.ok) || { px: B.x + 150, py: B.y - 90, a: -0.54, rm: 25 };
        const wr = 30 * PX;
        wedge.setAttribute('d', `M${B.x},${B.y} L${B.x + Math.cos(-45 * DEG) * wr},${B.y + Math.sin(-45 * DEG) * wr} A${wr},${wr} 0 0 1 ${B.x + Math.cos(45 * DEG) * wr},${B.y + Math.sin(45 * DEG) * wr} Z`);
        const wedgeText = text(s, B.x + 160, B.y - 120, '45° of aim', 't-small t-ray');
        const bestRing = svgEl('circle', { cx: best.px, cy: best.py, r: 9, fill: 'none', stroke: '#ffb02e', 'stroke-width': 2.5 }, s);
        const bestText = text(s, best.px + 12, best.py - 10, 'clear spot', 't-small t-boss');

        // Target
        svgEl('circle', { cx: T.x, cy: T.y, r: 15, class: 'p-target-ring' }, s);
        svgEl('circle', { cx: T.x, cy: T.y, r: 8, class: 'p-target' }, s);
        text(s, T.x, T.y + 34, 'target · 65 m', 't-small', { 'text-anchor': 'middle' });

        // Fire line and lookahead
        const fireLine = svgEl('line', { x1: B.x, y1: B.y, x2: T.x - 16, y2: T.y, class: 'p-guide' }, s);
        const sweep = svgEl('rect', { x: B.x - BODY, y: B.y - BODY, width: 2 * BODY, height: 2 * BODY, rx: 2, class: 'p-danger-fill' }, s);
        const blockText = text(s, pillar.x + 8, pillar.y + 26, 'would scrape the wall', 't-small t-danger');
        // Heading and burst path
        const ux = (best.px - B.x) / Math.hypot(best.px - B.x, best.py - B.y);
        const uy = (best.py - B.y) / Math.hypot(best.px - B.x, best.py - B.y);
        const heading = makeArrow(s, 'p-boss-line', '');
        heading.g.querySelector('polygon').setAttribute('fill', '#ffb02e');
        const trail = svgEl('polyline', { class: 'p-boss-line', points: '' }, s);
        trail.style.opacity = '0.45';
        const ghost = svgEl('g', { transform: `translate(${B.x},${B.y})` }, s);
        diamond(ghost, 'p-boss', 9).style.opacity = '0.3';
        const boss = svgEl('g', null, s);
        diamond(boss, 'p-boss', 10);

        // Speed meter (speed per tick: +0.2 per tick up to the 1.25 cap; 11 ticks while 10 → 0)
        const speeds = [];
        for (let k = 0; k < 11; k++) speeds.push(Math.min(1.25, 0.2 * (k + 1)));
        const MX = 372, MY = 284, MW = 18, MG = 6, MH = 40;
        text(s, MX, MY - MH - 10, 'speed / tick', 't-small');
        const bars = speeds.map((v, k) => {
            const h = v / 1.25 * MH;
            svgEl('rect', { x: MX + k * (MW + MG), y: MY - h, width: MW, height: h, fill: 'rgba(255,255,255,0.08)' }, s);
            return svgEl('rect', { x: MX + k * (MW + MG), y: MY - h, width: MW, height: h, fill: '#ffb02e' }, s);
        });
        text(s, MX - 6, MY - 2, '0.2', 't-small', { 'text-anchor': 'end' });
        text(s, MX + 11 * (MW + MG) - 2, MY - MH - 10, '1.25 cap', 't-small t-boss', { 'text-anchor': 'end' });
        const cum = [0];
        speeds.forEach((v, k) => cum.push(cum[k] + v));

        const D = 7.2;
        const TICK = 0.2;
        function render(t, still) {
            const a = still ? 1 : smooth(t / 0.5);
            fireLine.style.opacity = String(a);
            // Lookahead: the body box slides ~2 m along the straight line and touches the wall.
            const sweepP = still ? 1 : smooth((t - 0.5) / 0.7);
            setAttrs(sweep, { x: (B.x - BODY + 16 * sweepP).toFixed(1) });
            show(sweep, sweepP > 0);
            show(blockText, sweepP >= 1);
            // Samples
            const dp = still ? 1 : clamp((t - 1.3) / 1.2, 0, 1);
            const shown = Math.floor(dp * N);
            dots.forEach((o, i) => { o.c.style.opacity = i < shown ? (o.ok ? '1' : '0.7') : '0'; });
            const wp = still ? 1 : smooth((t - 1.3) / 0.6);
            wedge.style.opacity = String(0.6 * wp);
            wedgeText.style.opacity = String(wp);
            const pick = still || t >= 2.5;
            show(bestRing, pick);
            show(bestText, pick);
            if (pick) heading.set(B.x, B.y, B.x + ux * 110, B.y + uy * 110, 10); else heading.hide();
            // Burst
            const bt = still ? 11 : clamp((t - 2.9) / TICK, 0, 11);
            const k = Math.floor(bt);
            const frac = bt - k;
            const dist = k >= 11 ? cum[11] : cum[k] + speeds[k] * frac;
            const bx = B.x + ux * dist * PX, by = B.y + uy * dist * PX;
            boss.setAttribute('transform', `translate(${bx.toFixed(1)},${by.toFixed(1)})`);
            setAttrs(trail, { points: bt > 0 ? `${B.x},${B.y} ${bx.toFixed(1)},${by.toFixed(1)}` : '' });
            show(ghost, bt > 0);
            bars.forEach((b, i) => { b.style.opacity = i < Math.ceil(bt) ? '1' : '0'; });
            if (status) {
                if (still) status.textContent = 'burst: 11 ticks, ' + cum[11].toFixed(2) + ' blocks';
                else if (t < 2.9) status.textContent = t < 1.3 ? 'checking the straight line' : 'second brain: 600 points';
                else if (bt < 11) status.textContent = 'burst timer ' + Math.max(0, 10 - k) + ' · speed ' + speeds[Math.min(k, 10)].toFixed(2);
                else status.textContent = 'burst done · ' + cum[11].toFixed(2) + ' blocks';
            }
        }
        return timeline(fig, D, render);
    }

    /* ─── 04 · Voxel A* (TestProcedure) ───────────────────────────────────────
       A 2D side-view analogue, computed with the same rules:
       - activation: cntlost > 1 (527); flashdrive allowed after 16 ticks and the route flown
         after 20 (CommonflashProcedure 291–292, 394–396, 446–459)
       - standoff goal (Longrangeuse0 is set every tick by Demo2Procedure 103): 16 bearings,
         radii 16..36 step 5, planes 0/±8; needs free space and line of sight; score
         tent peak 26 m (+6/m from 16, −3/m after 26) + 1.5 × max(0, 8 − |dy|) + 30 × cos(angle
         to own side); best first (110–143, 186–251)
       - octree: 64 m top cells; air cells > 16 m always split; mixed content via 6×6 (64 m),
         3×3 (32 m) or corner probes; split near start/goal (32 m, or 16 m for cells ≤ 8 m);
         coarse pass to 16 m, then a 4 m pass inside a 28 m corridor (1246–1280, 1808–2018)
       - clearance ellipse 12 × 8 m, layers 1/6..1 (95–104, 2021–2033)
       - A* edges ≤ 1.5 × the larger cell, clear line, cost × (1 + 2 × (1 − clearance)),
         5,000 iteration cap (1567–1617); greedy line-of-sight smoothing; 8 m waypoints
         (1630–1660); rebuild every 3 ticks (69–70). */
    function initPathfind(fig) {
        const canvas = fig.querySelector('[data-ep-canvas]');
        const ctx = canvas.getContext('2d');
        const stepBtns = Array.from(fig.querySelectorAll('[data-ep-step]'));
        const stepText = fig.querySelector('[data-ep-steptext]');
        const status = fig.querySelector('[data-ep-status]');
        const ladder = Array.from(fig.querySelectorAll('[data-ep-ladder]'));

        const W = 128, H = 64;
        const S = { x: 12, y: 30 };            // Epsilon (centre)
        const T = { x: 108, y: 55.5 };         // target (centre, standing on the ground)
        const pillar = { x0: 90, x1: 93, y0: 44 };
        const ledge = { x0: 20, x1: 40, y0: 19, y1: 22 };
        const groundTop = (x) => {
            let top = 58;
            const m = Math.max(0, 1 - Math.abs(x - 64) / 22);
            top = Math.min(top, 58 - 44 * (m * m * (3 - 2 * m)));
            const h = Math.max(0, 1 - Math.abs(x - 116) / 10);
            top = Math.min(top, 58 - 3 * h);
            return top;
        };
        const grid = new Uint8Array(W * H);
        for (let ix = 0; ix < W; ix++) {
            const gt = groundTop(ix + 0.5);
            for (let iy = 0; iy < H; iy++) {
                let solid = iy + 0.5 >= gt;
                if (ix >= pillar.x0 && ix < pillar.x1 && iy >= pillar.y0) solid = true;
                if (ix >= ledge.x0 && ix < ledge.x1 && iy >= ledge.y0 && iy < ledge.y1) solid = true;
                grid[iy * W + ix] = solid ? 1 : 0;
            }
        }
        const solidAt = (x, y) => {
            const ix = Math.floor(x), iy = Math.floor(y);
            if (ix < 0 || iy < 0 || ix >= W || iy >= H) return iy >= H; // open sky / sides, floor below
            return grid[iy * W + ix] === 1;
        };
        const lineClear = (ax, ay, bx, by) => {
            const len = Math.hypot(bx - ax, by - ay);
            const n = Math.max(1, Math.ceil(len / 0.25));
            for (let i = 0; i <= n; i++) {
                const t = i / n;
                if (solidAt(ax + (bx - ax) * t, ay + (by - ay) * t)) return false;
            }
            return true;
        };
        const sweepClear = (ax, ay, bx, by) => {
            const len = Math.hypot(bx - ax, by - ay) || 1;
            const nx = -(by - ay) / len, ny = (bx - ax) / len;
            return lineClear(ax, ay, bx, by) && lineClear(ax + nx, ay + ny, bx + nx, by + ny) && lineClear(ax - nx, ay - ny, bx - nx, by - ny);
        };
        const boxFree = (x, y) => !solidAt(x - 0.9, y - 1) && !solidAt(x + 0.9, y - 1) && !solidAt(x - 0.9, y + 1) && !solidAt(x + 0.9, y + 1) && !solidAt(x, y);

        // Standoff goal (2D: bearings in the slice plane)
        const cands = [];
        const es = { x: S.x - T.x, y: S.y - T.y };
        const esLen = Math.hypot(es.x, es.y);
        for (let yi = 0; yi < 16; yi++) {
            const ang = TAU / 16 * yi;
            for (let r = 16; r <= 36; r += 5) {
                const cx = T.x + Math.cos(ang) * r, cy = T.y + Math.sin(ang) * r;
                let ok = cx > 1 && cx < W - 1 && cy > 1 && cy < H - 1 && boxFree(cx, cy) && lineClear(cx, cy, T.x, T.y - 1);
                let sc = 0;
                if (ok) {
                    sc = r <= 26 ? 6 * (r - 16) : 6 * 10 - 3 * (r - 26);
                    sc += 1.5 * Math.max(0, 8 - Math.abs(cy - T.y));
                    sc += 30 * ((cx - T.x) * es.x + (cy - T.y) * es.y) / (r * esLen);
                }
                cands.push({ x: cx, y: cy, ok, sc });
            }
        }
        const goal = cands.filter((c) => c.ok).sort((a, b) => b.sc - a.sc)[0] || { x: T.x - 20, y: T.y - 20 };

        // Octree (quadtree) scan
        function nearCorridor(cx, cy, chain, r) {
            const r2 = r * r;
            if ((cx - S.x) ** 2 + (cy - S.y) ** 2 < r2) return true;
            if ((cx - goal.x) ** 2 + (cy - goal.y) ** 2 < r2) return true;
            if (!chain) return false;
            for (const p of chain) if ((cx - p.x) ** 2 + (cy - p.y) ** 2 < r2) return true;
            return false;
        }
        function clearance(cx, cy) {
            const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1], [0.7071, 0.7071], [-0.7071, 0.7071], [0.7071, -0.7071], [-0.7071, -0.7071]];
            const layers = [1 / 6, 1 / 3, 0.5, 2 / 3, 5 / 6, 1];
            for (const rel of layers) {
                for (const d of dirs) {
                    if (solidAt(cx + d[0] * 12 * rel, cy + d[1] * 8 * rel)) return clamp((rel - 1 / 6) / (1 - 1 / 6), 0, 1);
                }
            }
            return 1;
        }
        function scan(minSize, chain, corridorR, pass, cells, nodes) {
            const collect = (ox, oy, size) => {
                const half = size / 2, cx = ox + half, cy = oy + half;
                if (chain && !nearCorridor(cx, cy, chain, corridorR + size * 0.707)) return;
                const centerAir = !solidAt(cx, cy);
                let sub = false;
                if (size > minSize) {
                    if (centerAir && size > 16) sub = true;
                    else {
                        let mixed = false;
                        if (size >= 64) {
                            const st = size / 6;
                            for (let sx = 0; sx < 6 && !mixed; sx++) for (let sy = 0; sy < 6 && !mixed; sy++) {
                                if (!solidAt(ox + st * (sx + 0.5), oy + st * (sy + 0.5)) !== centerAir) mixed = true;
                            }
                        } else if (size >= 32) {
                            const st = size / 3;
                            for (let sx = 0; sx < 3 && !mixed; sx++) for (let sy = 0; sy < 3 && !mixed; sy++) {
                                if (sx === 1 && sy === 1) continue;
                                if (!solidAt(ox + st * (sx + 0.5), oy + st * (sy + 0.5)) !== centerAir) mixed = true;
                            }
                        } else {
                            const off = half - 0.5;
                            for (const dx of [-1, 1]) for (const dy of [-1, 1]) {
                                if (!solidAt(cx + dx * off, cy + dy * off) !== centerAir) mixed = true;
                            }
                        }
                        const lim = size > 8 ? 32 : 16;
                        const nearSG = Math.hypot(cx - S.x, cy - S.y) < lim || Math.hypot(cx - goal.x, cy - goal.y) < lim;
                        sub = mixed || nearSG;
                    }
                }
                if (sub) {
                    const cs = size / 2;
                    collect(ox, oy, cs); collect(ox + cs, oy, cs); collect(ox, oy + cs, cs); collect(ox + cs, oy + cs, cs);
                } else {
                    cells.push({ x: ox, y: oy, s: size, air: centerAir, pass });
                    if (centerAir) nodes.push({ x: cx, y: cy, s: size, clr: clearance(cx, cy) });
                }
            };
            for (let gx = 0; gx < W; gx += 64) for (let gy = 0; gy < H; gy += 64) collect(gx, gy, 64);
        }
        function astar(nodes) {
            let si = -1, gi = -1, sb = Infinity, gb = Infinity;
            nodes.forEach((n, i) => {
                const ds = (n.x - S.x) ** 2 + (n.y - S.y) ** 2, dg = (n.x - goal.x) ** 2 + (n.y - goal.y) ** 2;
                if (ds < sb) { sb = ds; si = i; }
                if (dg < gb) { gb = dg; gi = i; }
            });
            const N = nodes.length;
            const g = new Float64Array(N).fill(Infinity), from = new Int32Array(N).fill(-1), closed = new Uint8Array(N);
            const order = [];
            const open = [[Math.hypot(nodes[si].x - nodes[gi].x, nodes[si].y - nodes[gi].y), si]];
            g[si] = 0;
            let found = false, iters = 0;
            while (open.length && iters++ < 5000) {
                let bi = 0;
                for (let i = 1; i < open.length; i++) if (open[i][0] < open[bi][0]) bi = i;
                const ci = open.splice(bi, 1)[0][1];
                if (ci === gi) { found = true; break; }
                if (closed[ci]) continue;
                closed[ci] = 1;
                order.push(ci);
                const c = nodes[ci];
                for (let ni = 0; ni < N; ni++) {
                    if (closed[ni] || ni === ci) continue;
                    const n = nodes[ni];
                    const maxRes = Math.max(c.s, n.s) * 1.5;
                    const e = Math.hypot(n.x - c.x, n.y - c.y);
                    if (e > maxRes) continue;
                    if (!lineClear(c.x, c.y, n.x, n.y)) continue;
                    const cost = e * (1 + 2 * (1 - (c.clr + n.clr) / 2));
                    const tg = g[ci] + cost;
                    if (tg < g[ni]) {
                        g[ni] = tg; from[ni] = ci;
                        open.push([tg + Math.hypot(n.x - nodes[gi].x, n.y - nodes[gi].y), ni]);
                    }
                }
            }
            if (!found) return { path: null, order };
            const path = [];
            for (let ci = gi; ci >= 0; ci = from[ci]) path.unshift({ x: nodes[ci].x, y: nodes[ci].y });
            return { path, order };
        }
        function smoothAndSpace(path) {
            const sm = [path[0]];
            let si = 0;
            while (si < path.length - 1) {
                let far = si + 1;
                for (let j = path.length - 1; j > si + 1; j--) {
                    if (sweepClear(path[si].x, path[si].y, path[j].x, path[j].y)) { far = j; break; }
                }
                sm.push(path[far]);
                si = far;
            }
            const wps = [];
            for (let i = 0; i < sm.length - 1; i++) {
                const a = sm[i], b = sm[i + 1];
                const steps = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 8));
                for (let k = i === 0 ? 1 : 0; k < steps; k++) wps.push({ x: lerp(a.x, b.x, k / steps), y: lerp(a.y, b.y, k / steps) });
            }
            wps.push(sm[sm.length - 1]);
            return { smooth: sm, wps };
        }

        const coarseCells = [], coarseNodes = [];
        scan(16, null, 0, 'coarse', coarseCells, coarseNodes);
        const coarse = astar(coarseNodes);
        const fineCells = [], fineNodes = [];
        scan(4, coarse.path, 28, 'fine', fineCells, fineNodes);
        const fine = astar(fineNodes);
        const route = fine.path || coarse.path || [S, goal];
        const sp = smoothAndSpace([{ x: S.x, y: S.y }, ...route, { x: goal.x, y: goal.y }]);
        const flyPts = [{ x: S.x, y: S.y }, ...sp.wps];
        const flyLen = [0];
        for (let i = 1; i < flyPts.length; i++) flyLen.push(flyLen[i - 1] + Math.hypot(flyPts[i].x - flyPts[i - 1].x, flyPts[i].y - flyPts[i - 1].y));

        const STEPS = [
            { d: 2.8, html: 'The eye-line to the target is blocked by the mountain. After <b>1 tick</b> the pathfinder starts planning; after <b>16</b> a flashdrive burst is allowed; after <b>20</b> Epsilon flies the planned route. Sight must come back for <b>5 ticks in a row</b> before the plan is dropped.' },
            { d: 2.6, html: 'It doesn’t fly at the target itself. It picks a <b>standoff point 16–36 m</b> away that is free and can see the target: best at <b>26 m</b>, on its own side, near the target’s height. The point is kept until it gets too close, too far, loses sight or can’t be reached.' },
            { d: 3.6, html: 'Space is cut into <b>64 m</b> cells. Cells that mix air and rock, or lie near the start or the goal, split again; rock is dropped. A coarse pass stops at <b>16 m</b>, then a <b>4 m</b> pass refines a <b>28 m</b> corridor around the coarse route (budget: 4,000 small cells, hard stop at 5,000).' },
            { d: 3.0, html: '<b>A*</b> searches the air cells. A step costs its length × (1 + 2 × (1 − clearance)), measured in a 12 × 8 m ellipse, so a route hugging rock costs up to <b>3×</b> as much. The search stops after 5,000 iterations.' },
            { d: 2.4, html: 'The route is pulled straight wherever the body fits through (greedy line of sight), then cut into <b>waypoints every 8 m</b>. Epsilon steers at the first waypoint.' },
            { d: 3.8, html: 'Epsilon flies the route and reaches a spot that can see the target. While sight is blocked the whole plan is rebuilt <b>every 3 ticks</b>, with the grid shifted by a random offset of up to <b>±32 m</b> so regular structures can’t fool the sampling.' },
        ];
        const starts = [];
        let acc = 0;
        STEPS.forEach((st) => { starts.push(acc); acc += st.d; });
        const HOLD = 1.6;
        const TOTAL = acc + HOLD;
        let t = 0;
        let curStep = -1;

        // Canvas sizing
        let cw = 0, ch = 0, dpr = 1, sc = 1;
        let terrain = null;
        function resize() {
            const w = canvas.clientWidth || canvas.parentElement.clientWidth;
            if (!w) return;
            dpr = Math.min(2, window.devicePixelRatio || 1);
            cw = w; ch = Math.round(w / 2);
            canvas.width = Math.round(cw * dpr);
            canvas.height = Math.round(ch * dpr);
            sc = cw / W;
            terrain = document.createElement('canvas');
            terrain.width = canvas.width; terrain.height = canvas.height;
            const tc = terrain.getContext('2d');
            tc.scale(dpr * sc, dpr * sc);
            tc.fillStyle = '#2a2f3d';
            for (let ix = 0; ix < W; ix++) for (let iy = 0; iy < H; iy++) if (grid[iy * W + ix]) tc.fillRect(ix, iy, 1.02, 1.02);
            tc.strokeStyle = '#4a5268';
            tc.lineWidth = 1.2 / sc;
            tc.beginPath();
            for (let ix = 0; ix < W; ix++) {
                for (let iy = 0; iy < H; iy++) {
                    if (grid[iy * W + ix] && (iy === 0 || !grid[(iy - 1) * W + ix])) { tc.moveTo(ix, iy); tc.lineTo(ix + 1, iy); }
                }
            }
            tc.stroke();
        }
        const X = (x) => x * sc, Y = (y) => y * sc;
        const fontPx = () => Math.max(10, Math.min(13, cw / 52));

        function label(str, x, y, color, align) {
            ctx.font = `500 ${fontPx()}px "JetBrains Mono", Consolas, monospace`;
            ctx.textAlign = align || 'left';
            ctx.textBaseline = 'middle';
            ctx.lineWidth = 3;
            ctx.strokeStyle = 'rgba(6,8,13,0.85)';
            ctx.strokeText(str, x, y);
            ctx.fillStyle = color;
            ctx.fillText(str, x, y);
        }
        function drawDiamond(x, y, r, fill, alpha) {
            ctx.save();
            ctx.globalAlpha = alpha === undefined ? 1 : alpha;
            ctx.beginPath();
            ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
            ctx.fillStyle = fill; ctx.fill();
            ctx.lineWidth = 1.5; ctx.strokeStyle = '#1b1206'; ctx.stroke();
            ctx.restore();
        }
        function polyline(pts, color, width, dash, alpha) {
            if (!pts || pts.length < 2) return;
            ctx.save();
            ctx.globalAlpha = alpha === undefined ? 1 : alpha;
            ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
            ctx.setLineDash(dash || []);
            ctx.beginPath();
            pts.forEach((p, i) => (i ? ctx.lineTo(X(p.x), Y(p.y)) : ctx.moveTo(X(p.x), Y(p.y))));
            ctx.stroke();
            ctx.restore();
        }
        function cellsLayer(cells, count, alpha) {
            ctx.save();
            ctx.globalAlpha = alpha;
            for (let i = 0; i < Math.min(count, cells.length); i++) {
                const c = cells[i];
                if (c.air) {
                    ctx.fillStyle = c.s <= 4 ? 'rgba(111,177,255,0.10)' : c.s <= 8 ? 'rgba(111,177,255,0.07)' : 'rgba(111,177,255,0.04)';
                    ctx.fillRect(X(c.x), Y(c.y), X(c.s), Y(c.s));
                }
                ctx.strokeStyle = c.air ? 'rgba(111,177,255,0.38)' : 'rgba(255,255,255,0.10)';
                ctx.lineWidth = 1;
                ctx.strokeRect(X(c.x) + 0.5, Y(c.y) + 0.5, X(c.s) - 1, Y(c.s) - 1);
            }
            ctx.restore();
        }
        function draw(step, p, still) {
            if (!cw) resize();
            if (!cw) return;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, cw, ch);
            const all = still && step === 6;
            // Cells
            if (step >= 2 || all) {
                if (step === 2 && !all) {
                    const cp = clamp(p / 0.4, 0, 1), fp = clamp((p - 0.4) / 0.6, 0, 1);
                    cellsLayer(coarseCells, Math.ceil(cp * coarseCells.length), fp > 0 ? 0.35 * (1 - fp) + 0.15 : 0.9);
                    if (fp > 0) cellsLayer(fineCells, Math.ceil(fp * fineCells.length), 1);
                } else cellsLayer(fineCells, fineCells.length, step >= 4 ? 0.45 : 0.8);
            }
            // Standoff band (under the rock)
            if (step >= 1 || all) {
                ctx.save();
                ctx.beginPath();
                ctx.arc(X(T.x), Y(T.y), X(36), 0, TAU);
                ctx.arc(X(T.x), Y(T.y), X(16), 0, TAU, true);
                ctx.fillStyle = 'rgba(255,176,46,0.06)';
                ctx.fill('evenodd');
                ctx.restore();
            }
            ctx.drawImage(terrain, 0, 0, cw, ch);
            // Standoff ring and candidates
            if (step >= 1 || all) {
                ctx.save();
                ctx.setLineDash([4, 5]);
                ctx.strokeStyle = 'rgba(255,176,46,0.45)';
                ctx.lineWidth = 1.2;
                ctx.beginPath(); ctx.arc(X(T.x), Y(T.y), X(26), 0, TAU); ctx.stroke();
                ctx.restore();
                const cp = step === 1 && !still ? clamp(p / 0.7, 0, 1) : 1;
                const n = Math.ceil(cp * cands.length);
                for (let i = 0; i < n; i++) {
                    const c = cands[i];
                    ctx.beginPath();
                    ctx.arc(X(c.x), Y(c.y), c.ok ? 2.6 : 1.6, 0, TAU);
                    ctx.fillStyle = c.ok ? 'rgba(255,198,92,0.9)' : 'rgba(255,255,255,0.18)';
                    ctx.fill();
                }
                if (step > 1 || p > 0.75 || still || all) {
                    ctx.save();
                    ctx.setLineDash([3, 4]);
                    ctx.strokeStyle = 'rgba(99,240,198,0.7)';
                    ctx.lineWidth = 1.2;
                    ctx.beginPath(); ctx.moveTo(X(goal.x), Y(goal.y)); ctx.lineTo(X(T.x), Y(T.y - 1)); ctx.stroke();
                    ctx.restore();
                    ctx.beginPath(); ctx.arc(X(goal.x), Y(goal.y), 7, 0, TAU);
                    ctx.lineWidth = 2.5; ctx.strokeStyle = '#ffb02e'; ctx.stroke();
                    if (step < 5) label('goal', X(goal.x) - 10, Y(goal.y) - 12, '#ffc65c', 'right');
                }
                if (cw > 420) label('standoff 16–36 m', X(T.x) + 4, Y(T.y - 36) + 12, 'rgba(255,198,92,0.85)', 'center');
            }
            // A* expansion and raw path
            if (step === 3 && !all) {
                const n = Math.ceil(clamp(p / 0.75, 0, 1) * fine.order.length);
                ctx.fillStyle = 'rgba(111,177,255,0.85)';
                for (let i = 0; i < n; i++) {
                    const nd = fineNodes[fine.order[i]];
                    ctx.beginPath(); ctx.arc(X(nd.x), Y(nd.y), Math.max(1.6, X(nd.s) * 0.12), 0, TAU); ctx.fill();
                }
                if (p > 0.75) polyline(route, '#ffb02e', 2.5, null, smooth((p - 0.75) / 0.25));
            }
            if (step >= 4 || all) {
                polyline(route, 'rgba(255,176,46,0.6)', 1.5, [3, 4], step === 4 ? 1 : 0.5);
                const pp = step === 4 && !still ? clamp(p / 0.6, 0, 1) : 1;
                if (pp > 0) {
                    polyline(sp.smooth, '#ffb02e', 2.8, null, pp);
                    const wn = Math.ceil(clamp((p - 0.3) / 0.6, 0, 1) * sp.wps.length);
                    const wcount = step === 4 && !still ? wn : sp.wps.length;
                    for (let i = 0; i < wcount; i++) {
                        ctx.beginPath(); ctx.arc(X(sp.wps[i].x), Y(sp.wps[i].y), 3.6, 0, TAU);
                        ctx.fillStyle = '#ffc65c'; ctx.fill();
                    }
                    if (wcount > 1 && cw > 420) label('8 m waypoints', X(sp.wps[1].x) + 8, Y(sp.wps[1].y) - 12, '#ffc65c');
                }
            }
            // Line of sight
            const flying = step === 5 && !all;
            const fp = flying ? clamp(p / 0.75, 0, 1) : (step > 5 || all ? 1 : 0);
            let bx = S.x, by = S.y;
            if (fp > 0) {
                const dist = smooth(fp) * flyLen[flyLen.length - 1];
                let i = 1;
                while (i < flyLen.length - 1 && flyLen[i] < dist) i++;
                const seg = flyLen[i] - flyLen[i - 1] || 1;
                const f = clamp((dist - flyLen[i - 1]) / seg, 0, 1);
                bx = lerp(flyPts[i - 1].x, flyPts[i].x, f);
                by = lerp(flyPts[i - 1].y, flyPts[i].y, f);
            }
            const seen = lineClear(bx, by, T.x, T.y - 1);
            if (step === 0 || (flying && !seen)) {
                ctx.save();
                ctx.setLineDash([5, 5]);
                ctx.strokeStyle = 'rgba(255,97,112,0.85)';
                ctx.lineWidth = 2;
                ctx.beginPath(); ctx.moveTo(X(bx), Y(by)); ctx.lineTo(X(T.x), Y(T.y - 1)); ctx.stroke();
                ctx.restore();
                if (step === 0) label('no line of sight', X(52), Y(36), '#ff6170', 'right');
            } else if (seen && (flying || all)) {
                ctx.save();
                ctx.strokeStyle = 'rgba(99,240,198,0.9)';
                ctx.lineWidth = 2;
                ctx.beginPath(); ctx.moveTo(X(bx), Y(by)); ctx.lineTo(X(T.x), Y(T.y - 1)); ctx.stroke();
                ctx.restore();
                label('in sight', X((bx + T.x) / 2), Y((by + T.y) / 2) - 12, '#63f0c6', 'center');
            }
            // Actors
            ctx.beginPath(); ctx.arc(X(T.x), Y(T.y), 6, 0, TAU); ctx.fillStyle = '#f3f4f8'; ctx.fill();
            label('target', X(T.x) + 9, Y(T.y) - 10, '#f3f4f8');
            if (fp > 0) drawDiamond(X(S.x), Y(S.y), 7, '#ffb02e', 0.3);
            drawDiamond(X(bx), Y(by), 8, '#ffb02e');
            label('Epsilon', X(bx), Y(by) - 16, '#ffc65c', 'center');
        }
        function setStep(i) {
            if (i === curStep) return;
            curStep = i;
            stepBtns.forEach((b, k) => { b.classList.toggle('is-active', k === i); b.setAttribute('aria-pressed', k === i ? 'true' : 'false'); });
            if (stepText) stepText.innerHTML = i >= 0 && i < STEPS.length ? STEPS[i].html
                : 'All six steps at once: the standoff goal, the cells that were scanned, the smoothed route and its 8 m waypoints. Pick a step to see it on its own.';
        }
        function ladderAt(ticks) {
            ladder.forEach((li) => li.classList.toggle('is-on', ticks > Number(li.dataset.epLadder)));
        }
        function render(time, still) {
            let step = STEPS.length - 1, p = 1;
            for (let i = 0; i < STEPS.length; i++) {
                if (time < starts[i] + STEPS[i].d) { step = i; p = (time - starts[i]) / STEPS[i].d; break; }
            }
            setStep(step);
            const ticks = step === 0 ? Math.floor(p * 24) : 24;
            ladderAt(ticks);
            if (status) status.textContent = step === 0 ? 'out of sight: ' + ticks + ' ticks' : 'step ' + (step + 1) + ' of 6';
            draw(step, clamp(p, 0, 1), still);
        }
        function renderStill(step) {
            const s = step === undefined ? 6 : step;
            setStep(s);
            ladderAt(24);
            if (status) status.textContent = '';
            draw(s, 1, true);
        }
        stepBtns.forEach((b) => b.addEventListener('click', () => {
            const i = Number(b.dataset.epStep);
            if (stepText) stepText.setAttribute('aria-live', 'polite');
            if (reduced) { renderStill(i); return; }
            t = starts[i];
            render(t, false);
        }));
        const replay = fig.querySelector('[data-ep-replay]');
        if (replay) replay.addEventListener('click', () => { if (reduced) renderStill(6); else { t = 0; render(0, false); } });
        let lastStill = null;
        if ('ResizeObserver' in window) {
            new ResizeObserver(() => {
                const w = canvas.clientWidth;
                if (!w || Math.abs(w - cw) < 1) return;
                resize();
                if (reduced) renderStill(lastStill === null ? 6 : lastStill); else render(t, false);
            }).observe(canvas);
        }
        return {
            frame(dt) {
                t += dt;
                if (t > TOTAL) t = 0;
                render(Math.min(t, acc - 0.0001), false);
            },
            still() { lastStill = 6; renderStill(6); },
            resume() { t = 0; curStep = -1; },
        };
    }

    /* ─── 05 · Dandelion escape ───────────────────────────────────────────────
       CommonflashProcedure: up to 5 guided seeds + DAMAGE_SIDE_DANDELION_PROBES = 16 random rays
       within DAMAGE_SIDE_DANDELION_CONE_DEG = 30° of the base (1675–1706, 1788–1798; 114–115).
       Clearance: body sweep to 32 m; hit ≥ 16 → (hit − 16) × 22.5, else −(16 − hit) × 45
       (6088–6116, 116–126). Run 12 m; if the first hit is closer, stop 1 m short, min 2 m
       (1585–1611, 113, 127–129). Only the clearance term is drawn. */
    function initDandelion(fig) {
        const s = fig.querySelector('svg');
        const PX = 6;
        const B = { x: 230, y: 200 };
        const A = { x: 66, y: 322 };
        const walls = [
            { x: 0, y: 0, w: 196, h: 34 },
            { x: 252, y: 0, w: 348, h: 34 },
            { x: 372, y: 60, w: 38, h: 280 },
            { x: 262, y: 120, w: 28, h: 30 },
            { x: 80, y: 60, w: 70, h: 50 },
        ];
        // guide circles
        svgEl('circle', { cx: B.x, cy: B.y, r: 32 * PX, class: 'p-guide' }, s);
        svgEl('circle', { cx: B.x, cy: B.y, r: 16 * PX, class: 'p-guide' }, s);
        text(s, 84, 232, '16 m · 0', 't-small');
        text(s, 22, 258, '32 m', 't-small');
        rectEls(s, walls);
        const coneEl = svgEl('path', { class: 'p-ray-fill' }, s);
        const raysG = svgEl('g', null, s);
        const hitArrow = makeArrow(s, 'p-danger-line', '');
        hitArrow.g.querySelector('polygon').setAttribute('fill', '#ff6170');
        const hitText = text(s, A.x + 8, A.y - 18, 'hit', 't-label t-danger');
        const winLine = svgEl('line', { class: 'p-boss-line' }, s);
        const winText = text(s, 0, 0, '', 't-label t-boss');
        const dashLine = svgEl('line', { stroke: '#ffb02e', 'stroke-width': 6, 'stroke-linecap': 'round', opacity: 0.35 }, s);
        const ghost = svgEl('g', { transform: `translate(${B.x},${B.y})` }, s);
        diamond(ghost, 'p-boss', 10).style.opacity = '0.3';
        const boss = svgEl('g', null, s);
        diamond(boss, 'p-boss', 11);

        const castLen = (ang) => {
            const dx = Math.cos(ang), dy = Math.sin(ang);
            const L = 32 * PX;
            let best = 1;
            const pad = 4; // body half-width, so the sweep stops when the body touches
            walls.forEach((w) => {
                const t = segRect(B.x, B.y, B.x + dx * L, B.y + dy * L, { x: w.x - pad, y: w.y - pad, w: w.w + 2 * pad, h: w.h + 2 * pad });
                if (t !== null && t < best) best = t;
            });
            return best * 32; // metres
        };
        const score = (hit) => (hit >= 16 ? (hit - 16) * 22.5 : -(16 - hit) * 45);
        const colorFor = (sc) => {
            if (sc < 0) {
                const k = clamp(-sc / 720, 0, 1);
                return `rgb(${Math.round(lerp(90, 255, k))},${Math.round(lerp(99, 97, k))},${Math.round(lerp(120, 112, k))})`;
            }
            const k = clamp(sc / 360, 0, 1);
            return k < 0.5
                ? `rgb(${Math.round(lerp(90, 111, k * 2))},${Math.round(lerp(99, 177, k * 2))},${Math.round(lerp(120, 255, k * 2))})`
                : `rgb(${Math.round(lerp(111, 99, (k - 0.5) * 2))},${Math.round(lerp(177, 240, (k - 0.5) * 2))},${Math.round(lerp(255, 198, (k - 0.5) * 2))})`;
        };
        const base = -70 * DEG;
        const damageAng = Math.atan2(A.y - B.y, A.x - B.x);
        const seeds = [base, damageAng + Math.PI / 2, damageAng + Math.PI]; // base, orbit guide, reverse cone
        const cr = 32 * PX;
        coneEl.setAttribute('d', `M${B.x},${B.y} L${B.x + Math.cos(base - 30 * DEG) * cr},${B.y + Math.sin(base - 30 * DEG) * cr} A${cr},${cr} 0 0 1 ${B.x + Math.cos(base + 30 * DEG) * cr},${B.y + Math.sin(base + 30 * DEG) * cr} Z`);

        let seed = 7;
        let rays = [];
        let winner = null;
        function build() {
            const r = rng(seed++);
            raysG.textContent = '';
            rays = [];
            const add = (ang, kind) => {
                const hit = castLen(ang);
                const sc = score(hit);
                const line = svgEl('line', { x1: B.x, y1: B.y, x2: B.x, y2: B.y, stroke: colorFor(sc), 'stroke-width': kind === 'seed' ? 2.4 : 1.8, 'stroke-linecap': 'round', 'stroke-dasharray': kind === 'seed' ? '6 4' : null }, raysG);
                const dot = svgEl('circle', { r: 3.4, fill: colorFor(sc) }, raysG);
                rays.push({ ang, hit, sc, line, dot, kind });
            };
            seeds.forEach((a) => add(a, 'seed'));
            for (let i = 0; i < 16; i++) add(base + (r() * 2 - 1) * 30 * DEG, 'cone');
            winner = rays.reduce((a, b) => (b.sc > a.sc ? b : a));
        }
        build();

        const D = 5.6;
        function render(t, still) {
            const hp = still ? 1 : smooth(t / 0.5);
            hitArrow.set(A.x, A.y, lerp(A.x, B.x - 14, hp), lerp(A.y, B.y + 10, hp), 10);
            show(hitText, hp > 0.2);
            const rp = still ? 1 : clamp((t - 0.7) / 1.3, 0, 1);
            coneEl.style.opacity = String(0.55 * (still ? 1 : smooth((t - 0.5) / 0.4)));
            rays.forEach((ray) => {
                const len = Math.min(ray.hit, rp * 32) * PX;
                const x2 = B.x + Math.cos(ray.ang) * len, y2 = B.y + Math.sin(ray.ang) * len;
                setAttrs(ray.line, { x2: x2.toFixed(1), y2: y2.toFixed(1) });
                const done = rp * 32 >= ray.hit;
                setAttrs(ray.dot, { cx: x2.toFixed(1), cy: y2.toFixed(1) });
                show(ray.dot, done && rp > 0);
                ray.line.style.opacity = rp > 0 ? '1' : '0';
            });
            const pick = still || t > 2.2;
            show(winLine, pick); show(winText, pick);
            if (pick) {
                const L = winner.hit * PX;
                setAttrs(winLine, { x1: B.x, y1: B.y, x2: B.x + Math.cos(winner.ang) * L, y2: B.y + Math.sin(winner.ang) * L });
                const tx = B.x + Math.cos(winner.ang) * Math.min(L, 150) + 10, ty = B.y + Math.sin(winner.ang) * Math.min(L, 150);
                setAttrs(winText, { x: tx.toFixed(1), y: ty.toFixed(1) });
                winText.textContent = (winner.sc >= 0 ? '+' : '') + Math.round(winner.sc);
            }
            const run = winner.hit < 12 ? Math.max(2, winner.hit - 1) : 12;
            const dp = still ? 1 : smooth((t - 3.0) / 0.6);
            const bx = B.x + Math.cos(winner.ang) * run * PX * dp, by = B.y + Math.sin(winner.ang) * run * PX * dp;
            boss.setAttribute('transform', `translate(${bx.toFixed(1)},${by.toFixed(1)})`);
            setAttrs(dashLine, { x1: B.x, y1: B.y, x2: bx.toFixed(1), y2: by.toFixed(1) });
            show(dashLine, dp > 0); show(ghost, dp > 0);
        }
        return timeline(fig, D, render, { onLoop: build });
    }

    /* ─── 06 · Ring-net ───────────────────────────────────────────────────────
       CommonenemylockProcedure: Ring +2 per tick while targeting Epsilon or its allies (100–128),
       threat when Ring > 16 (130), up to RING_NET_MAX_COUNT = 16 with clear centre-to-centre
       line of sight, weight (1 − effDist/48)², EMA α = 0.14 per tick (41–52, 320–393).
       CommonflashProcedure: refuse kick-off / reposition directions within
       RING_NET_REJECT_ANGLE_DEG = 60° of the net (42–43, 5311–5340). */
    function initRingNet(fig) {
        const s = fig.querySelector('svg');
        const C = { x: 300, y: 170 };
        const PXM = 150 / 48;
        svgEl('circle', { cx: C.x, cy: C.y, r: 150, class: 'p-guide' }, s);
        text(s, C.x + 150 * 0.71 + 4, C.y - 150 * 0.71 - 4, '48 m', 't-small');
        // A short wall about 18 m out, between Epsilon and the threat at 27 m / 322°.
        const wall = { x1: 332, y1: 120, x2: 356, y2: 151 };
        svgEl('line', { x1: wall.x1, y1: wall.y1, x2: wall.x2, y2: wall.y2, stroke: '#3d4456', 'stroke-width': 9, 'stroke-linecap': 'round' }, s);
        const cone = svgEl('path', { class: 'p-danger-fill' }, s);
        const candG = svgEl('g', null, s);
        const linesG = svgEl('g', null, s);
        const net = makeArrow(s, 'p-boss-line', '');
        net.g.querySelector('polygon').setAttribute('fill', '#ffb02e');
        const boss = svgEl('g', { transform: `translate(${C.x},${C.y})` }, s);
        diamond(boss, 'p-boss', 11);

        const threats = [
            { d: 12, a: 200, w: 7 },
            { d: 20, a: 150, w: -5 },
            { d: 33, a: 245, w: 6 },
            { d: 42, a: 95, w: -8 },
            { d: 52, a: 20, w: 4 },   // beyond 48 m
            { d: 27, a: 322, w: 0 },  // behind the wall
        ].map((th) => {
            const line = svgEl('line', { stroke: '#ff6170', 'stroke-linecap': 'round' }, linesG);
            const dot = svgEl('circle', { r: 7 }, s);
            const lbl = text(s, 0, 0, '', 't-small');
            return Object.assign(th, { line, dot, lbl });
        });
        const cands = [];
        for (let i = 0; i < 16; i++) {
            const ang = i * TAU / 16;
            cands.push({ ang, el: svgEl('line', { x1: C.x + Math.cos(ang) * 16, y1: C.y + Math.sin(ang) * 16, x2: C.x + Math.cos(ang) * 29, y2: C.y + Math.sin(ang) * 29, 'stroke-width': 3.5, 'stroke-linecap': 'round' }, candG) });
        }
        const losClear = (px, py) => !segIntersects(C.x, C.y, px, py, wall.x1, wall.y1, wall.x2, wall.y2);
        function segIntersects(ax, ay, bx, by, cx, cy, dx, dy) {
            const d1 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx);
            const d2 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx);
            const d3 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
            const d4 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax);
            return d1 * d2 < 0 && d3 * d4 < 0;
        }
        let nx = 0, ny = 0;
        let acc = 0;
        let time = 0;
        function rawNet() {
            let sx = 0, sy = 0;
            threats.forEach((th) => {
                const ang = (th.a + th.w * time) * DEG;
                th.px = C.x + Math.cos(ang) * th.d * PXM;
                th.py = C.y + Math.sin(ang) * th.d * PXM;
                th.los = losClear(th.px, th.py);
                th.weight = th.d < 48 && th.los ? (1 - th.d / 48) ** 2 : 0;
                sx += th.weight * Math.cos(ang);
                sy += th.weight * Math.sin(ang);
            });
            return { sx, sy };
        }
        function paint() {
            threats.forEach((th) => {
                const on = th.weight > 0;
                setAttrs(th.dot, { cx: th.px.toFixed(1), cy: th.py.toFixed(1), fill: on ? '#ff6170' : 'rgba(255,255,255,0.3)' });
                setAttrs(th.line, { x1: C.x, y1: C.y, x2: th.px.toFixed(1), y2: th.py.toFixed(1), 'stroke-width': on ? (1 + th.weight * 10).toFixed(2) : 1, opacity: on ? 0.8 : 0.25, 'stroke-dasharray': on ? null : '3 4' });
                const lx = th.px + (th.px >= C.x ? 10 : -10);
                setAttrs(th.lbl, { x: lx.toFixed(1), y: (th.py - 10).toFixed(1), 'text-anchor': th.px >= C.x ? 'start' : 'end' });
                th.lbl.textContent = on ? th.d + ' m · ' + th.weight.toFixed(2) : (th.d >= 48 ? th.d + ' m · too far' : 'no line of sight');
                th.lbl.setAttribute('class', on ? 't-small' : 't-small t-dim');
            });
            const len = Math.hypot(nx, ny);
            if (len > 0.005) {
                const ux = nx / len, uy = ny / len;
                const L = Math.min(140, 30 + len * 150);
                net.set(C.x, C.y, C.x + ux * L, C.y + uy * L, 11);
                const a0 = Math.atan2(uy, ux);
                const R = 130;
                cone.setAttribute('d', `M${C.x},${C.y} L${C.x + Math.cos(a0 - 60 * DEG) * R},${C.y + Math.sin(a0 - 60 * DEG) * R} A${R},${R} 0 0 1 ${C.x + Math.cos(a0 + 60 * DEG) * R},${C.y + Math.sin(a0 + 60 * DEG) * R} Z`);
                show(cone, true);
                cands.forEach((c) => {
                    const blocked = Math.cos(c.ang) * ux + Math.sin(c.ang) * uy >= Math.cos(60 * DEG);
                    c.el.setAttribute('stroke', blocked ? '#ff6170' : '#63f0c6');
                    c.el.setAttribute('opacity', blocked ? '0.95' : '0.8');
                });
            } else {
                net.hide(); show(cone, false);
                cands.forEach((c) => { c.el.setAttribute('stroke', '#63f0c6'); });
            }
        }
        // Start converged so the first frame already shows a net.
        const first = rawNet();
        nx = first.sx; ny = first.sy;
        paint();
        return {
            frame(dt) {
                time += dt;
                acc += dt;
                // EMA once per game tick (20 per second)
                while (acc >= 0.05) {
                    acc -= 0.05;
                    const r = rawNet();
                    nx = nx * (1 - 0.14) + r.sx * 0.14;
                    ny = ny * (1 - 0.14) + r.sy * 0.14;
                }
                rawNet();
                paint();
            },
            still() {
                time = 0;
                const r = rawNet();
                nx = r.sx; ny = r.sy;
                paint();
            },
        };
    }

    /* ─── 07 · Railgun salvo (Magic2Procedure + LianxumofaProcedure) ──────────
       CommonskillProcedure 108–124: status 160, one shell whenever status ∈ (102, 140] and
       status % 9 == 0 → 4 shells, 9 ticks apart. Magic2Procedure 70–89: aim jitter accepted
       when dot > 0.998. LianxumofaProcedure: SPEED = 10 m per tick, 40 sweep steps, a hostile
       (Ring > 16) closer than DETECT_R − 0.1 = 1.9 m or any block ends it (383–460); life
       > 15 ticks discards it (357); the entity is teleported back to its owner (466–490);
       the blast runs while cnt ≤ 4 (44–60, 265–345). */
    function initRailgun(fig) {
        const s = fig.querySelector('svg');
        const status = fig.querySelector('[data-ep-status]');
        const PX = 3.6;
        const O = { x: 34, y: 112 };
        const toPx = (mx, my) => ({ x: O.x + mx * PX, y: O.y - my * PX });
        const tgt = { x: 95, y: -6, hw: 0.4, hh: 0.95 };
        const cliffX = 132;
        const mesa = { x0: 88, x1: 102, top: -7 };
        // Scenery
        const g0 = toPx(0, -25);
        svgEl('line', { x1: 0, y1: g0.y, x2: 640, y2: g0.y, class: 'p-axis' }, s);
        const m0 = toPx(mesa.x0, mesa.top), m1 = toPx(mesa.x1, -25);
        svgEl('rect', { x: m0.x, y: m0.y, width: m1.x - m0.x, height: m1.y - m0.y, rx: 3, class: 'p-rock' }, s);
        const c0 = toPx(cliffX, 18);
        svgEl('rect', { x: c0.x, y: c0.y, width: 640 - c0.x, height: g0.y - c0.y, rx: 3, class: 'p-rock' }, s);
        const tp = toPx(tgt.x, tgt.y);
        const feet = toPx(tgt.x, tgt.y - tgt.hh);
        svgEl('rect', { x: tp.x - 5, y: feet.y - 16, width: 10, height: 16, rx: 3, class: 'p-target' }, s);
        text(s, tp.x, feet.y + 30, 'hostile · 95 m', 't-small', { 'text-anchor': 'middle' });
        const boss = svgEl('g', { transform: `translate(${O.x},${O.y})` }, s);
        diamond(boss, 'p-boss', 10);
        const scale = [50, 100, 150];
        scale.forEach((m) => {
            const p = toPx(m, -25);
            svgEl('line', { x1: p.x, y1: p.y - 4, x2: p.x, y2: p.y + 4, class: 'p-tick' }, s);
            text(s, p.x, p.y + 18, m + ' m', 't-small', { 'text-anchor': 'middle' });
        });
        text(s, toPx(10, 0).x, 24, '10 m per tick · 40 checks each', 't-small t-boss');

        const aim = Math.atan2(tgt.y, tgt.x);
        const jitterDeg = [0.3, -0.5, 1.9, -0.2];
        const shells = jitterDeg.map((j, i) => {
            const ang = aim + j * DEG;
            const dx = Math.cos(ang), dy = Math.sin(ang);
            // Simulate: 15 ticks max, 40 samples per 10 m segment.
            let hitTick = null, hitAt = null, hitWhat = null;
            for (let k = 1; k <= 15 && hitTick === null; k++) {
                for (let st = 0; st <= 40; st++) {
                    const dist = (k - 1) * 10 + 10 * st / 40;
                    const px = dx * dist, py = dy * dist;
                    const inBlock = px >= cliffX || py <= -25 || (px >= mesa.x0 && px <= mesa.x1 && py <= mesa.top);
                    if (inBlock) { hitTick = k; hitAt = dist; hitWhat = 'block'; break; }
                    const bx = Math.max(Math.abs(px - tgt.x) - tgt.hw, 0), by = Math.max(Math.abs(py - tgt.y) - tgt.hh, 0);
                    if (Math.hypot(bx, by) < 1.9) { hitTick = k; hitAt = dist; hitWhat = 'hostile'; break; }
                }
            }
            const trail = svgEl('line', { x1: O.x, y1: O.y, x2: O.x, y2: O.y, stroke: '#6fb1ff', 'stroke-width': 1.6, opacity: 0.35 }, s);
            const seg = svgEl('line', { stroke: '#a9d2ff', 'stroke-width': 3, 'stroke-linecap': 'round' }, s);
            const samples = svgEl('g', null, s);
            for (let st = 0; st <= 40; st += 2) svgEl('circle', { r: 1.3, fill: '#f3f4f8' }, samples);
            const blast = svgEl('circle', { fill: 'none', stroke: '#ffb02e', 'stroke-width': 2.5 }, s);
            const blastIn = svgEl('circle', { fill: 'rgba(255,176,46,0.25)' }, s);
            return { fire: i * 9, dx, dy, hitTick: hitTick || 15, hitAt: hitAt || 150, hitWhat, trail, seg, samples, blast, blastIn };
        });
        const missNote = text(s, 0, 0, 'passes over → cliff', 't-small t-ray', { 'text-anchor': 'end' });
        const TICK = 0.13;
        const LAST = 27 + 15 + 5;
        const D = LAST * TICK + 1.4;
        function render(t, still) {
            const tick = still ? LAST : t / TICK;
            let fired = 0;
            shells.forEach((sh) => {
                const local = tick - sh.fire;             // ticks since this shell launched
                if (local < 0) { [sh.trail, sh.seg, sh.samples, sh.blast, sh.blastIn].forEach((n) => show(n, false)); return; }
                fired++;
                const k = Math.min(Math.floor(local) + 1, sh.hitTick);   // current flight tick (1-based)
                const flying = local < sh.hitTick;
                const segEnd = flying ? Math.min(k * 10, sh.hitTick === k ? sh.hitAt : k * 10) : sh.hitAt;
                const segStart = flying ? (k - 1) * 10 : sh.hitAt;
                const a = toPx(sh.dx * segStart, sh.dy * segStart), b = toPx(sh.dx * segEnd, sh.dy * segEnd);
                const e = toPx(sh.dx * sh.hitAt, sh.dy * sh.hitAt);
                show(sh.trail, true);
                setAttrs(sh.trail, { x2: (flying ? b.x : e.x).toFixed(1), y2: (flying ? b.y : e.y).toFixed(1) });
                show(sh.seg, flying && !still); show(sh.samples, flying && !still);
                if (flying && !still) {
                    setAttrs(sh.seg, { x1: a.x.toFixed(1), y1: a.y.toFixed(1), x2: b.x.toFixed(1), y2: b.y.toFixed(1) });
                    Array.from(sh.samples.children).forEach((c, idx) => {
                        const f = idx / (sh.samples.children.length - 1);
                        setAttrs(c, { cx: lerp(a.x, b.x, f).toFixed(1), cy: lerp(a.y, b.y, f).toFixed(1) });
                    });
                }
                const since = local - sh.hitTick;            // ticks since contact
                const bl = still ? 4 : clamp(since + 1, 0, 4);
                const blOn = still || (since >= 0 && since < 5.5);
                show(sh.blast, blOn && bl > 0); show(sh.blastIn, blOn && bl > 0);
                if (blOn && bl > 0) {
                    const r = 3 + bl * 3.5;
                    setAttrs(sh.blast, { cx: e.x.toFixed(1), cy: e.y.toFixed(1), r: r.toFixed(1), opacity: still ? 0.9 : String(clamp(1 - (since - 3) / 2.5, 0.15, 1)) });
                    setAttrs(sh.blastIn, { cx: e.x.toFixed(1), cy: e.y.toFixed(1), r: (r * 0.6).toFixed(1) });
                }
            });
            const miss = shells.find((sh) => sh.hitWhat === 'block');
            if (miss) {
                const e = toPx(miss.dx * miss.hitAt, miss.dy * miss.hitAt);
                setAttrs(missNote, { x: (e.x - 12).toFixed(1), y: (e.y - 16).toFixed(1) });
                show(missNote, still || tick - miss.fire >= miss.hitTick);
            }
            if (status) status.textContent = still ? '4 shells · 9 ticks apart' : 'tick ' + Math.floor(tick) + ' · shells fired ' + fired + '/4';
        }
        return timeline(fig, D, render);
    }

    /* ─── 08 · Hellfire tornado (Diyuyehuo2Procedure) ─────────────────────────
       FLIGHT_SPEED 1.7, HOMING_ACCEL 0.12, HIT_RADIUS 4.5, PHASE_1_MAX_TICKS 80 (28–31,
       127–172); GROW_TICKS 20, ACTIVE_TICKS 200 (46–47, 94–124); TORNADO_BOTTOM_RADIUS 6 (34);
       control on Ring > 16 only, CONTROL_FULL_RADIUS 12, CONTROL_OUTER_RADIUS 18, pull onto the
       wall (inside → out, outside → in), swirl only inside 12 m, MAX_CONTROL_SPEED 2.4
       (41–51, 231–284). The motion on the ring is drawn schematically (no game drag or
       collisions are simulated); the radii and who is affected follow the code. */
    function initTornado(fig) {
        const s = fig.querySelector('svg');
        const status = fig.querySelector('[data-ep-status]');
        const PX = 6;
        const B = { x: 48, y: 178 };
        const T0 = { x: 64, y: 8 };   // metres from Epsilon (screen y down)
        const toPx = (p) => ({ x: B.x + p.x * PX, y: B.y + p.y * PX });
        const outer = svgEl('circle', { class: 'p-guide', fill: 'rgba(255,97,112,0.04)' }, s);
        const full = svgEl('circle', { class: 'p-guide' }, s);
        full.style.stroke = 'rgba(255,97,112,0.55)';
        const wallC = svgEl('circle', { fill: 'none', stroke: '#ffb02e', 'stroke-width': 5, 'stroke-dasharray': '10 7', 'stroke-linecap': 'round' }, s);
        const lblOuter = text(s, 0, 0, '18 m', 't-small t-danger');
        const lblFull = text(s, 0, 0, '12 m', 't-small t-danger');
        const lblWall = text(s, 0, 0, 'wall 6 m', 't-small t-boss');
        const trail = svgEl('polyline', { class: 'p-ray', points: '' }, s);
        trail.style.opacity = '0.6';
        const shot = svgEl('circle', { r: 6, fill: '#ffb02e' }, s);
        const boss = svgEl('g', { transform: `translate(${B.x},${B.y})` }, s);
        diamond(boss, 'p-boss', 10);

        // Phase 1 simulation (once): homing shot vs a slowly drifting target.
        const path = [];
        // Launched along Epsilon's fire direction (here 14° off the target's current bearing).
        const launch = Math.atan2(T0.y, T0.x) - 14 * DEG;
        let P = { x: 0, y: 0 }, V = { x: Math.cos(launch) * 1.7, y: Math.sin(launch) * 1.7 };
        let Tp = { x: T0.x, y: T0.y };
        const tPath = [];
        let trig = 80;
        for (let k = 1; k <= 80; k++) {
            Tp = { x: Tp.x - 0.06, y: Tp.y + 0.03 };
            const dx = Tp.x - P.x, dy = Tp.y - P.y, dl = Math.hypot(dx, dy) || 1;
            V = { x: V.x + dx / dl * 0.12, y: V.y + dy / dl * 0.12 };
            const vl = Math.hypot(V.x, V.y);
            if (vl > 1.7) V = { x: V.x / vl * 1.7, y: V.y / vl * 1.7 };
            P = { x: P.x + V.x, y: P.y + V.y };
            path.push({ x: P.x, y: P.y });
            tPath.push({ x: Tp.x, y: Tp.y });
            if (Math.hypot(Tp.x - P.x, Tp.y - P.y) - 0.3 <= 4.5) { trig = k; break; }
        }
        const center = path[path.length - 1];
        const ents = [
            { off: null, hostile: true, label: 'target' },
            { off: { x: -9, y: 7 }, hostile: true },
            { off: { x: 13, y: -7 }, hostile: true },
            { off: { x: 4, y: -16 }, hostile: true },
            { off: { x: 21, y: 9 }, hostile: true, label: 'out of reach' },
            { off: { x: -6, y: -9 }, hostile: false, label: 'neutral' },
        ].map((e) => {
            const dot = svgEl('circle', { r: 6.5, fill: e.hostile ? '#ff6170' : 'rgba(255,255,255,0.55)' }, s);
            const lbl = e.label ? text(s, 0, 0, e.label, e.hostile ? 't-small' : 't-small t-dim') : null;
            return Object.assign(e, { dot, lbl });
        });
        const GROW = 20, SHOW = 110;
        const TICK = 0.06;
        const TOTAL_TICKS = trig + GROW + SHOW;
        const D = TOTAL_TICKS * TICK + 1.2;

        function simulateControl(e, ticks) {
            // Start position relative to the tornado centre (metres).
            let start;
            if (!e.off) { const last = tPath[tPath.length - 1]; start = { x: last.x - center.x, y: last.y - center.y }; }
            else start = { x: e.off.x, y: e.off.y };
            let r = Math.hypot(start.x, start.y), a = Math.atan2(start.y, start.x);
            if (!e.hostile) return { r, a };
            for (let k = 0; k < ticks; k++) {
                const g = smooth(Math.min(1, (k + 1) / GROW));
                const outerR = 18 * g, fullR = 12 * g, wall = 6 * g;
                if (r > outerR) continue;
                const pull = r <= fullR ? 1 : smooth((outerR - r) / Math.max(outerR - fullR, 0.1));
                r += (wall - r) * 0.09 * pull;
                if (r <= fullR) a += 0.6 * clamp(r / Math.max(fullR, 0.1), 0, 1) * g * 0.07;
            }
            return { r, a };
        }
        function render(t, still) {
            const tick = still ? TOTAL_TICKS : t / TICK;
            const inFlight = tick < trig;
            const n = Math.max(1, Math.min(path.length, Math.floor(tick) + 1));
            const pts = [{ x: 0, y: 0 }, ...path.slice(0, n)];
            trail.setAttribute('points', pts.map((p) => { const q = toPx(p); return q.x.toFixed(1) + ',' + q.y.toFixed(1); }).join(' '));
            const sp = toPx(pts[pts.length - 1]);
            setAttrs(shot, { cx: sp.x.toFixed(1), cy: sp.y.toFixed(1) });
            show(shot, inFlight && !still);
            const ct = Math.max(0, tick - trig);
            const g = still ? 1 : smooth(Math.min(1, ct / GROW));
            const cp = toPx(center);
            const on = !inFlight || still;
            [outer, full, wallC, lblOuter, lblFull, lblWall].forEach((nd) => show(nd, on && g > 0.02));
            if (on) {
                setAttrs(outer, { cx: cp.x, cy: cp.y, r: (18 * g * PX).toFixed(1) });
                setAttrs(full, { cx: cp.x, cy: cp.y, r: (12 * g * PX).toFixed(1) });
                setAttrs(wallC, { cx: cp.x, cy: cp.y, r: (6 * g * PX).toFixed(1), 'stroke-dashoffset': (-ct * 3).toFixed(1) });
                setAttrs(lblOuter, { x: (cp.x + 18 * g * PX * 0.71 + 4).toFixed(1), y: (cp.y - 18 * g * PX * 0.71).toFixed(1) });
                setAttrs(lblFull, { x: (cp.x + 12 * g * PX * 0.71 + 4).toFixed(1), y: (cp.y - 12 * g * PX * 0.71).toFixed(1) });
                setAttrs(lblWall, { x: cp.x.toFixed(1), y: (cp.y + 6 * g * PX + 22).toFixed(1), 'text-anchor': 'middle' });
            }
            ents.forEach((e) => {
                let p;
                if (inFlight && !still) {
                    p = e.off ? { x: center.x + e.off.x, y: center.y + e.off.y } : tPath[Math.min(tPath.length - 1, Math.floor(tick))];
                } else {
                    const st = simulateControl(e, Math.floor(still ? 140 : ct));
                    p = { x: center.x + Math.cos(st.a) * st.r, y: center.y + Math.sin(st.a) * st.r };
                }
                const q = toPx(p);
                setAttrs(e.dot, { cx: q.x.toFixed(1), cy: q.y.toFixed(1) });
                if (e.lbl) {
                    if (!e.off) {
                        // The target's own label only while the shot is chasing it.
                        show(e.lbl, inFlight && !still);
                        setAttrs(e.lbl, { x: (q.x + 10).toFixed(1), y: (q.y - 10).toFixed(1) });
                    } else if (q.x > 440) {
                        setAttrs(e.lbl, { x: q.x.toFixed(1), y: (q.y + 26).toFixed(1), 'text-anchor': 'middle' });
                    } else {
                        setAttrs(e.lbl, { x: (q.x + 10).toFixed(1), y: (q.y - 10).toFixed(1), 'text-anchor': 'start' });
                    }
                }
            });
            if (status) {
                if (still) status.textContent = 'phase 3 · lasts 200 ticks';
                else if (inFlight) status.textContent = 'phase 1 · homing · tick ' + Math.floor(tick);
                else if (ct < GROW) status.textContent = 'phase 2 · growing · ' + Math.floor(ct) + '/20';
                else status.textContent = 'phase 3 · control · ' + Math.floor(ct - GROW) + '/200';
            }
        }
        return timeline(fig, D, render);
    }

    /* ─── Boot ────────────────────────────────────────────────────────────── */

    /* ─── 09 · Damage flow ────────────────────────────────────────────────────
       Same stepping highlight as figure 01, walking one hit through the shared procedures:
       skill → DodProcedure / Dod3Procedure → BlockdamageProcedure → Attacked2Procedure
       (hit reaction, stun) → KnockbackProcedure. */
    function initChain(fig) {
        return initTick(fig, { step: 0.9, pause: 0.8, label: (n) => 'hit ' + n });
    }

    const registry = {
        tick: initTick,
        chain: initChain,
        distance: initDistance,
        flashdrive: initFlashdrive,
        pathfind: initPathfind,
        dandelion: initDandelion,
        ringnet: initRingNet,
        railgun: initRailgun,
        tornado: initTornado,
    };
    function boot() {
        document.querySelectorAll('figure[data-ep]').forEach((fig) => {
            const fn = registry[fig.dataset.ep];
            if (!fn) return;
            try {
                const api = fn(fig);
                if (api) register(fig, api);
            } catch (err) {
                console.error('[epsilon-explainer] ' + fig.dataset.ep + ' failed to start', err);
            }
        });
        wireRunners();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
