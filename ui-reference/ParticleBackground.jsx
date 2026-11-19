import { useEffect, useRef } from "react";

function startParticles(canvas, { spacing = 30, radius = 260 } = {}) {
  const ctx = canvas.getContext("2d");
  const COLORS = ["#A879E5", "#7540C5", "#C5A6F2", "#35145D"];
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const m = { x: 0, y: 0, sx: 0, sy: 0, active: false, last: 0 };
  let w = 0, h = 0, dots = [], raf = 0;

  function build() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth; h = canvas.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    dots = [];
    for (let y = -spacing; y < h + spacing; y += spacing)
      for (let x = -spacing; x < w + spacing; x += spacing)
        dots.push({
          bx: x + (Math.random() - 0.5) * spacing,
          by: y + (Math.random() - 0.5) * spacing,
          z: Math.random(), ox: 0, oy: 0, vx: 0, vy: 0,
          c: COLORS[Math.floor(Math.random() ** 2 * COLORS.length)],
        });
    if (!m.active) { m.x = m.sx = w / 2; m.y = m.sy = h / 2; }
    if (reduce) frame(0);
  }
  function move(e) {
    const p = e.touches ? e.touches[0] : e;
    const r = canvas.getBoundingClientRect();
    m.x = p.clientX - r.left; m.y = p.clientY - r.top;
    m.active = true; m.last = performance.now();
  }
  function frame(t) {
    ctx.clearRect(0, 0, w, h);
    if (!reduce && (!m.active || t - m.last > 4000)) {
      m.x = w * (0.5 + 0.28 * Math.sin(t / 2600));
      m.y = h * (0.45 + 0.22 * Math.cos(t / 3300));
    }
    m.sx += (m.x - m.sx) * 0.1; m.sy += (m.y - m.sy) * 0.1;
    const px = m.sx / w - 0.5, py = m.sy / h - 0.5;
    ctx.lineCap = "round";
    for (const d of dots) {
      const depth = 0.35 + d.z * 0.9;                 // fake z-depth
      const x = d.bx + d.ox - px * 46 * depth;        // parallax
      const y = d.by + d.oy - py * 46 * depth;
      const dx = x - m.sx, dy = y - m.sy, dist = Math.hypot(dx, dy) || 1;
      let f = 0;
      if (dist < radius) {
        f = (1 - dist / radius) ** 2;
        d.vx += (dx / dist) * f * 1.4; d.vy += (dy / dist) * f * 1.4;
      }
      d.vx = (d.vx - d.ox * 0.045) * 0.86; d.vy = (d.vy - d.oy * 0.045) * 0.86;
      d.ox += d.vx; d.oy += d.vy;
      const a = Math.atan2(dy, dx) + Math.sin(t / 1200 + d.bx * 0.01) * 0.25;
      const len = 3 + depth * 4 + f * 14;
      const cx = (Math.cos(a) * len) / 2, cy = (Math.sin(a) * len) / 2;
      ctx.globalAlpha = Math.min(1, 0.22 + d.z * 0.45 + f * 0.5);
      ctx.strokeStyle = d.c; ctx.lineWidth = 1 + depth * 1.2 + f * 1.2;
      ctx.beginPath(); ctx.moveTo(x - cx, y - cy); ctx.lineTo(x + cx, y + cy); ctx.stroke();
    }
    if (!reduce) raf = requestAnimationFrame(frame);
  }
  function onVis() { cancelAnimationFrame(raf); if (!document.hidden && !reduce) raf = requestAnimationFrame(frame); }

  build();
  if (!reduce) raf = requestAnimationFrame(frame);
  window.addEventListener("resize", build);
  window.addEventListener("pointermove", move, { passive: true });
  window.addEventListener("touchmove", move, { passive: true });
  document.addEventListener("visibilitychange", onVis);
  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("resize", build);
    window.removeEventListener("pointermove", move);
    window.removeEventListener("touchmove", move);
    document.removeEventListener("visibilitychange", onVis);
  };
}
function startGlassGlow() {
  const h = (e) => {
    const c = e.target.closest && e.target.closest(".glass");
    if (!c) return;
    const r = c.getBoundingClientRect();
    c.style.setProperty("--mx", e.clientX - r.left + "px");
    c.style.setProperty("--my", e.clientY - r.top + "px");
  };
  document.addEventListener("pointermove", h, { passive: true });
  return () => document.removeEventListener("pointermove", h);
}

export default function ParticleBackground({ spacing = 30, radius = 260 }) {
  const ref = useRef(null);
  useEffect(() => {
    const stopA = startParticles(ref.current, { spacing, radius });
    const stopB = startGlassGlow();
    return () => { stopA(); stopB(); };
  }, [spacing, radius]);
  return <canvas ref={ref} className="s2r-bg" aria-hidden="true" />;
}