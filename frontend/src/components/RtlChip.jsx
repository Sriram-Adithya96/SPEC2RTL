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
        width: size,
        height: size,
        transition: "transform .15s ease-out",
        filter: "drop-shadow(0 16px 28px rgba(125,211,252,.15))",
      }}
    >
      <svg viewBox="0 0 200 200" width="100%" height="100%">
        <defs>
          <linearGradient id="chipBody" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#1a2332" />
            <stop offset="1" stopColor="#0a0e14" />
          </linearGradient>
          <linearGradient id="chipPin" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#7dd3fc" />
            <stop offset="1" stopColor="#243044" />
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

        <rect
          x="40"
          y="40"
          width="120"
          height="120"
          rx="16"
          fill="url(#chipBody)"
          stroke="#243044"
          strokeWidth="1.5"
        />
        <rect
          x="64"
          y="64"
          width="72"
          height="72"
          rx="10"
          fill="rgba(125,211,252,0.06)"
          stroke="rgba(125,211,252,0.3)"
          strokeWidth="1"
        />
        <text
          x="100"
          y="108"
          textAnchor="middle"
          fill="#d6deeb"
          fontSize="20"
          fontWeight="800"
          fontFamily="'JetBrains Mono', ui-monospace, monospace"
        >
          RTL
        </text>

        <circle cx="52" cy="52" r="3" fill="rgba(125,211,252,0.7)" />
        <circle cx="148" cy="52" r="3.5" fill="#4ade80" />
      </svg>
    </div>
  );
}
