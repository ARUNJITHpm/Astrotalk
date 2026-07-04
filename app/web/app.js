// Tara chat — streams the assistant reply token-by-token, Claude-desktop style.
(() => {
  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("composer-form");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const historyEl = document.getElementById("history");
  const historyEmpty = document.getElementById("history-empty");
  const newChatBtn = document.getElementById("new-chat");
  const memoryPanel = document.getElementById("memory-panel");
  const memoryFacts = document.getElementById("memory-facts");
  const memoryToggle = document.getElementById("memory-toggle");
  const changeNumberBtn = document.getElementById("change-number");
  const logoutBtn = document.getElementById("logout-btn");
  const userBadge = document.getElementById("user-badge");
  const profileModal = document.getElementById("profile-modal");
  const profileClose = document.getElementById("profile-close");
  const profileLogout = document.getElementById("profile-logout");
  const debugToggle = document.getElementById("debug-toggle");
  const debugDrawer = document.getElementById("debug-drawer");
  const debugBody = document.getElementById("debug-body");
  const debugClose = document.getElementById("debug-close");
  const appEl = document.querySelector(".app");

  /** Conversation state: [{role, content}]. Sent in full each request (API is stateless). */
  let messages = [];
  let streaming = false;
  // Developer debug: a dev tool, so it always starts hidden on load — click the
  // header toggle to open the right-side trace drawer for this session only.
  let debugMode = false;

  // Groups all turns of the current chat under one history entry. A fresh id is
  // minted per "new chat" and set when reopening a past conversation.
  const newConversationId = () =>
    (crypto.randomUUID && crypto.randomUUID()) ||
    "c-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  let conversationId = newConversationId();
  // The user's mobile number is the identity key (matches the SQL users.phone).
  // Persisted locally so returning visitors skip onboarding.
  let userId = localStorage.getItem("tara_phone") || null;
  // Display name captured at login/register — used to greet the user by name.
  let userName = localStorage.getItem("tara_name") || null;
  // Full profile (mobile, birth details) cached at login — for the profile card.
  let profile = null;
  try {
    profile = JSON.parse(localStorage.getItem("tara_profile") || "null");
  } catch (_) {
    profile = null;
  }

  const escapeHtml = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  // "നമസ്കാരം, <name> 🙏" when we know the name, else the plain greeting.
  const greetingText = () =>
    userName ? `നമസ്കാരം, ${escapeHtml(userName)} 🙏` : "നമസ്കാരം 🙏";

  // Client-side normalization mirrors identity.service.normalize_phone so the
  // same number is one key across SQL charts + Mongo history/memory.
  const normalizePhone = (raw) => {
    const s = raw.trim();
    const digits = s.replace(/\D/g, "");
    return s.startsWith("+") ? "+" + digits : digits;
  };

  // --- textarea auto-grow ---
  const autoGrow = () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  };
  input.addEventListener("input", autoGrow);

  // Enter to send, Shift+Enter for newline
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // Suggestion chips
  messagesEl.addEventListener("click", (e) => {
    if (e.target.classList.contains("chip")) {
      input.value = e.target.textContent;
      autoGrow();
      form.requestSubmit();
    }
  });

  newChatBtn.addEventListener("click", () => {
    if (streaming) return;
    // Start a brand-new conversation; the previous one is already persisted and
    // shows in the sidebar via loadHistory().
    conversationId = newConversationId();
    messages = [];
    document.querySelectorAll(".history-item.active").forEach((el) =>
      el.classList.remove("active")
    );
    renderWelcome();
    input.focus();
  });

  function renderWelcome() {
    messagesEl.innerHTML = `
      <div class="welcome">
        <div class="welcome-star">✦</div>
        <h1>${greetingText()}</h1>
        <p>ഞാൻ <strong>താര</strong> — നിങ്ങളുടെ Malayalam AI ജ്യോതിഷ കൂട്ടുകാരി.<br/>
           ഇന്ന് നിങ്ങളുടെ മനസ്സിൽ എന്താണ്?</p>
        <div class="suggestions">
          <button class="chip">എന്റെ ഇന്നത്തെ നക്ഷത്രഫലം</button>
          <button class="chip">ജോലിയെക്കുറിച്ച് ഉത്കണ്ഠയുണ്ട്</button>
          <button class="chip">പൊരുത്തം നോക്കാമോ?</button>
        </div>
      </div>`;
  }

  function clearWelcome() {
    const w = messagesEl.querySelector(".welcome");
    if (w) messagesEl.innerHTML = "";
  }

  function addRow(role, text) {
    clearWelcome();
    const row = document.createElement("div");
    row.className = "row";
    const isUser = role === "user";
    row.innerHTML = `
      <div class="avatar ${role}">${isUser ? "നി" : "✦"}</div>
      <div class="content">
        <div class="role-name">${isUser ? "നിങ്ങൾ" : "താര"}</div>
        <div class="bubble"></div>
      </div>`;
    row.querySelector(".bubble").textContent = text;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row.querySelector(".bubble");
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // --- Persisted history (MongoDB, via GET /chat/history/{user_id}) ---
  // Turns are stored newest-first; we group them into conversations so the
  // sidebar shows ONE entry per chat, not one per message.
  let conversations = []; // [{ id, turns:[oldest→newest], title, at }]

  function firstUserText(msgs) {
    for (const m of msgs || []) if (m.role === "user") return m.content;
    return "";
  }

  function groupIntoConversations(entries) {
    const byId = new Map();
    entries.forEach((entry, i) => {
      // Legacy turns saved before conversation_id existed each stand alone.
      const cid = entry.conversation_id || `legacy-${i}`;
      if (!byId.has(cid)) byId.set(cid, { id: cid, turns: [], at: entry.created_at });
      byId.get(cid).turns.push(entry);
    });
    // entries are newest-first; make each conversation's turns oldest-first and
    // title it by the opening question.
    return [...byId.values()].map((c) => {
      c.turns.reverse();
      c.title = firstUserText(c.turns[0] && c.turns[0].messages) || "സംഭാഷണം";
      c.at = c.turns[c.turns.length - 1].created_at;
      return c;
    });
  }

  async function loadHistory() {
    if (!userId) return;
    try {
      const res = await fetch(`/chat/history/${encodeURIComponent(userId)}?limit=100`);
      if (!res.ok) return;
      const entries = await res.json();
      if (!Array.isArray(entries)) return;
      conversations = groupIntoConversations(entries); // already newest-first
      historyEl.innerHTML = "";
      historyEmpty.hidden = conversations.length > 0;
      conversations.forEach((c) => {
        const item = document.createElement("div");
        item.className = "history-item";
        if (c.id === conversationId) item.classList.add("active");
        const title = document.createElement("div");
        title.textContent = c.title;
        title.style.overflow = "hidden";
        title.style.textOverflow = "ellipsis";
        const time = document.createElement("span");
        time.className = "hist-time";
        time.textContent = new Date(c.at).toLocaleString();
        item.appendChild(title);
        item.appendChild(time);
        item.addEventListener("click", () => openConversation(c.id));
        historyEl.appendChild(item);
      });
    } catch (_) {
      /* offline / Mongo disabled — leave the sidebar as-is */
    }
  }

  function openConversation(cid) {
    if (streaming) return;
    const conv = conversations.find((c) => c.id === cid);
    if (!conv) return;
    // Rebuild the full transcript from every turn, in order.
    messages = [];
    conv.turns.forEach((t) => {
      (t.messages || []).forEach((m) => messages.push({ role: m.role, content: m.content }));
      messages.push({ role: "assistant", content: t.reply });
    });
    conversationId = cid; // keep chatting appends to this same conversation
    messagesEl.innerHTML = "";
    messages.forEach((m) => addRow(m.role, m.content));
    document.querySelectorAll(".history-item.active").forEach((el) =>
      el.classList.remove("active")
    );
    scrollToBottom();
    input.focus();
    loadHistory(); // re-mark the active item
  }

  // --- "What Tara remembers": durable memory profile (GET /chat/memory) ---
  async function loadMemory() {
    if (!userId) return;
    try {
      const res = await fetch(`/chat/memory/${encodeURIComponent(userId)}`);
      if (!res.ok) {
        memoryPanel.hidden = true; // 404 = no profile yet / Mongo off
        return;
      }
      const profile = await res.json();
      const facts = profile.facts || [];
      if (!profile.summary && facts.length === 0) {
        memoryPanel.hidden = true;
        return;
      }
      memoryFacts.innerHTML = "";
      if (profile.summary) {
        const li = document.createElement("li");
        li.className = "memory-summary";
        li.textContent = profile.summary;
        memoryFacts.appendChild(li);
      }
      facts.slice(-8).forEach((f) => {
        const li = document.createElement("li");
        li.textContent = f.text;
        memoryFacts.appendChild(li);
      });
      memoryPanel.hidden = false;
    } catch (_) {
      memoryPanel.hidden = true;
    }
  }

  // Reveal text with a lightweight typewriter effect. The API returns the full
  // reply at once (JSON), so we animate it here to keep the live-typing feel.
  function typeOut(bubble, cursor, text) {
    return new Promise((resolve) => {
      let i = 0;
      const step = () => {
        i = Math.min(text.length, i + 2); // ~2 chars per tick
        bubble.textContent = text.slice(0, i);
        bubble.appendChild(cursor);
        scrollToBottom();
        if (i < text.length) setTimeout(step, 12);
        else resolve();
      };
      step();
    });
  }

  async function send(text) {
    messages.push({ role: "user", content: text });
    addRow("user", text);

    const bubble = addRow("assistant", "");
    const cursor = document.createElement("span");
    cursor.className = "cursor";
    bubble.appendChild(cursor);

    streaming = true;
    sendBtn.disabled = true;
    let reply = "";

    try {
      const res = await fetch("/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          conversation_id: conversationId,
          messages,
          debug: debugMode,
        }),
      });
      if (!res.ok) throw new Error("network");

      // /chat/message returns JSON (ChatResponse), not a token stream. Parse the
      // full reply, then type it out for the same live-typing feel.
      const data = await res.json();
      reply = data.reply || "…";
      await typeOut(bubble, cursor, reply);
      // Developer trace: show the orchestration details in the right-side drawer.
      if (debugMode && data.debug) {
        showDebug(data.debug, data.grounded_in || []);
      }
    } catch (err) {
      reply = "ക്ഷമിക്കണം, ഒരു പിശക് സംഭവിച്ചു. വീണ്ടും ശ്രമിക്കൂ.";
      bubble.textContent = reply;
    } finally {
      cursor.remove();
      streaming = false;
      sendBtn.disabled = false;
      messages.push({ role: "assistant", content: reply });
      input.focus();
      loadHistory(); // refresh sidebar with the just-persisted turn
      loadMemory(); // reflect any newly-distilled facts
    }
  }

  // --- Developer debug panel: renders the per-turn orchestration trace ---
  function renderDebugPanel(trace, groundedIn) {
    const j = (v) => escapeHtml(JSON.stringify(v ?? null, null, 2));
    const llm = trace.llm || {};
    const rag = trace.rag || {};

    const stepRows = (trace.pipeline || [])
      .map((s) => {
        const extra = Object.entries(s)
          .filter(([k]) => !["step", "ms", "tool"].includes(k))
          .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`)
          .join(", ");
        return `<tr><td>${escapeHtml(s.step)}</td><td class="dbg-ms">${s.ms}ms</td>
          <td class="dbg-tool">${escapeHtml(s.tool || "")}</td><td>${escapeHtml(extra)}</td></tr>`;
      })
      .join("");

    const hits = (rag.hits || [])
      .map(
        (h) =>
          `<li><code>${escapeHtml(h.id)}</code> <span class="dbg-dim">${escapeHtml(
            h.topic || ""
          )}</span><br>${escapeHtml(h.text)}${h.chars > (h.text || "").length ? "…" : ""}</li>`
      )
      .join("");

    const chips = (groundedIn || [])
      .map((g) => `<span class="dbg-chip">${escapeHtml(g)}</span>`)
      .join("");

    const wrap = document.createElement("div");
    wrap.className = "debug-panel";
    wrap.innerHTML = `
      <div class="debug-head">🐞 Developer trace <span class="dbg-dim">· ${
        trace.total_ms
      }ms · ${trace.crisis ? "⚠ CRISIS PATH (no astrology/LLM)" : "normal pipeline"}</span></div>

      <div class="debug-sec"><h4>Pipeline · steps &amp; tools</h4>
        <table class="dbg-table"><thead><tr><th>step</th><th>time</th><th>tool</th><th>detail</th></tr></thead>
        <tbody>${stepRows}</tbody></table>
      </div>

      <div class="debug-sec"><h4>LLM call · llm_client.complete</h4>
        <div class="dbg-kv">
          <span>provider</span><b class="${llm.mocked ? "dbg-warn" : "dbg-ok"}">${escapeHtml(
            llm.provider || "—"
          )}${llm.mocked ? " (mock — canned reply)" : " (live)"}</b>
          <span>model</span><b>${escapeHtml(llm.model || "—")}</b>
          <span>api_key_set</span><b class="${llm.api_key_set ? "dbg-ok" : "dbg-warn"}">${
            llm.api_key_set
          }</b>
          <span>max_tokens</span><b>${llm.max_tokens ?? "—"}</b>
          <span>usage</span><b>${llm.usage ? escapeHtml(JSON.stringify(llm.usage)) : "—"}</b>
          <span>messages_sent</span><b>${escapeHtml(JSON.stringify(llm.messages_sent || []))}</b>
        </div>
      </div>

      <div class="debug-sec"><h4>RAG · knowledge.retrieve</h4>
        <div class="dbg-kv"><span>query</span><b>${escapeHtml(rag.query || "—")}</b></div>
        <ul class="dbg-hits">${hits || "<li class='dbg-dim'>no hits</li>"}</ul>
      </div>

      <div class="debug-sec"><h4>Grounded in</h4>
        <div class="dbg-chips">${chips || "<span class='dbg-dim'>nothing</span>"}</div>
      </div>

      <details class="debug-sec"><summary>System prompt · ${
        (trace.system_prompt || "").length
      } chars</summary><pre>${escapeHtml(trace.system_prompt || "—")}</pre></details>

      <details class="debug-sec"><summary>Chart · ${
        trace.chart && trace.chart.loaded ? "loaded" : "none"
      }</summary><pre>${j(trace.chart && trace.chart.data)}</pre></details>

      <details class="debug-sec"><summary>Transits · astrology_engine.get_transits</summary><pre>${j(
        trace.transits
      )}</pre></details>

      <details class="debug-sec"><summary>Memory · ${
        trace.memory && trace.memory.used ? "used" : "none"
      }</summary><pre>${escapeHtml((trace.memory && trace.memory.text) || "—")}</pre></details>
    `;
    return wrap;
  }

  // --- Debug: right-side drawer, shown only while Debug is on ---
  let lastTrace = null;
  let lastGrounded = [];

  function debugPlaceholder() {
    debugBody.innerHTML =
      '<div class="debug-empty">Send a message to see how Tara builds the reply — ' +
      "pipeline steps, LLM params, RAG hits, grounding, and the full system prompt.</div>";
  }

  function showDebug(trace, groundedIn) {
    lastTrace = trace;
    lastGrounded = groundedIn || [];
    debugBody.innerHTML = "";
    debugBody.appendChild(renderDebugPanel(trace, lastGrounded));
    debugBody.scrollTop = 0;
  }

  function updateDebugToggle() {
    debugToggle.classList.toggle("on", debugMode);
    debugToggle.textContent = debugMode ? "🐞 Debug: on" : "🐞 Debug";
    // Open/close the drawer and make room for it in the layout.
    debugDrawer.hidden = !debugMode;
    appEl.classList.toggle("debug-open", debugMode);
    if (debugMode) {
      if (lastTrace) showDebug(lastTrace, lastGrounded);
      else debugPlaceholder();
    }
  }

  debugToggle.addEventListener("click", () => {
    debugMode = !debugMode;
    updateDebugToggle();
  });
  debugClose.addEventListener("click", () => {
    debugMode = false;
    updateDebugToggle();
  });
  updateDebugToggle();

  // --- Memory: click the header to expand/collapse the facts (collapsed default) ---
  memoryToggle.addEventListener("click", () => {
    const willShow = memoryFacts.hidden;
    memoryFacts.hidden = !willShow;
    memoryToggle.setAttribute("aria-expanded", String(willShow));
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!userId) {
      window.location.href = "/auth";
      return;
    }
    const text = input.value.trim();
    if (!text || streaming) return;
    input.value = "";
    autoGrow();
    send(text);
  });

  // --- Account control: greet the user in the header, allow logout ---
  function updateAccountControl() {
    // Header badge: name if known, else the mobile number.
    if (userName) {
      userBadge.textContent = `👤 ${userName}`;
      userBadge.hidden = false;
    } else if (userId) {
      userBadge.textContent = `📱 ${userId}`;
      userBadge.hidden = false;
    } else {
      userBadge.hidden = true;
    }
    // Sidebar footer chip doubles as a logout control.
    if (userId) {
      changeNumberBtn.hidden = false;
      changeNumberBtn.textContent = `📱 ${userId} · ലോഗ്ഔട്ട്`;
    } else {
      changeNumberBtn.hidden = true;
    }
  }

  function logout() {
    if (streaming) return;
    // Forget the current user and return to the login / register page.
    localStorage.removeItem("tara_phone");
    localStorage.removeItem("tara_name");
    localStorage.removeItem("tara_profile");
    window.location.href = "/auth";
  }

  // --- Profile card: the logged-in user's details ---
  function openProfile() {
    const p = profile || {};
    const name = userName || p.name || "";
    document.getElementById("pf-name").textContent = name || "—";
    document.getElementById("pf-avatar").textContent = name ? name.trim()[0] : "👤";
    document.getElementById("pf-phone").textContent = p.phone || userId || "—";
    document.getElementById("pf-dob").textContent = p.dob || "—";
    document.getElementById("pf-time").textContent = p.birth_time || "അറിയില്ല";
    document.getElementById("pf-place").textContent = p.birth_place || "—";
    profileModal.hidden = false;
  }
  function closeProfile() {
    profileModal.hidden = true;
  }

  userBadge.addEventListener("click", openProfile);
  profileClose.addEventListener("click", closeProfile);
  profileLogout.addEventListener("click", logout);
  profileModal.addEventListener("click", (e) => {
    if (e.target === profileModal) closeProfile(); // click backdrop to dismiss
  });

  logoutBtn.addEventListener("click", logout);
  changeNumberBtn.addEventListener("click", logout);

  // Fill in the display name for sessions that logged in before the name was
  // cached locally, so the greeting/header still show it (no re-login needed).
  async function ensureUserName() {
    if (userName || !userId) return;
    try {
      const res = await fetch("/identity/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: userId }),
      });
      if (!res.ok) return;
      const profile = await res.json();
      if (profile.name) {
        userName = profile.name;
        localStorage.setItem("tara_name", userName);
        updateAccountControl();
        // Refresh the greeting only if the welcome splash is still on screen.
        if (messagesEl.querySelector(".welcome")) renderWelcome();
      }
    } catch (_) {
      /* offline — keep the plain greeting */
    }
  }

  // Gate the chat behind the auth page: no account → redirect to login/register.
  // Otherwise greet the returning user by name and load history + durable memory.
  if (userId) {
    updateAccountControl();
    renderWelcome(); // show the personalized greeting first
    ensureUserName();
    loadHistory();
    loadMemory();
  } else {
    window.location.replace("/auth");
  }
})();
