// Story Studio — client for the AI-managed story tree + RAG co-author.
// All AI/story content is inserted via textContent (never innerHTML) to avoid XSS.
(function () {
  "use strict";

  const api = "/api/story";
  const $ = (id) => document.getElementById(id);

  const el = {
    tree: $("ss-tree"),
    treeEmpty: $("ss-tree-empty"),
    treeFilter: $("ss-tree-filter"),
    decompose: $("ss-decompose"),
    exportTree: $("ss-export-tree"),
    viewMap: $("ss-view-map"),
    viewList: $("ss-view-list"),
    rebuild: $("ss-rebuild"),
    rag: $("ss-rag"),
    ragText: $("ss-rag-text"),
    cacheValue: $("ss-cache-value"),
    cache: $("ss-cache"),
    toasts: $("ss-toasts"),
    nodeTitle: $("ss-node-title"),
    editTitle: $("ss-edit-title"),
    editContent: $("ss-edit-content"),
    exportNode: $("ss-export-node"),
    importNode: $("ss-import-node"),
    save: $("ss-save"),
    addChild: $("ss-add-child"),
    del: $("ss-delete"),
    // languages
    langSelect: $("ss-lang-select"),
    langTabs: $("ss-lang-tabs"),
    langContent: $("ss-lang-content"),
    translate: $("ss-translate"),
    saveLang: $("ss-save-lang"),
    // assets
    nodeAsset: $("ss-node-asset"),
    nodeAssets: $("ss-node-assets"),
    assetsEmpty: $("ss-assets-empty"),
    // chat
    chat: $("ss-chat"),
    chatForm: $("ss-chat-form"),
    chatInput: $("ss-chat-input"),
    chatSend: $("ss-chat-send"),
    chatClear: $("ss-chat-clear"),
    modelConfig: $("ss-model-config"),
    modelConfigPanel: $("ss-model-config-panel"),
    modelLabel: $("ss-model-label"),
    modelBaseUrl: $("ss-model-base-url"),
    modelApiKey: $("ss-model-api-key"),
    modelName: $("ss-model-name"),
    modelContext: $("ss-model-context"),
    modelSaveConfig: $("ss-model-save-config"),
    modelClearConfig: $("ss-model-clear-config"),
    thinking: $("ss-thinking"),
    file: $("ss-file"),
    attachments: $("ss-attachments"),
    patchMode: $("ss-patch-mode"),
    patch: $("ss-patch"),
    patchSummary: $("ss-patch-summary"),
    patchBadge: $("ss-patch-badge"),
    patchOps: $("ss-patch-ops"),
    patchApply: $("ss-patch-apply"),
    patchReject: $("ss-patch-reject"),
    // gate (password)
    gate: $("ss-gate"),
    shell: $("ss-app"),
    gateForm: $("ss-gate-form"),
    gateInput: $("ss-gate-input"),
    gateError: $("ss-gate-error"),
    // telemetry
    tokTurn: $("ss-tok-turn"),
    tokStat: $("ss-tok"),
    ctx: $("ss-ctx"),
    ctxText: $("ss-ctx-text"),
    ctxFill: $("ss-ctx-fill"),
    // slot
    slot: $("ss-slot"),
    slotText: $("ss-slot-text"),
    slotNote: $("ss-slot-note"),
  };

  document.body.classList.add("ss-story-studio-page");
  document.body.classList.remove("ss-panel-maxed");
  document.querySelectorAll(".ss-panel-backdrop, .ss-gate").forEach((node) => node.remove());
  if (el.shell) el.shell.classList.remove("is-locked");

  // state
  const state = {
    tree: null,
    selected: null,
    view: "map",
    collapsed: new Set(),      // node ids collapsed in the tree
    chat: [],                  // [{id, role, content}] — full transcript, source of truth
    ragTimer: null,
    cacheTimer: null,
    slotTimer: null,           // polls slot status
    heartbeatTimer: null,      // renews our hold on the AI slot
    pending: [],               // transient attachments staged for the next message
    patch: null,
    lang: "en",                // currently edited language code
    authed: false,             // session passed the password gate
    holdsSlot: false,          // this session owns the AI conversation slot
  };

  let msgSeq = 0;
  const nextMsgId = () => `m${Date.now().toString(36)}${(msgSeq++).toString(36)}`;
  const modelProviderKey = "storyStudio.modelProvider";

  // ---- helpers ----

  async function req(method, path, body) {
    const res = await fetch(api + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch { /* no body */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || `Request failed (${res.status})`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function toast(message, kind = "info") {
    const t = document.createElement("div");
    t.className = `ss-toast ss-toast-${kind}`;
    t.textContent = message;
    el.toasts.appendChild(t);
    setTimeout(() => t.classList.add("ss-toast-in"), 10);
    setTimeout(() => {
      t.classList.remove("ss-toast-in");
      setTimeout(() => t.remove(), 300);
    }, 4200);
  }

  function download(filename, text) {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ---- RAG status ----

  function renderRag(status) {
    const s = (status && status.state) || "Unknown";
    const map = { Ready: "ready", Indexing: "indexing", Empty: "empty", NotConfigured: "off", Error: "error", Unknown: "unknown" };
    el.rag.dataset.state = map[s] || "unknown";
    el.ragText.textContent = (status && status.message) || "RAG";
  }

  async function refreshRag(showToast) {
    try {
      const status = await req("GET", "/rag/status");
      renderRag(status);
      if (showToast) {
        if (status.state === "Ready") toast(`RAG healthy · ${status.chunkCount} chunks`, "success");
        else if (status.state === "NotConfigured") toast("RAG offline — embedding provider not set.", "warn");
        else if (status.state === "Empty") toast("RAG has no index yet.", "warn");
      }
      return status;
    } catch {
      renderRag({ state: "Error", message: "RAG status error" });
    }
  }

  async function rebuildIndex() {
    el.rebuild.disabled = true;
    toast("Rebuilding RAG index…", "info");
    try {
      const poll = setInterval(refreshRag, 1200);
      const status = await req("POST", "/rag/rebuild");
      clearInterval(poll);
      renderRag(status);
      if (status.state === "Ready") toast(`RAG index ready · ${status.chunkCount} chunks`, "success");
      else toast(status.message || "Index build finished.", "warn");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.rebuild.disabled = false;
    }
  }

  // ---- Cache utilization badge ----

  async function refreshCache() {
    try {
      const s = await req("GET", "/cache/stats");
      const o = s.overall || {};
      const rate = typeof o.hitRate === "number" ? o.hitRate : 0;
      el.cacheValue.textContent = `${rate}% · ${o.hits || 0}/${o.total || 0}`;
      el.cache.dataset.tone = rate >= 40 ? "warm" : "";
      el.cache.title = `AI call cache — chat ${s.chat ? s.chat.hitRate : 0}% · embeddings ${s.embeddings ? s.embeddings.hitRate : 0}% · ${s.entries}/${s.maxEntries} entries`;
    } catch {
      el.cacheValue.textContent = "—";
    }
  }

  // ---- Main-brain token telemetry ----

  function fmt(n) { return typeof n === "number" ? n.toLocaleString() : "—"; }

  function renderTelemetry(t) {
    if (!t) return;
    const last = t.last || {}, cum = t.cumulative || {}, ctx = t.context || {};
    el.tokTurn.textContent = (last.input != null) ? `↑${fmt(last.input)} ↓${fmt(last.output)}` : "—";
    el.tokTurn.title = `Last turn — in: ${fmt(last.input)} · out: ${fmt(last.output)}${last.fromCache ? " · (cache hit, 0 billed)" : ""} · cached: ${fmt(last.cached)}\nCumulative — in: ${fmt(cum.input)} · out: ${fmt(cum.output)}`;
    const used = ctx.used || 0, max = ctx.max || 0, pct = ctx.percent || 0;
    el.ctxText.textContent = max ? `${fmt(used)} / ${fmt(max)}` : "—";
    el.ctxFill.style.width = Math.min(100, pct) + "%";
    el.ctx.dataset.tone = pct >= 80 ? "hot" : "";
  }

  async function refreshTelemetry() {
    try { renderTelemetry(await req("GET", "/telemetry")); } catch { /* silent */ }
  }

  // ---- AI slot (single-writer occupancy) ----

  function renderSlot(s) {
    if (!s) return;
    const held = !!s.held;
    if (held && state.holdsSlot) {
      el.slot.dataset.state = "held";
      el.slotText.textContent = `You hold the AI (${s.expiresInSeconds}s)`;
    } else if (held) {
      el.slot.dataset.state = "busy";
      el.slotText.textContent = "AI busy";
    } else {
      el.slot.dataset.state = "free";
      el.slotText.textContent = "AI free";
    }
    updateComposerLock();
  }

  async function refreshSlot() {
    try { renderSlot(await req("GET", "/slot/status")); } catch { /* silent */ }
  }

  // Dim + disable the chat composer when this session can't drive the AI right now.
  function updateComposerLock() {
    const s = el.slot.dataset.state;
    const ok = state.authed && (s === "held" || s === "free");
    el.chatForm.classList.toggle("is-locked", !ok);
    if (!ok && s === "busy") {
      el.slotNote.hidden = false;
      el.slotNote.textContent = "Another session is using the co-author. You'll take over when it goes idle.";
    } else if (!ok && !state.authed) {
      el.slotNote.hidden = false;
      el.slotNote.textContent = "Unlock the studio to drive the AI.";
    } else {
      el.slotNote.hidden = true;
    }
  }

  async function claimSlot() {
    try {
      const data = await req("POST", "/slot/claim");
      state.holdsSlot = !!data.claimed;
      renderSlot(data.status || data);
      if (!state.holdsSlot) toast("AI is busy — waiting for the other session to finish.", "warn");
    } catch (e) {
      // 409 = held by someone else; render whatever status came back.
      if (e.data && e.data.status) renderSlot(e.data.status);
      else toast(e.message, "error");
    }
    startHeartbeat();
  }

  function startHeartbeat() {
    if (state.heartbeatTimer) clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = setInterval(async () => {
      if (!state.holdsSlot) return;
      try {
        const data = await req("POST", "/slot/heartbeat");
        if (!data.renewed) { state.holdsSlot = false; renderSlot(data.status); }
      } catch { /* will retry next tick */ }
    }, 25000);
  }

  async function releaseSlot() {
    if (!state.holdsSlot) return;
    try { await req("POST", "/slot/release"); } catch { /* best effort */ }
    state.holdsSlot = false;
  }

  // ---- Password gate (removed) ----
  // The gate UI was deleted from the page, so the studio is always unlocked.
  // showGate is a no-op kept only so any legacy callers don't throw.

  function showGate() {
    state.authed = true;
  }

  function hideGate() {
    state.authed = true;
  }

  async function checkAuth() {
    // The password gate was removed from the page, so the studio is always
    // considered unlocked. Never block bootstrapping on server auth status.
    if (!el.gate) { hideGate(); return true; }
    try {
      const s = await req("GET", "/auth/status");
      if (s.authed) { hideGate(); return true; }
      showGate(s.requiresPassword ? null : "Access required.");
      return false;
    } catch {
      showGate(null);
      return false;
    }
  }

  async function doLogin(e) {
    e.preventDefault();
    el.gateError.hidden = true;
    try {
      const data = await req("POST", "/auth/login", { password: el.gateInput.value || "" });
      if (data.authed) {
        el.gateInput.value = "";
        hideGate();
        toast("Unlocked.", "success");
        await Promise.all([refreshTelemetry(), refreshSlot(), claimSlot(), loadTree().catch(() => {}), refreshRag(true), refreshCache()]);
      }
    } catch (err) {
      el.gateError.hidden = false;
      el.gateError.textContent = err.message || "Wrong password.";
    }
  }

  // ---- Tree ----

  function bucketFlag(node) { return node && typeof node.bucket === "string" && node.bucket.length > 0; }

  function renderTree() {
    el.tree.querySelectorAll(".ss-node").forEach((n) => n.remove());
    if (!state.tree || !state.tree.nodes || state.tree.nodes.length === 0) {
      el.treeEmpty.hidden = false;
      return;
    }
    el.treeEmpty.hidden = true;
    const frag = document.createDocumentFragment();
    state.tree.nodes.forEach((n) => frag.appendChild(renderNode(n)));
    el.tree.appendChild(frag);
    applyFilter();
  }

  function renderNode(node) {
    const wrap = document.createElement("div");
    wrap.className = "ss-node";
    wrap.dataset.id = node.id;
    wrap.style.setProperty("--depth", node.depth || 0);
    const hasChildren = node.children && node.children.length;
    if (hasChildren && state.collapsed.has(node.id)) wrap.classList.add("is-collapsed");

    if (hasChildren) {
      const caret = document.createElement("button");
      caret.type = "button";
      caret.className = "ss-node-caret";
      caret.textContent = state.collapsed.has(node.id) ? "▸" : "▾";
      caret.title = "Collapse / expand";
      caret.addEventListener("click", (ev) => { ev.stopPropagation(); toggleCollapse(node.id); });
      wrap.appendChild(caret);
    }

    const row = document.createElement("button");
    row.type = "button";
    row.className = "ss-node-row";
    row.dataset.id = node.id;

    const num = document.createElement("span");
    num.className = "ss-node-num";
    num.textContent = node.number || "";
    const title = document.createElement("span");
    title.className = "ss-node-title";
    title.textContent = node.title || "(untitled)";
    row.appendChild(num);
    row.appendChild(title);

    // meta badges: child count, assets, translations
    const meta = document.createElement("span");
    meta.className = "ss-node-meta";
    if (hasChildren) {
      const b = document.createElement("span");
      b.className = "ss-node-badge";
      b.textContent = `${node.children.length}`;
      meta.appendChild(b);
    }
    if (node.assets && node.assets.length) {
      const b = document.createElement("span");
      b.className = "ss-node-badge ss-node-badge-asset";
      b.textContent = `🖼 ${node.assets.length}`;
      meta.appendChild(b);
    }
    const langs = translationCodes(node);
    if (langs.length) {
      const b = document.createElement("span");
      b.className = "ss-node-badge";
      b.textContent = langs.join("/");
      meta.appendChild(b);
    }
    if (meta.childNodes.length) row.appendChild(meta);

    row.addEventListener("click", () => selectNode(node.id));
    if (state.selected === node.id) row.classList.add("is-selected");
    wrap.appendChild(row);

    if (hasChildren) {
      const kids = document.createElement("div");
      kids.className = "ss-node-children";
      node.children.forEach((c) => kids.appendChild(renderNode(c)));
      wrap.appendChild(kids);
    }
    return wrap;
  }

  function toggleCollapse(id) {
    if (state.collapsed.has(id)) state.collapsed.delete(id);
    else state.collapsed.add(id);
    renderTree();
  }

  function setView(view) {
    state.view = view;
    el.tree.dataset.view = view;
    el.viewMap.classList.toggle("is-active", view === "map");
    el.viewList.classList.toggle("is-active", view === "list");
  }

  function applyFilter() {
    const q = (el.treeFilter.value || "").trim().toLowerCase();
    const nodes = el.tree.querySelectorAll(".ss-node");
    if (!q) { nodes.forEach((n) => n.classList.remove("is-filtered-out")); return; }
    // Show a node if it or any descendant matches.
    const matches = (node) => {
      const row = node.querySelector(":scope > .ss-node-row");
      const text = row ? row.textContent.toLowerCase() : "";
      let hit = text.includes(q);
      node.querySelectorAll(":scope > .ss-node-children > .ss-node").forEach((child) => {
        if (matches(child)) hit = true;
      });
      node.classList.toggle("is-filtered-out", !hit);
      return hit;
    };
    el.tree.querySelectorAll(":scope > .ss-node").forEach(matches);
  }

  function findNode(id, nodes) {
    nodes = nodes || (state.tree && state.tree.nodes) || [];
    for (const n of nodes) {
      if (n.id === id) return n;
      const hit = findNode(id, n.children || []);
      if (hit) return hit;
    }
    return null;
  }

  function translationCodes(node) {
    const codes = new Set();
    if (node && node.translations) Object.keys(node.translations).forEach((k) => { if (node.translations[k]) codes.add(k); });
    if (node && node.contentEn) codes.add("en");
    return Array.from(codes).sort();
  }

  function selectNode(id) {
    state.selected = id;
    const node = findNode(id);
    if (!node) return;
    el.nodeTitle.textContent = `${node.number || ""} ${node.title || ""}`.trim();
    el.editTitle.value = node.title || "";
    el.editContent.value = node.content || "";
    [el.editTitle, el.editContent, el.save, el.addChild, el.del,
     el.exportNode, el.importNode, el.nodeAsset, el.langSelect, el.translate, el.saveLang, el.langContent]
      .forEach((b) => (b.disabled = false));
    renderLangTabs(node);
    loadLang(state.lang);
    renderAssets(node);
    document.querySelectorAll(".ss-node-row").forEach((r) => r.classList.toggle("is-selected", r.dataset.id === id));
  }

  async function loadTree() {
    const data = await req("GET", "/tree");
    state.tree = data.tree;
    renderTree();
  }

  async function decompose() {
    if (!confirm("Rebuild the tree from the source book? This replaces the current tree.")) return;
    el.decompose.disabled = true;
    toast("Decomposing into the authority structure…", "info");
    try {
      const data = await req("POST", "/decompose", {});
      state.tree = data.tree;
      state.selected = null;
      renderTree();
      toast(`Tree built · ${data.nodeCount} sections`, "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.decompose.disabled = false;
    }
  }

  async function saveNode() {
    if (!state.selected) return;
    el.save.disabled = true;
    try {
      const node = await req("PUT", `/node/${state.selected}`, {
        title: el.editTitle.value,
        content: el.editContent.value,
      });
      const local = findNode(state.selected);
      if (local) { local.title = node.title; local.content = node.content; }
      renderTree();
      selectNode(state.selected);
      toast("Section saved.", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.save.disabled = false;
    }
  }

  async function addChild() {
    if (!state.selected) return;
    const title = prompt("New section title:");
    if (title === null) return;
    try {
      await req("POST", "/node", { parentId: state.selected, title, content: "" });
      await loadTree();
      toast("Section added.", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function deleteNode() {
    if (!state.selected) return;
    if (!confirm("Prune this section and everything under it? This cannot be undone.")) return;
    try {
      await req("DELETE", `/node/${state.selected}`);
      state.selected = null;
      await loadTree();
      resetEditor();
      toast("Section pruned.", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  function resetEditor() {
    el.nodeTitle.textContent = "Select a section";
    el.editTitle.value = "";
    el.editContent.value = "";
    el.langContent.value = "";
    el.langTabs.innerHTML = "";
    el.nodeAssets.querySelectorAll(".ss-asset").forEach((a) => a.remove());
    el.assetsEmpty.hidden = false;
    [el.editTitle, el.editContent, el.save, el.addChild, el.del,
     el.exportNode, el.importNode, el.nodeAsset, el.langSelect, el.translate, el.saveLang, el.langContent]
      .forEach((b) => (b.disabled = true));
  }

  // ---- Export / import node & tree ----

  async function exportNode() {
    if (!state.selected) return;
    window.location.href = `${api}/node/${state.selected}/export`;
  }

  async function importNode() {
    if (!state.selected) return;
    const file = el.importNode.files && el.importNode.files[0];
    if (!file) return;
    if (!confirm(`Overwrite this section's content with "${file.name}"?`)) { el.importNode.value = ""; return; }
    try {
      const text = await file.text();
      const node = await req("PUT", `/node/${state.selected}/content`, { content: text });
      const local = findNode(state.selected);
      if (local) local.content = node.content;
      el.editContent.value = node.content || "";
      toast("Section content overwritten.", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.importNode.value = "";
    }
  }

  function exportTree() {
    if (!state.tree) { toast("Nothing to export yet.", "warn"); return; }
    window.location.href = `${api}/export`;
  }

  // ---- Languages ----

  function renderLangTabs(node) {
    el.langTabs.innerHTML = "";
    const codes = translationCodes(node);
    if (!codes.length) {
      const hint = document.createElement("span");
      hint.className = "ss-assets-empty";
      hint.textContent = "No translations yet. Pick a language, auto-translate or type, then Save language.";
      el.langTabs.appendChild(hint);
      return;
    }
    codes.forEach((code) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "ss-lang-tab" + (code === state.lang ? " is-active" : "");
      const dot = document.createElement("span");
      dot.className = "ss-lang-dot";
      dot.textContent = "● ";
      tab.appendChild(dot);
      tab.appendChild(document.createTextNode(code));
      tab.addEventListener("click", () => { state.lang = code; el.langSelect.value = code; renderLangTabs(node); loadLang(code); });
      el.langTabs.appendChild(tab);
    });
  }

  function langValue(node, code) {
    if (!node) return "";
    if (node.translations && node.translations[code]) return node.translations[code];
    if (code === "en" && node.contentEn) return node.contentEn;
    return "";
  }

  function loadLang(code) {
    const node = findNode(state.selected);
    state.lang = code;
    el.langContent.value = langValue(node, code);
  }

  async function saveLang() {
    if (!state.selected) return;
    const code = el.langSelect.value;
    el.saveLang.disabled = true;
    try {
      const node = await req("PUT", `/node/${state.selected}/translation`, { lang: code, text: el.langContent.value });
      const local = findNode(state.selected);
      if (local) { local.translations = node.translations; local.contentEn = node.contentEn; }
      renderLangTabs(local);
      renderTree();
      toast(`Saved ${code} version.`, "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.saveLang.disabled = false;
    }
  }

  async function translate() {
    if (!state.selected) return;
    const node = findNode(state.selected);
    if (!node || !node.content) { toast("Nothing to translate.", "warn"); return; }
    const code = el.langSelect.value;
    const langName = el.langSelect.options[el.langSelect.selectedIndex].textContent.replace(/\s*\(.*\)$/, "");
    el.translate.disabled = true;
    el.langContent.value = "Translating…";
    try {
      const data = await req("POST", "/translate", { text: node.content, targetLang: langName });
      el.langContent.value = data.translation || "";
      state.lang = code;
      toast("Draft translation ready — review then Save language.", "success");
    } catch (e) {
      el.langContent.value = "";
      toast(e.message, "error");
    } finally {
      el.translate.disabled = false;
    }
  }

  // ---- Node assets ----

  function renderAssets(node) {
    el.nodeAssets.querySelectorAll(".ss-asset").forEach((a) => a.remove());
    const assets = (node && node.assets) || [];
    el.assetsEmpty.hidden = assets.length > 0;
    assets.forEach((asset) => {
      const card = document.createElement("div");
      card.className = "ss-asset";
      if (asset.kind === "image") {
        const img = document.createElement("img");
        img.className = "ss-asset-thumb";
        img.loading = "lazy";
        img.alt = asset.fileName || "asset";
        img.src = `${api}/node/${node.id}/asset/${asset.id}`;
        card.appendChild(img);
      } else {
        const ph = document.createElement("div");
        ph.className = "ss-asset-file";
        ph.textContent = asset.kind === "text" ? "📄" : "📎";
        card.appendChild(ph);
      }
      const name = document.createElement("span");
      name.className = "ss-asset-name";
      name.textContent = asset.fileName || asset.id;
      name.title = asset.fileName || "";
      card.appendChild(name);

      const del = document.createElement("button");
      del.type = "button";
      del.className = "ss-asset-del";
      del.textContent = "×";
      del.title = "Remove asset";
      del.addEventListener("click", () => removeAsset(node.id, asset.id));
      card.appendChild(del);

      el.nodeAssets.appendChild(card);
    });
  }

  async function onNodeAssetPicked() {
    if (!state.selected) return;
    const file = el.nodeAsset.files && el.nodeAsset.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    toast(`Uploading ${file.name}…`, "info");
    try {
      const res = await fetch(`${api}/node/${state.selected}/asset`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      const local = findNode(state.selected);
      if (local) { (local.assets = local.assets || []).push(data); }
      renderAssets(local);
      renderTree();
      toast(`Attached ${data.fileName}`, "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.nodeAsset.value = "";
    }
  }

  async function removeAsset(nodeId, assetId) {
    if (!confirm("Detach this asset from the section?")) return;
    try {
      await req("DELETE", `/node/${nodeId}/asset/${assetId}`);
      const local = findNode(nodeId);
      if (local && local.assets) local.assets = local.assets.filter((a) => a.id !== assetId);
      renderAssets(local);
      renderTree();
      toast("Asset detached.", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  // ---- Chat attachments (transient) ----

  function renderAttachments() {
    el.attachments.innerHTML = "";
    if (state.pending.length === 0) { el.attachments.hidden = true; return; }
    el.attachments.hidden = false;
    state.pending.forEach((f, i) => {
      const chip = document.createElement("span");
      chip.className = "ss-attach-chip";
      const label = document.createElement("span");
      label.textContent = `${f.kind === "image" ? "🖼" : "📄"} ${f.fileName}`;
      const rm = document.createElement("button");
      rm.type = "button";
      rm.textContent = "×";
      rm.title = "Remove";
      rm.addEventListener("click", () => { state.pending.splice(i, 1); renderAttachments(); });
      chip.appendChild(label);
      chip.appendChild(rm);
      el.attachments.appendChild(chip);
    });
  }

  async function onFilePicked() {
    const file = el.file.files && el.file.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    toast(`Uploading ${file.name}…`, "info");
    try {
      const res = await fetch(api + "/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      state.pending.push(data);
      renderAttachments();
      toast(`Attached ${data.fileName}`, "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.file.value = "";
    }
  }

  function collectImageUrls() {
    return state.pending.filter((f) => f.kind === "image" && f.dataUrl).map((f) => f.dataUrl);
  }

  function collectDraftText() {
    const texts = state.pending.filter((f) => f.kind === "text" && f.text).map((f) => `【${f.fileName}】\n${f.text}`);
    return texts.length ? texts.join("\n\n") : null;
  }

  // ---- Patch review ----

  function renderPatch(patch, valid, errors) {
    state.patch = patch;
    el.patch.hidden = false;
    el.patchSummary.textContent = patch.summary || "Proposed changes";
    el.patchBadge.textContent = valid ? `${patch.ops.length} ops · valid` : `invalid`;
    el.patchBadge.dataset.valid = valid ? "1" : "0";
    el.patchApply.disabled = !valid;

    el.patchOps.innerHTML = "";
    (patch.ops || []).forEach((op) => {
      const li = document.createElement("li");
      li.className = `ss-op ss-op-${(op.op || "").toLowerCase()}`;
      const head = document.createElement("div");
      head.className = "ss-op-head";
      const kind = document.createElement("span");
      kind.className = "ss-op-kind";
      kind.textContent = (op.op || "?").toUpperCase();
      const target = document.createElement("span");
      target.className = "ss-op-target";
      target.textContent = op.title || labelForId(op.targetId) || op.targetId || op.parentId || "";
      head.appendChild(kind);
      head.appendChild(target);
      li.appendChild(head);
      if (op.reason) {
        const reason = document.createElement("p");
        reason.className = "ss-op-reason";
        reason.textContent = op.reason;
        li.appendChild(reason);
      }
      if (op.content) {
        const body = document.createElement("pre");
        body.className = "ss-op-content";
        body.textContent = op.content.length > 600 ? op.content.slice(0, 600) + "…" : op.content;
        li.appendChild(body);
      }
      el.patchOps.appendChild(li);
    });
    if (!valid && errors && errors.length) {
      const err = document.createElement("li");
      err.className = "ss-op ss-op-error";
      err.textContent = "⚠ " + errors.join(" · ");
      el.patchOps.appendChild(err);
    }
  }

  function labelForId(id) {
    if (!id) return "";
    const n = findNode(id);
    return n ? `${n.number || ""} ${n.title || ""}`.trim() : "";
  }

  function clearPatch() {
    state.patch = null;
    el.patch.hidden = true;
    el.patchOps.innerHTML = "";
  }

  async function applyPatch() {
    if (!state.patch) return;
    el.patchApply.disabled = true;
    toast("Applying patch…", "info");
    try {
      const data = await req("POST", "/patch/apply", state.patch);
      state.tree = data.tree;
      renderTree();
      clearPatch();
      pushMessage("assistant", `Patch applied: ${(data.applied || []).join("; ") || "no changes"}. Index rebuilt.`);
      toast("Patch applied & reindexed.", "success");
      refreshRag();
    } catch (e) {
      toast(e.message, "error");
      el.patchApply.disabled = false;
    }
  }

  async function proposePatch(instruction) {
    const provider = modelProviderPayload();
    const payload = {
      instruction,
      draftText: collectDraftText(),
      imageDataUrls: collectImageUrls(),
      thinking: thinkingLevel(),
    };
    if (provider) payload.provider = provider;
    const thinkingEl = renderThinking("Drafting a patch across the whole book…");
    try {
      const data = await req("POST", "/patch/propose", payload);
      thinkingEl.remove();
      renderPatch(data.patch, data.valid, data.errors);
      pushMessage("assistant", `Proposed: ${data.patch.summary || "(changeset)"} — review below, then Apply.`);
      state.pending = [];
      renderAttachments();
      if (data.telemetry) renderTelemetry(data.telemetry);
    } catch (e) {
      thinkingEl.remove();
      if (e.status === 409) { state.holdsSlot = false; await refreshSlot(); }
      toast(e.message, "error");
    }
  }

  // ---- Chat transcript (with edit / delete / resend) ----

  function thinkingLevel() { return (el.thinking && el.thinking.value) || "high"; }

  // The transcript in state.chat is the single source of truth; we re-render from it.
  function pushMessage(role, content) {
    const m = { id: nextMsgId(), role, content };
    state.chat.push(m);
    renderChat();
    return m;
  }

  function renderThinking(text) {
    const t = document.createElement("div");
    t.className = "ss-msg ss-msg-ai ss-thinking";
    t.textContent = text;
    el.chat.appendChild(t);
    el.chat.scrollTop = el.chat.scrollHeight;
    return t;
  }

  function renderChat() {
    // Keep the seed greeting, drop everything else, rebuild from state.chat.
    el.chat.querySelectorAll(".ss-msg:not(.ss-msg-seed)").forEach((n) => n.remove());
    state.chat.forEach((m) => el.chat.appendChild(renderMessage(m)));
    el.chat.scrollTop = el.chat.scrollHeight;
  }

  function renderMessage(m) {
    const msg = document.createElement("div");
    msg.className = `ss-msg ss-msg-${m.role === "assistant" ? "ai" : "me"}`;
    msg.dataset.id = m.id;

    const body = document.createElement("div");
    body.className = "ss-msg-body";
    const p = document.createElement("p");
    p.textContent = m.content;
    body.appendChild(p);

    // hover actions
    const actions = document.createElement("div");
    actions.className = "ss-msg-actions";
    if (m.role === "user") {
      actions.appendChild(iconBtn("✎", "Edit", () => beginEdit(m.id)));
      actions.appendChild(iconBtn("↻", "Resend from here", () => resendFrom(m.id)));
    } else {
      actions.appendChild(iconBtn("↻", "Regenerate", () => regenerate(m.id)));
    }
    actions.appendChild(iconBtn("🗑", "Delete", () => deleteMessage(m.id)));
    body.appendChild(actions);

    msg.appendChild(body);

    if (m.citations && m.citations.length) {
      const cites = document.createElement("div");
      cites.className = "ss-cites";
      m.citations.forEach((c) => {
        const chip = document.createElement("span");
        chip.className = "ss-cite";
        chip.textContent = c;
        cites.appendChild(chip);
      });
      msg.appendChild(cites);
    }
    return msg;
  }

  function iconBtn(glyph, title, handler) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ss-msg-act";
    b.textContent = glyph;
    b.title = title;
    b.addEventListener("click", (e) => { e.stopPropagation(); handler(); });
    return b;
  }

  function indexOfMsg(id) { return state.chat.findIndex((m) => m.id === id); }

  function deleteMessage(id) {
    const i = indexOfMsg(id);
    if (i < 0) return;
    state.chat.splice(i, 1);
    renderChat();
  }

  function beginEdit(id) {
    const i = indexOfMsg(id);
    if (i < 0) return;
    const msgEl = el.chat.querySelector(`.ss-msg[data-id="${id}"] .ss-msg-body`);
    if (!msgEl) return;
    msgEl.querySelector("p").hidden = true;
    const actions = msgEl.querySelector(".ss-msg-actions");
    if (actions) actions.style.display = "none";

    const box = document.createElement("div");
    box.className = "ss-msg-edit";
    const ta = document.createElement("textarea");
    ta.value = state.chat[i].content;
    const row = document.createElement("div");
    row.className = "ss-msg-edit-row";
    const cancel = document.createElement("button");
    cancel.type = "button"; cancel.className = "ss-btn ss-btn-ghost ss-btn-sm"; cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => renderChat());
    const saveResend = document.createElement("button");
    saveResend.type = "button"; saveResend.className = "ss-btn ss-btn-sm"; saveResend.textContent = "Save & resend";
    saveResend.addEventListener("click", () => {
      state.chat[i].content = ta.value.trim();
      resendFrom(id);
    });
    const saveOnly = document.createElement("button");
    saveOnly.type = "button"; saveOnly.className = "ss-btn ss-btn-ghost ss-btn-sm"; saveOnly.textContent = "Save";
    saveOnly.addEventListener("click", () => { state.chat[i].content = ta.value.trim(); renderChat(); });
    row.appendChild(cancel); row.appendChild(saveOnly); row.appendChild(saveResend);
    box.appendChild(ta); box.appendChild(row);
    msgEl.appendChild(box);
    ta.focus();
  }

  // Truncate everything after this user message, then re-ask the co-author.
  async function resendFrom(id) {
    const i = indexOfMsg(id);
    if (i < 0 || state.chat[i].role !== "user") return;
    const text = state.chat[i].content;
    state.chat = state.chat.slice(0, i + 1); // drop later turns
    renderChat();
    await askCoauthor(text);
  }

  // Regenerate an assistant reply: find the user turn before it and resend.
  async function regenerate(id) {
    const i = indexOfMsg(id);
    if (i < 0) return;
    let u = i - 1;
    while (u >= 0 && state.chat[u].role !== "user") u--;
    if (u < 0) return;
    await resendFrom(state.chat[u].id);
  }

  // History for the API = all turns before the last user message we're answering.
  function historyForApi() {
    return state.chat
      .filter((m) => m.content && (m.role === "user" || m.role === "assistant"))
      .slice(-16)
      .map((m) => ({ role: m.role, content: m.content }));
  }

  async function askCoauthor(text) {
    el.chatSend.disabled = true;
    const thinkingEl = renderThinking("Consulting the whole book…");
    // history excludes the just-added user turn (it's the message being answered).
    const hist = historyForApi();
    if (hist.length && hist[hist.length - 1].role === "user" && hist[hist.length - 1].content === text) hist.pop();
    try {
      const provider = modelProviderPayload();
      const payload = {
        message: text,
        history: hist.slice(-8),
        imageDataUrls: collectImageUrls(),
        thinking: thinkingLevel(),
      };
      if (provider) payload.provider = provider;
      const data = await req("POST", "/chat", payload);
      thinkingEl.remove();
      const m = { id: nextMsgId(), role: "assistant", content: data.reply || "(no reply)", citations: data.citations };
      state.chat.push(m);
      renderChat();
      state.pending = [];
      renderAttachments();
      refreshCache();
      if (data.telemetry) { renderTelemetry(data.telemetry); state.holdsSlot = true; refreshSlot(); }
    } catch (err) {
      thinkingEl.remove();
      if (err.status === 409) { state.holdsSlot = false; await refreshSlot(); }
      toast(err.message, "error");
    } finally {
      el.chatSend.disabled = false;
    }
  }

  async function sendChat(e) {
    e.preventDefault();
    const text = el.chatInput.value.trim();
    if (!text && state.pending.length === 0) return;

    if (el.patchMode && el.patchMode.checked) {
      const shown = text || "(place the attached draft)";
      pushMessage("user", shown);
      el.chatInput.value = "";
      el.chatSend.disabled = true;
      try { await proposePatch(shown); } finally { el.chatSend.disabled = false; }
      return;
    }

    pushMessage("user", text);
    el.chatInput.value = "";
    await askCoauthor(text);
  }

  function clearChat() {
    if (state.chat.length && !confirm("Clear the whole conversation?")) return;
    state.chat = [];
    renderChat();
  }

  function modelProviderFromFields() {
    const provider = {
      label: (el.modelLabel && el.modelLabel.value.trim()) || "",
      baseUrl: (el.modelBaseUrl && el.modelBaseUrl.value.trim()) || "",
      apiKey: (el.modelApiKey && el.modelApiKey.value.trim()) || "",
      model: (el.modelName && el.modelName.value.trim()) || "",
      maxContextTokens: el.modelContext && el.modelContext.value ? Number(el.modelContext.value) : null,
    };
    const any = provider.label || provider.baseUrl || provider.apiKey || provider.model || provider.maxContextTokens;
    if (!any) return null;
    if (!provider.baseUrl || !provider.apiKey || !provider.model) {
      throw new Error("Model provider needs Base URL, API key, and model.");
    }
    if (provider.maxContextTokens !== null && (!Number.isInteger(provider.maxContextTokens) || provider.maxContextTokens <= 0)) {
      throw new Error("Max context must be a positive whole number.");
    }
    return provider;
  }

  function modelProviderPayload() {
    const provider = modelProviderFromFields();
    if (!provider) return null;
    return {
      baseUrl: provider.baseUrl,
      apiKey: provider.apiKey,
      model: provider.model,
      maxContextTokens: provider.maxContextTokens,
    };
  }

  function setModelProviderFields(provider) {
    if (el.modelLabel) el.modelLabel.value = provider?.label || "";
    if (el.modelBaseUrl) el.modelBaseUrl.value = provider?.baseUrl || "";
    if (el.modelApiKey) el.modelApiKey.value = provider?.apiKey || "";
    if (el.modelName) el.modelName.value = provider?.model || "";
    if (el.modelContext) el.modelContext.value = provider?.maxContextTokens || "";
  }

  function loadModelProvider() {
    if (!el.modelConfigPanel) return;
    try {
      const saved = localStorage.getItem(modelProviderKey);
      setModelProviderFields(saved ? JSON.parse(saved) : null);
    } catch {
      setModelProviderFields(null);
    }
  }

  function saveModelProvider() {
    try {
      const provider = modelProviderFromFields();
      if (provider) {
        localStorage.setItem(modelProviderKey, JSON.stringify(provider));
        toast("Model provider saved.", "success");
      } else {
        localStorage.removeItem(modelProviderKey);
        toast("Model provider cleared.", "info");
      }
    } catch (e) {
      toast(e.message, "error");
    }
  }

  function clearModelProvider() {
    localStorage.removeItem(modelProviderKey);
    setModelProviderFields(null);
    toast("Model provider cleared.", "info");
  }

  // ---- init ----

  // ---- panel fullscreen ----

  function setPanelFullscreen(panel, on) {
    if (!panel) return;
    if (on) {
      // Only one panel may be fullscreen at a time.
      document.querySelectorAll(".ss-panel.is-fullscreen").forEach((p) => {
        if (p !== panel) p.classList.remove("is-fullscreen");
      });
      panel.classList.add("is-fullscreen");
      document.body.classList.add("ss-panel-maxed");
      if (!document.querySelector(".ss-panel-backdrop")) {
        const bd = document.createElement("div");
        bd.className = "ss-panel-backdrop";
        bd.addEventListener("click", () => exitFullscreen());
        document.body.appendChild(bd);
      }
    } else {
      panel.classList.remove("is-fullscreen");
      if (!document.querySelector(".ss-panel.is-fullscreen")) {
        document.body.classList.remove("ss-panel-maxed");
        const bd = document.querySelector(".ss-panel-backdrop");
        if (bd) bd.remove();
      }
    }
  }

  function togglePanelFullscreen(btn) {
    const panel = btn.closest(".ss-panel");
    if (!panel) return;
    setPanelFullscreen(panel, !panel.classList.contains("is-fullscreen"));
  }

  function exitFullscreen() {
    document.querySelectorAll(".ss-panel.is-fullscreen").forEach((p) => {
      p.classList.remove("is-fullscreen");
    });
    document.body.classList.remove("ss-panel-maxed");
    const bd = document.querySelector(".ss-panel-backdrop");
    if (bd) bd.remove();
  }

  function bind() {
    if (el.gateForm) el.gateForm.addEventListener("submit", doLogin);
    el.decompose.addEventListener("click", decompose);
    el.exportTree.addEventListener("click", exportTree);
    el.rebuild.addEventListener("click", rebuildIndex);
    el.viewMap.addEventListener("click", () => setView("map"));
    el.viewList.addEventListener("click", () => setView("list"));
    el.treeFilter.addEventListener("input", applyFilter);
    el.save.addEventListener("click", saveNode);
    el.addChild.addEventListener("click", addChild);
    el.del.addEventListener("click", deleteNode);
    el.exportNode.addEventListener("click", exportNode);
    el.importNode.addEventListener("change", importNode);
    el.nodeAsset.addEventListener("change", onNodeAssetPicked);
    el.langSelect.addEventListener("change", () => loadLang(el.langSelect.value));
    el.translate.addEventListener("click", translate);
    el.saveLang.addEventListener("click", saveLang);
    el.chatForm.addEventListener("submit", sendChat);
    el.chatClear.addEventListener("click", clearChat);
    if (el.modelConfig) el.modelConfig.addEventListener("click", () => {
      if (el.modelConfigPanel) el.modelConfigPanel.hidden = !el.modelConfigPanel.hidden;
    });
    if (el.modelSaveConfig) el.modelSaveConfig.addEventListener("click", saveModelProvider);
    if (el.modelClearConfig) el.modelClearConfig.addEventListener("click", clearModelProvider);
    el.file.addEventListener("change", onFilePicked);
    el.patchApply.addEventListener("click", applyPatch);
    el.patchReject.addEventListener("click", () => { clearPatch(); toast("Patch rejected.", "info"); });
    el.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); el.chatForm.requestSubmit(); }
    });
    document.querySelectorAll(".ss-panel-expand").forEach((btn) => {
      btn.addEventListener("click", () => togglePanelFullscreen(btn));
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && document.querySelector(".ss-panel.is-fullscreen")) {
        exitFullscreen();
      }
    });
  }

  async function init() {
    bind();
    loadModelProvider();
    setView("map");
    // Pollers start now; they no-op meaningfully until auth resolves.
    state.ragTimer = setInterval(refreshRag, 30000);
    state.cacheTimer = setInterval(refreshCache, 15000);
    state.slotTimer = setInterval(refreshSlot, 10000);

    // Release the AI slot when the tab closes so another session can take over at once.
    window.addEventListener("beforeunload", () => {
      if (navigator.sendBeacon) navigator.sendBeacon(api + "/slot/release", "");
    });

    const authed = await checkAuth();
    if (!authed) return; // gate is shown; doLogin() finishes bootstrapping after unlock.

    await Promise.all([refreshTelemetry(), refreshSlot(), claimSlot(), loadTree().catch(() => {}), refreshRag(true), refreshCache()]);
  }

  init();
})();
