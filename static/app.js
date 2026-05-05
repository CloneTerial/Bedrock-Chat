/* ── State ───────────────────────────────────────────────────────────── */
let convId = null;
let models = {};
let settings = {};
let streaming = false;
let abort = null;
let editingIndex = null;
let selectedFiles = [];
let allConversations = [];

/* ── Init ────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  await loadModels();
  await loadSettings();
  await loadConvList();
  setupImageClicks();
  setupKeyboardShortcuts();
  
  // Check for hash-based navigation (e.g. #conv-id)
  const hash = location.hash.slice(1);
  if (hash) await loadConv(hash).catch(() => {});
  document.getElementById("msgIn").focus();
});

/* ── Markdown / highlight setup ─────────────────────────────────────── */
const renderer = new marked.Renderer();
renderer.code = function (code, lang) {
  if (typeof code === "object") {
    lang = code.lang;
    code = code.text;
  }
  lang = (lang || "").split(/\s+/)[0] || "plaintext";
  let hl;
  try {
    hl = hljs.getLanguage(lang)
      ? hljs.highlight(code, { language: lang }).value
      : hljs.highlightAuto(code).value;
  } catch {
    hl = esc(code);
  }
  const renderBtn = ["html", "svg", "mermaid"].includes(lang)
    ? `<button class="cp" onclick="renderArt(this, '${lang}')">Render</button>`
    : "";
  return `<pre><div class="ch"><span>${esc(lang)}</span><div style="display:flex;gap:8px">${renderBtn}<button class="cp" onclick="cpCode(this)">Copy</button></div></div><code class="hljs">${hl}</code></pre>`;
};
marked.setOptions({ renderer, breaks: true, gfm: true });

function md(text) {
  if (!text) return "";
  let processedText = text;
  if (processedText.includes("<think>")) {
    processedText = processedText.replace(
      /<think>([\s\S]*?)<\/think>/g,
      '<details class="think-block" open><summary>🧠 Thought Process</summary><div class="think-content">$1</div></details>',
    );
  }
  try {
    return marked.parse(processedText);
  } catch {
    return `<p>${esc(processedText)}</p>`;
  }
}
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
function cpCode(btn) {
  const code = btn.closest("pre").querySelector("code").textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = "Copied!";
    setTimeout(() => (btn.textContent = "Copy"), 1600);
  });
}

/* ── API helpers ─────────────────────────────────────────────────────── */
const api = (path, opts) =>
  fetch("/api/" + path, opts).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });

async function loadModels() {
  try {
    models = await api("models");
  } catch {
    models = {};
  }
  const grouped = {};
  for (const [id, m] of Object.entries(models)) {
    (grouped[m.provider] ||= []).push({ id, ...m });
  }
  let html = "";
  for (const [prov, list] of Object.entries(grouped)) {
    html += `<optgroup label="${esc(prov)}">`;
    list.forEach((m) => {
      html += `<option value="${esc(m.id)}">${esc(m.name)}</option>`;
    });
    html += `</optgroup>`;
  }
  document.getElementById("modelSel").innerHTML = html;
  document.getElementById("defMod").innerHTML = html;
}

async function loadSettings() {
  try {
    settings = await api("settings");
  } catch {
    settings = {
      system_prompt: "",
      default_model: "",
      temperature: 0.7,
      max_tokens: 4096,
      tools_enabled: true,
    };
  }
  applySettings(settings);
}

function applySettings(s) {
  const sel = document.getElementById("modelSel");
  if (s.default_model) sel.value = s.default_model;
  document.getElementById("modelLbl").textContent = modelName(sel.value);
  document.getElementById("sysP").value = s.system_prompt || "";
  document.getElementById("defMod").value = s.default_model || sel.value;
  document.getElementById("tSlider").value = s.temperature || 0.7;
  document.getElementById("tVal").textContent = s.temperature || 0.7;
  document.getElementById("mTok").value = s.max_tokens || 4096;
  document.getElementById("tDef").checked = s.tools_enabled !== false;
  document.getElementById("toolsTog").checked = s.tools_enabled !== false;
}

async function loadConvList() {
  let list = [];
  try {
    list = await api("conversations");
  } catch {
    return;
  }
  allConversations = list;
  renderChatList(list);
  const total = list.reduce((s, c) => s + (c.total_cost || 0), 0);
  document.getElementById("totalCost").textContent = `Session total: $${total.toFixed(6)}`;
}

