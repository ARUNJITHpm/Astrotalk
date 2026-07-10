// TARA UI — astrologer directory + free consult booking.
// Browsing is public; booking requires the same localStorage session as /ui.
(() => {
  const $ = (id) => document.getElementById(id);
  const grid = $("astro-grid");
  const emptyEl = $("astro-empty");
  const filter = $("district-filter");
  const drawer = $("drawer");
  const scrim = $("drawer-scrim");
  const drawerBody = $("drawer-body");
  const toastEl = $("toast");
  const mineSection = $("mine-section");
  const mineList = $("mine-list");

  const authToken = localStorage.getItem("tara_token") || null;
  const authHeaders = (extra = {}) =>
    authToken ? { ...extra, Authorization: `Bearer ${authToken}` } : extra;

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  const WEEKDAYS_ML = ["ഞായർ", "തിങ്കൾ", "ചൊവ്വ", "ബുധൻ", "വ്യാഴം", "വെള്ളി", "ശനി"];
  const SPECIALTY_ML = {
    career: "തൊഴിൽ", marriage: "വിവാഹം", children: "സന്താനം",
    education: "വിദ്യാഭ്യാസം", health: "ആരോഗ്യം", wealth: "സാമ്പത്തികം",
    obstacles: "തടസ്സങ്ങൾ", peace: "മനസ്സമാധാനം", ancestors: "പിതൃകർമ്മം",
  };

  let toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toastEl.hidden = true), 3200);
  }

  const ymd = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const hhmm = (iso) => String(iso).slice(11, 16); // "…T09:30:00+05:30" → "09:30"

  // ---------- directory ----------
  async function loadDirectory() {
    const district = filter.value;
    const q = district ? `?district=${encodeURIComponent(district)}` : "";
    let list = [];
    try {
      const res = await fetch(`/astrologers${q}`);
      list = await res.json();
    } catch (_) {
      toast("വിവരങ്ങൾ ലഭ്യമായില്ല. വീണ്ടും ശ്രമിക്കൂ.");
      return;
    }
    grid.innerHTML = "";
    emptyEl.hidden = list.length > 0;
    list.forEach((a) => grid.appendChild(card(a)));
  }

  function card(a) {
    const el = document.createElement("article");
    el.className = "astro-card";
    const chips = (a.specialties || [])
      .map((s) => `<span class="spec-chip">${esc(SPECIALTY_ML[s] || s)}</span>`)
      .join("");
    el.innerHTML = `
      <div class="astro-card-top">
        <div class="astro-avatar">✦</div>
        <div>
          <div class="astro-name">${esc(a.name)}</div>
          <div class="astro-place">${esc(a.town)}, ${esc(a.district)}</div>
        </div>
        <div class="astro-rating">★ ${esc(a.rating)}</div>
      </div>
      <div class="astro-meta">${esc(a.experience_years)} വർഷ പരിചയം · ${esc((a.languages || []).join(", "))}</div>
      <div class="astro-specs">${chips}</div>
      <p class="astro-bio">${esc(a.bio_ml || "")}</p>
      <button class="btn astro-book-btn">സമയം ബുക്ക് ചെയ്യാം</button>`;
    el.querySelector(".astro-book-btn").addEventListener("click", () => openDrawer(a));
    return el;
  }

  // ---------- booking drawer ----------
  let current = null;

  function openDrawer(a) {
    current = a;
    drawerBody.innerHTML = `
      <div class="drawer-astro">
        <div class="astro-name">${esc(a.name)}</div>
        <div class="astro-place">${esc(a.town)}, ${esc(a.district)} · ★ ${esc(a.rating)}</div>
      </div>
      <div class="drawer-label">തീയതി തിരഞ്ഞെടുക്കൂ</div>
      <div class="date-row" id="date-row"></div>
      <div class="drawer-label">സമയം</div>
      <div class="slot-row" id="slot-row"><span class="muted">തീയതി തിരഞ്ഞെടുക്കൂ</span></div>
      <textarea class="drawer-note" id="drawer-note" rows="2" placeholder="കുറിപ്പ് (ഐച്ഛികം)"></textarea>`;
    const dateRow = $("date-row");
    const today = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      const b = document.createElement("button");
      b.className = "date-chip";
      b.innerHTML = `<span>${WEEKDAYS_ML[d.getDay()]}</span><strong>${d.getDate()}</strong>`;
      b.addEventListener("click", () => {
        [...dateRow.children].forEach((c) => c.classList.remove("active"));
        b.classList.add("active");
        loadSlots(a.id, ymd(d));
      });
      dateRow.appendChild(b);
    }
    drawer.hidden = false;
    scrim.hidden = false;
  }

  function closeDrawer() {
    drawer.hidden = true;
    scrim.hidden = true;
    current = null;
  }

  async function loadSlots(astroId, date) {
    const slotRow = $("slot-row");
    slotRow.innerHTML = `<span class="muted">ലോഡ് ചെയ്യുന്നു…</span>`;
    let slots = [];
    try {
      const res = await fetch(`/astrologers/${encodeURIComponent(astroId)}/availability?date=${date}`);
      slots = await res.json();
    } catch (_) {
      slotRow.innerHTML = `<span class="muted">സമയം ലഭ്യമായില്ല</span>`;
      return;
    }
    if (!slots.length) {
      slotRow.innerHTML = `<span class="muted">ഈ ദിവസം ഒഴിവില്ല</span>`;
      return;
    }
    slotRow.innerHTML = "";
    slots.forEach((s) => {
      const b = document.createElement("button");
      b.className = "slot-chip";
      b.textContent = hhmm(s.starts_at);
      b.addEventListener("click", () => confirmBooking(astroId, s.starts_at));
      slotRow.appendChild(b);
    });
  }

  async function confirmBooking(astroId, startsAt) {
    if (!authToken) {
      window.location.href = "/ui/login";
      return;
    }
    const note = ($("drawer-note") && $("drawer-note").value.trim()) || null;
    try {
      const res = await fetch(`/astrologers/${encodeURIComponent(astroId)}/book`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ starts_at: startsAt, note }),
      });
      if (res.status === 401 || res.status === 403) {
        window.location.href = "/ui/login";
        return;
      }
      if (res.status === 409) {
        toast("ആ സമയം ഇപ്പോൾ ലഭ്യമല്ല. മറ്റൊന്ന് തിരഞ്ഞെടുക്കൂ.");
        return;
      }
      if (!res.ok) throw new Error("book failed");
      toast("ബുക്ക് ചെയ്തു ✓");
      closeDrawer();
      loadMine();
    } catch (_) {
      toast("ബുക്കിംഗ് പരാജയപ്പെട്ടു. വീണ്ടും ശ്രമിക്കൂ.");
    }
  }

  // ---------- my bookings ----------
  async function loadMine() {
    if (!authToken) return;
    let rows = [];
    try {
      const res = await fetch("/astrologers/bookings/me", { headers: authHeaders() });
      if (!res.ok) return;
      rows = await res.json();
    } catch (_) {
      return;
    }
    const active = rows.filter((b) => b.status !== "cancelled");
    mineSection.hidden = active.length === 0;
    mineList.innerHTML = "";
    active.forEach((b) => {
      const when = new Date(b.starts_at);
      const el = document.createElement("div");
      el.className = "mine-item";
      el.innerHTML = `
        <div>
          <div class="astro-name">${esc(b.astrologer_id)}</div>
          <div class="astro-place">${when.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</div>
        </div>
        <button class="btn-ghost cancel-btn">റദ്ദാക്കുക</button>`;
      el.querySelector(".cancel-btn").addEventListener("click", () => cancelBooking(b.id));
      mineList.appendChild(el);
    });
  }

  async function cancelBooking(id) {
    try {
      const res = await fetch(`/astrologers/bookings/${id}/cancel`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error("cancel failed");
      toast("ബുക്കിംഗ് റദ്ദാക്കി");
      loadMine();
    } catch (_) {
      toast("റദ്ദാക്കാനായില്ല. വീണ്ടും ശ്രമിക്കൂ.");
    }
  }

  // ---------- deep link + wiring ----------
  filter.addEventListener("change", loadDirectory);
  $("drawer-close").addEventListener("click", closeDrawer);
  scrim.addEventListener("click", closeDrawer);

  async function init() {
    const params = new URLSearchParams(window.location.search);
    const preDistrict = params.get("district");
    if (preDistrict) filter.value = preDistrict;
    await loadDirectory();
    loadMine();

    const preAstro = params.get("astro");
    if (preAstro) {
      try {
        const res = await fetch(`/astrologers/${encodeURIComponent(preAstro)}`);
        if (res.ok) openDrawer(await res.json());
      } catch (_) {}
    }
  }

  init();
})();
