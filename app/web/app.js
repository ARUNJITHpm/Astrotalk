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
  // LLM provider pick (header selector). Sarvam (Malayalam-first) is the
  // default; the server falls back automatically if a provider has no key.
  const modelSelect = document.getElementById("model-select");
  let modelProvider = localStorage.getItem("tara_model") || "sarvam";
  modelSelect.value = modelProvider;
  modelSelect.addEventListener("change", () => {
    modelProvider = modelSelect.value;
    localStorage.setItem("tara_model", modelProvider);
  });

  // Groups all turns of the current chat under one history entry. A fresh id is
  // minted per "new chat" and set when reopening a past conversation.
  const newConversationId = () =>
    (crypto.randomUUID && crypto.randomUUID()) ||
    "c-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  let conversationId = newConversationId();
  // The user's mobile number is the identity key (matches the SQL users.phone).
  // Persisted locally so returning visitors skip onboarding.
  let userId = localStorage.getItem("tara_phone") || null;
  // Bearer session token (47h TTL). Every user-scoped call carries it; a 401
  // means it expired or was revoked → back to the login page.
  let authToken = localStorage.getItem("tara_token") || null;
  // Display name captured at login/register — used to greet the user by name.
  let userName = localStorage.getItem("tara_name") || null;

  const authHeaders = (extra = {}) =>
    authToken ? { ...extra, Authorization: `Bearer ${authToken}` } : extra;

  function sessionExpired() {
    // Keep the profile cache; drop only the credentials and re-login.
    localStorage.removeItem("tara_token");
    window.location.href = "/auth";
  }
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

  // Suggestion chips (welcome + per-reply follow-ups). A chip either types its
  // text into the composer, or opens the prashnam modal (data-action).
  messagesEl.addEventListener("click", (e) => {
    if (e.target.classList.contains("chip")) {
      if (e.target.dataset.action === "prashnam") {
        openPrashnam();
        return;
      }
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
    activePorutham = null; // partner context belongs to the old conversation
    document.querySelectorAll(".history-item.active").forEach((el) =>
      el.classList.remove("active")
    );
    renderWelcome();
    input.focus();
  });

  // Welcome chip pool — a random 4 show per load (plus the prashnam chip), so
  // returning users keep discovering what they can ask.
  const WELCOME_CHIPS = [
    "എന്റെ ഇന്നത്തെ നക്ഷത്രഫലം",
    "ജോലിയെക്കുറിച്ച് ഉത്കണ്ഠയുണ്ട്",
    "പൊരുത്തം നോക്കാമോ?",
    "എന്റെ ദശാകാലം എങ്ങനെ പോകുന്നു?",
    "വിവാഹം എപ്പോൾ നടക്കും?",
    "ഏഴര ശനി എന്നെ ബാധിക്കുമോ?",
    "നല്ലൊരു മുഹൂർത്തം നോക്കാമോ?",
    "ഏത് ക്ഷേത്രത്തിൽ വഴിപാട് ചെയ്യണം?",
  ];

  function renderWelcome() {
    const picks = [...WELCOME_CHIPS].sort(() => Math.random() - 0.5).slice(0, 4);
    const chips = picks
      .map((t) => `<button class="chip">${escapeHtml(t)}</button>`)
      .join("");
    messagesEl.innerHTML = `
      <div class="welcome">
        <div class="welcome-star">✦</div>
        <h1>${greetingText()}</h1>
        <p>ഞാൻ <strong>താര</strong> — നിങ്ങളുടെ Malayalam AI ജ്യോതിഷ കൂട്ടുകാരി.<br/>
           ഇന്ന് നിങ്ങളുടെ മനസ്സിൽ എന്താണ്?</p>
        <div class="suggestions">
          ${chips}
          <button class="chip chip-prashnam" data-action="prashnam">🪷 പ്രശ്നം ചോദിക്കൂ</button>
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

  // Stick-to-bottom: while the reply types out, follow it only if the user is
  // already at the bottom — scrolling up to read must not be fought.
  let stickToBottom = true;
  messagesEl.addEventListener("scroll", () => {
    stickToBottom =
      messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 80;
  });

  function scrollToBottom(force = false) {
    if (!force && !stickToBottom) return;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ChatGPT-style reading position: pin the QUESTION to the top of the view
  // when the reply starts; the answer grows downward without moving the view.
  function anchorToLatestUser() {
    const rows = messagesEl.querySelectorAll(".row");
    let row = null;
    for (const r of rows) if (r.querySelector(".avatar.user")) row = r;
    if (!row) return;
    const top =
      row.getBoundingClientRect().top -
      messagesEl.getBoundingClientRect().top +
      messagesEl.scrollTop;
    messagesEl.scrollTop = Math.max(0, top - 12);
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
    entries.forEach((entry) => {
      // Turns saved before conversation_id existed (or by old clients) all fold
      // into ONE bucket — one turn per sidebar row flooded it with duplicates.
      const cid = entry.conversation_id || "legacy";
      if (!byId.has(cid)) byId.set(cid, { id: cid, turns: [], at: entry.created_at });
      byId.get(cid).turns.push(entry);
    });
    // entries are newest-first; make each conversation's turns oldest-first and
    // title it by the opening question.
    return [...byId.values()].map((c) => {
      c.turns.reverse();
      c.title =
        c.id === "legacy"
          ? "മുൻ സംഭാഷണങ്ങൾ"
          : firstUserText(c.turns[0] && c.turns[0].messages) || "സംഭാഷണം";
      c.at = c.turns[c.turns.length - 1].created_at;
      return c;
    });
  }

  // "ഇന്ന് · 6:01 PM", "ഇന്നലെ · 11:58 AM", else "4 Jul · 10:48 AM".
  function formatWhen(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const now = new Date();
    const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const startOfDay = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const days = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
    if (days === 0) return `ഇന്ന് · ${time}`;
    if (days === 1) return `ഇന്നലെ · ${time}`;
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) + ` · ${time}`;
  }

  // Rebuilding the sidebar every turn made items flicker/re-animate; skip the
  // DOM work when nothing actually changed.
  let historySig = null;

  async function loadHistory() {
    if (!userId) return;
    try {
      const res = await fetch(`/chat/history/${encodeURIComponent(userId)}?limit=100`, {
        headers: authHeaders(),
      });
      if (res.status === 401) return sessionExpired();
      if (!res.ok) return;
      const entries = await res.json();
      if (!Array.isArray(entries)) return;
      conversations = groupIntoConversations(entries); // already newest-first
      const sig =
        conversations.map((c) => `${c.id}|${c.at}|${c.turns.length}`).join(";") +
        "@" +
        conversationId;
      if (sig === historySig) return;
      historySig = sig;
      historyEl.innerHTML = "";
      historyEmpty.hidden = conversations.length > 0;
      conversations.forEach((c) => {
        const item = document.createElement("div");
        item.className = "history-item";
        if (c.id === conversationId) item.classList.add("active");
        const title = document.createElement("div");
        title.className = "hist-title";
        title.textContent = c.title;
        const time = document.createElement("span");
        time.className = "hist-time";
        time.textContent = formatWhen(c.at);
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
    activePorutham = null; // partner context is not persisted across reloads
    conv.turns.forEach((t) => {
      (t.messages || []).forEach((m) => messages.push({ role: m.role, content: m.content }));
      messages.push({ role: "assistant", content: t.reply });
    });
    conversationId = cid; // keep chatting appends to this same conversation
    messagesEl.innerHTML = "";
    messages.forEach((m, i) => {
      const bubble = addRow(m.role, m.content);
      if (m.role === "assistant")
        addActions(bubble.closest(".row"), m.content, i, i === messages.length - 1);
    });
    document.querySelectorAll(".history-item.active").forEach((el) =>
      el.classList.remove("active")
    );
    stickToBottom = true;
    scrollToBottom(true);
    input.focus();
    loadHistory(); // re-mark the active item
  }

  // --- "What Tara remembers": durable memory profile (GET /chat/memory) ---
  async function loadMemory() {
    if (!userId) return;
    try {
      const res = await fetch(`/chat/memory/${encodeURIComponent(userId)}`, {
        headers: authHeaders(),
      });
      if (res.status === 401) return sessionExpired();
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
  // No scrolling in here — the view is anchored at the question when the
  // reply starts and must not chase the growing text.
  function typeOut(bubble, cursor, text) {
    return new Promise((resolve) => {
      let i = 0;
      const step = () => {
        i = Math.min(text.length, i + 2); // ~2 chars per tick
        bubble.textContent = text.slice(0, i);
        bubble.appendChild(cursor);
        if (i < text.length) setTimeout(step, 12);
        else resolve();
      };
      step();
    });
  }

  // --- Follow-up chips: deterministic next steps from what grounded the reply.
  // No extra LLM cost — grounded_in already says which knowledge was used.
  function followUpsFor(groundedIn) {
    const g = groundedIn || [];
    const has = (p) => g.some((x) => x.startsWith(p));
    const out = [];
    if (has("temple:")) out.push({ text: "ഈ ക്ഷേത്രത്തിലെ വഴിപാടുകൾ വിശദമാക്കാമോ?" });
    if (has("knowledge:dosha-sade-sati"))
      out.push({ text: "ഏഴര ശനിയിൽ ഞാൻ എന്ത് ശ്രദ്ധിക്കണം?" });
    if (has("knowledge:dosha-chovva"))
      out.push({ text: "ചൊവ്വാ ദോഷത്തിന് എന്ത് ചെയ്യാം?" });
    if (has("knowledge:mahadasha") || has("varga:"))
      out.push({ text: "എന്റെ ദശാകാലം കൂടുതൽ വിശദമാക്കൂ" });
    if (has("prashnam:"))
      out.push({ text: "🪷 മറ്റൊരു പ്രശ്നം ചോദിക്കൂ", action: "prashnam" });
    // Gentle defaults so there is always a next step on screen.
    out.push({ text: "എന്റെ ഇന്നത്തെ നക്ഷത്രഫലം പറയൂ" });
    if (!out.some((c) => c.action))
      out.push({ text: "🪷 പ്രശ്നം ചോദിക്കൂ", action: "prashnam" });
    return out.slice(0, 3);
  }

  function renderFollowUps(bubble, groundedIn) {
    const row = bubble.closest(".row");
    if (!row) return;
    const wrap = document.createElement("div");
    wrap.className = "followups";
    followUpsFor(groundedIn).forEach((c) => {
      const btn = document.createElement("button");
      btn.className = "chip chip-followup";
      btn.textContent = c.text;
      if (c.action) btn.dataset.action = c.action;
      wrap.appendChild(btn);
    });
    row.querySelector(".content").appendChild(wrap);
    scrollToBottom();
  }

  // --- message actions: copy / retry / feedback (Claude-desktop style) ---
  // Feedback lives client-side (localStorage), keyed by conversation + message
  // index, so thumbs survive reloads of the same conversation.
  const FB_KEY = "tara_feedback";
  const fbLoad = () => {
    try { return JSON.parse(localStorage.getItem(FB_KEY)) || {}; } catch (_) { return {}; }
  };
  const fbGet = (cid, idx) => fbLoad()[`${cid}|${idx}`] || null;
  const fbSet = (cid, idx, val) => {
    const m = fbLoad();
    if (val) m[`${cid}|${idx}`] = val;
    else delete m[`${cid}|${idx}`];
    localStorage.setItem(FB_KEY, JSON.stringify(m));
  };

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (_) {}
      ta.remove();
      return ok;
    }
  }

  function mkAct(cls, icon, title, onClick) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `msg-act ${cls}`;
    b.textContent = icon;
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", onClick);
    return b;
  }

  // Attach copy/retry/feedback under an assistant row. Retry only makes sense
  // on the newest reply, so a canRetry bar strips retry from older bars first.
  function addActions(row, text, idx, canRetry) {
    if (!row) return;
    const old = row.querySelector(".msg-actions");
    if (old) old.remove();
    if (canRetry)
      document.querySelectorAll(".msg-act.retry").forEach((b) => b.remove());

    const bar = document.createElement("div");
    bar.className = "msg-actions";

    const copyBtn = mkAct("copy", "📋", "പകർത്തൂ", async () => {
      const ok = await copyText(text);
      copyBtn.textContent = ok ? "✓" : "📋";
      copyBtn.classList.toggle("done", ok);
      setTimeout(() => {
        copyBtn.textContent = "📋";
        copyBtn.classList.remove("done");
      }, 1400);
    });
    bar.appendChild(copyBtn);

    if (canRetry) bar.appendChild(mkAct("retry", "🔄", "വീണ്ടും ശ്രമിക്കൂ", retryLast));

    const up = mkAct("fb-up", "👍", "നല്ല മറുപടി", () => setFb("up"));
    const down = mkAct("fb-down", "👎", "മെച്ചപ്പെടുത്തണം", () => setFb("down"));
    const saved = fbGet(conversationId, idx);
    if (saved === "up") up.classList.add("active");
    if (saved === "down") down.classList.add("active");
    function setFb(val) {
      const already = (val === "up" ? up : down).classList.contains("active");
      up.classList.toggle("active", !already && val === "up");
      down.classList.toggle("active", !already && val === "down");
      fbSet(conversationId, idx, already ? null : val);
      const prev = bar.querySelector(".msg-act-note");
      if (prev) prev.remove();
      if (!already) {
        const note = document.createElement("span");
        note.className = "msg-act-note";
        note.textContent = "നന്ദി 🙏";
        bar.appendChild(note);
        setTimeout(() => note.remove(), 1600);
      }
    }
    bar.appendChild(up);
    bar.appendChild(down);

    row.querySelector(".content").appendChild(bar);
  }

  // Re-ask the last question: drop the newest reply, resend the same turn.
  function retryLast() {
    if (streaming) return;
    if (messages.length && messages[messages.length - 1].role === "assistant") {
      messages.pop();
      const rows = messagesEl.querySelectorAll(".row");
      for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].querySelector(".avatar.assistant")) { rows[i].remove(); break; }
      }
    }
    if (!messages.length || messages[messages.length - 1].role !== "user") return;
    send(null, null, null, true);
  }

  // The partner from the last 💑 form stays attached for the REST of the
  // conversation, so follow-up questions ("what are our stars?") keep the
  // engine's computed porutham facts in the prompt — the LLM can't reliably
  // dig them out of chat history on its own. Cleared on new chat / switch.
  let activePorutham = null;

  async function send(text, prashnam = null, porutham = null, resend = false) {
    if (porutham) activePorutham = porutham;
    else porutham = activePorutham;
    // Retire the previous turn's follow-up chips — stale ones pile up fast.
    document.querySelectorAll(".followups").forEach((el) => el.remove());
    if (!resend) {
      messages.push({ role: "user", content: text });
      addRow("user", text);
    }

    const bubble = addRow("assistant", "");
    const cursor = document.createElement("span");
    cursor.className = "cursor";
    bubble.appendChild(cursor);
    // Pin the question to the top — the reply streams downward from here.
    anchorToLatestUser();

    streaming = true;
    sendBtn.disabled = true;
    let reply = "";

    try {
      const res = await fetch("/chat/message", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          user_id: userId,
          conversation_id: conversationId,
          messages,
          prashnam,
          porutham,
          provider: modelProvider,
          debug: debugMode,
        }),
      });
      if (res.status === 401) return sessionExpired();
      if (res.status === 429) {
        reply = "അല്പനേരം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കൂ — ഈ മണിക്കൂറിലെ സന്ദേശപരിധി കഴിഞ്ഞു. 🙏";
        bubble.textContent = reply;
        return;
      }
      if (!res.ok) throw new Error("network");

      // /chat/message returns JSON (ChatResponse), not a token stream. Parse the
      // full reply, then type it out for the same live-typing feel.
      const data = await res.json();
      reply = data.reply || "…";
      await typeOut(bubble, cursor, reply);
      // Engagement: offer tappable next steps tied to what grounded this reply
      // (skipped on the crisis path — no astrology prompts there).
      if (!data.is_safety_response) renderFollowUps(bubble, data.grounded_in);
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
      // copy / retry / feedback bar — retry lives only on this newest reply
      addActions(bubble.closest(".row"), reply, messages.length - 1, true);
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
    // Revoke the session server-side (fire-and-forget), then forget the user
    // locally and return to the login / register page.
    if (authToken) {
      fetch("/identity/logout", { method: "POST", headers: authHeaders() }).catch(
        () => {}
      );
    }
    localStorage.removeItem("tara_token");
    localStorage.removeItem("tara_phone");
    localStorage.removeItem("tara_name");
    localStorage.removeItem("tara_profile");
    window.location.href = "/auth";
  }

  // --- Profile card: the logged-in user's details ---
  // Fixed astro identity on the profile card (nakshatram / rasi / lagnam /
  // running dasha) — fetched once from the user's stored chart and cached.
  let natalCache = null;
  const LORD_ML = {
    surya: "സൂര്യൻ", chandra: "ചന്ദ്രൻ", chevvai: "ചൊവ്വ", budhan: "ബുധൻ",
    guru: "വ്യാഴം", shukran: "ശുക്രൻ", shani: "ശനി", rahu: "രാഹു", ketu: "കേതു",
  };
  // One fetch of the stored natal chart serves both the profile card's astro
  // rows and the എന്റെ ജാതകം drawer. Throws so callers can show a fallback.
  async function fetchNatal() {
    if (natalCache) return natalCache;
    const uid = profile && profile.id;
    if (!uid) throw new Error("no uid");
    const res = await fetch(`/identity/users/${uid}/chart`, { headers: authHeaders() });
    if (res.status === 401) { sessionExpired(); throw new Error("401"); }
    if (!res.ok) throw new Error("no chart");
    natalCache = (await res.json()).natal_json;
    return natalCache;
  }
  async function fillProfileAstro() {
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v || "—";
    };
    let n;
    try {
      n = (await fetchNatal()) || {};
    } catch (_) {
      return ["pf-star", "pf-rasi", "pf-lagnam", "pf-dasha"].forEach((i) => set(i));
    }
    set("pf-star", (n.nakshatram || "—") +
      (n.nakshatra_pada ? ` · പാദം ${n.nakshatra_pada}` : ""));
    set("pf-rasi", n.rasi);
    set("pf-lagnam", n.lagnam);
    const cur = n.dasha && n.dasha.current;
    const maha = cur && (cur.mahadasha || cur);
    const lord = maha && (maha.lord_ml || LORD_ML[maha.lord] || maha.lord);
    set("pf-dasha", lord ? lord + " ദശ" : "—");
  }

  function openProfile() {
    const p = profile || {};
    const name = userName || p.name || "";
    document.getElementById("pf-name").textContent = name || "—";
    document.getElementById("pf-avatar").textContent = name ? name.trim()[0] : "👤";
    document.getElementById("pf-phone").textContent = p.phone || userId || "—";
    document.getElementById("pf-dob").textContent = p.dob || "—";
    document.getElementById("pf-time").textContent = p.birth_time || "അറിയില്ല";
    document.getElementById("pf-place").textContent = p.birth_place || "—";
    fillProfileAstro(); // async — rows show "…" until the chart arrives
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

  // --- എന്റെ ജാതകം drawer: the user's natal chart, rendered by chart.js ---
  const chartDrawer = document.getElementById("chart-drawer");
  const chartBackdrop = document.getElementById("chart-backdrop");
  const chartBody = document.getElementById("chart-body");
  let chartRendered = false;
  async function openChart() {
    chartBackdrop.hidden = false;
    chartDrawer.classList.add("open");
    if (chartRendered) return;
    if (!(profile && profile.id)) {
      chartBody.innerHTML =
        '<div class="muted" style="text-align:center;padding:40px 12px">ജാതകം കാണാൻ ഒരിക്കൽ ലോഗ്ഔട്ട് ചെയ്ത് വീണ്ടും ലോഗിൻ ചെയ്യൂ 🙏</div>';
      return;
    }
    try {
      const natal = await fetchNatal();
      chartBody.innerHTML = TaraChart.render(natal, profile);
      TaraChart.bind(chartBody, natal, profile);
      chartRendered = true;
    } catch (_) {
      chartBody.innerHTML =
        '<div class="muted" style="text-align:center;padding:40px 12px">ജാതകം ലഭ്യമല്ല — അല്പസമയത്തിനു ശേഷം ശ്രമിക്കൂ 🙏</div>';
    }
  }
  function closeChart() {
    chartDrawer.classList.remove("open");
    chartBackdrop.hidden = true;
  }
  document.getElementById("chart-open").addEventListener("click", openChart);
  document.getElementById("chart-close").addEventListener("click", closeChart);
  chartBackdrop.addEventListener("click", closeChart);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeChart();
  });

  // --- Prashnam (Kerala horary): thamboola count / swarna arudha pick ---
  // The pick is sent as a structured `prashnam` field; the SERVER computes the
  // question-moment chart and the rules — the client only collects the ritual
  // interaction. The 12 squares are deliberately unlabeled (the querent should
  // not know which rasi they touch).
  const prashnamModal = document.getElementById("prashnam-modal");
  const prashnamOpen = document.getElementById("prashnam-open");
  const prashnamClose = document.getElementById("prashnam-close");
  const prashnamQuestion = document.getElementById("prashnam-question");
  const arudhaGrid = document.getElementById("arudha-grid");
  const leafCount = document.getElementById("leaf-count");
  const thamboolaSend = document.getElementById("thamboola-send");
  const sankhyaNumber = document.getElementById("sankhya-number");
  const sankhyaSend = document.getElementById("sankhya-send");
  const prashnamPanes = {
    swarna: document.getElementById("prashnam-swarna"),
    thamboola: document.getElementById("prashnam-thamboola"),
    sankhya: document.getElementById("prashnam-sankhya"),
  };

  for (let i = 0; i < 12; i++) {
    const sq = document.createElement("button");
    sq.type = "button";
    sq.className = "arudha-square";
    sq.dataset.index = String(i);
    sq.textContent = "✦";
    sq.setAttribute("aria-label", `കളം ${i + 1}`);
    arudhaGrid.appendChild(sq);
  }

  function openPrashnam() {
    if (streaming) return;
    // Seed the question from the composer, if the user already typed one.
    if (input.value.trim()) prashnamQuestion.value = input.value.trim();
    prashnamModal.hidden = false;
    prashnamQuestion.focus();
  }
  function closePrashnam() {
    prashnamModal.hidden = true;
  }

  function prashnamQuestionText() {
    const q = prashnamQuestion.value.trim();
    if (!q) {
      prashnamQuestion.focus();
      prashnamQuestion.classList.add("needs-question");
      setTimeout(() => prashnamQuestion.classList.remove("needs-question"), 900);
      return null;
    }
    return q;
  }

  function submitPrashnam(prashnam, label) {
    const q = prashnamQuestionText();
    if (!q || streaming) return;
    closePrashnam();
    prashnamQuestion.value = "";
    leafCount.value = "";
    sankhyaNumber.value = "";
    input.value = "";
    autoGrow();
    send(`🪷 [${label}] ${q}`, prashnam);
  }

  prashnamModal.querySelectorAll(".prashnam-mode").forEach((btn) => {
    btn.addEventListener("click", () => {
      prashnamModal
        .querySelectorAll(".prashnam-mode")
        .forEach((b) => b.classList.toggle("active", b === btn));
      const mode = btn.dataset.mode;
      Object.entries(prashnamPanes).forEach(([m, pane]) => {
        pane.hidden = m !== mode;
      });
      if (mode === "thamboola") leafCount.focus();
      if (mode === "sankhya") sankhyaNumber.focus();
    });
  });

  arudhaGrid.addEventListener("click", (e) => {
    const sq = e.target.closest(".arudha-square");
    if (!sq) return;
    submitPrashnam(
      { mode: "swarna", arudha_rasi_index: Number(sq.dataset.index) },
      "സ്വർണ പ്രശ്നം"
    );
  });

  thamboolaSend.addEventListener("click", () => {
    const n = Number(leafCount.value);
    if (!Number.isInteger(n) || n < 1 || n > 108) {
      leafCount.focus();
      return;
    }
    submitPrashnam({ mode: "thamboola", leaf_count: n }, "താംബൂല പ്രശ്നം");
  });
  leafCount.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      thamboolaSend.click();
    }
  });

  sankhyaSend.addEventListener("click", () => {
    const n = Number(sankhyaNumber.value);
    if (!Number.isInteger(n) || n < 1 || n > 108) {
      sankhyaNumber.focus();
      return;
    }
    submitPrashnam({ mode: "sankhya", number: n }, "സംഖ്യാ പ്രശ്നം");
  });
  sankhyaNumber.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sankhyaSend.click();
    }
  });

  prashnamOpen.addEventListener("click", openPrashnam);
  prashnamClose.addEventListener("click", closePrashnam);
  prashnamModal.addEventListener("click", (e) => {
    if (e.target === prashnamModal) closePrashnam();
  });

  // --- Porutham (ദശപൊരുത്തം): partner's birth details, matched server-side ---
  // The form collects only the partner's details; the SERVER computes the
  // partner's chart and grades the ten Kerala poruthams against the logged-in
  // user's own chart. `gender` is the PARTNER's — the user is the opposite side.
  const poruthamModal = document.getElementById("porutham-modal");
  const poruthamOpen = document.getElementById("porutham-open");
  const poruthamClose = document.getElementById("porutham-close");
  const poruthamName = document.getElementById("porutham-name");
  const poruthamDob = document.getElementById("porutham-dob");
  const poruthamTime = document.getElementById("porutham-time");
  const poruthamPlace = document.getElementById("porutham-place");
  const poruthamSend = document.getElementById("porutham-send");
  const poruthamError = document.getElementById("porutham-error");
  let partnerGender = "female";

  function openPorutham() {
    if (streaming) return;
    poruthamError.hidden = true;
    poruthamModal.hidden = false;
    poruthamName.focus();
  }
  function closePorutham() {
    poruthamModal.hidden = true;
  }
  function poruthamFail(msg) {
    poruthamError.textContent = msg;
    poruthamError.hidden = false;
  }

  poruthamModal.querySelectorAll(".porutham-sex").forEach((btn) => {
    btn.addEventListener("click", () => {
      partnerGender = btn.dataset.gender;
      poruthamModal
        .querySelectorAll(".porutham-sex")
        .forEach((b) => b.classList.toggle("active", b === btn));
    });
  });

  function submitPorutham() {
    if (streaming) return;
    const name = poruthamName.value.trim();
    const dob = poruthamDob.value; // YYYY-MM-DD from <input type=date>
    const time = poruthamTime.value; // HH:MM or ""
    const place = poruthamPlace.value.trim();
    if (!dob) return poruthamFail("പങ്കാളിയുടെ ജനന തീയതി നൽകൂ.");
    if (!place) return poruthamFail("പങ്കാളിയുടെ ജനന സ്ഥലം നൽകൂ.");
    const porutham = {
      name,
      gender: partnerGender,
      dob,
      birth_time: time || null,
      birth_place: place,
    };
    closePorutham();
    // Reset for next time.
    poruthamName.value = "";
    poruthamDob.value = "";
    poruthamTime.value = "";
    poruthamPlace.value = "";
    const who = name || "പങ്കാളി";
    send(`💑 ${who}യുമായുള്ള പൊരുത്തം നോക്കാമോ?`, null, porutham);
  }

  poruthamSend.addEventListener("click", submitPorutham);
  poruthamOpen.addEventListener("click", openPorutham);
  poruthamClose.addEventListener("click", closePorutham);
  poruthamModal.addEventListener("click", (e) => {
    if (e.target === poruthamModal) closePorutham();
  });

  // Fill in the display name for sessions that logged in before the name was
  // cached locally, so the greeting/header still show it (no re-login needed).
  async function ensureUserName() {
    if (userName || !userId) return;
    try {
      const res = await fetch("/identity/me", { headers: authHeaders() });
      if (res.status === 401) return sessionExpired();
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

  // Gate the chat behind the auth page: no account or no live session token →
  // redirect to login/register. Otherwise greet the returning user by name and
  // load history + durable memory.
  if (userId && authToken) {
    updateAccountControl();
    renderWelcome(); // show the personalized greeting first
    ensureUserName();
    loadHistory();
    loadMemory();
  } else {
    window.location.replace("/auth");
  }
})();
