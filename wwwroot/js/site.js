/*!
 * Showheel — site.js
 * Shared interaction layer. Vanilla JS, no dependencies. Include once per page:
 *   @section Scripts { <script src="~/js/site.js" asp-append-version="true"></script> }
 *
 * COMPONENT API (markup contract — styles live in site.css)
 * ---------------------------------------------------------------------------
 * [data-reveal]               Hidden until scrolled into view, then fades/slides in.
 *   [data-reveal-delay="1-6"] Optional stagger, 80 ms per step.
 *                             .kd-card / .kd-pair / .kd-side-card / .kd-mason-item are
 *                             auto-revealed (with automatic stagger) even without the attribute.
 *
 * [data-lightbox]             Container. Clicking an <img> inside a <figure> (any depth), or an
 *                             a[data-lightbox-item], opens the fullscreen viewer.
 *   img[data-full]            Optional hi-res URL (default: the img's src; for a[data-lightbox-item]
 *                             its data-full or href).
 *   <figcaption>              Caption (fallback: data-caption on the anchor, then img alt).
 *                             Only items currently visible (not filtered out) are in the sequence.
 *                             Keys: ← → Home End Esc. Swipe left/right on touch, swipe down closes.
 *                             Images inside a plain <a href> (without data-lightbox-item) stay links.
 *
 * .kd-filter[data-filter-for="GALLERY_ID"] > button.kd-chip[data-filter="all" | "tag"]
 *                             Filters the DIRECT children of #GALLERY_ID by data-tags="tag1 tag2".
 *                             Active chip: .is-active + aria-pressed="true". Hidden items get the
 *                             [hidden] attribute + .is-filtered-out. A count badge is appended to each
 *                             chip (opt out: data-filter-count="off" on the .kd-filter). A chip that
 *                             starts with .is-active / aria-pressed="true" sets the initial filter.
 *
 * [data-tilt="7"]             3D tilt + glare that follows the pointer (max degrees, default 7).
 *                             Fine pointers only; off with prefers-reduced-motion. Put it on a
 *                             wrapper element, not on an <img> (the glare is an injected child).
 * [data-cursor="LABEL"]       Optional short label shown next to the HUD cursor reticle on hover.
 *
 * CSS-only (see site.css):
 *   .kd-hud                   Corner brackets (::before). Vars: --kd-hud-inset (8px; negative draws
 *                             outside — needs no overflow:hidden), --kd-hud-len, --kd-hud-w, --kd-hud-color.
 *   .kd-placeholder(--video|--image)[data-label] > span
 *                             "Standby" media slot (16:9 / 4:3). Has its own brackets, which switch off
 *                             when it is a direct child of a .kd-hud wrapper.
 *   .kd-badge(--cyan|--muted|--solid), .kd-chip, .kd-rule (animated heading rule).
 * Home page:                  canvas[data-starfield], [data-scramble], [data-terminal], [data-hud-pointer].
 */
