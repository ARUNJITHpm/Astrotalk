// Tara motion layer — GSAP-driven polish over the chat UI.
// Non-invasive: hooks into the DOM via MutationObservers so app.js stays
// focused on chat logic. Everything here degrades to the static UI if GSAP
// fails to load or the user prefers reduced motion.
(() => {
  if (!window.gsap) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion) return;

  const gsap = window.gsap;
  const chat = document.querySelector(".chat");
  const messagesEl = document.getElementById("messages");
  const sidebar = document.querySelector(".sidebar");
  const historyEl = document.getElementById("history");
  const profileModal = document.getElementById("profile-modal");
  const debugDrawer = document.getElementById("debug-drawer");
  const composerForm = document.getElementById("composer-form");
  const sendBtn = document.getElementById("send");

  /* ---------- Ambient cosmos: a soft drifting starfield behind the chat ---------- */
  function buildCosmos() {
    if (!chat) return;
    const layer = document.createElement("div");
    layer.className = "cosmos";
    layer.setAttribute("aria-hidden", "true");
    chat.prepend(layer);

    const COUNT = 26;
    for (let i = 0; i < COUNT; i++) {
      const s = document.createElement("span");
      s.className = "cosmos-star";
      const size = gsap.utils.random(1.5, 3.2);
      gsap.set(s, {
        width: size,
        height: size,
        left: gsap.utils.random(0, 100) + "%",
        top: gsap.utils.random(0, 100) + "%",
        opacity: gsap.utils.random(0.05, 0.35),
      });
      layer.appendChild(s);
      // Twinkle: each star breathes on its own rhythm.
      gsap.to(s, {
        opacity: gsap.utils.random(0.35, 0.7),
        duration: gsap.utils.random(1.6, 4),
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        delay: gsap.utils.random(0, 3),
      });
      // Slow vertical drift, wrapping around.
      gsap.to(s, {
        y: gsap.utils.random(-60, -140),
        duration: gsap.utils.random(30, 70),
        repeat: -1,
        yoyo: true,
        ease: "none",
      });
    }

    // A couple of faint accent glyphs floating in the depth.
    ["✦", "✧", "✦"].forEach(() => {
      const g = document.createElement("span");
      g.className = "cosmos-glyph";
      g.textContent = Math.random() > 0.5 ? "✦" : "✧";
      gsap.set(g, {
        left: gsap.utils.random(5, 92) + "%",
        top: gsap.utils.random(8, 88) + "%",
        fontSize: gsap.utils.random(10, 18),
        opacity: gsap.utils.random(0.04, 0.1),
        rotation: gsap.utils.random(-30, 30),
      });
      layer.appendChild(g);
      gsap.to(g, {
        y: gsap.utils.random(-40, 40),
        rotation: "+=" + gsap.utils.random(-40, 40),
        duration: gsap.utils.random(24, 48),
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
      });
    });
  }

  /* ---------- Page-load intro ---------- */
  function intro() {
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    if (sidebar) {
      tl.from(sidebar, { x: -48, autoAlpha: 0, duration: 0.6, clearProps: "all" });
      tl.from(
        sidebar.querySelectorAll(".brand, .new-chat, .side-section-title, .sidebar-foot"),
        { x: -18, autoAlpha: 0, duration: 0.45, stagger: 0.06 },
        "-=0.3"
      );
    }
    tl.from(".chat-head", { y: -18, autoAlpha: 0, duration: 0.5 }, "-=0.35");
    tl.from(".composer", { y: 24, autoAlpha: 0, duration: 0.5 }, "-=0.3");

    // The brand star slowly spins forever, with a gentle pulse.
    const brandStar = document.querySelector(".brand-star");
    if (brandStar) {
      gsap.set(brandStar, { display: "inline-block", transformOrigin: "50% 50%" });
      gsap.to(brandStar, { rotation: 360, duration: 60, repeat: -1, ease: "none" });
      gsap.to(brandStar, {
        scale: 1.18,
        duration: 1.8,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
      });
    }
  }

  /* ---------- Welcome splash: choreographed entrance (re-runs on new chat) ---------- */
  function animateWelcome(welcome) {
    const star = welcome.querySelector(".welcome-star");
    const h1 = welcome.querySelector("h1");
    const p = welcome.querySelector("p");
    const chips = welcome.querySelectorAll(".chip");

    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    if (star) {
      gsap.set(star, { display: "inline-block", transformOrigin: "50% 50%" });
      tl.from(star, {
        scale: 0,
        rotation: -180,
        autoAlpha: 0,
        duration: 0.9,
        ease: "elastic.out(1, 0.55)",
      });
      // Keep it floating gently afterwards.
      gsap.to(star, {
        y: -7,
        duration: 2.2,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        delay: 1,
      });
    }
    if (h1) tl.from(h1, { y: 26, autoAlpha: 0, duration: 0.55 }, "-=0.55");
    if (p) tl.from(p, { y: 18, autoAlpha: 0, duration: 0.5 }, "-=0.35");
    if (chips.length)
      tl.from(
        chips,
        { y: 16, autoAlpha: 0, scale: 0.92, duration: 0.45, stagger: 0.08, ease: "back.out(1.7)" },
        "-=0.25"
      );
  }

  /* ---------- Message rows: slide up as they land ---------- */
  function animateRow(row, index) {
    const delay = Math.min(index * 0.05, 0.5);
    gsap.from(row, { y: 18, autoAlpha: 0, duration: 0.45, ease: "power2.out", delay });
    const avatar = row.querySelector(".avatar");
    if (avatar)
      gsap.from(avatar, {
        scale: 0.4,
        duration: 0.5,
        ease: "back.out(2)",
        delay: delay + 0.05,
      });
  }

  if (messagesEl) {
    // Animate whatever app.js drops into #messages: welcome splashes and rows.
    new MutationObserver((mutations) => {
      let rowIndex = 0;
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType !== 1) continue;
          if (node.classList.contains("welcome")) animateWelcome(node);
          else if (node.classList.contains("row")) animateRow(node, rowIndex++);
        }
      }
    }).observe(messagesEl, { childList: true });
    // The initial server-rendered welcome is already in the DOM.
    const initial = messagesEl.querySelector(".welcome");
    if (initial) animateWelcome(initial);
  }

  /* ---------- Sidebar history: items cascade in on the FIRST load only ----------
     (the sidebar rebuilds after every turn; re-animating it each time smeared
     the items over each other) */
  if (historyEl) {
    let pending = [];
    let scheduled = false;
    let introDone = false;
    new MutationObserver((mutations) => {
      if (introDone) return;
      for (const m of mutations)
        for (const node of m.addedNodes)
          if (node.nodeType === 1 && node.classList.contains("history-item")) pending.push(node);
      if (pending.length && !scheduled) {
        introDone = true;
        scheduled = true;
        requestAnimationFrame(() => {
          gsap.from(pending, {
            x: -14,
            autoAlpha: 0,
            duration: 0.35,
            stagger: 0.04,
            ease: "power2.out",
            clearProps: "all",
          });
          pending = [];
          scheduled = false;
        });
      }
    }).observe(historyEl, { childList: true });
  }

  /* ---------- Profile modal: backdrop fade + card pop on open ---------- */
  if (profileModal) {
    new MutationObserver(() => {
      if (profileModal.hidden) return;
      const card = profileModal.querySelector(".modal-card");
      gsap.fromTo(profileModal, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.25, ease: "power1.out" });
      if (card)
        gsap.fromTo(
          card,
          { y: 26, scale: 0.92, autoAlpha: 0 },
          { y: 0, scale: 1, autoAlpha: 1, duration: 0.45, ease: "back.out(1.6)" }
        );
    }).observe(profileModal, { attributes: true, attributeFilter: ["hidden"] });
  }

  /* ---------- Debug drawer: slides in from the right ---------- */
  if (debugDrawer) {
    new MutationObserver(() => {
      if (debugDrawer.hidden) return;
      gsap.fromTo(
        debugDrawer,
        { x: "100%" },
        { x: "0%", duration: 0.45, ease: "power3.out", clearProps: "transform" }
      );
    }).observe(debugDrawer, { attributes: true, attributeFilter: ["hidden"] });
  }

  /* ---------- Micro-interactions ---------- */
  if (composerForm && sendBtn) {
    composerForm.addEventListener("submit", () => {
      gsap.fromTo(
        sendBtn,
        { scale: 0.75 },
        { scale: 1, duration: 0.55, ease: "elastic.out(1, 0.45)" }
      );
    });
  }
  // Suggestion chips get a springy hover lift.
  document.addEventListener("mouseover", (e) => {
    if (e.target.classList && e.target.classList.contains("chip"))
      gsap.to(e.target, { scale: 1.05, y: -2, duration: 0.25, ease: "power2.out" });
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.classList && e.target.classList.contains("chip"))
      gsap.to(e.target, { scale: 1, y: 0, duration: 0.3, ease: "power2.out" });
  });

  buildCosmos();
  intro();
})();
