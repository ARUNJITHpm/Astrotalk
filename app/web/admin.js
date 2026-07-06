// Tara admin dashboard script - manages login, tabs, data rendering, and chat exploration.
(function () {
  "use strict";

  const TOKEN_KEY = "tara_admin_token";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat();
  const fmtNum = (n) => nf.format(n || 0);
  // Costs are tiny fractions; show enough precision to be meaningful without
  // the ₹0.000000 noise. Full value lives in the title tooltip where rendered.
  const fmtPrice = (n, symbol = "₹") => {
    const v = n || 0;
    if (v === 0) return symbol + "0";
    if (v >= 1) return symbol + v.toFixed(2);
    if (v >= 0.01) return symbol + v.toFixed(4);
    return symbol + v.toFixed(6);
  };

  const relTime = (iso) => {
    if (!iso) return "—";
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60e3) return "just now";
    if (diff < 3600e3) return Math.floor(diff / 60e3) + "m ago";
    if (diff < 86400e3) return Math.floor(diff / 3600e3) + "h ago";
    if (diff < 7 * 86400e3) return Math.floor(diff / 86400e3) + "d ago";
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };

  let currentTab = "dashboard";
  let chatUsers = []; // Users loaded for explorer sidebar
  let activeChatPhone = null; // Currently selected user phone
  let activeSessionId = null; // Currently selected conversation id
  let activeUserSessions = {}; // {conversation_id: [turns newest-first]}
  let sortedSessionIds = []; // Session ids, most recent first

  function authHeaders() {
    const t = localStorage.getItem(TOKEN_KEY);
    return t ? { "X-Admin-Token": t, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  }

  function showGate(msg) {
    $("dash").classList.add("hidden");
    $("gate").classList.remove("hidden");
    $("gateErr").textContent = msg || "";
    $("passwordInput").value = "";
    $("passwordInput").focus();
  }

  function showDash() {
    $("gate").classList.add("hidden");
    $("dash").classList.remove("hidden");
  }

  // Prefill admin/chargemod credentials helper
  window.prefillCreds = function (e) {
    if (e) e.preventDefault();
    $("usernameInput").value = "admin";
    $("passwordInput").value = "chargemod";
    $("gateErr").textContent = "";
  };

  // Submit Login credentials to POST /admin/login
  window.submitLogin = async function () {
    const username = $("usernameInput").value.trim();
    const password = $("passwordInput").value.trim();
    const errEl = $("gateErr");

    if (!username || !password) {
      errEl.textContent = "Please enter both username and password.";
      return;
    }

    errEl.textContent = "Authenticating…";
    try {
      const res = await fetch("/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      if (!res.ok) {
        throw new Error("Invalid username or password");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.token);
      errEl.textContent = "";
      loadOverview();
    } catch (err) {
      errEl.textContent = err.message;
    }
  };

  window.signOut = function () {
    localStorage.removeItem(TOKEN_KEY);
    showGate("");
  };

  // Setup enter key trigger for login input fields
  [$("usernameInput"), $("passwordInput")].forEach((el) => {
    if (el) {
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") window.submitLogin();
      });
    }
  });

  // ---- Tab Switching ----
  window.switchTab = function (tab) {
    currentTab = tab;

    ["dashboard", "explorer"].forEach((t) => {
      const btn = $("tab-" + t);
      const view = $("view-" + t);
      if (t === tab) {
        btn.classList.add("active");
        view.classList.remove("hidden");
      } else {
        btn.classList.remove("active");
        view.classList.add("hidden");
      }
    });

    if (tab === "explorer" && !chatUsers.length) {
      loadChatUsers();
    }
  };

  // Mobile drill-down: which pane is visible (<980px). Desktop shows all three.
  window.explorerStage = function (stage) {
    $("explorer").dataset.stage = stage;
  };

  // ---- Data Load & Refresh ----
  window.refreshData = function () {
    if (currentTab === "dashboard") {
      loadOverview();
    } else {
      loadChatUsers();
      if (activeChatPhone) {
        selectChatUser(activeChatPhone, { keepStage: true });
      }
    }
  };

  async function boot() {
    let tokenRequired = true;
    try {
      const cfg = await fetch("/admin/config").then((r) => r.json());
      tokenRequired = !!cfg.token_required;
    } catch (_) { /* Fallback to gating on load error */ }

    if (tokenRequired && !localStorage.getItem(TOKEN_KEY)) {
      showGate("");
      return;
    }
    loadOverview();
  }

  async function loadOverview() {
    const btn = $("refreshBtn");
    if (btn) { btn.disabled = true; btn.textContent = "Loading…"; }
    try {
      const res = await fetch("/admin/overview", { headers: authHeaders() });
      if (res.status === 401) { showGate("Session expired — please log in again."); return; }
      if (res.status === 503) {
        showDash();
        banner("Admin dashboard is disabled in this environment. Set ADMIN_TOKEN to enable it.");
        return;
      }
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      showDash();
      renderDashboard(data);
    } catch (err) {
      banner("Could not load analytics: " + err.message);
      showDash();
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "↻ Refresh"; }
    }
  }

  function banner(msg) {
    const b = $("banner");
    if (!msg) { b.classList.add("hidden"); return; }
    b.textContent = msg;
    b.classList.remove("hidden");
  }

  // ---- Render Dashboard Metrics ----
  function renderDashboard(d) {
    banner("");
    $("genAt").textContent = new Date(d.generated_at).toLocaleString();

    renderKpis(d);
    renderStatus(d.system);
    renderSignupTrend(d.users);
    renderChatTrend(d.chat);
    renderModelUsageTable(d.llm);
    renderProviders(d.llm);
    renderTopUsers(d.chat);
    renderRecent(d.users);
  }

  function tile(label, value, sub, foot, accent) {
    return `<div class="tile${accent ? " accent" : ""}">
      <div class="label">${label}</div>
      <div class="value">${value}${sub ? ` <small>${sub}</small>` : ""}</div>
      ${foot ? `<div class="foot">${foot}</div>` : ""}
    </div>`;
  }

  function renderKpis(d) {
    const u = d.users || {};
    const c = d.chat || {};
    const l = (d.llm && d.llm.totals) || {};
    const chatTurns = c.available ? fmtNum(c.total_turns) : "n/a";
    const chatFoot = c.available
      ? `${fmtNum(c.turns_24h)} in last 24h`
      : "Mongo disabled";

    const totalCostInr = l.price_inr !== undefined ? fmtPrice(l.price_inr, "₹") : "n/a";
    const totalCostUsd = l.price_usd !== undefined ? fmtPrice(l.price_usd, "$") : "n/a";

    $("kpis").innerHTML = [
      tile("Total users", fmtNum(u.total_users), "", `<span class="up">+${fmtNum(u.new_users_7d)}</span> this week`, true),
      tile("Active sessions", fmtNum(u.active_sessions), "", "unexpired logins"),
      tile("Chat turns", chatTurns, "", chatFoot),
      tile("Total Cost (INR)", totalCostInr, "", `Estimated Cost (USD): ${totalCostUsd}`, true),
      tile("Tokens used", fmtNum(l.total_tokens), "", `${fmtNum(l.calls)} LLM calls · ${fmtNum(l.live_calls)} live`),
      tile("New today", fmtNum(u.new_users_24h), "", `${fmtNum(u.new_users_30d)} in 30 days`),
    ].join("");
  }

  function renderStatus(sys) {
    if (!sys) return;
    const ints = sys.integrations || {};
    const parts = [];
    parts.push(pill(`env: ${sys.app_env}`, sys.app_env === "production"));
    parts.push(pill(`chat: ${sys.chat_provider}`, true));
    for (const [name, on] of Object.entries(ints)) {
      parts.push(pill(name, on, on ? "live" : "mock"));
    }
    $("statusPills").innerHTML = parts.join("");
  }

  function pill(label, on, tag) {
    return `<span class="pill ${on ? "on" : "off"}">
      <span class="dot"></span>${label}${tag ? ` · <span class="muted">${tag}</span>` : ""}
    </span>`;
  }

  function barChart(el, series, fromEl, toEl) {
    const max = Math.max(1, ...series.map((p) => p.count));
    el.innerHTML = series
      .map((p) => {
        const h = Math.round((p.count / max) * 100);
        return `<div class="bar" title="${p.date}: ${p.count}">
          <div class="fill" style="height:${h}%"></div>
          <div class="cap">${p.count || ""}</div>
        </div>`;
      })
      .join("");
    if (fromEl && series.length) fromEl.textContent = series[0].date.slice(5);
    if (toEl && series.length) toEl.textContent = series[series.length - 1].date.slice(5);
  }

  function renderSignupTrend(u) {
    barChart($("signupBars"), (u && u.signups_daily_14d) || [], $("signupFrom"), $("signupTo"));
  }

  function renderChatTrend(c) {
    if (!c || !c.available) {
      $("chatTrendWrap").classList.add("hidden");
      const e = $("chatTrendEmpty");
      e.classList.remove("hidden");
      e.textContent = "Chat history is stored in MongoDB, which is disabled (MOCK_MONGO). Enable it to see chat trends.";
      return;
    }
    $("chatTrendWrap").classList.remove("hidden");
    $("chatTrendEmpty").classList.add("hidden");
    barChart($("chatBars"), c.turns_daily_14d || [], $("chatFrom"), $("chatTo"));
  }

  function hbar(label, value, max, meta) {
    const pct = Math.round((value / Math.max(1, max)) * 100);
    return `<div class="hbar">
      <div class="hb-top"><span>${label}</span><b>${fmtNum(value)}</b></div>
      <div class="track"><span style="width:${pct}%"></span></div>
      ${meta ? `<div class="meta">${meta}</div>` : ""}
    </div>`;
  }

  function renderProviders(llm) {
    const by = (llm && llm.by_provider) || {};
    const rows = Object.entries(by);
    const wrap = $("providerBars");
    if (!rows.length) {
      wrap.innerHTML = "";
      $("providerEmpty").classList.remove("hidden");
      return;
    }
    $("providerEmpty").classList.add("hidden");
    const max = Math.max(...rows.map(([, v]) => v.total_tokens || 0), 1);
    wrap.innerHTML = rows
      .sort((a, b) => (b[1].total_tokens || 0) - (a[1].total_tokens || 0))
      .map(([name, v]) => {
        const costStr = `<span class="cost">${fmtPrice(v.price_inr, "₹")}</span>`;
        const metaStr = `<span>${fmtNum(v.calls)} calls · ${fmtNum(v.prompt_tokens)} in / ${fmtNum(v.completion_tokens)} out</span>${costStr}`;
        return hbar(name, v.total_tokens || 0, max, metaStr);
      })
      .join("");
  }

  function renderModelUsageTable(llm) {
    const byModel = (llm && llm.by_model) || {};
    const tableBody = $("modelUsageTable").querySelector("tbody");
    const emptyEl = $("modelUsageEmpty");
    const rows = Object.entries(byModel);

    if (!rows.length) {
      tableBody.innerHTML = "";
      emptyEl.classList.remove("hidden");
      $("modelUsageTable").classList.add("hidden");
      return;
    }

    emptyEl.classList.add("hidden");
    $("modelUsageTable").classList.remove("hidden");

    tableBody.innerHTML = rows
      .sort((a, b) => (b[1].total_tokens || 0) - (a[1].total_tokens || 0))
      .map(([modelName, data]) => {
        return `<tr>
          <td style="font-weight: 600; color: #fff;">${escapeHtml(modelName)}</td>
          <td class="num">${fmtNum(data.calls)}</td>
          <td class="num">${fmtNum(data.prompt_tokens)}</td>
          <td class="num">${fmtNum(data.completion_tokens)}</td>
          <td class="num" style="font-weight: 500;">${fmtNum(data.total_tokens)}</td>
          <td class="num" style="color: var(--gold); font-weight: 600;" title="₹${(data.price_inr || 0).toFixed(6)}">${fmtPrice(data.price_inr, "₹")}</td>
          <td class="num" style="color: #93c5fd;" title="$${(data.price_usd || 0).toFixed(6)}">${fmtPrice(data.price_usd, "$")}</td>
        </tr>`;
      })
      .join("");
  }

  function renderTopUsers(c) {
    const body = $("topUsersTable").querySelector("tbody");
    const empty = $("topUsersEmpty");
    const rows = (c && c.available && c.top_users) || [];
    if (!c || !c.available) {
      $("topUsersTable").classList.add("hidden");
      empty.classList.remove("hidden");
      empty.textContent = "Chat history disabled (MOCK_MONGO).";
      return;
    }
    $("topUsersTable").classList.remove("hidden");
    if (!rows.length) { empty.classList.remove("hidden"); empty.textContent = "No chats yet."; body.innerHTML = ""; return; }
    empty.classList.add("hidden");
    body.innerHTML = rows
      .map((r) => `<tr><td style="font-weight: 500; font-variant-numeric: tabular-nums;">${escapeHtml(r.user)}</td><td class="num">${fmtNum(r.turns)}</td></tr>`)
      .join("");
  }

  function renderRecent(u) {
    const body = $("recentTable").querySelector("tbody");
    const rows = (u && u.recent_users) || [];
    if (!rows.length) { $("recentEmpty").classList.remove("hidden"); body.innerHTML = ""; return; }
    $("recentEmpty").classList.add("hidden");
    body.innerHTML = rows
      .map((r) => {
        const when = r.created_at ? new Date(r.created_at).toLocaleDateString() : "—";
        const chart = r.has_chart
          ? '<span style="color:var(--good)">Active ●</span>'
          : '<span class="muted">None ○</span>';
        return `<tr>
          <td style="font-weight: 600; color:#fff;">${escapeHtml(r.name)}</td>
          <td class="muted" style="font-variant-numeric: tabular-nums;">${escapeHtml(r.phone)}</td>
          <td>${chart}</td>
          <td class="muted">${when}</td>
        </tr>`;
      })
      .join("");
  }

  // ================= CHAT EXPLORER =================
  // Three panes: users → sessions → conversation. On narrow screens only one
  // pane is visible at a time (data-stage drill-down with back buttons).

  const skeletonRows = (n) =>
    Array.from({ length: n }, () =>
      `<div style="padding: 12px 14px; display:flex; gap:11px; align-items:center;">
        <div class="skeleton" style="width:36px;height:36px;border-radius:50%;flex-shrink:0;"></div>
        <div style="flex:1;"><div class="skeleton" style="height:12px;width:70%;margin-bottom:7px;"></div>
        <div class="skeleton" style="height:10px;width:45%;"></div></div>
      </div>`
    ).join("");

  async function loadChatUsers() {
    const listEl = $("explorerUserList");
    if (!chatUsers.length) listEl.innerHTML = skeletonRows(7);
    try {
      const res = await fetch("/admin/users-chats", { headers: authHeaders() });
      if (!res.ok) throw new Error("HTTP " + res.status);
      chatUsers = await res.json();
      renderChatUsersList();
    } catch (err) {
      listEl.innerHTML = `<div class="pane-placeholder">Could not load users: ${escapeHtml(err.message)}</div>`;
    }
  }

  function initials(name) {
    const parts = String(name || "?").trim().split(/\s+/);
    return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  }

  function renderChatUsersList() {
    const listEl = $("explorerUserList");
    const query = $("userSearch").value.trim().toLowerCase();

    const filtered = chatUsers.filter((u) => {
      return u.phone.toLowerCase().includes(query) || u.name.toLowerCase().includes(query);
    });

    if (!filtered.length) {
      const msg = query ? `No users match “${escapeHtml(query)}”` : "No users with chat history yet.";
      listEl.innerHTML = `<div class="pane-placeholder"><span class="icon">🔎</span><span>${msg}</span></div>`;
      return;
    }

    listEl.innerHTML = filtered
      .map((u) => {
        const activeClass = activeChatPhone === u.phone ? " active" : "";
        return `<div class="user-item${activeClass}" data-phone="${escapeHtml(u.phone)}">
          <div class="avatar">${escapeHtml(initials(u.name))}</div>
          <div class="u-body">
            <div class="u-top">
              <span class="name">${escapeHtml(u.name)}</span>
              <span class="time" title="${u.last_active ? new Date(u.last_active).toLocaleString() : ""}">${relTime(u.last_active)}</span>
            </div>
            <div class="u-bottom">
              <span class="phone">${escapeHtml(u.phone)}</span>
              <span class="turns">${fmtNum(u.turns)} turns</span>
            </div>
          </div>
        </div>`;
      })
      .join("");

    listEl.querySelectorAll(".user-item").forEach((el) => {
      el.addEventListener("click", () => selectChatUser(el.dataset.phone));
    });
  }

  window.filterChatUsers = function () {
    renderChatUsersList();
  };

  // First user message of the session, used as its human-readable title.
  function sessionTitle(turns) {
    const oldest = turns[turns.length - 1];
    const firstMsg = oldest && oldest.messages && oldest.messages[0];
    const text = firstMsg && firstMsg.content ? firstMsg.content : "(no message)";
    return text.length > 80 ? text.slice(0, 80) + "…" : text;
  }

  function renderSessionList() {
    const listEl = $("sessionList");
    listEl.classList.remove("hidden");
    $("sessionsPlaceholder").classList.add("hidden");

    listEl.innerHTML = sortedSessionIds
      .map((cid) => {
        const turns = activeUserSessions[cid];
        const latest = turns[0];
        const cost = turns.reduce((s, t) => s + (t.price_inr || 0), 0);
        const activeClass = cid === activeSessionId ? " active" : "";
        const dateStr = new Date(latest.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
        return `<div class="session-item${activeClass}" data-cid="${escapeHtml(cid)}">
          <div class="s-title">${escapeHtml(sessionTitle(turns))}</div>
          <div class="s-meta">
            <span>${turns.length} turn${turns.length === 1 ? "" : "s"}</span>
            <span class="s-cost">${fmtPrice(cost, "₹")}</span>
          </div>
          <div class="s-date">${dateStr}</div>
        </div>`;
      })
      .join("");

    listEl.querySelectorAll(".session-item").forEach((el) => {
      el.addEventListener("click", () => {
        switchConversation(el.dataset.cid);
        explorerStage("chat");
      });
    });
  }

  function statChip(label, value, cls) {
    return `<span class="stat-chip${cls ? " " + cls : ""}">${label} <b>${value}</b></span>`;
  }

  function switchConversation(cid) {
    activeSessionId = cid;
    const turns = activeUserSessions[cid] || [];
    const messagesView = $("chatMessagesView");

    // Mark active row in the session list
    document.querySelectorAll(".session-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.cid === cid);
    });

    $("chatPlaceholder").classList.add("hidden");
    $("chatHeader").classList.remove("hidden");
    messagesView.classList.remove("hidden");

    // Session totals in the header
    let totalCostInr = 0;
    let totalTokens = 0;
    turns.forEach((t) => {
      totalCostInr += t.price_inr || 0;
      totalTokens += t.total_tokens || 0;
    });
    $("chatHeaderStats").innerHTML = [
      statChip("turns", fmtNum(turns.length)),
      statChip("tokens", fmtNum(totalTokens)),
      statChip("cost", fmtPrice(totalCostInr, "₹"), "cost"),
    ].join("");

    if (!turns.length) {
      messagesView.innerHTML = `<div class="pane-placeholder">No messages logged in this session.</div>`;
      return;
    }

    // Turns come newest-first from the API; display chronologically with day dividers.
    const chronTurns = [...turns].reverse();
    let lastDay = "";

    messagesView.innerHTML = chronTurns
      .map((t) => {
        const d = new Date(t.created_at);
        const dayStr = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
        const divider = dayStr !== lastDay ? `<div class="day-divider">${dayStr}</div>` : "";
        lastDay = dayStr;

        const userContent = t.messages.map((m) => escapeHtml(m.content)).join("<br/>");
        const replyContent = escapeHtml(t.reply).replace(/\n/g, "<br/>");
        const timeStr = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

        const providerStr = escapeHtml(t.llm_provider || "mock");
        const modelStr = escapeHtml(t.llm_model || "—");
        const costStr = fmtPrice(t.price_inr, "₹") + " / " + fmtPrice(t.price_usd, "$");

        return `${divider}<div class="chat-turn">
          <span class="msg-time">${timeStr}</span>
          <div class="msg-bubble user">${userContent}</div>
          <div class="msg-bubble assistant">${replyContent}</div>
          <div class="turn-meta">
            <span class="meta-badge">${providerStr} · <b>${modelStr}</b></span>
            <span class="meta-badge">tokens <b>${fmtNum(t.total_tokens || 0)}</b> (${t.prompt_tokens || 0} in / ${t.completion_tokens || 0} out)</span>
            <span class="meta-badge cost" title="₹${(t.price_inr || 0).toFixed(6)} / $${(t.price_usd || 0).toFixed(6)}">${costStr}</span>
          </div>
        </div>`;
      })
      .join("");

    messagesView.scrollTop = messagesView.scrollHeight;
  }

  async function selectChatUser(phone, opts) {
    activeChatPhone = phone;
    activeSessionId = null;
    renderChatUsersList(); // re-render sidebar to move the active highlight

    const u = chatUsers.find((x) => x.phone === phone);
    $("sessionsPaneTitle").textContent = u ? u.name : "Sessions";
    $("sessionsPaneSub").textContent = phone;
    $("chatHeaderName").textContent = u ? u.name : "User";
    $("chatHeaderPhone").textContent = phone;

    const listEl = $("sessionList");
    listEl.classList.remove("hidden");
    $("sessionsPlaceholder").classList.add("hidden");
    listEl.innerHTML = skeletonRows(4);

    // Reset conversation pane until a session is chosen
    $("chatHeader").classList.add("hidden");
    $("chatMessagesView").classList.add("hidden");
    $("chatPlaceholder").classList.remove("hidden");

    if (!(opts && opts.keepStage)) explorerStage("sessions");

    try {
      const res = await fetch(`/admin/user-chat/${encodeURIComponent(phone)}`, { headers: authHeaders() });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const turns = await res.json();

      if (!turns.length) {
        listEl.innerHTML = `<div class="pane-placeholder"><span class="icon">🗂️</span><span>No messages logged in chat history.</span></div>`;
        return;
      }

      // Group turns by conversation_id (turns arrive newest-first)
      activeUserSessions = {};
      turns.forEach((t) => {
        const cid = t.conversation_id || "ungrouped";
        if (!activeUserSessions[cid]) activeUserSessions[cid] = [];
        activeUserSessions[cid].push(t);
      });

      // Sessions ordered by their latest turn, most recent first
      sortedSessionIds = Object.keys(activeUserSessions).sort((a, b) => {
        return new Date(activeUserSessions[b][0].created_at) - new Date(activeUserSessions[a][0].created_at);
      });

      // Auto-open the most recent session (desktop shows it beside the list;
      // on mobile the user taps a session to advance to the chat pane).
      activeSessionId = sortedSessionIds[0];
      renderSessionList();
      switchConversation(activeSessionId);
    } catch (err) {
      listEl.innerHTML = `<div class="pane-placeholder" style="color: var(--danger);">Failed to load chat: ${escapeHtml(err.message)}</div>`;
    }
  }
  window.selectChatUser = selectChatUser;

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  }

  boot();
})();
