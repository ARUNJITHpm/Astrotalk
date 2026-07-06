// TARA UI — shared motion layer: starfield canvas, custom cursor,
// magnetic buttons, staggered reveals. Respects prefers-reduced-motion.
(() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- starfield: slow parallax drift + rare shooting stars ----------
  const canvas = document.getElementById("starfield");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    let W, H, stars = [], shooting = null;
    let mx = 0.5, my = 0.5; // normalized mouse for parallax

    const resize = () => {
      W = canvas.width = window.innerWidth * devicePixelRatio;
      H = canvas.height = window.innerHeight * devicePixelRatio;
      const n = Math.min(260, Math.floor((window.innerWidth * window.innerHeight) / 6000));
      stars = Array.from({ length: n }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        z: Math.random(), // depth: parallax + size + brightness
        tw: Math.random() * Math.PI * 2, // twinkle phase
        gold: Math.random() < 0.12,
      }));
    };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", (e) => {
      mx = e.clientX / window.innerWidth;
      my = e.clientY / window.innerHeight;
    });

    let t = 0;
    const frame = () => {
      t += 0.016;
      ctx.clearRect(0, 0, W, H);
      const px = (mx - 0.5) * 30 * devicePixelRatio;
      const py = (my - 0.5) * 30 * devicePixelRatio;
      for (const s of stars) {
        const tw = reduced ? 1 : 0.55 + 0.45 * Math.sin(s.tw + t * (0.6 + s.z));
        const r = (0.4 + s.z * 1.3) * devicePixelRatio;
        const x = (s.x + px * s.z + W) % W;
        const y = (s.y + py * s.z + (reduced ? 0 : t * 2 * s.z * devicePixelRatio) + H) % H;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = s.gold
          ? `rgba(233,185,104,${0.5 * tw})`
          : `rgba(210,205,255,${0.42 * tw})`;
        ctx.fill();
      }
      // shooting star: spawn rarely, streak diagonally with a fading tail
      if (!reduced) {
        if (!shooting && Math.random() < 0.0035) {
          shooting = { x: Math.random() * W * 0.7, y: Math.random() * H * 0.3, life: 1 };
        }
        if (shooting) {
          shooting.x += 14 * devicePixelRatio;
          shooting.y += 6 * devicePixelRatio;
          shooting.life -= 0.02;
          const g = ctx.createLinearGradient(
            shooting.x, shooting.y,
            shooting.x - 90 * devicePixelRatio, shooting.y - 38 * devicePixelRatio
          );
          g.addColorStop(0, `rgba(244,217,166,${0.85 * shooting.life})`);
          g.addColorStop(1, "transparent");
          ctx.strokeStyle = g;
          ctx.lineWidth = 1.6 * devicePixelRatio;
          ctx.beginPath();
          ctx.moveTo(shooting.x, shooting.y);
          ctx.lineTo(shooting.x - 90 * devicePixelRatio, shooting.y - 38 * devicePixelRatio);
          ctx.stroke();
          if (shooting.life <= 0) shooting = null;
        }
      }
      requestAnimationFrame(frame);
    };
    if (reduced) {
      // one static render — no animation loop
      t = 1; const px = 0, py = 0;
      for (const s of stars) {
        ctx.beginPath();
        ctx.arc(s.x, s.y, (0.4 + s.z * 1.3) * devicePixelRatio, 0, Math.PI * 2);
        ctx.fillStyle = s.gold ? "rgba(233,185,104,0.5)" : "rgba(210,205,255,0.4)";
        ctx.fill();
      }
    } else {
      requestAnimationFrame(frame);
    }
  }

  // ---------- custom cursor: dot follows instantly, ring eases behind ----------
  const dot = document.getElementById("cursor-dot");
  const ring = document.getElementById("cursor-ring");
  if (dot && ring && matchMedia("(pointer: fine)").matches && !reduced) {
    let x = -100, y = -100, rx = -100, ry = -100;
    window.addEventListener("mousemove", (e) => { x = e.clientX; y = e.clientY; });
    const loop = () => {
      rx += (x - rx) * 0.16;
      ry += (y - ry) * 0.16;
      dot.style.transform = `translate(${x}px,${y}px) translate(-50%,-50%)`;
      ring.style.transform = `translate(${rx}px,${ry}px) translate(-50%,-50%)`;
      requestAnimationFrame(loop);
    };
    loop();
    // grow the ring over anything interactive
    document.addEventListener("mouseover", (e) => {
      const hit = e.target.closest("button, a, input, textarea, select, .chip, .history-item, .si-cell");
      document.body.classList.toggle("cursor-hover", !!hit);
    });
  }

  // ---------- magnetic buttons: [data-magnetic] leans toward the cursor ----------
  if (!reduced && matchMedia("(pointer: fine)").matches) {
    document.querySelectorAll("[data-magnetic]").forEach((el) => {
      const strength = 0.32;
      el.addEventListener("mousemove", (e) => {
        const r = el.getBoundingClientRect();
        const dx = e.clientX - (r.left + r.width / 2);
        const dy = e.clientY - (r.top + r.height / 2);
        el.style.transform = `translate(${dx * strength}px, ${dy * strength}px)`;
      });
      el.addEventListener("mouseleave", () => {
        el.style.transition = "transform 0.5s cubic-bezier(0.34,1.56,0.64,1)";
        el.style.transform = "";
        setTimeout(() => (el.style.transition = ""), 500);
      });
    });
  }

  // ---------- reveals: [data-reveal] fades up on load / when scrolled into view ----------
  const revealables = [...document.querySelectorAll("[data-reveal]")];
  revealables.forEach((el, i) => {
    if (!el.style.getPropertyValue("--reveal-delay")) {
      el.style.setProperty("--reveal-delay", `${Math.min(i * 0.09, 0.7)}s`);
    }
  });
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((en) => {
        if (en.isIntersecting) { en.target.classList.add("revealed"); io.unobserve(en.target); }
      }),
      { threshold: 0.12 }
    );
    revealables.forEach((el) => io.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add("revealed"));
  }
})();
