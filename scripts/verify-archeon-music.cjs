'use strict';
const assert = require('node:assert/strict');
const { createPlayer } = require('../wwwroot/js/archeon-music.js');
class Audio extends EventTarget {
    paused = true; ended = false; src = ''; calls = 0; reject = false; pending = null;
    load() { this.ended = false; this.paused = true; }
    play() {
        this.calls++;
        if (this.reject) return Promise.reject(Object.assign(new Error('blocked'), { name: 'NotAllowedError' }));
        this.paused = false;
        return this.pending || Promise.resolve();
    }
    pause() { this.paused = true; this.dispatchEvent(new Event('pause')); }
    end() { this.ended = true; this.paused = true; this.dispatchEvent(new Event('ended')); }
}
function clock() {
    let now = 0, id = 0; const jobs = new Map();
    return { now: () => now, setTimeout: (fn, delay) => { jobs.set(++id, { at: now + delay, fn }); return id; }, clearTimeout: id => jobs.delete(id),
        tick(ms) { const end = now + ms; while (true) { const next = [...jobs].sort((a, b) => a[1].at - b[1].at)[0]; if (!next || next[1].at > end) break; jobs.delete(next[0]); now = next[1].at; next[1].fn(); } now = end; }, get size() { return jobs.size; } };
}
const tracks = Array.from({ length: 9 }, (_, i) => ({ src: '/images/archeonvibe' + (i + 1) + '.mp3', title: 'Track ' + (i + 1) }));
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    const audio = new Audio(), time = clock(); let state;
    const player = createPlayer(audio, tracks, value => { state = value; }, time);
    await flush(); assert.equal(state.state, 'playing'); assert.equal(state.index, 0);
    audio.end(); assert.equal(state.state, 'waiting'); time.tick(9999); assert.equal(state.index, 0);
    time.tick(1); await flush(); assert.equal(state.index, 1); assert.equal(state.state, 'playing');
    audio.end(); time.tick(4000); player.pause(); time.tick(30000); assert.equal(state.index, 1);
    assert.equal(state.state, 'paused-waiting'); player.toggle(); time.tick(5999); assert.equal(state.index, 1);
    time.tick(1); await flush(); assert.equal(state.index, 2);
    audio.end(); player.next(); await flush(); assert.equal(state.index, 3); assert.equal(time.size, 0);
    for (let i = 0; i < 5; i++) await player.next(); assert.equal(state.index, 8);
    audio.end(); time.tick(10000); await flush(); assert.equal(state.index, 0);
    await player.previous(); assert.equal(state.index, 8);
    player.pause(); time.tick(100000); assert.equal(state.state, 'paused'); assert(audio.paused);
    await player.next(); assert.equal(state.index, 0); assert.equal(state.state, 'playing');
    audio.pause(); assert.equal(state.state, 'paused');
    player.destroy(); assert.equal(time.size, 0);
    const blockedAudio = new Audio(); blockedAudio.reject = true;
    const blocked = createPlayer(blockedAudio, tracks, value => { state = value; }, clock());
    await flush(); assert.equal(state.state, 'blocked');
    blockedAudio.reject = false; await blocked.retryAutoplay(); assert.equal(state.state, 'playing');
    blocked.pause(); const calls = blockedAudio.calls; blocked.retryAutoplay(); assert.equal(blockedAudio.calls, calls);
    blocked.destroy();
    const lateAudio = new Audio(); let resolve;
    lateAudio.pending = new Promise(r => { resolve = r; });
    const late = createPlayer(lateAudio, tracks, value => { state = value; }, clock());
    late.pause(); resolve(); await flush(); assert.equal(state.state, 'paused'); assert(lateAudio.paused); late.destroy();
    console.log('PASS: autoplay, blocked autoplay recovery, pause/resume, 10-second gap, paused gap, manual skip, 9-to-1 wrap, previous wrap, stale play promise, timer cleanup');
})().catch(error => { console.error(error); process.exitCode = 1; });
