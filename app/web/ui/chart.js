// TARA UI — natal chart renderer (South Indian / Kerala style).
// Exposes window.TaraChart.render(natalJson, user) → HTML string for the
// chart drawer: birth tiles, D1/D9 rasi grid, dasha timeline, doshas, planets.
(() => {
  const RASIS = [
    "മേടം", "ഇടവം", "മിഥുനം", "കർക്കടകം", "ചിങ്ങം", "കന്നി",
    "തുലാം", "വൃശ്ചികം", "ധനു", "മകരം", "കുംഭം", "മീനം",
  ];

  // South Indian chart is a FIXED grid: each rasi always sits in the same cell.
  // Map rasi_index (0 = മേടം) → [row, col] in the 4×4 frame (1-based).
  const SI_POS = {
    11: [1, 1], 0: [1, 2], 1: [1, 3], 2: [1, 4],
    10: [2, 1],                        3: [2, 4],
    9:  [3, 1],                        4: [3, 4],
    8:  [4, 1], 7: [4, 2], 6: [4, 3],  5: [4, 4],
  };

  // Navagraha: short label, full Malayalam name, accent color.
  const GRAHAS = {
    surya:   { s: "സൂ",  full: "സൂര്യൻ",  c: "#f2a24e" },
    chandra: { s: "ച",   full: "ചന്ദ്രൻ",  c: "#d8dcf5" },
    chevvai: { s: "ചൊ",  full: "ചൊവ്വ",   c: "#f07168" },
    budhan:  { s: "ബു",  full: "ബുധൻ",    c: "#6fd8a8" },
    guru:    { s: "വ്യാ", full: "വ്യാഴം",   c: "#f2d24e" },
    shukran: { s: "ശു",  full: "ശുക്രൻ",   c: "#e88fd8" },
    shani:   { s: "ശ",   full: "ശനി",     c: "#7f9df0" },
    rahu:    { s: "രാ",  full: "രാഹു",    c: "#a78bfa" },
    ketu:    { s: "കേ",  full: "കേതു",    c: "#c8a878" },
  };

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  const rasiIndexOf = (p) =>
    typeof p.rasi_index === "number" ? p.rasi_index : RASIS.indexOf(p.rasi);

  // ---- one South Indian grid. planets: {id:{rasi, rasi_index?, retrograde?}} ----
  function siGrid(planets, lagnamName, centerLabel, centerSub) {
    const lagnaIdx = RASIS.indexOf(lagnamName);
    const byRasi = Array.from({ length: 12 }, () => []);
    Object.entries(planets || {}).forEach(([id, p]) => {
      const idx = rasiIndexOf(p);
      if (idx >= 0) byRasi[idx].push({ id, ...p });
    });

    let cells = "";
    for (let idx = 0; idx < 12; idx++) {
      const [r, c] = SI_POS[idx];
      const chips = byRasi[idx]
        .map((p) => {
          const g = GRAHAS[p.id] || { s: p.id.slice(0, 2), full: p.id, c: "#9a96c8" };
          const deg = typeof p.degree === "number" ? ` ${p.degree.toFixed(1)}°` : "";
          return `<span class="si-planet${p.retrograde ? " retro" : ""}"
            style="--p-color:${g.c}" title="${esc(g.full)}${deg}${p.nakshatra ? " · " + esc(p.nakshatra) : ""}">${g.s}</span>`;
        })
        .join("");
      cells += `<div class="si-cell${idx === lagnaIdx ? " lagna" : ""}"
        style="grid-area:${r} / ${c}">
        <span class="si-rasi-name">${RASIS[idx]}</span>
        <span class="si-planets">${chips}</span>
      </div>`;
    }
    return `<div class="si-chart">
      ${cells}
      <div class="si-center">
        <span class="om">🕉</span>
        <span class="label">${esc(centerLabel)}</span>
        ${centerSub ? `<span class="sub">${esc(centerSub)}</span>` : ""}
      </div>
    </div>`;
  }

  // ---- dasha timeline: mahadashas with the running one highlighted ----
  function dashaSection(dasha) {
    if (!dasha || !Array.isArray(dasha.mahadashas) || !dasha.mahadashas.length) return "";
    const now = Date.now();
    // dasha.current may be the period itself or {as_of, mahadasha, antardasha}.
    const cur = dasha.current && (dasha.current.mahadasha || dasha.current);
    const fmt = (iso) => {
      const d = new Date(iso);
      return isNaN(d) ? "" : d.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
    };
    const rows = dasha.mahadashas
      .map((m) => {
        const g = GRAHAS[m.lord] || { full: m.lord, c: "#9a96c8" };
        const start = new Date(m.start).getTime();
        const end = new Date(m.end).getTime();
        const isCur = cur ? m.lord === cur.lord && m.start === cur.start
                          : start <= now && now < end;
        const pct = isCur && end > start
          ? Math.max(2, Math.min(100, ((now - start) / (end - start)) * 100)) : 0;
        return `<div class="dasha-item${isCur ? " current" : ""}">
          <span class="lord" style="--p-color:${g.c}">${esc(g.full)}</span>
          <span class="span">${fmt(m.start)} → ${fmt(m.end)}</span>
          <span class="years">${Number(m.years).toFixed(1)}y</span>
          ${isCur ? `<span class="dasha-now-chip">ഇപ്പോൾ</span>
                     <span class="dasha-progress" style="width:${pct}%"></span>` : ""}
        </div>`;
      })
      .join("");
    return `<section class="drawer-sec"><h4>വിംശോത്തരി ദശ</h4>
      <div class="dasha-list">${rows}</div></section>`;
  }

  // ---- doshas: computed facts → present / absent cards ----
  function doshaSection(doshas) {
    if (!doshas || typeof doshas !== "object") return "";
    const NAMES = {
      chovva_dosha: ["🔴", "ചൊവ്വാ ദോഷം"],
      kala_sarpa_dosha: ["🐍", "കാളസർപ്പ ദോഷം"],
    };
    const cards = Object.entries(doshas)
      .filter(([, d]) => d && d.computed !== false)
      .map(([key, d]) => {
        const [ico, name] = NAMES[key] || ["✴️", key.replace(/_/g, " ")];
        return `<div class="dosha-card">
          <span>${ico}</span><span class="name">${esc(name)}</span>
          <span class="dosha-state ${d.present ? "present" : "absent"}">
            ${d.present ? "ഉണ്ട്" : "ഇല്ല"}
          </span>
        </div>`;
      })
      .join("");
    if (!cards) return "";
    return `<section class="drawer-sec"><h4>ദോഷ പരിശോധന</h4>
      <div class="dosha-grid">${cards}</div>
      <p class="muted" style="font-size:11.5px;margin-top:8px">
        ദോഷം ഉണ്ടെങ്കിലും പരിഹാരങ്ങളുണ്ട് — താരയോട് ചോദിക്കൂ 🙏</p></section>`;
  }

  // ---- planet detail table ----
  function planetTable(planets) {
    const rows = Object.entries(planets || {})
      .map(([id, p]) => {
        const g = GRAHAS[id] || { full: id, c: "#9a96c8" };
        return `<tr>
          <td class="grah" style="--p-color:${g.c}">${esc(g.full)}</td>
          <td>${esc(p.rasi || "—")}</td>
          <td>${typeof p.degree === "number" ? p.degree.toFixed(2) + "°" : "—"}</td>
          <td>${esc(p.nakshatra || "—")}${p.pada ? `<span class="muted">·${p.pada}</span>` : ""}</td>
          <td>${p.house ?? "—"}</td>
          <td>${p.retrograde ? '<span class="retro-flag">വക്രം ℞</span>' : ""}</td>
        </tr>`;
      })
      .join("");
    if (!rows) return "";
    return `<section class="drawer-sec"><h4>ഗ്രഹനില വിശദമായി</h4>
      <div style="overflow-x:auto"><table class="planet-table">
        <thead><tr><th>ഗ്രഹം</th><th>രാശി</th><th>ഡിഗ്രി</th><th>നക്ഷത്രം</th><th>ഭാവം</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`;
  }

  function render(natal, user) {
    if (!natal || !natal.planets) {
      return `<div class="muted" style="text-align:center;padding:40px 12px">
        ജാതകം ഇതുവരെ തയ്യാറായിട്ടില്ല.<br/>അല്പസമയത്തിനു ശേഷം വീണ്ടും നോക്കൂ 🙏</div>`;
    }

    // birth summary tiles: janma rasi (moon), nakshatram, lagnam
    const tiles = `<section class="drawer-sec">
      <div class="birth-tiles">
        <div class="birth-tile"><div class="k">നക്ഷത്രം</div>
          <div class="v">${esc(natal.nakshatram || "—")}${natal.nakshatra_pada ? `<span class="muted" style="font-size:11px"> · പാദം ${natal.nakshatra_pada}</span>` : ""}</div></div>
        <div class="birth-tile"><div class="k">ജന്മരാശി</div>
          <div class="v">${esc(natal.rasi || "—")}</div></div>
        <div class="birth-tile"><div class="k">ലഗ്നം</div>
          <div class="v">${esc(natal.lagnam || "—")}</div></div>
      </div>
      ${natal.birth_time_known === false
        ? '<p class="muted" style="font-size:11.5px;margin-top:8px">⏱ ജനന സമയം അറിയാത്തതിനാൽ ലഗ്നം ഏകദേശമാണ്</p>' : ""}
    </section>`;

    // D1 + optional vargas (D9 first): toggle re-renders the grid in place
    const vargas = natal.vargas || {};
    const vargaKeys = Object.keys(vargas);
    const toggles = ["D1", ...vargaKeys]
      .map((k, i) => `<button data-varga="${k}" class="${i === 0 ? "active" : ""}">${k === "D1" ? "D1 · രാശി" : `${k} · ${esc((vargas[k] && vargas[k].varga) || "")}`}</button>`)
      .join("");
    const chartSec = `<section class="drawer-sec"><h4>ഗ്രഹനില ചക്രം</h4>
      <div class="si-wrap">
        ${vargaKeys.length ? `<div class="si-toggle" id="varga-toggle">${toggles}</div>` : ""}
        <div id="si-holder">${siGrid(natal.planets, natal.lagnam,
          user && user.name ? user.name : "ജാതകം",
          natal.source === "swiss-ephemeris" ? "Swiss Ephemeris · Lahiri" : "")}</div>
      </div></section>`;

    return tiles + chartSec + dashaSection(natal.dasha)
      + doshaSection(natal.doshas) + planetTable(natal.planets);
  }

  // After injecting render()'s HTML, call bind(container, natal, user) to make
  // the D1/varga toggle live.
  function bind(container, natal, user) {
    const toggle = container.querySelector("#varga-toggle");
    const holder = container.querySelector("#si-holder");
    if (!toggle || !holder) return;
    toggle.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-varga]");
      if (!btn) return;
      toggle.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
      const key = btn.dataset.varga;
      if (key === "D1") {
        holder.innerHTML = siGrid(natal.planets, natal.lagnam,
          user && user.name ? user.name : "ജാതകം",
          natal.source === "swiss-ephemeris" ? "Swiss Ephemeris · Lahiri" : "");
      } else {
        const v = natal.vargas[key] || {};
        holder.innerHTML = siGrid(v.planets || {}, v.lagnam || "",
          `${key} · ${v.varga || ""}`, v.signifies || "");
      }
    });
  }

  window.TaraChart = { render, bind };
})();
