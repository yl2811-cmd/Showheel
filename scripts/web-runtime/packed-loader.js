/* Published assets only. The authoring atlas and its offline files stay unchanged. */
(() => {
  'use strict';
  const records = window.SHOWHEEL_PACKED || {};
  const pending = new Map();
  const completedScripts = new Set();
  const metrics = { requests: 0, compressedBytes: 0, decodedBytes: 0, retries: 0, cacheHits: 0 };
  const abortError = () => new DOMException('The scene was closed.', 'AbortError');
  const key = url => decodeURI(new URL(url, document.baseURI).pathname);
  const record = url => records[key(url)];
  async function retrieve(r, signal) {
    let cache;
    try { cache = await caches.open('showheel-packed-v1'); } catch {}
    for (let attempt = 0; attempt < 3; attempt++) {
      signal.throwIfAborted();
      try {
        let response = await cache?.match(r.url);
        if (response) metrics.cacheHits++;
        else {
          response = await fetch(r.url, { signal, cache: 'force-cache' });
          metrics.requests++;
          if (!response.ok) throw Error('Resource HTTP ' + response.status);
        }
        const compressed = await response.arrayBuffer();
        signal.throwIfAborted();
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', compressed)), b => b.toString(16).padStart(2, '0')).join('');
        if (digest !== r.sha256) throw Error('Resource integrity check failed');
        if (!window.DecompressionStream) throw Error('Please update your browser to open this scene.');
        const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
        const decoded = await new Response(stream).arrayBuffer();
        signal.throwIfAborted();
        if (decoded.byteLength !== r.bytes) throw Error('Incomplete resource');
        metrics.compressedBytes += compressed.byteLength;
        metrics.decodedBytes += decoded.byteLength;
        try { await cache?.put(r.url, new Response(compressed)); } catch {}
        return decoded;
      } catch (error) {
        if (signal.aborted) throw abortError();
        try { await cache?.delete(r.url); } catch {}
        if (attempt === 2 || !window.DecompressionStream) throw error;
        metrics.retries++;
        await new Promise((resolve, reject) => {
          const done = () => { signal.removeEventListener('abort', cancel); resolve(); };
          const timer = setTimeout(done, 250 * (attempt + 1));
          const cancel = () => { clearTimeout(timer); reject(abortError()); };
          signal.addEventListener('abort', cancel, { once: true });
        });
      }
    }
  }
  function bytes(url, signal) {
    if (signal?.aborted) return Promise.reject(abortError());
    const r = record(url);
    if (!r) return fetch(url, { signal }).then(response => {
      if (!response.ok) throw Error('Resource HTTP ' + response.status);
      return response.arrayBuffer();
    });
    let job = pending.get(r.url);
    if (job?.controller.signal.aborted) { pending.delete(r.url); job = null; }
    if (!job) {
      job = { controller: new AbortController(), users: 0 };
      job.promise = retrieve(r, job.controller.signal).finally(() => { if (pending.get(r.url) === job) pending.delete(r.url); });
      pending.set(r.url, job);
    }
    job.users++;
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (fn, value) => {
        if (settled) return;
        settled = true;
        signal?.removeEventListener('abort', cancel);
        if (--job.users === 0) job.controller.abort();
        fn(value);
      };
      const cancel = () => finish(reject, abortError());
      signal?.addEventListener('abort', cancel, { once: true });
      job.promise.then(value => finish(resolve, value), error => finish(reject, error));
    });
  }
  function attach(element) {
    const src = element.src;
    if (!record(src)) { document.head.appendChild(element); return element; }
    const controller = new AbortController();
    const remove = element.remove.bind(element);
    element.remove = () => { controller.abort(); remove(); };
    bytes(src, controller.signal).then(buffer => {
      if (controller.signal.aborted) return;
      element.removeAttribute('src');
      element.textContent = new TextDecoder().decode(buffer) + '\n//# sourceURL=' + src;
      let failure;
      const capture = event => { failure = event.error || Error(event.message); };
      window.addEventListener('error', capture);
      try { document.head.appendChild(element); } finally { window.removeEventListener('error', capture); }
      if (failure) throw failure;
      element.dispatchEvent(new Event('load'));
    }).catch(error => {
      if (error.name !== 'AbortError') { element.dataset.loadError = error.message; element.dispatchEvent(new Event('error')); }
    });
    return element;
  }
  function script(src, signal) {
    return new Promise((resolve, reject) => {
      const element = document.createElement('script');
      const cancel = () => { element.remove(); reject(abortError()); };
      const cleanup = () => signal?.removeEventListener('abort', cancel);
      element.src = src;
      element.onload = () => { cleanup(); element.remove(); resolve(); };
      element.onerror = () => { cleanup(); element.remove(); reject(Error(element.dataset.loadError || 'Cannot load ' + src)); };
      if (signal?.aborted) return reject(abortError());
      signal?.addEventListener('abort', cancel, { once: true });
      attach(element);
    });
  }
  document.addEventListener('click', async event => {
    const anchor = event.target.closest('a[download]');
    if (!anchor || !record(anchor.href)) return;
    event.preventDefault();
    try {
      const data = await bytes(anchor.href);
      const url = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
      const link = document.createElement('a'); link.href = url; link.download = anchor.download || key(anchor.href).split('/').pop(); link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { const status = document.getElementById('load-status'); if (status) status.textContent = '下载未能完成，请再次点击。'; }
  });
  async function once(src, signal) {
    if (signal?.aborted) throw abortError();
    const url = new URL(src, document.baseURI).href;
    if (completedScripts.has(url)) return;
    await script(src, signal);
    completedScripts.add(url);
  }
  window.SHOWHEEL_ASSETS = { bytes, attach, script, once, metrics, pending: () => pending.size };
})();
