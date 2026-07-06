// TARA UI chat — same /chat/message brain as the classic UI, new cinematic skin.
// Highlights: case-morphing top banner (default/prashnam/temple/dosha/dasha/
// panchangam/crisis), case-tinted reply cards, chart drawer, panchangam strip.
(() => {
  const $ = (id) => document.getElementById(id);
  const messagesEl = $("messages");
  const scrollEl = $("messages-scroll");
  const form = $("composer-form");
  const input = $("input");
  const sendBtn = $("send");

  // ---------- session (same localStorage keys as the classic UI) ----------
  let userId = localStorage.getItem("tara_phone") || null;
  let authToken = localStorage.getItem("tara_token") || null;
  let userName = localStorage.getItem("tara_name") || null;
  let profile = null;
  try { profile = JSON.parse(localStorage.getItem("tara_profile") || "null"); } catch (_) {}

  if (!userId || !authToken) {
    window.location.replace("/ui/login");
    return;
  }

  const authHeaders = (extra = {}) =>
    authToken ? { ...extra, Authorization: `Bearer ${authToken}` } : extra;

  function sessionExpired() {
    localStorage.removeItem("tara_token");
    window.location.href = "/ui/login";
  }

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  // Replies carry light markdown (Sarvam bolds chart facts like **പൂരം**);
  // render just **bold** — everything else stays escaped plain text.
  const rich = (s) => esc(s).replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");

  // ---------- conversation state ----------
  let messages = [];
  let streaming = false;
  const newConversationId = () =>
    (crypto.randomUUID && crypto.randomUUID()) ||
    "c-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  let conversationId = newConversationId();

  const modelSelect = $("model-select");
  let modelProvider = localStorage.getItem("tara_model") || "sarvam";
  modelSelect.value = modelProvider;
  modelSelect.addEventListener("change", () => {
    modelProvider = modelSelect.value;
    localStorage.setItem("tara_model", modelProvider);
  });

  // ---------- CASE ENGINE: the top banner + reply styling morph per context ----------
  const CASES = {
    default: { icon: "✦", title: "താര", sub: "നിങ്ങളുടെ ജ്യോതിഷ കൂട്ടുകാരി", tag: "" },
    prashnam: { icon: "🪷", title: "പ്രശ്നം", sub: "ചോദ്യമുഹൂർത്തത്തിന്റെ ചക്രം നോക്കുന്നു", tag: "പ്രശ്നഫലം" },
    porutham: { icon: "💑", title: "പൊരുത്തം", sub: "പത്ത് പൊരുത്തങ്ങൾ — രണ്ട് ജാതകങ്ങൾ ചേർത്ത്", tag: "പൊരുത്തഫലം" },
    temple: { icon: "🛕", title: "ക്ഷേത്രം & വഴിപാട്", sub: "അനുയോജ്യമായ ക്ഷേത്രവും വഴിപാടും", tag: "ക്ഷേത്ര നിർദ്ദേശം" },
    dosha: { icon: "🔱", title: "ദോഷ പരിശോധന", sub: "ദോഷവും പരിഹാരവും — ശാന്തമായി", tag: "ദോഷ വിശകലനം" },
    dasha: { icon: "⏳", title: "ദശാകാലം", sub: "വിംശോത്തരി ദശയും ഗോചരവും", tag: "ദശാഫലം" },
    panchangam: { icon: "🌅", title: "പഞ്ചാംഗം", sub: "ഇന്നത്തെ നക്ഷത്രം · തിഥി · നല്ല നേരം", tag: "ഇന്നത്തെ ഫലം" },
    crisis: { icon: "🤝", title: "ഒപ്പമുണ്ട്", sub: "നിങ്ങൾ ഒറ്റയ്ക്കല്ല — സഹായം അരികിലുണ്ട്", tag: "" },
  };

  function detectCase(groundedIn, isSafety, wasPrashnam) {
    if (isSafety) return "crisis";
    const g = groundedIn || [];
    const has = (p) => g.some((x) => String(x).startsWith(p));
    if (wasPrashnam || has("prashnam")) return "prashnam";
    if (has("porutham")) return "porutham";
    if (has("temple")) return "temple";
    if (has("knowledge:dosha") || has("dosha")) return "dosha";
    if (has("knowledge:mahadasha") || has("varga") || has("dasha")) return "dasha";
    if (has("panchangam") || has("knowledge:muhurtham")) return "panchangam";
    return "default";
  }

  let currentCase = "default";
  function setCase(name) {
    if (!CASES[name]) name = "default";
    if (name === currentCase) return;
    currentCase = name;
    const c = CASES[name];
    document.body.dataset.case = name;
    $("case-badge").textContent = c.icon;
    $("case-title").textContent = c.title;
    $("case-sub").textContent = c.sub;
    // retrigger the swap animation
    const meta = $("case-meta");
    meta.classList.remove("switching");
    void meta.offsetWidth;
    meta.classList.add("switching");
  }

  // ---------- rendering ----------
  const greetingText = () =>
    userName ? `നമസ്കാരം, ${esc(userName)} 🙏` : "നമസ്കാരം 🙏";

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
    const chips = picks.map((t) => `<button class="chip">${esc(t)}</button>`).join("");
    messagesEl.innerHTML = `
      <div class="welcome">
        <div class="welcome-star">✦</div>
        <h1 class="display text-grad">${greetingText()}</h1>
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

  function addRow(role, text, caseName) {
    clearWelcome();
    const row = document.createElement("div");
    row.className = `row ${role}`;
    const isUser = role === "user";
    const tag = !isUser && caseName && caseName !== "default" && CASES[caseName].tag
      ? `<div class="case-tag">${CASES[caseName].icon} ${CASES[caseName].tag}</div>` : "";
    if (!isUser && caseName && caseName !== "default") row.classList.add("case-card");
    row.innerHTML = `
      <div class="avatar ${role}">${isUser ? (userName ? esc(userName.trim()[0]) : "നി") : "✦"}</div>
      <div class="content">
        <div class="role-name">${isUser ? "നിങ്ങൾ" : "താര ✦"}</div>
        ${tag}
        <div class="bubble"></div>
      </div>`;
    const bubbleEl = row.querySelector(".bubble");
    if (isUser) bubbleEl.textContent = text;
    else bubbleEl.innerHTML = rich(text);
    messagesEl.appendChild(row);
    scrollToBottom();
    return row.querySelector(".bubble");
  }

  // Stick-to-bottom scrolling: while the reply is typing we only follow it if
  // the user is already at the bottom. The moment they scroll up to read,
  // auto-scroll stops fighting them; a ⬇ button offers the way back down.
  let stickToBottom = true;
  const jumpBtn = $("jump-latest");

  function scrollToBottom(force = false) {
    if (!force && !stickToBottom) return;
    scrollEl.scrollTop = scrollEl.scrollHeight;
  }

  scrollEl.addEventListener("scroll", () => {
    stickToBottom =
      scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < 80;
    jumpBtn.hidden = stickToBottom;
  });

  jumpBtn.addEventListener("click", () => {
    stickToBottom = true;
    jumpBtn.hidden = true;
    scrollToBottom(true);
  });

  // ChatGPT-style reading position: when a reply starts, pin the QUESTION to
  // the top of the view and let the answer grow downward — never chase it.
  function anchorToLatestUser() {
    const rows = messagesEl.querySelectorAll(".row.user");
    const row = rows[rows.length - 1];
    if (!row) return;
    const top =
      row.getBoundingClientRect().top -
      scrollEl.getBoundingClientRect().top +
      scrollEl.scrollTop;
    scrollEl.scrollTop = Math.max(0, top - 14);
  }

  // chips inside messages: type into composer or open prashnam
  messagesEl.addEventListener("click", (e) => {
    if (!e.target.classList.contains("chip")) return;
    if (e.target.dataset.action === "prashnam") return openPrashnam();
    input.value = e.target.textContent;
    autoGrow();
    form.requestSubmit();
  });

  // ---------- textarea ----------
  const autoGrow = () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  };
  input.addEventListener("input", autoGrow);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // ---------- history sidebar ----------
  let conversations = [];
  let historySig = null;
  const historyEl = $("history");
  const historyEmpty = $("history-empty");

  const firstUserText = (msgs) => {
    for (const m of msgs || []) if (m.role === "user") return m.content;
    return "";
  };

  function groupIntoConversations(entries) {
    const byId = new Map();
    entries.forEach((entry) => {
      const cid = entry.conversation_id || "legacy";
      if (!byId.has(cid)) byId.set(cid, { id: cid, turns: [], at: entry.created_at });
      byId.get(cid).turns.push(entry);
    });
    return [...byId.values()].map((c) => {
      c.turns.reverse();
      c.title = c.id === "legacy" ? "മുൻ സംഭാഷണങ്ങൾ"
        : firstUserText(c.turns[0] && c.turns[0].messages) || "സംഭാഷണം";
      c.at = c.turns[c.turns.length - 1].created_at;
      return c;
    });
  }

  function formatWhen(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const now = new Date();
    const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const sod = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const days = Math.round((sod(now) - sod(d)) / 86400000);
    if (days === 0) return `ഇന്ന് · ${time}`;
    if (days === 1) return `ഇന്നലെ · ${time}`;
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) + ` · ${time}`;
  }

  async function loadHistory() {
    try {
      const res = await fetch(`/chat/history/${encodeURIComponent(userId)}?limit=100`, {
        headers: authHeaders(),
      });
      if (res.status === 401) return sessionExpired();
      if (!res.ok) return;
      const entries = await res.json();
      if (!Array.isArray(entries)) return;
      conversations = groupIntoConversations(entries);
      const sig = conversations.map((c) => `${c.id}|${c.at}|${c.turns.length}`).join(";")
        + "@" + conversationId;
      if (sig === historySig) return;
      historySig = sig;
      historyEl.innerHTML = "";
      historyEmpty.hidden = conversations.length > 0;
      conversations.forEach((c) => {
        const item = document.createElement("div");
        item.className = "history-item";
        if (c.id === conversationId) item.classList.add("active");
        item.innerHTML = `<div class="hist-title"></div><span class="hist-time">${formatWhen(c.at)}</span>`;
        item.querySelector(".hist-title").textContent = c.title;
        item.addEventListener("click", () => openConversation(c.id));
        historyEl.appendChild(item);
      });
    } catch (_) { /* offline / Mongo off */ }
  }

  function openConversation(cid) {
    if (streaming) return;
    const conv = conversations.find((c) => c.id === cid);
    if (!conv) return;
    messages = [];
    conv.turns.forEach((t) => {
      (t.messages || []).forEach((m) => messages.push({ role: m.role, content: m.content }));
      messages.push({ role: "assistant", content: t.reply });
    });
    conversationId = cid;
    activePorutham = null; // partner context is not persisted across reloads
    messagesEl.innerHTML = "";
    messages.forEach((m, i) => {
      const bubble = addRow(m.role, m.content);
      if (m.role === "assistant")
        addActions(bubble.closest(".row"), m.content, i, i === messages.length - 1);
    });
    setCase("default");
    stickToBottom = true;
    jumpBtn.hidden = true;
    scrollToBottom(true);
    input.focus();
    loadHistory();
  }

  $("new-chat").addEventListener("click", () => {
    if (streaming) return;
    conversationId = newConversationId();
    messages = [];
    activePorutham = null; // partner context belongs to the old conversation
    document.querySelectorAll(".history-item.active").forEach((el) => el.classList.remove("active"));
    setCase("default");
    renderWelcome();
    input.focus();
  });

  // ---------- memory panel ----------
  const memoryPanel = $("memory-panel");
  const memoryFacts = $("memory-facts");
  $("memory-toggle").addEventListener("click", () => {
    const willShow = memoryFacts.hidden;
    memoryFacts.hidden = !willShow;
    $("memory-toggle").setAttribute("aria-expanded", String(willShow));
  });

  async function loadMemory() {
    try {
      const res = await fetch(`/chat/memory/${encodeURIComponent(userId)}`, {
        headers: authHeaders(),
      });
      if (res.status === 401) return sessionExpired();
      if (!res.ok) { memoryPanel.hidden = true; return; }
      const prof = await res.json();
      const facts = prof.facts || [];
      if (!prof.summary && facts.length === 0) { memoryPanel.hidden = true; return; }
      memoryFacts.innerHTML = "";
      if (prof.summary) {
        const li = document.createElement("li");
        li.className = "memory-summary";
        li.textContent = prof.summary;
        memoryFacts.appendChild(li);
      }
      facts.slice(-8).forEach((f) => {
        const li = document.createElement("li");
        li.textContent = f.text;
        memoryFacts.appendChild(li);
      });
      memoryPanel.hidden = false;
    } catch (_) { memoryPanel.hidden = true; }
  }

  // ---------- panchangam strip (today's sky at a glance) ----------
  async function loadPanchangam() {
    try {
      const res = await fetch("/astrology/panchangam", { headers: authHeaders() });
      if (!res.ok) return;
      const p = await res.json();
      const bits = [];
      if (p.nakshatram) bits.push(`✦ <b>${esc(p.nakshatram)}</b>`);
      if (p.tithi) bits.push(`${esc(p.tithi)}`);
      if (p.nalla_neram) bits.push(`നല്ല നേരം <b>${esc(p.nalla_neram)}</b>`);
      if (!bits.length) return;
      const strip = $("panchang-strip");
      strip.innerHTML = bits.join('<span class="dot">·</span>');
      strip.hidden = false;
    } catch (_) { /* keep hidden */ }
  }

  // ---------- typewriter ----------
  // No scrolling in here at all — the view is anchored at the question and
  // must not move with the growing text (the user controls the scroll).
  function typeOut(bubble, cursor, text) {
    return new Promise((resolve) => {
      let i = 0;
      const step = () => {
        i = Math.min(text.length, i + 2);
        bubble.textContent = text.slice(0, i);
        bubble.appendChild(cursor);
        if (i < text.length) setTimeout(step, 12);
        else resolve();
      };
      step();
    });
  }

  // ---------- follow-up chips ----------
  function followUpsFor(groundedIn) {
    const g = groundedIn || [];
    const has = (p) => g.some((x) => String(x).startsWith(p));
    const out = [];
    if (has("porutham")) out.push({ text: "ഞങ്ങളുടെ പൊരുത്തം കൂടുതൽ വിശദമാക്കാമോ?" });
    if (has("temple:")) out.push({ text: "ഈ ക്ഷേത്രത്തിലെ വഴിപാടുകൾ വിശദമാക്കാമോ?" });
    if (has("knowledge:dosha-sade-sati")) out.push({ text: "ഏഴര ശനിയിൽ ഞാൻ എന്ത് ശ്രദ്ധിക്കണം?" });
    if (has("knowledge:dosha-chovva")) out.push({ text: "ചൊവ്വാ ദോഷത്തിന് എന്ത് ചെയ്യാം?" });
    if (has("knowledge:mahadasha") || has("varga:"))
      out.push({ text: "എന്റെ ദശാകാലം കൂടുതൽ വിശദമാക്കൂ" });
    if (has("prashnam:")) out.push({ text: "🪷 മറ്റൊരു പ്രശ്നം ചോദിക്കൂ", action: "prashnam" });
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
      btn.className = "chip";
      btn.textContent = c.text;
      if (c.action) btn.dataset.action = c.action;
      wrap.appendChild(btn);
    });
    row.querySelector(".content").appendChild(wrap);
    scrollToBottom();
  }

  // ---------- message actions: copy / retry / feedback (Claude-desktop style) ----------
  // Feedback lives client-side for now (localStorage), keyed by conversation +
  // message index, so thumbs survive reloads of the same conversation.
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
      // http fallback: hidden textarea + execCommand
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

  // Attach the action bar to an assistant row. `idx` is the message's index in
  // `messages`; retry only makes sense on the newest reply, so adding a bar
  // with canRetry strips the retry button from every older bar first.
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

    if (canRetry) {
      bar.appendChild(mkAct("retry", "🔄", "വീണ്ടും ശ്രമിക്കൂ", retryLast));
    }

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
      // transient "thanks" note
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

  // Re-ask the last question: drop the newest assistant reply from the state
  // and the DOM, then resend the same user turn (with its prashnam, if any).
  function retryLast() {
    if (streaming) return;
    if (messages.length && messages[messages.length - 1].role === "assistant") {
      messages.pop();
      const rows = messagesEl.querySelectorAll(".row.assistant");
      const last = rows[rows.length - 1];
      if (last) last.remove();
    }
    if (!messages.length || messages[messages.length - 1].role !== "user") return;
    send(null, lastPrashnam, true);
  }

  function renderGrounded(bubble, groundedIn) {
    const g = (groundedIn || []).slice(0, 4);
    if (!g.length) return;
    const row = bubble.closest(".row");
    const wrap = document.createElement("div");
    wrap.className = "grounded-row";
    wrap.innerHTML = g.map((x) => `<span class="grounded-chip">${esc(x)}</span>`).join("");
    row.querySelector(".content").appendChild(wrap);
  }

  // ---------- send ----------
  let lastPrashnam = null; // remembered so 🔄 retry can repeat a prashnam turn
  // The partner from the last 💑 form stays attached for the REST of the
  // conversation, so follow-ups ("what are our stars?") keep the engine's
  // computed porutham facts in the prompt — the LLM can't reliably dig them
  // out of chat history on its own. Cleared on new chat / conversation switch.
  let activePorutham = null;

  async function send(text, prashnam = null, resend = false) {
    document.querySelectorAll(".followups").forEach((el) => el.remove());
    if (!resend) {
      messages.push({ role: "user", content: text });
      addRow("user", text);
    }
    lastPrashnam = prashnam;
    if (prashnam) setCase("prashnam");

    const bubble = addRow("assistant", "");
    bubble.innerHTML = '<span class="thinking"><i></i><i></i><i></i></span>';
    const cursor = document.createElement("span");
    cursor.className = "cursor-caret";
    // Pin the question to the top — the reply streams downward from here and
    // the view stays put; the ⬇ button (or scrolling down) shows the rest.
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
          porutham: activePorutham,
          provider: modelProvider,
        }),
      });
      if (res.status === 401) return sessionExpired();
      if (res.status === 429) {
        reply = "അല്പനേരം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കൂ — ഈ മണിക്കൂറിലെ സന്ദേശപരിധി കഴിഞ്ഞു. 🙏";
        bubble.textContent = reply;
        return;
      }
      if (!res.ok) throw new Error("network");

      const data = await res.json();
      reply = data.reply || "…";

      // morph the banner + tint this reply for its case
      const caseName = detectCase(data.grounded_in, data.is_safety_response, !!prashnam);
      setCase(caseName);
      const row = bubble.closest(".row");
      if (caseName !== "default") {
        row.classList.add("case-card");
        if (CASES[caseName].tag && !row.querySelector(".case-tag")) {
          const tag = document.createElement("div");
          tag.className = "case-tag";
          tag.textContent = `${CASES[caseName].icon} ${CASES[caseName].tag}`;
          row.querySelector(".content").insertBefore(tag, bubble);
        }
      }

      bubble.textContent = "";
      await typeOut(bubble, cursor, reply);
      bubble.innerHTML = rich(reply); // upgrade the typed text to rendered bold
      if (!data.is_safety_response) {
        renderGrounded(bubble, data.grounded_in);
        renderFollowUps(bubble, data.grounded_in);
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
      loadHistory();
      loadMemory();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || streaming) return;
    input.value = "";
    autoGrow();
    send(text);
  });

  // ---------- prashnam modal ----------
  const prashnamModal = $("prashnam-modal");
  const prashnamQuestion = $("prashnam-question");
  const arudhaGrid = $("arudha-grid");
  const prashnamPanes = {
    swarna: $("prashnam-swarna"),
    thamboola: $("prashnam-thamboola"),
    sankhya: $("prashnam-sankhya"),
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
    if (input.value.trim()) prashnamQuestion.value = input.value.trim();
    prashnamModal.hidden = false;
    prashnamQuestion.focus();
  }
  const closePrashnam = () => { prashnamModal.hidden = true; };

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
    $("leaf-count").value = "";
    $("sankhya-number").value = "";
    input.value = "";
    autoGrow();
    send(`🪷 [${label}] ${q}`, prashnam);
  }

  prashnamModal.querySelectorAll(".prashnam-mode").forEach((btn) => {
    btn.addEventListener("click", () => {
      prashnamModal.querySelectorAll(".prashnam-mode")
        .forEach((b) => b.classList.toggle("active", b === btn));
      const mode = btn.dataset.mode;
      Object.entries(prashnamPanes).forEach(([m, pane]) =>
        pane.classList.toggle("hidden", m !== mode)
      );
      if (mode === "thamboola") $("leaf-count").focus();
      if (mode === "sankhya") $("sankhya-number").focus();
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

  $("thamboola-send").addEventListener("click", () => {
    const n = Number($("leaf-count").value);
    if (!Number.isInteger(n) || n < 1 || n > 108) return $("leaf-count").focus();
    submitPrashnam({ mode: "thamboola", leaf_count: n }, "താംബൂല പ്രശ്നം");
  });
  $("leaf-count").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); $("thamboola-send").click(); }
  });

  $("sankhya-send").addEventListener("click", () => {
    const n = Number($("sankhya-number").value);
    if (!Number.isInteger(n) || n < 1 || n > 108) return $("sankhya-number").focus();
    submitPrashnam({ mode: "sankhya", number: n }, "സംഖ്യാ പ്രശ്നം");
  });
  $("sankhya-number").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); $("sankhya-send").click(); }
  });

  $("prashnam-open").addEventListener("click", openPrashnam);
  $("prashnam-close").addEventListener("click", closePrashnam);
  prashnamModal.addEventListener("click", (e) => {
    if (e.target === prashnamModal) closePrashnam();
  });

  // ---------- porutham (compatibility) modal ----------
  const poruthamModal = $("porutham-modal");
  let poruthamGender = "female"; // the PARTNER's gender

  poruthamModal.querySelectorAll(".porutham-sex").forEach((btn) => {
    btn.addEventListener("click", () => {
      poruthamModal.querySelectorAll(".porutham-sex")
        .forEach((b) => b.classList.toggle("active", b === btn));
      poruthamGender = btn.dataset.gender;
    });
  });

  function poruthamFail(msg) {
    const el = $("porutham-error");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function openPorutham() {
    if (streaming) return;
    $("porutham-error").classList.add("hidden");
    poruthamModal.hidden = false;
    $("porutham-name").focus();
  }
  const closePorutham = () => { poruthamModal.hidden = true; };

  $("porutham-send").addEventListener("click", () => {
    const name = $("porutham-name").value.trim();
    const dob = $("porutham-dob").value;
    const btime = $("porutham-time").value;
    const place = $("porutham-place").value.trim();
    if (!dob) return poruthamFail("പങ്കാളിയുടെ ജനന തീയതി നൽകൂ.");
    if (!place) return poruthamFail("പങ്കാളിയുടെ ജനന സ്ഥലം നൽകൂ.");
    activePorutham = {
      name,
      gender: poruthamGender,
      dob,
      birth_time: btime || null,
      birth_place: place,
    };
    closePorutham();
    setCase("porutham");
    const who = name || "പങ്കാളി";
    send(`💑 ${who}യുമായുള്ള പൊരുത്തം നോക്കാമോ?`);
  });

  $("porutham-open").addEventListener("click", openPorutham);
  $("porutham-close").addEventListener("click", closePorutham);
  poruthamModal.addEventListener("click", (e) => {
    if (e.target === poruthamModal) closePorutham();
  });

  // ---------- chart drawer ----------
  const chartDrawer = $("chart-drawer");
  const chartBackdrop = $("chart-backdrop");
  const chartBody = $("chart-body");
  let chartRendered = false;
  // One fetch serves both the chart drawer and the profile card's astro rows.
  let natalCache = null;

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
  $("chart-open").addEventListener("click", openChart);
  $("chart-close").addEventListener("click", closeChart);
  chartBackdrop.addEventListener("click", closeChart);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeChart(); closePrashnam(); closePorutham(); closeProfile(); }
  });

  // ---------- profile + logout ----------
  const profileModal = $("profile-modal");

  // Fixed astro identity (nakshatram / rasi / lagnam / running dasha) shown on
  // the profile card — the details users check to trust the readings are theirs.
  const LORD_ML = {
    surya: "സൂര്യൻ", chandra: "ചന്ദ്രൻ", chevvai: "ചൊവ്വ", budhan: "ബുധൻ",
    guru: "വ്യാഴം", shukran: "ശുക്രൻ", shani: "ശനി", rahu: "രാഹു", ketu: "കേതു",
  };
  async function fillProfileAstro() {
    const set = (id, v) => { $(id).textContent = v || "—"; };
    let natal = null;
    try { natal = await fetchNatal(); } catch (_) {}
    if (!natal) { ["pf-star", "pf-rasi", "pf-lagnam", "pf-dasha"].forEach((i) => set(i)); return; }
    set("pf-star", (natal.nakshatram || "—") +
      (natal.nakshatra_pada ? ` · പാദം ${natal.nakshatra_pada}` : ""));
    set("pf-rasi", natal.rasi);
    set("pf-lagnam", natal.lagnam);
    const cur = natal.dasha && natal.dasha.current;
    const maha = cur && (cur.mahadasha || cur);
    set("pf-dasha", maha && (maha.lord_ml || LORD_ML[maha.lord] || maha.lord)
      ? (maha.lord_ml || LORD_ML[maha.lord] || maha.lord) + " ദശ" : "—");
  }

  function openProfile() {
    const p = profile || {};
    const name = userName || p.name || "";
    $("pf-name").textContent = name || "—";
    $("pf-avatar").textContent = name ? name.trim()[0] : "✦";
    $("pf-phone").textContent = p.phone || userId || "—";
    $("pf-dob").textContent = p.dob || "—";
    $("pf-time").textContent = p.birth_time || "അറിയില്ല";
    $("pf-place").textContent = p.birth_place || "—";
    fillProfileAstro(); // async — rows show "…" until the chart arrives
    profileModal.hidden = false;
  }
  $("pf-chart").addEventListener("click", () => {
    profileModal.hidden = true;
    openChart();
  });
  const closeProfile = () => { profileModal.hidden = true; };
  $("side-avatar").addEventListener("click", openProfile);
  $("side-user-meta").addEventListener("click", openProfile);
  $("profile-close").addEventListener("click", closeProfile);
  profileModal.addEventListener("click", (e) => { if (e.target === profileModal) closeProfile(); });

  function logout() {
    if (streaming) return;
    if (authToken) {
      fetch("/identity/logout", { method: "POST", headers: authHeaders() }).catch(() => {});
    }
    ["tara_token", "tara_phone", "tara_name", "tara_profile"].forEach((k) =>
      localStorage.removeItem(k)
    );
    window.location.href = "/ui/login";
  }
  $("logout-btn").addEventListener("click", logout);
  $("profile-logout").addEventListener("click", logout);

  function updateSidebarUser() {
    $("side-user-name").textContent = userName || "—";
    $("side-user-phone").textContent = userId || "";
    $("side-avatar").textContent = userName ? userName.trim()[0] : "✦";
  }

  async function ensureUserName() {
    if (userName) return;
    try {
      const res = await fetch("/identity/me", { headers: authHeaders() });
      if (res.status === 401) return sessionExpired();
      if (!res.ok) return;
      const me = await res.json();
      if (me.name) {
        userName = me.name;
        localStorage.setItem("tara_name", userName);
        updateSidebarUser();
        if (messagesEl.querySelector(".welcome")) renderWelcome();
      }
    } catch (_) {}
  }

  // ---------- boot ----------
  updateSidebarUser();
  renderWelcome();
  ensureUserName();
  loadHistory();
  loadMemory();
  loadPanchangam();
})();