function renderChatList(list) {
  const el = document.getElementById("chatList");
  if (list.length === 0) {
    el.innerHTML = `<div style="padding:20px;font-size:13px;color:var(--tx-dim);text-align:center">No conversations yet</div>`;
  } else {
    el.innerHTML = list
      .map(
        (c) =>
          `<div class="chat-item${c.id === convId ? " active" : ""}" onclick="loadConv('${c.id}')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span class="ci-t" title="${esc(c.title)}">${esc(c.title)}</span>
        <button class="ci-d" onclick="event.stopPropagation();delConv('${c.id}')" title="Delete">✕</button>
      </div>`,
      )
      .join("");
  }
}

function modelName(id) {
  return models[id]?.name || id || "Unknown model";
}

/* ── Conversations ───────────────────────────────────────────────────── */
function newChat() {
  convId = null;
  location.hash = "";
  const msgs = document.getElementById("msgs");
  msgs.innerHTML = "";
  const wel = document.createElement("div");
  wel.className = "welcome";
  wel.id = "welcome";
  wel.innerHTML = `
    <div class="w-icon">⚡</div>
    <h1>Bedrock AI Chat</h1>
    <p>Premium Interface — Powered by AWS Bedrock</p>
    <div class="hints">
      <button onclick="useHint(this)">Explain quantum computing simply</button>
      <button onclick="useHint(this)">Write a Python web scraper</button>
      <button onclick="useHint(this)">Help me debug my code</button>
      <button onclick="useHint(this)">Create a business plan outline</button>
    </div>`;
  msgs.appendChild(wel);
  resetTok();
  loadConvList();
  document.getElementById("msgIn").focus();
  if (window.innerWidth <= 768) toggleSidebar(false);
}

async function loadConv(id) {
  let c;
  try {
    c = await api(`conversations/${id}`);
  } catch {
    return;
  }
  convId = id;
  location.hash = id;
  const el = document.getElementById("msgs");
  el.innerHTML = "";

  for (const m of c.messages) {
    if (m.role === "user" && Array.isArray(m.content) && m.content.every((b) => b.toolResult)) continue;

    if (m.role === "user") {
      const text = (m.content || []).filter((b) => b.text).map((b) => b.text).join("\n");
      if (text.trim()) addMsgHtml("user", md(text));
    }

    if (m.role === "assistant") {
      let html = "";
      for (const b of m.content || []) {
        if (b.text) html += md(b.text);
        if (b.toolUse) html += toolHtml(b.toolUse.name, b.toolUse.input, null);
      }
      if (html) addMsgHtml("assistant", html);
    }
  }

  updateTok({
    input_tokens: c.total_input_tokens,
    output_tokens: c.total_output_tokens,
    cost: c.total_cost,
  });
  loadConvList();
  scrollDown();
  if (window.innerWidth <= 768) toggleSidebar(false);
}

async function delConv(id) {
  if (!confirm("Delete this conversation?")) return;
  try {
    await api(`conversations/${id}`, { method: "DELETE" });
  } catch {
    return;
  }
  if (convId === id) newChat();
  else loadConvList();
}

/* ── Send message ────────────────────────────────────────────────────── */
function useHint(btn) {
  document.getElementById("msgIn").value = btn.textContent;
  send();
}
function onKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    onSendClick();
  }
}
function onSendClick() {
  if (streaming) stopStream();
  else send();
}
function stopStream() {
  abort?.abort();
}

