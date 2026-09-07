/* Ordered soundtrack; only naturally ended tracks receive the ten-second gap. */
(() => {
    'use strict';
    function createPlayer(audio, tracks, notify, clock = {
        now: () => Date.now(),
        setTimeout: (handler, delay) => setTimeout(handler, delay),
        clearTimeout: id => clearTimeout(id)
    }) {
        let index = 0, state = 'idle', wanted = false, generation = 0;
        let timer = null, deadline = 0, remaining = 0;
        const listeners = [];
        const report = () => notify({ index, count: tracks.length, state, title: tracks[index]?.title || '' });
        function clearTimer() { if (timer !== null) clock.clearTimeout(timer); timer = null; }
        function load() { audio.src = tracks[index].src; audio.load(); }
        async function play() {
            if (!tracks.length) return;
            const token = ++generation;
            wanted = true;
            state = 'loading'; report();
            try {
                await audio.play();
                if (token !== generation) { if (!wanted) audio.pause(); return; }
                state = 'playing'; report();
            } catch (error) {
                if (token !== generation) return;
                wanted = false;
                state = error.name === 'NotAllowedError' ? 'blocked' : 'error';
                report();
            }
        }
        function schedule(delay) {
            clearTimer();
            remaining = delay;
            deadline = clock.now() + delay;
            wanted = true;
            state = 'waiting'; report();
            timer = clock.setTimeout(() => {
                timer = null; remaining = 0;
                if (wanted) skip(1);
            }, delay);
        }
        function pause() {
            if (state === 'waiting') remaining = Math.max(0, deadline - clock.now());
            clearTimer();
            generation++; wanted = false;
            audio.pause();
            state = remaining > 0 ? 'paused-waiting' : 'paused'; report();
        }
        function skip(direction) {
            if (!tracks.length) return;
            clearTimer(); remaining = 0; generation++; wanted = false;
            audio.pause();
            index = (index + direction + tracks.length) % tracks.length;
            load();
            return play();
        }
        function toggle() {
            if (wanted) pause();
            else if (remaining > 0) schedule(remaining);
            else { if (state === 'error') load(); return play(); }
        }
        function on(event, handler) { audio.addEventListener(event, handler); listeners.push([event, handler]); }
        on('ended', () => { if (wanted && state !== 'waiting') schedule(10000); });
        on('error', () => { clearTimer(); remaining = 0; wanted = false; generation++; state = 'error'; report(); });
        on('pause', () => {
            if (wanted && audio.paused && !audio.ended && (state === 'playing' || state === 'loading')) {
                wanted = false; generation++; state = 'paused'; report();
            }
        });
        if (tracks.length) { load(); play(); }
        else { state = 'unavailable'; report(); }
        return {
            toggle, next: () => skip(1), previous: () => skip(-1), pause,
            retryAutoplay: () => { if (state === 'blocked') return play(); },
            destroy() { clearTimer(); generation++; wanted = false; audio.pause(); listeners.forEach(([event, handler]) => audio.removeEventListener(event, handler)); }
        };
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = { createPlayer };
    if (typeof document === 'undefined') return;
    const root = document.querySelector('[data-archeon-music]');
    if (!root) return;
    const audio = root.querySelector('audio');
    const tracks = JSON.parse(root.querySelector('[data-music-tracks]').textContent);
    const toggle = root.querySelector('[data-music-toggle]');
    const player = createPlayer(audio, tracks, ({ index, count, state, title }) => {
        root.dataset.state = state;
        root.querySelector('[data-music-title]').textContent = count ? `${title} · ${index + 1}/${count}` : 'Archeon soundtrack';
        const active = ['playing', 'loading', 'waiting'].includes(state);
        toggle.textContent = active ? '暂停' : '播放';
        toggle.setAttribute('aria-label', active ? '暂停背景音乐' : '播放背景音乐');
        root.querySelectorAll('button').forEach(button => { button.disabled = !count; });
        const labels = { playing: '正在播放', loading: '加载中…', waiting: '曲间停歇 · 10 秒后继续', 'paused-waiting': '曲间停歇已暂停', paused: '已暂停', blocked: '点击播放，开启音乐', error: '无法播放，可重试或切换下一首', unavailable: '音乐文件尚未就绪' };
        root.querySelector('[data-music-status]').textContent = labels[state] || '';
    });
    toggle.addEventListener('click', () => player.toggle());
    root.querySelector('[data-music-next]').addEventListener('click', () => player.next());
    root.querySelector('[data-music-previous]').addEventListener('click', () => player.previous());
    const activate = event => { if (!root.contains(event.target)) player.retryAutoplay(); };
    document.addEventListener('pointerdown', activate);
    document.addEventListener('keydown', activate);
    window.addEventListener('pagehide', () => player.pause());
})();
