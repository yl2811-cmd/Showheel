// Story Studio — client for the AI-managed story tree + RAG co-author.
// All AI/story content is inserted via textContent (never innerHTML) to avoid XSS.
(function () {
  "use strict";

  const api = "/api/story";
  const $ = (id) => document.getElementById(id);

  const el = {
    tree: $("ss-tree"),
    treeEmpty: $("ss-tree-empty"),
    decompose: $("ss-decompose"),
    rebuild: $("ss-rebuild"),
    rag: $("ss-rag"),
    ragText: $("ss-rag-text"),
    toasts: $("ss-toasts"),
    nodeTitle: $("ss-node-title"),
    editTitle: $("ss-edit-title"),
    editContent: $("ss-edit-content"),
    save: $("ss-save"),
    addChild: $("ss-add-child"),
    del: $("ss-delete"),
    translate: $("ss-translate"),
    translation: $("ss-translation"),
    translationBody: $("ss-translation-body"),
    translationClose: $("ss-translation-close"),
    chat: $("ss-chat"),
    chatForm: $("ss-chat-form"),
    chatInput: $("ss-chat-input"),
    chatSend: $("ss-chat-send"),
    audit: $("ss-audit"),
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
  };

  // pending = attachments staged for the next message; patch = the proposed changeset.
  const state = { tree: null, selected: null, chatHistory: [], ragTimer: null, pending: [], patch: null };

  // ---- helpers ----

  async function req(method, path, body) {
    const res = await fetch(api + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch { /* no body */ }
    if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
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

  // ---- RAG status ----

  function renderRag(status) {
    const state = (status && status.state) || "Unknown";
    const map = {
      Ready: "ready",
      Indexing: "indexing",
      Empty: "empty",
      NotConfigured: "off",
      Error: "error",
      Unknown: "unknown",
    };
    el.rag.dataset.state = map[state] || "unknown";
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
    } catch (e) {
      renderRag({ state: "Error", message: "RAG status error" });
    }
  }

  async function rebuildIndex() {
    el.rebuild.disabled = true;
    toast("Rebuilding RAG index…", "info");
    try {
      // Poll status while the rebuild runs so the UI shows progress.
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

  // ---- Tree ----

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
  }

  function renderNode(node) {
    const wrap = document.createElement("div");
    wrap.className = "ss-node";
    wrap.style.setProperty("--depth", node.depth || 0);

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
    row.addEventListener("click", () => selectNode(node.id));
    if (state.selected === node.id) row.classList.add("is-selected");

    wrap.appendChild(row);
    if (node.children && node.children.length) {
      node.children.forEach((c) => wrap.appendChild(renderNode(c)));
    }
    return wrap;
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

  function selectNode(id) {
    state.selected = id;
    const node = findNode(id);
    if (!node) return;
    el.nodeTitle.textContent = `${node.number || ""} ${node.title || ""}`.trim();
    el.editTitle.value = node.title || "";
    el.editContent.value = node.content || "";
    [el.editTitle, el.editContent, el.save, el.addChild, el.del, el.translate].forEach((b) => (b.disabled = false));
    el.translation.hidden = true;
    document.querySelectorAll(".ss-node-row").forEach((r) => r.classList.toggle("is-selected", r.dataset.id === id));
  }

  async function loadTree() {
    const data = await req("GET", "/tree");
    state.tree = data.tree;
    renderTree();
  }

  async function decompose() {
    el.decompose.disabled = true;
    toast("Decomposing story into tree…", "info");
    try {
      const data = await req("POST", "/decompose", {});
      state.tree = data.tree;
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
      el.nodeTitle.textContent = "Select a section";
      el.editTitle.value = "";
      el.editContent.value = "";
      [el.editTitle, el.editContent, el.save, el.addChild, el.del, el.translate].forEach((b) => (b.disabled = true));
      toast("Section pruned.", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  // ---- Translation (separate model) ----

  async function translate() {
    if (!state.selected) return;
    const node = findNode(state.selected);
    if (!node || !node.content) { toast("Nothing to translate.", "warn"); return; }
    el.translate.disabled = true;
    el.translation.hidden = false;
    el.translationBody.textContent = "Translating…";
    try {
      const data = await req("POST", "/translate", { text: node.content, targetLang: "English" });
      el.translationBody.textContent = data.translation || "(empty)";
    } catch (e) {
      el.translationBody.textContent = "";
      toast(e.message, "error");
    } finally {
      el.translate.disabled = false;
    }
  }

  // ---- Co-author chat ----

  function thinkingLevel() {
    return (el.thinking && el.thinking.value) || "high";
  }

  // ---- Attachments (txt drafts / images) ----

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
      appendChat("assistant", `Patch applied: ${(data.applied || []).join("; ") || "no changes"}. Index rebuilt.`);
      toast("Patch applied & reindexed.", "success");
      refreshRag();
    } catch (e) {
      toast(e.message, "error");
      el.patchApply.disabled = false;
    }
  }

  async function proposePatch(instruction) {
    const payload = {
      instruction,
      draftText: collectDraftText(),
      imageDataUrls: collectImageUrls(),
      thinking: thinkingLevel(),
    };
    const thinking = document.createElement("div");
    thinking.className = "ss-msg ss-msg-ai ss-thinking";
    thinking.textContent = "Drafting a patch across the whole book…";
    el.chat.appendChild(thinking);
    el.chat.scrollTop = el.chat.scrollHeight;
    try {
      const data = await req("POST", "/patch/propose", payload);
      thinking.remove();
      renderPatch(data.patch, data.valid, data.errors);
      appendChat("assistant", `Proposed: ${data.patch.summary || "(changeset)"} — review below, then Apply.`);
      state.pending = [];
      renderAttachments();
    } catch (e) {
      thinking.remove();
      toast(e.message, "error");
    }
  }

  function appendChat(role, text, citations) {
    const msg = document.createElement("div");
    msg.className = `ss-msg ss-msg-${role === "assistant" ? "ai" : "me"}`;
    const p = document.createElement("p");
    p.textContent = text;
    msg.appendChild(p);
    if (citations && citations.length) {
      const cites = document.createElement("div");
      cites.className = "ss-cites";
      citations.forEach((c) => {
        const chip = document.createElement("span");
        chip.className = "ss-cite";
        chip.textContent = c;
        cites.appendChild(chip);
      });
      msg.appendChild(cites);
    }
    el.chat.appendChild(msg);
    el.chat.scrollTop = el.chat.scrollHeight;
  }

  async function sendChat(e) {
    e.preventDefault();
    const text = el.chatInput.value.trim();
    if (!text && state.pending.length === 0) return;
    el.chatSend.disabled = true;

    // Patch mode: ask the co-author for a reviewable changeset instead of a chat reply.
    if (el.patchMode && el.patchMode.checked) {
      const shown = text || "(place the attached draft)";
      appendChat("user", shown);
      el.chatInput.value = "";
      try {
        await proposePatch(shown);
      } finally {
        el.chatSend.disabled = false;
      }
      return;
    }

    appendChat("user", text);
    el.chatInput.value = "";

    const thinking = document.createElement("div");
    thinking.className = "ss-msg ss-msg-ai ss-thinking";
    thinking.textContent = "Consulting the whole book…";
    el.chat.appendChild(thinking);
    el.chat.scrollTop = el.chat.scrollHeight;

    const images = collectImageUrls();
    try {
      const data = await req("POST", "/chat", {
        message: text,
        history: state.chatHistory.slice(-8),
        imageDataUrls: images,
        thinking: thinkingLevel(),
      });
      thinking.remove();
      appendChat("assistant", data.reply || "(no reply)", data.citations);
      state.chatHistory.push({ role: "user", content: text });
      state.chatHistory.push({ role: "assistant", content: data.reply || "" });
      state.pending = [];
      renderAttachments();
    } catch (err) {
      thinking.remove();
      toast(err.message, "error");
    } finally {
      el.chatSend.disabled = false;
    }
  }

  async function audit() {
    el.audit.disabled = true;
    appendChat("assistant", "Auditing the whole book for duplication / contradiction / stale content…");
    try {
      const data = await req("POST", "/audit", { thinking: thinkingLevel() });
      appendChat("assistant", data.report || "(no findings)");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      el.audit.disabled = false;
    }
  }

  // ---- init ----

  function bind() {
    el.decompose.addEventListener("click", decompose);
    el.rebuild.addEventListener("click", rebuildIndex);
    el.save.addEventListener("click", saveNode);
    el.addChild.addEventListener("click", addChild);
    el.del.addEventListener("click", deleteNode);
    el.translate.addEventListener("click", translate);
    el.translationClose.addEventListener("click", () => (el.translation.hidden = true));
    el.chatForm.addEventListener("submit", sendChat);
    el.audit.addEventListener("click", audit);
    el.file.addEventListener("change", onFilePicked);
    el.patchApply.addEventListener("click", applyPatch);
    el.patchReject.addEventListener("click", () => { clearPatch(); toast("Patch rejected.", "info"); });
    el.chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); el.chatForm.requestSubmit(); }
    });
  }

  async function init() {
    bind();
    await Promise.all([loadTree().catch(() => {}), refreshRag(true)]);
    // Light heartbeat so the RAG notification stays honest.
    state.ragTimer = setInterval(refreshRag, 30000);
  }

  init();
})();
