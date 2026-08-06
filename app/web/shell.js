// Shared back-button wiring for the hand-written pages.
//
// Include on a page:
//   <script src="/static/shell.js" data-nav="off"></script>
//
// Any element with [data-back] becomes a back button. Its value is the fallback
// destination for when there is no history to pop (the page was opened from a
// link or a bookmark) — default "/".
//
// This file used to also render a bottom nav and reveal admin-only links.
// Console plan Part 14 deleted admin.html and console.html, which were the only
// two pages that passed a `data-nav` key, so both were dead: the one page left
// (`ui/chat.html`, the white-label surface the orgs module serves at
// /a/{handle}/ui) passes `data-nav="off"` and carries its own nav and its own
// admin reveal. `data-nav` is still read so an old include does not throw, and
// still means nothing but "off".
(() => {
  // Self-contained styling: the pages that include this have unrelated palettes,
  // so the button borrows the page's own colours via currentColor and a
  // translucent backdrop rather than importing any stylesheet.
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
  `;

  function injectStyle() {
    const el = document.createElement("style");
    el.textContent = CSS;
    document.head.appendChild(el);
  }

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

  function start() {
    injectStyle();
    bindBack();
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", start);
  else start();
})();
