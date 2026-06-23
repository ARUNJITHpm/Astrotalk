// Tara chat — streams the assistant reply token-by-token, Claude-desktop style.
(() => {
  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("composer-form");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const historyEl = document.getElementById("history");
  const newChatBtn = document.getElementById("new-chat");

  /** Conversation state: [{role, content}]. Sent in full each request (API is stateless). */
  let messages = [];
  let streaming = false;

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
    if (messages.length) archiveConversation();
    messages = [];
    renderWelcome();
    input.focus();
  });

  function renderWelcome() {
    messagesEl.innerHTML = `
      <div class="welcome">
        <div class="welcome-star">✦</div>
        <h1>നമസ്കാരം 🙏</h1>
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

  function archiveConversation() {
    const firstUser = messages.find((m) => m.role === "user");
    if (!firstUser) return;
    const item = document.createElement("div");
    item.className = "history-item";
    item.textContent = firstUser.content;
    historyEl.prepend(item);
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
        body: JSON.stringify({ user_id: "demo", messages }),
      });
      if (!res.ok || !res.body) throw new Error("network");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        reply += decoder.decode(value, { stream: true });
        bubble.textContent = reply;
        bubble.appendChild(cursor);
        scrollToBottom();
      }
    } catch (err) {
      reply = reply || "ക്ഷമിക്കണം, ഒരു പിശക് സംഭവിച്ചു. വീണ്ടും ശ്രമിക്കൂ.";
      bubble.textContent = reply;
    } finally {
      cursor.remove();
      streaming = false;
      sendBtn.disabled = false;
      messages.push({ role: "assistant", content: reply });
      input.focus();
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
})();