async function send() {
  const inp = document.getElementById("msgIn");
  const text = inp.value.trim();
  if (!text || streaming) return;

  if (editingIndex !== null) {
    const wrap = document.getElementById("msgs");
    while (wrap.children.length > editingIndex) wrap.removeChild(wrap.lastChild);
  }

  const uploaded = await uploadFiles();
  streaming = true;
  setSendBtn(true);
  inp.value = "";
  autoGrow(inp);

  const w = document.getElementById("welcome");
  if (w) w.remove();

  addMsgHtml("user", md(text));
  const aEl = addMsgHtml("assistant", '<div class="dots"><span></span><span></span><span></span></div>');
  const ct = aEl.querySelector(".m-ct");
  scrollDown();

  let fullMessage = text;
  if (uploaded && uploaded.length > 0) {
    fullMessage += `\n\n[System Note: User uploaded: ${uploaded.join(", ")}]`;
  }

  const body = {
    message: fullMessage,
    conversation_id: convId,
    model: document.getElementById("modelSel").value,
    temperature: parseFloat(settings.temperature ?? 0.7),
    max_tokens: parseInt(settings.max_tokens ?? 4096),
    tools_enabled: document.getElementById("toolsTog").checked,
    edit_index: editingIndex,
  };

  editingIndex = null;
  abort = new AbortController();
  let accumulated = "";
  let streamText = "";
  let firstChunk = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: abort.signal,
    });

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";

      for (const ln of lines) {
        if (!ln.startsWith("data: ")) continue;
        let d = JSON.parse(ln.slice(6));

        switch (d.type) {
          case "conversation_id":
            convId = d.id;
            location.hash = d.id;
            break;
          case "text":
            if (firstChunk) { ct.innerHTML = ""; firstChunk = false; }
            streamText += d.content;
            ct.innerHTML = accumulated + md(streamText);
            if (nearBottom()) scrollDown();
            break;
          case "tool_start":
            if (streamText) { accumulated += md(streamText); streamText = ""; }
            accumulated += `<div class="tool-call-ui"><div class="tc-head">🔧 Calling: ${esc(d.name)}</div>`;
            ct.innerHTML = accumulated;
            break;
          case "tool_exec":
            // Optional: show input
            break;
          case "tool_result":
            accumulated += `<div class="tc-body">${esc(JSON.stringify(d.result, null, 2))}</div></div>`;
            firstChunk = true;
            ct.innerHTML = accumulated;
            break;
          case "metadata":
            updateTok(d);
            loadConvList();
            break;
          case "error":
            ct.innerHTML += `<div class="err">⚠ ${esc(d.message)}</div>`;
            break;
          case "done":
            ct.innerHTML = accumulated + md(streamText);
            ct.querySelectorAll("pre code:not(.hljs)").forEach(el => hljs.highlightElement(el));
            scrollDown();
            break;
        }
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") ct.innerHTML += `<div class="err">⚠ ${esc(err.message)}</div>`;
  } finally {
    streaming = false;
    setSendBtn(false);
    loadConvList();
  }
}

/* ── UI helpers ──────────────────────────────────────────────────────── */
function addMsgHtml(role, html) {
  const wrap = document.getElementById("msgs");
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  
  const actions = role === "user" 
    ? `<div class="msg-actions"><button onclick="copyMsg(this)">Copy</button><button onclick="editMsg(this)">Edit</button></div>`
    : `<div class="msg-actions"><button onclick="copyMsg(this)">Copy</button></div>`;

  div.innerHTML = `
    <div class="msg-content">
      <div class="msg-meta">${role === "user" ? "You" : "Assistant"} ${actions}</div>
      <div class="m-ct">${html}</div>
    </div>`;
  wrap.appendChild(div);
  return div;
}

function toolHtml(name, input, result) {
  return `<div class="tool-call-ui">
    <div class="tc-head">🔧 Tool: ${esc(name)}</div>
    <div class="tc-body">${esc(JSON.stringify(input, null, 2))}</div>
  </div>`;
}

function updateTok(d) {
  const inp = d.input_tokens ?? d.total_input_tokens ?? 0;
  const out = d.output_tokens ?? d.total_output_tokens ?? 0;
  const cost = d.cost ?? d.total_cost ?? 0;
  document.getElementById("tokInfo").innerHTML =
    `<span title="Input">↑ ${inp.toLocaleString()}</span>` +
    `<span title="Output">↓ ${out.toLocaleString()}</span>` +
    `<span title="Cost">$${cost.toFixed(6)}</span>`;
}

function resetTok() {
  document.getElementById("tokInfo").innerHTML = `<span>↑ 0</span><span>↓ 0</span><span>$0.000000</span>`;
}

function setSendBtn(isStreaming) {
  const btn = document.getElementById("sendBtn");
  document.getElementById("icSend").style.display = isStreaming ? "none" : "";
  document.getElementById("icStop").style.display = isStreaming ? "" : "none";
}

function scrollDown() {
  const w = document.getElementById("msgsWrap");
  w.scrollTop = w.scrollHeight;
}

function nearBottom() {
  const w = document.getElementById("msgsWrap");
  return w.scrollHeight - w.scrollTop - w.clientHeight < 150;
}

function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 200) + "px";
}

function onModelChange() {
  const id = document.getElementById("modelSel").value;
  document.getElementById("modelLbl").textContent = modelName(id);
}

