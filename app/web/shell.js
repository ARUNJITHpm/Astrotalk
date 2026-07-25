// Shared app shell — the back button and the mobile bottom nav.
//
// Include on every page:
//   <script src="/static/shell.js" data-nav="admin"></script>
//
// data-nav is the key of the current section, which marks that item active and
// injects the bottom nav. Pages that already carry their own <nav> markup
// (chat, feed, astrologers) pass data-nav="off": they only get the back-button
// wiring, so the bar is never rendered twice.
//
// Any element with [data-back] becomes a back button. Its value is the fallback
// destination for when there is no history to pop (the page was opened from a
// link or a bookmark) — default "/".
(() => {
  const script =
    document.currentScript || document.querySelector('script[src*="shell.js"]');
  const navKey = (script && script.dataset.nav) || "off";

  // Operator destinations only. This shell now ships on /admin and /console
  // alone: the Tara-era consumer pages it also used to link (the /feed page,
  // the chat at /, /ui/astrologers) were removed when the Nithara app took the
  // root, and / is a React SPA that renders its own tab bar.
  const ITEMS = [
    { key: "admin", href: "/admin", icon: "📊", label: "അഡ്മിൻ", adminOnly: true },
    { key: "console", href: "/console", icon: "🛠️", label: "കൺസോൾ", adminOnly: true },
    { key: "app", href: "/", icon: "🪔", label: "ആപ്പ്" },
  ];

  // Self-contained styling: these pages have unrelated palettes (the chat's
  // warm theme, the console's indigo), so the shell borrows the page's own
  // colours via currentColor and a translucent backdrop rather than importing
  // any stylesheet.
  const CSS = `
    .tara-back {
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(127,127,127,0.12); color: inherit;
      border: 1px solid rgba(127,127,127,0.28); border-radius: 999px;
      padding: 7px 13px 7px 10px; font: inherit; font-size: 13px; font-weight: 600;
      line-height: 1; cursor: pointer; text-decoration: none;
      transition: background 0.15s, transform 0.15s;
    }
    .tara-back:hover { background: rgba(127,127,127,0.22); }
    .tara-back:active { transform: scale(0.96); }
    .tara-back .tara-back-ic { font-size: 15px; line-height: 1; }
    /* The chat header is crowded on a phone (menu, model picker, chart, logout):
       drop to the arrow alone rather than push the title out. */
    @media (max-width: 520px) {
      .tara-back { padding: 7px 10px; }
      .tara-back .tara-back-label { display: none; }
    }

    .tara-shellnav { display: none; }
    @media (max-width: 720px) {
      .tara-shellnav {
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 90;
        display: flex; justify-content: space-around; align-items: stretch;
        height: calc(58px + env(safe-area-inset-bottom, 0px));
        padding-bottom: env(safe-area-inset-bottom, 0px);
        background: rgba(12, 14, 28, 0.96);
        backdrop-filter: blur(12px);
        border-top: 1px solid rgba(255,255,255,0.10);
      }
      .tara-shellnav a {
        flex: 1; display: flex; flex-direction: column;
        align-items: center; justify-content: center; gap: 2px;
        font-size: 11px; font-weight: 600; color: #cfd2e4;
        opacity: .68; text-decoration: none;
      }
      .tara-shellnav a .ic { font-size: 20px; line-height: 1; }
      .tara-shellnav a.active { opacity: 1; color: #f0b892; }
      /* Keep the fixed bar off the end of the page's own content. */
      body.tara-has-shellnav { padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px)); }
    }
    .tara-shellnav a.admin-hidden { display: none; }
  `;

  function injectStyle() {
    const el = document.createElement("style");
    el.textContent = CSS;
    document.head.appendChild(el);
  }

  // ---- Back button ----
  // history.back() keeps the user's real trail (e.g. feed → astrologer → back).
  // Landing straight on the page leaves nothing to pop, so fall back to a link.
  function bindBack() {
    document.querySelectorAll("[data-back]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        const fallback = el.getAttribute("data-back") || "/";
        if (window.history.length > 1) window.history.back();
        else window.location.href = fallback;
      });
    });
  }

  // ---- Bottom nav ----
  function buildNav() {
    if (navKey === "off") return null;
    const nav = document.createElement("nav");
    nav.className = "tara-shellnav";
    nav.setAttribute("aria-label", "വിഭാഗങ്ങൾ");
    nav.innerHTML = ITEMS.map((it) => {
      const cls = [
        it.key === navKey ? "active" : "",
        it.adminOnly ? "admin-only admin-hidden" : "",
      ].join(" ").trim();
      return `<a href="${it.href}"${cls ? ` class="${cls}"` : ""}
        ><span class="ic" aria-hidden="true">${it.icon}</span>${it.label}</a>`;
    }).join("");
    document.body.appendChild(nav);
    document.body.classList.add("tara-has-shellnav");
    return nav;
  }

  // ---- Admin reveal ----
  // Show the admin/console links from the cached flag first so they don't flash
  // in late, then confirm with the server (the cache is only a hint; the API
  // enforces the real check).
  function applyAdmin(on) {
    document
      .querySelectorAll(".admin-only")
      .forEach((el) => el.classList.toggle("admin-hidden", !on));
  }

  function revealAdmin() {
    applyAdmin(localStorage.getItem("tara_is_admin") === "1");
    const token = localStorage.getItem("tara_token");
    if (!token) return;
    fetch("/identity/me", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((p) => {
        if (!p) return;
        if (p.is_admin) localStorage.setItem("tara_is_admin", "1");
        else localStorage.removeItem("tara_is_admin");
        applyAdmin(!!p.is_admin);
      })
      .catch(() => {});
  }

  function start() {
    injectStyle();
    bindBack();
    if (buildNav()) revealAdmin();
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", start);
  else start();
})();