(() => {
    'use strict';
    if (window.__kdSiteInit) return;
    window.__kdSiteInit = true;

    const doc = document;
    const root = doc.documentElement;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    const hasIO = 'IntersectionObserver' in window;
    const $$ = (sel, ctx = doc) => Array.from(ctx.querySelectorAll(sel));
    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
    const pad2 = (n) => String(n).padStart(2, '0');
    const EASE = 'cubic-bezier(.2,.8,.2,1)';

    root.classList.add('kd-js', 'kd-reveal-armed');

    const safe = (name, fn) => {
        try { fn(); } catch (err) { console.error('[site.js] ' + name + ' failed', err); }
    };

    /* ─── Top bar: scrolled state, progress bar, nav scrollspy ───────────── */
    function initChrome() {
        const bar = doc.querySelector('.kd-topbar');
        const progress = doc.querySelector('.kd-progress');
        const cssTimeline = window.CSS && CSS.supports && CSS.supports('animation-timeline: scroll()');
        let queued = false;
        const update = () => {
            queued = false;
            const y = window.scrollY;
            if (bar) bar.classList.toggle('is-scrolled', y > 24);
            if (progress && !cssTimeline) {
                const max = root.scrollHeight - window.innerHeight;
                progress.style.setProperty('--kd-progress', max > 0 ? clamp(y / max, 0, 1).toFixed(4) : '0');
            }
        };
        const queue = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
        window.addEventListener('scroll', queue, { passive: true });
        window.addEventListener('resize', queue, { passive: true });
        update();

        const work = doc.getElementById('work');
        const workLink = doc.querySelector('.kd-nav a[href="/#work"]');
        if (work && workLink && hasIO) {
            new IntersectionObserver(([entry]) => {
                workLink.classList.toggle('is-active', entry.isIntersecting);
            }, { rootMargin: '-40% 0px -55% 0px' }).observe(work);
        }
    }

    /* ─── Hero background parallax (.background-image + data-motion-*) ──── */
    function initParallax() {
        const targets = $$('.background-image');
        if (!targets.length || reduceMotion) return;
        const items = targets.map((el) => ({
            el,
            host: el.parentElement,
            depth: parseFloat(el.dataset.motionDepth || '1') || 1,
            scale: parseFloat(el.dataset.motionScale || '1.08') || 1.08,
            x: 0, y: 0, sy: 0, visible: true
        }));
        let tx = 0, ty = 0, raf = 0;
        const STRENGTH = 34;

        const frame = () => {
            raf = 0;
            let moving = false;
            items.forEach((it) => {
                if (!it.visible) return;
                const goalX = -tx * STRENGTH * it.depth;
                const goalY = -ty * STRENGTH * it.depth;
                it.x += (goalX - it.x) * 0.08;
                it.y += (goalY - it.y) * 0.08;
                const top = it.host ? it.host.getBoundingClientRect().top : 0;
                it.sy = top < 0 ? -top * 0.28 : 0;
                if (Math.abs(goalX - it.x) > 0.05 || Math.abs(goalY - it.y) > 0.05) moving = true;
                it.el.style.transform =
                    `translate3d(${it.x.toFixed(2)}px, ${(it.y + it.sy).toFixed(2)}px, 0) scale(${it.scale})`;
            });
            if (moving) raf = requestAnimationFrame(frame);
        };
        const kick = () => { if (!raf) raf = requestAnimationFrame(frame); };

        items.forEach((it) => { it.el.style.transform = `translate3d(0,0,0) scale(${it.scale})`; });
        if (hasIO) {
            const io = new IntersectionObserver((entries) => {
                entries.forEach((e) => {
                    const it = items.find((i) => i.host === e.target);
                    if (it) it.visible = e.isIntersecting;
                });
                kick();
            });
            items.forEach((it) => it.host && io.observe(it.host));
        }
        if (finePointer) {
            doc.addEventListener('mousemove', (e) => {
                const nx = (e.clientX / window.innerWidth) * 2 - 1;
                const ny = (e.clientY / window.innerHeight) * 2 - 1;
                tx = nx * Math.abs(nx) * 0.6 + nx * 0.4;
                ty = ny * Math.abs(ny) * 0.6 + ny * 0.4;
                kick();
            }, { passive: true });
        }
        window.addEventListener('scroll', kick, { passive: true });
    }

    /* ─── Scroll reveal ─────────────────────────────────────────────────── */
    function initReveal() {
        $$('.kd-card, .kd-pair, .kd-side-card, .kd-mason-item').forEach((el) => {
            if (!el.hasAttribute('data-reveal')) {
                el.setAttribute('data-reveal', '');
                el.setAttribute('data-reveal-auto', '');
            }
        });
        const items = $$('[data-reveal]');
        if (!items.length) return;
        const show = (el) => el.classList.add('is-in');
        if (reduceMotion || !hasIO) { items.forEach(show); return; }

        const io = new IntersectionObserver((entries) => {
            let step = 0;
            entries
                .filter((e) => e.isIntersecting)
                .sort((a, b) => (a.boundingClientRect.top - b.boundingClientRect.top) ||
                                (a.boundingClientRect.left - b.boundingClientRect.left))
                .forEach((e) => {
                    const el = e.target;
                    if (el.hasAttribute('data-reveal-auto')) {
                        el.style.setProperty('--kd-reveal-delay', `${Math.min(step, 6) * 80}ms`);
                        step += 1;
                    }
                    show(el);
                    io.unobserve(el);
                });
        }, { threshold: 0, rootMargin: '0px 0px -7% 0px' });
        items.forEach((el) => io.observe(el));
    }

    /* ─── Lightbox ──────────────────────────────────────────────────────── */
    function initLightbox() {
        const containers = $$('[data-lightbox]');
        if (!containers.length) return;

        const TRIGGER = 'a[data-lightbox-item], figure img';
        const isVisible = (el) => !el.closest('[hidden], .is-filtered-out') && el.getClientRects().length > 0;
        const isTrigger = (el, container) => {
            if (!el || el.closest('[data-lightbox]') !== container) return false;
            if (el.tagName === 'IMG') {
                const fig = el.closest('figure');
                if (!fig || !container.contains(fig)) return false;
                if (el.closest('a')) return false; // a[data-lightbox-item] or a real link
            }
            return true;
        };
        const collect = (container) => $$(TRIGGER, container).filter((el) => isTrigger(el, container) && isVisible(el));
        const textOf = (node) => (node ? node.textContent : '').replace(/\s+/g, ' ').trim();
        const describe = (el) => {
            if (el.tagName === 'A') {
                const img = el.querySelector('img');
                const fig = el.closest('figure');
                return {
                    src: el.dataset.full || el.getAttribute('href'),
                    thumb: img ? (img.currentSrc || img.src) : '',
                    caption: textOf(fig && fig.querySelector('figcaption')) || el.dataset.caption || (img && img.alt) || el.title || '',
                    alt: (img && img.alt) || el.dataset.caption || ''
                };
            }
            const fig = el.closest('figure');
            return {
                src: el.dataset.full || el.currentSrc || el.src,
                thumb: el.currentSrc || el.src,
                caption: textOf(fig && fig.querySelector('figcaption')) || el.alt || '',
                alt: el.alt || ''
            };
        };

        // Make image triggers keyboard reachable.
        containers.forEach((container) => {
            $$(TRIGGER, container).filter((el) => isTrigger(el, container)).forEach((el) => {
                el.setAttribute('aria-haspopup', 'dialog');
                if (!el.dataset.cursor) el.dataset.cursor = 'VIEW';
                if (el.tagName === 'IMG') {
                    el.classList.add('kd-lb-trigger');
                    el.tabIndex = 0;
                    el.setAttribute('role', 'button');
                    el.setAttribute('aria-label', 'View larger' + (el.alt ? ': ' + el.alt : ''));
                }
            });
        });

        let lb = null, ui = null;
        const state = { items: [], index: 0, trigger: null, token: 0, closeTimer: 0, inerted: [], swipe: null, swallowClick: false };
        const icon = (d) => `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path d="${d}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

        const build = () => {
            lb = doc.createElement('div');
            lb.className = 'kd-lightbox';
            lb.hidden = true;
            lb.setAttribute('role', 'dialog');
            lb.setAttribute('aria-modal', 'true');
            lb.setAttribute('aria-label', 'Image viewer');
            lb.innerHTML = `
                <div class="kd-lightbox-backdrop" data-lb-close></div>
                <div class="kd-lightbox-top">
                    <span class="kd-lightbox-counter" aria-live="polite"></span>
                    <span class="kd-lightbox-hint" aria-hidden="true">← → navigate · esc close</span>
                    <button type="button" class="kd-lightbox-btn kd-lightbox-close" data-lb-close aria-label="Close viewer">${icon('M6 6l12 12M18 6L6 18')}</button>
                </div>
                <figure class="kd-lightbox-stage">
                    <div class="kd-lightbox-frame">
                        <img class="kd-lightbox-img" alt="" draggable="false" />
                        <span class="kd-lightbox-loader" aria-hidden="true"></span>
                    </div>
                    <figcaption class="kd-lightbox-caption"></figcaption>
                </figure>
                <button type="button" class="kd-lightbox-btn kd-lightbox-nav kd-lightbox-prev" data-lb-prev aria-label="Previous image">${icon('M15 5l-7 7 7 7')}</button>
                <button type="button" class="kd-lightbox-btn kd-lightbox-nav kd-lightbox-next" data-lb-next aria-label="Next image">${icon('M9 5l7 7-7 7')}</button>`;
            doc.body.appendChild(lb);
            ui = {
                counter: lb.querySelector('.kd-lightbox-counter'),
                stage: lb.querySelector('.kd-lightbox-stage'),
                frame: lb.querySelector('.kd-lightbox-frame'),
                img: lb.querySelector('.kd-lightbox-img'),
                caption: lb.querySelector('.kd-lightbox-caption'),
                close: lb.querySelector('.kd-lightbox-close'),
                prev: lb.querySelector('[data-lb-prev]'),
                next: lb.querySelector('[data-lb-next]')
            };
            lb.addEventListener('click', (e) => {
                if (state.swallowClick) { state.swallowClick = false; return; }
                const t = e.target;
                if (t.closest('[data-lb-prev]')) return step(-1);
                if (t.closest('[data-lb-next]')) return step(1);
                if (t.closest('[data-lb-close]') || t === ui.stage || t === ui.frame || t === lb) close();
            });
            ui.stage.addEventListener('pointerdown', (e) => {
                if (e.pointerType === 'mouse' || !e.isPrimary) return;
                state.swipe = { x: e.clientX, y: e.clientY };
            });
            ui.stage.addEventListener('pointerup', (e) => {
                const s = state.swipe;
                state.swipe = null;
                if (!s) return;
                const dx = e.clientX - s.x, dy = e.clientY - s.y;
                if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.3) {
                    state.swallowClick = true;
                    setTimeout(() => { state.swallowClick = false; }, 350);
                    step(dx < 0 ? 1 : -1);
                } else if (dy > 90 && dy > Math.abs(dx) * 1.3) {
                    state.swallowClick = true;
                    setTimeout(() => { state.swallowClick = false; }, 350);
                    close();
                }
            });
            ui.stage.addEventListener('pointercancel', () => { state.swipe = null; });
        };

        const lockPage = (on) => {
            if (on) {
                const gap = window.innerWidth - root.clientWidth;
                root.style.setProperty('--kd-scrollbar-gap', gap + 'px');
                root.classList.add('kd-scroll-locked');
                state.inerted = Array.from(doc.body.children).filter((el) => el !== lb && !el.inert && el.tagName !== 'SCRIPT');
                state.inerted.forEach((el) => { el.inert = true; });
            } else {
                root.classList.remove('kd-scroll-locked');
                root.style.removeProperty('--kd-scrollbar-gap');
                state.inerted.forEach((el) => { el.inert = false; });
                state.inerted = [];
            }
        };

        const render = (dir) => {
            const total = state.items.length;
            const item = state.items[state.index];
            ui.counter.textContent = `${pad2(state.index + 1)} / ${pad2(total)}`;
            ui.caption.textContent = item.caption;
            ui.caption.hidden = !item.caption;
            ui.prev.hidden = ui.next.hidden = total < 2;

            const token = ++state.token;
            const img = ui.img;
            const reveal = () => {
                if (!reduceMotion && img.animate) {
                    img.animate(
                        [{ opacity: 0, translate: `${dir * 36}px 0`, scale: dir ? '1' : '0.97' },
                         { opacity: 1, translate: '0 0', scale: '1' }],
                        { duration: 380, easing: EASE }
                    );
                }
            };
            img.alt = item.alt;
            if (item.thumb && item.thumb !== item.src) {
                img.src = item.thumb;
                reveal();
            }
            ui.frame.classList.add('is-loading');
            const full = new Image();
            full.decoding = 'async';
            const done = () => {
                if (token !== state.token) return;
                ui.frame.classList.remove('is-loading');
                const wasThumb = img.getAttribute('src') === item.thumb && item.thumb !== item.src;
                img.src = item.src;
                if (!wasThumb) reveal();
            };
            full.onload = done;
            full.onerror = done;
            full.src = item.src;

            // Warm up neighbours.
            [1, -1].forEach((d) => {
                const n = state.items[(state.index + d + total) % total];
                if (n && total > 1) { const pre = new Image(); pre.src = n.src; }
            });
        };

        const go = (index, dir) => {
            const total = state.items.length;
            state.index = (index + total) % total;
            render(dir);
        };
        const step = (dir) => { if (state.items.length > 1) go(state.index + dir, dir); };

        const focusables = () => [ui.close, ui.prev, ui.next].filter((b) => !b.hidden);
        const onKey = (e) => {
            switch (e.key) {
                case 'Escape': e.preventDefault(); close(); break;
                case 'ArrowRight': e.preventDefault(); step(1); break;
                case 'ArrowLeft': e.preventDefault(); step(-1); break;
                case 'Home': e.preventDefault(); go(0, -1); break;
                case 'End': e.preventDefault(); go(state.items.length - 1, 1); break;
                case 'Tab': {
                    const list = focusables();
                    const i = list.indexOf(doc.activeElement);
                    e.preventDefault();
                    const next = e.shiftKey ? (i <= 0 ? list.length - 1 : i - 1) : (i + 1) % list.length;
                    list[next].focus();
                    break;
                }
                default: break;
            }
        };

        const open = (items, index, trigger) => {
            if (!lb) build();
            clearTimeout(state.closeTimer);
            state.items = items.map(describe);
            state.trigger = trigger;
            lb.hidden = false;
            lockPage(true);
            go(index, 0);
            requestAnimationFrame(() => lb.classList.add('is-open'));
            ui.close.focus({ preventScroll: true });
            doc.addEventListener('keydown', onKey, true);
        };

        function close() {
            if (!lb || lb.hidden) return;
            lb.classList.remove('is-open');
            doc.removeEventListener('keydown', onKey, true);
            lockPage(false);
            state.token += 1;
            const finish = () => { lb.hidden = true; ui.img.removeAttribute('src'); };
            if (reduceMotion) finish(); else state.closeTimer = setTimeout(finish, 280);
            if (state.trigger && doc.contains(state.trigger)) state.trigger.focus({ preventScroll: true });
        }

        const tryOpen = (target, e) => {
            const el = target.closest('a[data-lightbox-item]') || target.closest('figure img');
            if (!el) return;
            const container = el.closest('[data-lightbox]');
            if (!container || !isTrigger(el, container)) return;
            const items = collect(container);
            const index = items.indexOf(el);
            if (index < 0) return;
            e.preventDefault();
            open(items, index, el);
        };
        doc.addEventListener('click', (e) => {
            if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            if (!(e.target instanceof Element)) return;
            tryOpen(e.target, e);
        });
        doc.addEventListener('keydown', (e) => {
            if ((e.key === 'Enter' || e.key === ' ') && e.target instanceof Element && e.target.classList.contains('kd-lb-trigger')) {
                tryOpen(e.target, e);
            }
        });
    }

    /* ─── Filter chips ──────────────────────────────────────────────────── */
    function initFilters() {
        $$('.kd-filter[data-filter-for]').forEach((bar) => {
            const gallery = doc.getElementById(bar.dataset.filterFor);
            const chips = $$('.kd-chip[data-filter]', bar);
            if (!gallery || !chips.length) return;

            const items = () => Array.from(gallery.children).filter((el) => !el.matches('script, template, style'));
            const tagsOf = (el) => (el.dataset.tags || '').toLowerCase().split(/\s+/).filter(Boolean);
            const keyOf = (chip) => (chip.dataset.filter || 'all').trim().toLowerCase();
            const matches = (el, key) => key === 'all' || tagsOf(el).includes(key);

            if (bar.dataset.filterCount !== 'off') {
                const all = items();
                chips.forEach((chip) => {
                    let count = chip.querySelector('.kd-chip-count');
                    if (!count) {
                        count = doc.createElement('span');
                        count.className = 'kd-chip-count';
                        chip.appendChild(count);
                    }
                    count.textContent = String(all.filter((el) => matches(el, keyOf(chip))).length);
                });
            }

            const status = doc.createElement('p');
            status.className = 'visually-hidden';
            status.setAttribute('role', 'status');
            bar.insertAdjacentElement('afterend', status);

            const setShown = (el, on) => {
                el.hidden = !on;
                el.classList.toggle('is-filtered-out', !on);
                el.classList.remove('is-filtering-out');
            };

            let timer = 0;
            const apply = (chip, animate) => {
                const key = keyOf(chip);
                chips.forEach((c) => {
                    const on = c === chip;
                    c.classList.toggle('is-active', on);
                    c.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                gallery.dataset.activeFilter = key;
                const all = items();
                const show = all.filter((el) => matches(el, key));
                const hide = all.filter((el) => !matches(el, key));
                const label = (chip.firstChild && chip.firstChild.nodeType === 3 ? chip.firstChild.textContent : chip.textContent).trim();
                status.textContent = key === 'all'
                    ? `Showing all ${all.length} items`
                    : `Showing ${show.length} of ${all.length} items: ${label}`;

                clearTimeout(timer);
                if (!animate || reduceMotion) {
                    show.forEach((el) => setShown(el, true));
                    hide.forEach((el) => setShown(el, false));
                    return;
                }
                show.forEach((el) => el.classList.remove('is-filtering-out'));
                const leaving = hide.filter((el) => !el.hidden);
                leaving.forEach((el) => el.classList.add('is-filtering-out'));

                timer = setTimeout(() => {
                    const before = new Map();
                    show.forEach((el) => { if (!el.hidden) before.set(el, el.getBoundingClientRect()); });
                    hide.forEach((el) => setShown(el, false));
                    let n = 0;
                    show.forEach((el) => {
                        const wasHidden = el.hidden;
                        setShown(el, true);
                        if (wasHidden) {
                            if (el.classList.contains('is-in')) {
                                // CSS reveal animation replays when an element is displayed again.
                                el.style.setProperty('--kd-reveal-delay', `${Math.min(n, 8) * 40}ms`);
                            } else if (!el.hasAttribute('data-reveal') && el.animate) {
                                el.animate([{ opacity: 0, scale: '0.96' }, { opacity: 1, scale: '1' }],
                                    { duration: 360, delay: Math.min(n, 8) * 40, easing: EASE, fill: 'backwards' });
                            }
                            n += 1;
                            return;
                        }
                        const r0 = before.get(el);
                        if (!r0 || !el.animate) return;
                        const r1 = el.getBoundingClientRect();
                        const dx = r0.left - r1.left, dy = r0.top - r1.top;
                        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
                            el.animate([{ translate: `${dx}px ${dy}px` }, { translate: '0 0' }],
                                { duration: 460, easing: EASE });
                        }
                    });
                }, 170);
            };

            chips.forEach((chip) => {
                if (chip.tagName === 'BUTTON' && !chip.hasAttribute('type')) chip.type = 'button';
                chip.addEventListener('click', () => apply(chip, true));
            });
            const initial = chips.find((c) => c.classList.contains('is-active') || c.getAttribute('aria-pressed') === 'true') ||
                            chips.find((c) => keyOf(c) === 'all') || chips[0];
            apply(initial, false);
            status.textContent = '';
        });
    }

    /* ─── Tilt + glare ──────────────────────────────────────────────────── */
    function initTilt() {
        if (reduceMotion || !finePointer) return;
        const VOID = /^(IMG|VIDEO|IFRAME|INPUT|CANVAS)$/;
        $$('[data-tilt]').forEach((el) => {
            const max = clamp(parseFloat(el.getAttribute('data-tilt')) || 7, 1, 20);
            if (!VOID.test(el.tagName) && !el.querySelector(':scope > .kd-tilt-glare')) {
                const glare = doc.createElement('span');
                glare.className = 'kd-tilt-glare';
                glare.setAttribute('aria-hidden', 'true');
                el.appendChild(glare);
            }
            let rect = null, raf = 0, px = 0.5, py = 0.5;
            const render = () => {
                raf = 0;
                el.style.setProperty('--kd-rx', `${((0.5 - py) * max * 2).toFixed(2)}deg`);
                el.style.setProperty('--kd-ry', `${((px - 0.5) * max * 2).toFixed(2)}deg`);
                el.style.setProperty('--kd-gx', `${(px * 100).toFixed(1)}%`);
                el.style.setProperty('--kd-gy', `${(py * 100).toFixed(1)}%`);
            };
            el.addEventListener('pointerenter', (e) => {
                if (e.pointerType !== 'mouse') return;
                rect = el.getBoundingClientRect();
                el.classList.add('is-tilting');
            });
            el.addEventListener('pointermove', (e) => {
                if (e.pointerType !== 'mouse') return;
                if (!rect) { rect = el.getBoundingClientRect(); el.classList.add('is-tilting'); }
                px = clamp((e.clientX - rect.left) / rect.width, 0, 1);
                py = clamp((e.clientY - rect.top) / rect.height, 0, 1);
                if (!raf) raf = requestAnimationFrame(render);
            });
            el.addEventListener('pointerleave', () => {
                rect = null;
                if (raf) { cancelAnimationFrame(raf); raf = 0; }
                el.classList.remove('is-tilting');
                ['--kd-rx', '--kd-ry'].forEach((p) => el.style.removeProperty(p));
            });
            window.addEventListener('scroll', () => { rect = null; }, { passive: true });
        });
    }

    /* ─── HUD cursor reticle (system cursor stays visible) ──────────────── */
    function initCursor() {
        if (reduceMotion || !finePointer) return;
        const el = doc.createElement('div');
        el.className = 'kd-cursor';
        el.setAttribute('aria-hidden', 'true');
        el.innerHTML = '<span class="kd-cursor-reticle"></span><span class="kd-cursor-label"></span>';
        doc.body.appendChild(el);
        const label = el.querySelector('.kd-cursor-label');
        const ACTIVE = 'a[href], button, [role="button"], [data-tilt], [data-cursor], summary, label[for], .kd-chip';
        const BLOCKED = 'input, textarea, select, iframe, video, [contenteditable=""], [contenteditable="true"]';
        let x = -100, y = -100, tx = -100, ty = -100, raf = 0, shown = false;

        const frame = () => {
            raf = 0;
            x += (tx - x) * 0.3;
            y += (ty - y) * 0.3;
            el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
            if (Math.abs(tx - x) + Math.abs(ty - y) > 0.2) raf = requestAnimationFrame(frame);
        };
        const setShown = (on) => { shown = on; el.classList.toggle('is-visible', on); };

        doc.addEventListener('pointermove', (e) => {
            if (e.pointerType !== 'mouse') { setShown(false); return; }
            tx = e.clientX; ty = e.clientY;
            if (!shown) { x = tx; y = ty; setShown(true); }
            if (!raf) raf = requestAnimationFrame(frame);
        }, { passive: true });
        doc.addEventListener('pointerover', (e) => {
            const t = e.target instanceof Element ? e.target : null;
            if (!t) return;
            const blocked = t.closest(BLOCKED);
            el.classList.toggle('is-blocked', !!blocked);
            const hit = blocked ? null : t.closest(ACTIVE);
            el.classList.toggle('is-active', !!hit);
            const tag = hit && (hit.dataset.cursor || (hit.closest('[data-cursor]') || {}).dataset?.cursor);
            label.textContent = tag || '';
            el.classList.toggle('has-label', !!tag);
        });
        doc.addEventListener('pointerdown', () => el.classList.add('is-down'));
        doc.addEventListener('pointerup', () => el.classList.remove('is-down'));
        root.addEventListener('mouseleave', () => setShown(false));
        window.addEventListener('blur', () => setShown(false));
    }

    /* ─── Hero starfield / constellation canvas ─────────────────────────── */
    function initStarfield() {
        const canvas = doc.querySelector('canvas[data-starfield]');
        if (!canvas || !canvas.getContext) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        const host = canvas.closest('section') || canvas.parentElement;
        const readout = host.querySelector('[data-hud-pointer]');
        const interactive = finePointer && !reduceMotion;
        const COLORS = ['rgb(214,232,255)', 'rgb(140,196,255)', 'rgb(255,196,110)'];
        const LINK = 150, PAIR = 96;

        let w = 0, h = 0, stars = [], raf = 0, last = 0, t = 0, inView = true;
        let meteor = null, meteorIn = 3.5 + Math.random() * 4;
        const ptr = { x: 0, y: 0, sx: 0, sy: 0, on: 0, goal: 0, px: 0, py: 0 };

        const makeStar = () => {
            const z = Math.pow(Math.random(), 1.7) * 0.85 + 0.15;
            return {
                x: Math.random() * w, y: Math.random() * h, z,
                r: 0.5 + z * 1.45,
                vx: (Math.random() - 0.5) * 6 * z,
                vy: -(1.5 + Math.random() * 5) * z,
                ph: Math.random() * Math.PI * 2,
                sp: 0.5 + Math.random() * 1.8,
                c: Math.random() < 0.1 ? 2 : (Math.random() < 0.35 ? 1 : 0)
            };
        };

        const draw = (dt) => {
            const secs = dt / 1000;
            ctx.clearRect(0, 0, w, h);
            const k = Math.min(1, secs * 7);
            ptr.on += (ptr.goal - ptr.on) * Math.min(1, secs * 4);
            ptr.sx += (ptr.x - ptr.sx) * k;
            ptr.sy += (ptr.y - ptr.sy) * k;
            const goalPx = ptr.goal ? (ptr.x / w - 0.5) : 0;
            const goalPy = ptr.goal ? (ptr.y / h - 0.5) : 0;
            ptr.px += (goalPx - ptr.px) * Math.min(1, secs * 2.5);
            ptr.py += (goalPy - ptr.py) * Math.min(1, secs * 2.5);
            const scroll = window.scrollY * 0.35;
            const near = [];

            for (let i = 0; i < stars.length; i++) {
                const s = stars[i];
                s.x += s.vx * secs;
                s.y += s.vy * secs;
                if (s.x < -12) s.x += w + 24; else if (s.x > w + 12) s.x -= w + 24;
                if (s.y < -12) s.y += h + 24; else if (s.y > h + 12) s.y -= h + 24;
                const x = s.x - ptr.px * 46 * s.z;
                let y = s.y - ptr.py * 30 * s.z - scroll * s.z;
                y = ((y % h) + h) % h;
                const tw = reduceMotion ? 1 : 0.62 + 0.38 * Math.sin(t * s.sp + s.ph);
                ctx.globalAlpha = (0.34 + 0.66 * s.z) * tw;
                ctx.fillStyle = COLORS[s.c];
                if (s.r < 0.95) {
                    ctx.fillRect(x, y, s.r * 1.7, s.r * 1.7);
                } else {
                    ctx.beginPath();
                    ctx.arc(x, y, s.r, 0, Math.PI * 2);
                    ctx.fill();
                    if (s.z > 0.72) {
                        ctx.globalAlpha *= 0.14;
                        ctx.beginPath();
                        ctx.arc(x, y, s.r * 3.4, 0, Math.PI * 2);
                        ctx.fill();
                    }
                }
                if (ptr.on > 0.02 && near.length < 26) {
                    const dx = x - ptr.sx, dy = y - ptr.sy;
                    const d2 = dx * dx + dy * dy;
                    if (d2 < LINK * LINK) near.push({ x, y, d: Math.sqrt(d2) });
                }
            }

            if (near.length) {
                near.sort((a, b) => a.d - b.d);
                ctx.lineWidth = 0.9;
                ctx.strokeStyle = 'rgb(150,205,255)';
                for (let i = 0; i < near.length; i++) {
                    const p = near[i];
                    const fade = (1 - p.d / LINK) * ptr.on;
                    if (i < 7) {
                        ctx.globalAlpha = fade * 0.7;
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(ptr.sx, ptr.sy);
                        ctx.stroke();
                    }
                    for (let j = i + 1; j < near.length; j++) {
                        const q = near[j];
                        const d = Math.hypot(p.x - q.x, p.y - q.y);
                        if (d < PAIR) {
                            ctx.globalAlpha = (1 - d / PAIR) * fade * 0.6;
                            ctx.beginPath();
                            ctx.moveTo(p.x, p.y);
                            ctx.lineTo(q.x, q.y);
                            ctx.stroke();
                        }
                    }
                    if (i < 7) {
                        ctx.globalAlpha = fade * 0.9;
                        ctx.strokeStyle = 'rgb(255,190,90)';
                        ctx.beginPath();
                        ctx.arc(p.x, p.y, 2.6, 0, Math.PI * 2);
                        ctx.stroke();
                        ctx.strokeStyle = 'rgb(150,205,255)';
                    }
                }
            }

            if (!reduceMotion) {
                meteorIn -= secs;
                if (!meteor && meteorIn <= 0) {
                    meteor = { x: w * (0.35 + Math.random() * 0.6), y: h * Math.random() * 0.35, life: 0, dur: 0.9 + Math.random() * 0.5, ang: Math.PI * (0.78 + Math.random() * 0.1), len: 120 + Math.random() * 120 };
                    meteorIn = 6 + Math.random() * 8;
                }
                if (meteor) {
                    meteor.life += secs;
                    const p = meteor.life / meteor.dur;
                    if (p >= 1) {
                        meteor = null;
                    } else {
                        const dist = p * 520;
                        const hx = meteor.x + Math.cos(meteor.ang) * dist;
                        const hy = meteor.y + Math.sin(meteor.ang) * dist;
                        const tx = hx - Math.cos(meteor.ang) * meteor.len;
                        const ty = hy - Math.sin(meteor.ang) * meteor.len;
                        const g = ctx.createLinearGradient(hx, hy, tx, ty);
                        g.addColorStop(0, 'rgba(255,236,200,0.9)');
                        g.addColorStop(1, 'rgba(255,236,200,0)');
                        ctx.globalAlpha = Math.sin(p * Math.PI);
                        ctx.strokeStyle = g;
                        ctx.lineWidth = 1.2;
                        ctx.beginPath();
                        ctx.moveTo(hx, hy);
                        ctx.lineTo(tx, ty);
                        ctx.stroke();
                    }
                }
            }
            ctx.globalAlpha = 1;
        };

        const frame = (now) => {
            raf = 0;
            const dt = last ? Math.min(64, now - last) : 16;
            last = now;
            t += dt / 1000;
            draw(dt);
            if (inView && !doc.hidden) raf = requestAnimationFrame(frame);
        };
        const start = () => {
            if (raf || reduceMotion || !inView || doc.hidden) return;
            last = 0;
            raf = requestAnimationFrame(frame);
        };
        const stop = () => { if (raf) cancelAnimationFrame(raf); raf = 0; };

        const resize = () => {
            const rect = canvas.getBoundingClientRect();
            const nw = Math.max(1, rect.width), nh = Math.max(1, rect.height);
            const dpr = Math.min(2, window.devicePixelRatio || 1);
            canvas.width = Math.round(nw * dpr);
            canvas.height = Math.round(nh * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            if (w && h) stars.forEach((s) => { s.x = (s.x / w) * nw; s.y = (s.y / h) * nh; });
            w = nw; h = nh;
            const target = Math.round(clamp((w * h) / (finePointer ? 6200 : 9500), 40, finePointer ? 260 : 120));
            while (stars.length < target) stars.push(makeStar());
            stars.length = target;
            if (!raf) draw(16);
        };

        resize();
        canvas.classList.add('is-ready');
        if ('ResizeObserver' in window) new ResizeObserver(resize).observe(canvas);
        else window.addEventListener('resize', resize, { passive: true });
        if (reduceMotion) return;

        if (hasIO) {
            new IntersectionObserver(([e]) => {
                inView = e.isIntersecting;
                if (inView) start(); else stop();
            }).observe(canvas);
        }
        doc.addEventListener('visibilitychange', () => { if (doc.hidden) stop(); else start(); });

        if (interactive) {
            let readQueued = false;
            host.addEventListener('pointermove', (e) => {
                if (e.pointerType !== 'mouse') return;
                const r = canvas.getBoundingClientRect();
                ptr.x = e.clientX - r.left;
                ptr.y = e.clientY - r.top;
                if (!ptr.goal) { ptr.sx = ptr.x; ptr.sy = ptr.y; }
                ptr.goal = 1;
                if (readout && !readQueued) {
                    readQueued = true;
                    requestAnimationFrame(() => {
                        readQueued = false;
                        readout.textContent = `X ${String(Math.round(ptr.x)).padStart(4, '0')} · Y ${String(Math.round(ptr.y)).padStart(4, '0')}`;
                    });
                }
            }, { passive: true });
            host.addEventListener('pointerleave', () => { ptr.goal = 0; });
        }
        start();
    }

    /* ─── Text decode / scramble ────────────────────────────────────────── */
    function initScramble() {
        const els = $$('[data-scramble]');
        if (!els.length) return;
        const settle = (el) => el.classList.add('is-scrambled');
        if (reduceMotion) { els.forEach(settle); return; }

        const GLYPHS = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789/<>#*+=';
        const t0 = performance.now();
        // Glyph widths are locked during the effect, so the element's real web font must be
        // loaded first (document.fonts.ready can resolve before the font is even requested).
        const fontSpec = (el) => {
            const cs = getComputedStyle(el);
            return `${cs.fontWeight} 32px ${cs.fontFamily.split(',')[0].trim()}`;
        };
        const fontOk = (el) => !doc.fonts || doc.fonts.check(fontSpec(el));
        const loads = doc.fonts && doc.fonts.load
            ? Promise.all(els.map((el) => doc.fonts.load(fontSpec(el)).catch(() => null)))
            : Promise.resolve();
        Promise.race([loads, new Promise((r) => setTimeout(r, 1600))]).then(() => {
            const late = performance.now() - t0 > 1500;
            els.forEach((el) => (late || !fontOk(el) ? settle(el) : run(el)));
        });

        function run(el) {
            const text = el.textContent.replace(/\s+/g, ' ').trim();
            el.setAttribute('aria-label', text);
            el.textContent = '';
            const chars = [];
            // Words are wrapped so a line can only break at the original spaces.
            text.split(' ').forEach((word, wi) => {
                if (wi > 0) el.appendChild(doc.createTextNode(' '));
                const wrap = doc.createElement('span');
                wrap.className = 'kd-scramble-word';
                wrap.setAttribute('aria-hidden', 'true');
                Array.from(word).forEach((ch) => {
                    const span = doc.createElement('span');
                    span.className = 'kd-scramble-ch';
                    span.textContent = ch;
                    wrap.appendChild(span);
                    chars.push({ span, ch });
                });
                el.appendChild(wrap);
            });
            chars.forEach((c) => { c.w = c.span.getBoundingClientRect().width; });
            chars.forEach((c, i) => {
                c.span.style.width = c.w + 'px';
                c.end = 260 + i * 70 + Math.random() * 220;
                c.span.textContent = GLYPHS[(Math.random() * GLYPHS.length) | 0];
                c.span.classList.add('is-noise');
            });
            el.classList.add('is-scrambled', 'is-scrambling');
            const begin = performance.now();
            let lastSwap = 0;
            const tick = (now) => {
                const elapsed = now - begin;
                const swap = now - lastSwap > 60;
                if (swap) lastSwap = now;
                let pending = false;
                chars.forEach((c) => {
                    if (c.done) return;
                    if (elapsed >= c.end) {
                        c.done = true;
                        c.span.textContent = c.ch;
                        c.span.classList.remove('is-noise');
                        c.span.classList.add('is-locked');
                        return;
                    }
                    pending = true;
                    if (swap) c.span.textContent = GLYPHS[(Math.random() * GLYPHS.length) | 0];
                });
                if (pending) requestAnimationFrame(tick);
                else setTimeout(() => {
                    el.textContent = text;
                    el.removeAttribute('aria-label');
                    el.classList.remove('is-scrambling');
                }, 700);
            };
            requestAnimationFrame(tick);
        }
    }

    /* ─── Animated terminal (home "AI · Vibe Code" card) ────────────────── */
    function initTerminals() {
        if (reduceMotion || !hasIO) return;
        $$('[data-terminal]').forEach((term) => {
            const lines = $$('.kd-term-line', term);
            if (!lines.length) return;
            const texts = lines.map((l) => l.textContent);
            const caret = doc.createElement('span');
            caret.className = 'kd-term-caret';
            let visible = false, started = false, pending = null, timer = 0, li = 0;

            const later = (fn, ms) => {
                clearTimeout(timer);
                timer = setTimeout(() => {
                    if (!visible || doc.hidden) { pending = fn; return; }
                    fn();
                }, ms);
            };
            const resume = () => {
                if (pending && visible && !doc.hidden) { const fn = pending; pending = null; fn(); }
            };
            const put = (line, text) => { line.textContent = text; line.appendChild(caret); };
            const kind = (line) => (line.classList.contains('is-cmd') ? 'cmd'
                : line.classList.contains('is-code') ? 'code'
                : line.hasAttribute('data-progress') ? 'progress' : 'out');

            const nextLine = () => {
                if (li >= lines.length) {
                    later(() => {
                        term.classList.add('is-clearing');
                        later(() => { term.classList.remove('is-clearing'); restart(); }, 420);
                    }, 3400);
                    return;
                }
                const line = lines[li];
                const text = texts[li];
                line.classList.add('is-shown');
                const type = kind(line);
                if (type === 'out') {
                    put(line, '');
                    later(() => { put(line, text); li += 1; later(nextLine, 260); }, 320);
                } else if (type === 'progress') {
                    const label = line.dataset.progress || 'simulating';
                    let k = 0;
                    const tick = () => {
                        put(line, `  ▸ ${label} ${'█'.repeat(k)}${'░'.repeat(10 - k)} ${k * 10}%`);
                        if (k < 10) { k += 1; later(tick, 80 + Math.random() * 120); }
                        else { put(line, text); li += 1; later(nextLine, 300); }
                    };
                    tick();
                } else {
                    const chars = Array.from(text);
                    let ci = 0;
                    put(line, '');
                    const typeChar = () => {
                        ci += 1;
                        put(line, chars.slice(0, ci).join(''));
                        if (ci < chars.length) later(typeChar, type === 'cmd' ? 24 + Math.random() * 46 : 12 + Math.random() * 18);
                        else { li += 1; later(nextLine, 320); }
                    };
                    later(typeChar, type === 'cmd' ? 420 : 160);
                }
            };
            const restart = () => {
                lines.forEach((l) => { l.textContent = ''; l.classList.remove('is-shown'); });
                li = 0;
                nextLine();
            };

            new IntersectionObserver(([e]) => {
                visible = e.isIntersecting;
                if (visible && !started) { started = true; term.classList.add('is-live'); restart(); }
                else resume();
            }, { threshold: 0.35 }).observe(term);
            doc.addEventListener('visibilitychange', resume);
        });
    }

    /* ─── Pause decorative CSS loops while offscreen ────────────────────── */
    function initOffscreenPause() {
        if (!hasIO) return;
        const els = $$('.kd-placeholder, .kd-hero-hud');
        if (!els.length) return;
        const io = new IntersectionObserver((entries) => {
            entries.forEach((e) => e.target.classList.toggle('is-offscreen', !e.isIntersecting));
        });
        els.forEach((el) => io.observe(el));
    }

    safe('chrome', initChrome);
    safe('reveal', initReveal);
    safe('parallax', initParallax);
    safe('lightbox', initLightbox);
    safe('filters', initFilters);
    safe('tilt', initTilt);
    safe('cursor', initCursor);
    safe('starfield', initStarfield);
    safe('scramble', initScramble);
    safe('terminals', initTerminals);
    safe('offscreen', initOffscreenPause);
})();
