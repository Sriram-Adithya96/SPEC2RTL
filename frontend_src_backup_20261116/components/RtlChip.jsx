import { useEffect, useRef } from "react";

const POS = [47, 62, 77, 92, 107, 122, 137, 152]; // 8 pins per side

export default function RtlChip({ size = 180 }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const onMove = (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const dx = (e.clientX - (r.left + r.width / 2)) / window.innerWidth;
        const dy = (e.clientY - (r.top + r.height / 2)) / window.innerHeight;
        el.style.transform = `perspective(600px) rotateX(${-dy * 24}deg) rotateY(${dx * 30}deg)`;
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      style={{
        width: size, height: size,
        transition: "transform .15s ease-out",
        filter: "drop-shadow(0 18px 26px rgba(117,64,197,.40))",
      }}
    >
      <svg viewBox="0 0 200 200" width="100%" height="100%">
        <defs>
          <linearGradient id="chipBody" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#A879E5" />
            <stop offset="1" stopColor="#35145D" />
          </linearGradient>
          <linearGradient id="chipPin" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#DCCBFA" />
            <stop offset="1" stopColor="#A879E5" />
          </linearGradient>
        </defs>

        {POS.map((p) => (
          <g key={p} fill="url(#chipPin)">
            <rect x={p - 3} y="22" width="6" height="18" rx="2" />
            <rect x={p - 3} y="160" width="6" height="18" rx="2" />
            <rect x="22" y={p - 3} width="18" height="6" rx="2" />
            <rect x="160" y={p - 3} width="18" height="6" rx="2" />
          </g>
        ))}

        <rect x="40" y="40" width="120" height="120" rx="20"
              fill="url(#chipBody)" stroke="rgba(255,255,255,.35)" />
        <rect x="64" y="64" width="72" height="72" rx="12"
              fill="rgba(255,255,255,.14)" stroke="rgba(255,255,255,.45)" />
        <text x="100" y="108" textAnchor="middle" fill="#fff" fontSize="21" fontWeight="700"
              fontFamily="'JetBrains Mono', ui-monospace, monospace">RTL</text>

        <circle cx="52" cy="52" r="3" fill="rgba(255,255,255,.7)" />
        <circle cx="148" cy="52" r="4" fill="#C8F52F" />
      </svg>
    </div>
  );
}