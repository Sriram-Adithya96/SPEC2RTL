import { useEffect, useRef } from "react";

export default function BinaryBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return undefined;
    const x = c.getContext("2d");
    if (!x) return undefined;

    const S = 20;
    const R = 150;
    let cols = 0;
    let rows = 0;
    let cells = [];
    let W = 0;
    let H = 0;
    let mx = -999;
    let my = -999;
    let rafId = 0;

    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function init() {
      const d = window.devicePixelRatio || 1;
      W = window.innerWidth;
      H = window.innerHeight;
      c.width = W * d;
      c.height = H * d;
      x.setTransform(d, 0, 0, d, 0, 0);

      cols = Math.ceil(W / S);
      rows = Math.ceil(H / S);
      cells = [];
      for (let i = 0; i < cols * rows; i++) {
        cells.push({ v: Math.random() < 0.5 ? 0 : 1, e: 0 });
      }
      x.font = '600 14px "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace';
      x.textAlign = "center";
      x.textBaseline = "middle";
      draw();
    }

    function draw() {
      x.clearRect(0, 0, W, H);
      for (let r = 0; r < rows; r++) {
        for (let q = 0; q < cols; q++) {
          const k = cells[r * cols + q];
          if (!k) continue;
          const px = q * S + S / 2;
          const py = r * S + S / 2;
          const dx = px - mx;
          const dy = py - my;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < R) {
            const t = 1 - dist / R;
            if (Math.random() < t * 0.35) k.v = 1 - k.v;
            k.e = Math.max(k.e, t);
          } else if (Math.random() < 0.0008) {
            k.v = 1 - k.v;
          }

          const a = 0.06 + k.e * 0.85;
          if (k.e > 0.02) {
            x.fillStyle = "rgba(125,211,252," + a + ")";
          } else {
            x.fillStyle = "rgba(125,211,252,.06)";
          }
          if (k.e > 0.55) {
            x.fillStyle = "rgba(190,170,255," + a + ")";
          }
          x.fillText(k.v, px, py);
          k.e *= 0.93;
        }
      }
    }

    function loop() {
      draw();
      rafId = requestAnimationFrame(loop);
    }

    function handlePointerMove(e) {
      mx = e.clientX;
      my = e.clientY;
    }

    function handlePointerLeave() {
      mx = -999;
      my = -999;
    }

    function handleResize() {
      init();
    }

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerleave", handlePointerLeave, { passive: true });
    window.addEventListener("resize", handleResize, { passive: true });

    init();
    if (!still) {
      loop();
    }

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerleave", handlePointerLeave);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      id="bg"
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        width: "100%",
        height: "100%",
        zIndex: 0,
        pointerEvents: "none",
      }}
    />
  );
}