function toggleSidebar(force) {
  const sb = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  const isMobile = window.innerWidth <= 768;
  
  if (isMobile) {
    // Mobile: Toggle 'open' class
    const isOpen = force !== undefined ? force : !sb.classList.contains("open");
    sb.classList.toggle("open", isOpen);
    if (overlay) overlay.classList.toggle("open", isOpen);
  } else {
    // Desktop: Toggle 'closed' class for width/transform transition
    const isClosed = force !== undefined ? !force : !sb.classList.contains("closed");
    sb.classList.toggle("closed", isClosed);
  }
}

function toggleArt() {
  document.getElementById("artPanel").classList.toggle("open");
}

function bgClose(e) {
  if (e.target === document.getElementById("setModal")) closeSettings();
}

function openSettings() { document.getElementById("setModal").classList.add("open"); }
function closeSettings() { document.getElementById("setModal").classList.remove("open"); }

async function saveSettings() {
  const newSettings = {
    system_prompt: document.getElementById("sysP").value,
    default_model: document.getElementById("defMod").value,
    temperature: parseFloat(document.getElementById("tSlider").value),
    max_tokens: parseInt(document.getElementById("mTok").value),
    tools_enabled: document.getElementById("tDef").checked,
  };
  try {
    settings = await api("settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newSettings),
    });
    applySettings(settings);
    closeSettings();
  } catch (e) { alert(e.message); }
}

function resetSettings() {
  if (!settings.default_system_prompt) return;
  document.getElementById("sysP").value = settings.default_system_prompt;
}

function copyMsg(btn) {
  const text = btn.closest(".msg-content").querySelector(".m-ct").innerText;
  navigator.clipboard.writeText(text).then(() => {
    btn.innerText = "Copied!";
    setTimeout(() => (btn.innerText = "Copy"), 1500);
  });
}

function editMsg(btn) {
  const msgDiv = btn.closest(".msg");
  const allMsgs = Array.from(document.getElementById("msgs").children);
  editingIndex = allMsgs.indexOf(msgDiv);
  const text = msgDiv.querySelector(".m-ct").innerText;
  const inputEl = document.getElementById("msgIn");
  inputEl.value = text;
  inputEl.focus();
  autoGrow(inputEl);
}

/* ── Theme ───────────────────────────────────────────────────────────── */
function toggleTheme() {
  const html = document.documentElement;
  const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const btn = document.getElementById("themeBtn");
  if (!btn) return;
  btn.innerHTML = theme === "dark" 
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`;
}

function initTheme() {
  const theme = localStorage.getItem("theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
  updateThemeIcon(theme);
}

/* ── Files ───────────────────────────────────────────────────────────── */
function onFileChange() {
  const el = document.getElementById("fileIn");
  for (const f of el.files) if (!selectedFiles.find(sf => sf.name === f.name)) selectedFiles.push(f);
  renderFileChips();
  el.value = "";
}

function renderFileChips() {
  document.getElementById("fileChips").innerHTML = selectedFiles
    .map((f, i) => `<div class="f-chip">📄 ${esc(f.name)} <b onclick="removeFile(${i})">✕</b></div>`).join("");
}

function removeFile(i) { selectedFiles.splice(i, 1); renderFileChips(); }

async function uploadFiles() {
  if (selectedFiles.length === 0) return [];
  const fd = new FormData();
  selectedFiles.forEach(f => fd.append("files", f));
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    selectedFiles = []; renderFileChips();
    return data.filenames;
  } catch (e) { return []; }
}

function filterChats(q) {
  const query = q.toLowerCase();
  renderChatList(allConversations.filter(c => c.title.toLowerCase().includes(query)));
}

function setupImageClicks() {
  document.addEventListener("click", e => {
    if (e.target.tagName === "IMG" && e.target.closest(".m-ct")) {
      const m = document.getElementById("imgModal");
      document.getElementById("imgModalContent").src = e.target.src;
      m.classList.add("open");
    }
  });
}
function closeImgModal() { document.getElementById("imgModal").classList.remove("open"); }

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "n") { e.preventDefault(); newChat(); }
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); onSendClick(); }
    if ((e.ctrlKey || e.metaKey) && e.key === "/") { e.preventDefault(); toggleSidebar(); }
    if (e.key === "Escape") { closeImgModal(); closeSettings(); }
  });
}
