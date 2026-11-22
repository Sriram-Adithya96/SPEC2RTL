import React, { useEffect, useState } from "react";

/**
 * RtlChipHero
 * Polished Inline-SVG hero for the Spec2RTL login page.
 * - 30% larger RTL microchip relative to the motherboard plate.
 * - Board plate with enhanced depth: specular top edge highlight & dark extruded bottom thickness.
 * - Subtle 5% opacity dot-grid matrix on the plate surface.
 * - 1.5x thicker circuit traces with layered cyan glow and animated light pulses.
 * - Pulsing circular solder pads at the plate periphery.
 * - 0s and 1s begin strictly at the chip pin tips (never overlapping the RTL/VERILOG text),
 *   traveling along the traces and softly fading out at the pads (staggered ~8-10 visible).
 * - Full prefers-reduced-motion compliance.
 */

const FONT = "'JetBrains Mono','Fira Code',ui-monospace,monospace";

// 30% larger chip centered on the motherboard plate
const CHIP = { x: 263, y: 142, w: 234, h: 196 };

// Traces begin exactly at the chip pin tips and travel out to the plate edge solder pads.
// bitPath starts ~12px outward along each trace so no digit overlaps a pin or chip edge.
const TRACES = [
  // Left traces (start at left pin tips x=248, bitPath starts at x=236)
  { d: "M248 185 H175 V105", bitPath: "M236 185 H175 V105", dur: 3.4, bits: 2 },
  { d: "M248 240 H80", bitPath: "M236 240 H80", dur: 2.8, bits: 1 },
  { d: "M248 295 H150 V415 H40", bitPath: "M236 295 H150 V415 H40", dur: 4.2, bits: 2 },

  // Right traces (start at right pin tips x=512, bitPath starts at x=524)
  { d: "M512 185 H585 V105", bitPath: "M524 185 H585 V105", dur: 3.4, bits: 2 },
  { d: "M512 240 H680", bitPath: "M524 240 H680", dur: 2.8, bits: 1 },
  { d: "M512 295 H610 V415 H720", bitPath: "M524 295 H610 V415 H720", dur: 4.2, bits: 2 },

  // Bottom traces (start at bottom pin tips y=366, bitPath starts at y=378)
  { d: "M330 366 V425 H240 V482", bitPath: "M330 378 V425 H240 V482", dur: 3.6, bits: 2 },
  { d: "M380 366 V482", bitPath: "M380 378 V482", dur: 2.6, bits: 1 },
  { d: "M430 366 V425 H520 V482", bitPath: "M430 378 V425 H520 V482", dur: 3.6, bits: 2 },

  // Top traces (start at top pin tips y=128, bitPath starts at y=116)
  { d: "M330 128 V105", bitPath: "M330 116 V105", dur: 2.2, bits: 1 },
  { d: "M430 128 V105", bitPath: "M430 116 V105", dur: 2.2, bits: 1 },
];

// Extract end coordinates for solder pads
const ENDS = TRACES.map(({ d }) => {
  let x = 0, y = 0;
  d.split(/(?=[MHV])/).forEach((seg) => {
    const cmd = seg[0];
    const vals = seg.slice(1).trim().split(/\s+/).map(Number);
    if (cmd === "M") { x = vals[0]; y = vals[1]; }
    if (cmd === "H") x = vals[0];
    if (cmd === "V") y = vals[0];
  });
  return { x, y };
});

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

export default function RtlChipHero({ className = "", style }) {
  const reduced = usePrefersReducedMotion();
  const [glowReady, setGlowReady] = useState(reduced);

  useEffect(() => {
    if (reduced) return;
    const t = setTimeout(() => setGlowReady(true), 50);
    return () => clearTimeout(t);
  }, [reduced]);

  // Pins distributed evenly along the larger chip edges
  const topPins = Array.from({ length: 14 }, (_, i) => CHIP.x + 18 + i * 15);
  const bottomPins = Array.from({ length: 14 }, (_, i) => CHIP.x + 18 + i * 15);
  const sidePins = Array.from({ length: 9 }, (_, i) => CHIP.y + 22 + i * 18);

  const glowStyle = reduced
    ? {}
    : {
        transition: "opacity 800ms cubic-bezier(0.16, 1, 0.3, 1)",
        opacity: glowReady ? 1 : 0,
      };

  return (
    <svg
      viewBox="0 0 760 560"
      className={className}
      style={style}
      role="img"
      aria-label="Spec2RTL animated microchip with flowing data traces"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Ambient background glow */}
        <radialGradient id="s2r-glow" cx="50%" cy="46%" r="55%">
          <stop offset="0%" stopColor="#7c6cf5" stopOpacity="0.45" />
          <stop offset="55%" stopColor="#38bdf8" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#060814" stopOpacity="0" />
        </radialGradient>

        {/* Board Plate Linear Gradient */}
        <linearGradient id="s2r-plate" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a1c4e" />
          <stop offset="50%" stopColor="#111335" />
          <stop offset="100%" stopColor="#0b0d24" />
        </linearGradient>

        {/* Plate top edge specular highlight */}
        <linearGradient id="s2r-top-edge" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.3" />
          <stop offset="30%" stopColor="#a5b4fc" stopOpacity="0.9" />
          <stop offset="70%" stopColor="#38bdf8" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0.3" />
        </linearGradient>

        {/* 3D Chip Face Gradients */}
        <linearGradient id="s2r-chip" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#343292" />
          <stop offset="45%" stopColor="#25246f" />
          <stop offset="100%" stopColor="#181647" />
        </linearGradient>

        <linearGradient id="s2r-layer" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#24236a" />
          <stop offset="100%" stopColor="#100f2e" />
        </linearGradient>

        {/* Pin Gradient */}
        <linearGradient id="s2r-pin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#e0f2fe" />
          <stop offset="50%" stopColor="#7dd3fc" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>

        {/* Clean RTL text gradient */}
        <linearGradient id="s2r-text" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#c7d2fe" />
        </linearGradient>

        {/* Subtle 5% dot-grid pattern for plate surface */}
        <pattern id="s2r-plate-grid" width="22" height="22" patternUnits="userSpaceOnUse">
          <circle cx="11" cy="11" r="1.1" fill="#818cf8" />
        </pattern>

        {/* Filters */}
        <filter id="s2r-blur-lg" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="22" />
        </filter>
        <filter id="s2r-blur-sm" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
        <filter id="s2r-trace-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3.5" />
        </filter>
        <filter id="s2r-bit-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* Gentle readable glow for RTL text */}
        <filter id="s2r-text-gentle-glow" x="-20%" y="-30%" width="140%" height="160%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* ── 1. Ambient Background Aura ───────────────────────── */}
      <ellipse cx="380" cy="270" rx="360" ry="260" fill="url(#s2r-glow)" style={glowStyle} />

      {/* ── 2. Motherboard Plate with Enhanced Depth ─────────── */}
      {/* Plate Soft Drop Shadow */}
      <path
        d="M140 120 L620 120 Q632 120 636 132 L735 450 Q740 480 710 480 L50 480 Q20 480 25 450 L124 132 Q128 120 140 120 Z"
        fill="#3730a3"
        opacity="0.28"
        filter="url(#s2r-blur-lg)"
      />

      {/* Plate Extruded Bottom "Thickness" Strip */}
      <path
        d="M50 480 L710 480 Q735 480 738 465 L740 473 Q735 491 708 491 L52 491 Q25 491 22 473 L25 465 Q28 480 50 480 Z"
        fill="#070918"
        stroke="#1e1b4b"
        strokeWidth="1"
      />

      {/* Main Plate Surface */}
      <path
        d="M140 110 L620 110 Q632 110 636 122 L735 450 Q740 480 710 480 L50 480 Q20 480 25 450 L124 122 Q128 110 140 110 Z"
        fill="url(#s2r-plate)"
        stroke="#3730a3"
        strokeOpacity="0.75"
        strokeWidth="1.5"
      />

      {/* Plate Surface 5% Subtle Dot-Grid Pattern */}
      <path
        d="M140 110 L620 110 Q632 110 636 122 L735 450 Q740 480 710 480 L50 480 Q20 480 25 450 L124 122 Q128 110 140 110 Z"
        fill="url(#s2r-plate-grid)"
        opacity="0.05"
      />

      {/* Lighter Top Edge Highlight */}
      <path
        d="M140 110 L620 110"
        stroke="url(#s2r-top-edge)"
        strokeWidth="2.2"
        strokeLinecap="round"
        opacity="0.9"
      />

      {/* ── 3. Circuit Traces (1.5x Thicker with Layered Glow) ── */}
      <g fill="none" strokeLinejoin="round" strokeLinecap="round">
        {/* Glow Underneath Layer */}
        {TRACES.map((t) => (
          <path
            key={`glow-${t.d}`}
            d={t.d}
            stroke="#0ea5e9"
            strokeWidth="5"
            opacity="0.45"
            filter="url(#s2r-trace-glow)"
          />
        ))}

        {/* Deep Indigo Base (1.5x thicker: 4.5px) */}
        {TRACES.map((t) => (
          <path
            key={`base-${t.d}`}
            d={t.d}
            stroke="#2e2b7a"
            strokeWidth="4.5"
            opacity="0.95"
          />
        ))}

        {/* Cyan Core Trace (1.8px) */}
        {TRACES.map((t) => (
          <path
            key={`core-${t.d}`}
            d={t.d}
            stroke="#38bdf8"
            strokeWidth="1.8"
            opacity="0.85"
          />
        ))}

        {/* Faint Moving Light Pulse Along Each Trace */}
        {!reduced &&
          TRACES.map((t, ti) => (
            <path
              key={`pulse-${t.d}`}
              d={t.d}
              stroke="#e0f2fe"
              strokeWidth="2.4"
              strokeDasharray="24 180"
              opacity="0.75"
              filter="url(#s2r-blur-sm)"
            >
              <animate
                attributeName="stroke-dashoffset"
                from="204"
                to="0"
                dur={`${t.dur}s`}
                begin={`${ti * 0.28}s`}
                repeatCount="indefinite"
              />
            </path>
          ))}
      </g>

      {/* ── 4. End Solder Pads (Slightly Larger with Soft Pulsing Glow) ── */}
      {ENDS.map((p, i) => (
        <g key={`pad-${i}`}>
          {/* Outer soft pulsing glow */}
          <circle cx={p.x} cy={p.y} r="8.5" fill="#38bdf8" filter="url(#s2r-blur-sm)">
            {!reduced && (
              <animate
                attributeName="opacity"
                values="0.25;0.75;0.25"
                dur="2.4s"
                begin={`${i * 0.22}s`}
                repeatCount="indefinite"
              />
            )}
          </circle>
          {/* Outer pad ring */}
          <circle cx={p.x} cy={p.y} r="4.6" fill="#38bdf8" opacity="0.65" />
          {/* Inner bright core */}
          <circle cx={p.x} cy={p.y} r="2.2" fill="#e0f2fe" />
        </g>
      ))}

      {/* Decorative dashed orbit ring around chip */}
      <ellipse
        cx="380"
        cy="240"
        rx="185"
        ry="145"
        fill="none"
        stroke="#818cf8"
        strokeOpacity="0.4"
        strokeWidth="1.2"
        strokeDasharray="4 6"
      />

      {/* ── 5. Microchip (30% Larger, Multi-Layer 3D Depth) ─── */}
      {/* Chip ambient glow */}
      <rect
        x={CHIP.x - 12}
        y={CHIP.y - 12}
        width={CHIP.w + 24}
        height={CHIP.h + 24}
        rx="26"
        fill="#6366f1"
        opacity="0.4"
        filter="url(#s2r-blur-lg)"
        style={glowStyle}
      />

      {/* Stacked 3D thickness layers */}
      {[18, 14, 10, 6].map((dy, i) => (
        <rect
          key={dy}
          x={CHIP.x - 2 + (3 - i) * 0.5}
          y={CHIP.y + dy}
          width={CHIP.w + 4 - (3 - i)}
          height={CHIP.h}
          rx="16"
          fill="url(#s2r-layer)"
          stroke="#4f46e5"
          strokeOpacity="0.55"
          strokeWidth="1"
        />
      ))}

      {/* Chip Pins (Connected directly to trace starts) */}
      {/* Top Pins */}
      {topPins.map((x) => (
        <rect
          key={`t${x}`}
          x={x}
          y={CHIP.y - 14}
          width="7"
          height="16"
          rx="1.5"
          fill="url(#s2r-pin)"
        />
      ))}

      {/* Bottom Pins */}
      {bottomPins.map((x) => (
        <rect
          key={`b${x}`}
          x={x}
          y={CHIP.y + CHIP.h + 12}
          width="7"
          height="16"
          rx="1.5"
          fill="url(#s2r-pin)"
        />
      ))}

      {/* Side Pins */}
      {sidePins.map((y) => (
        <g key={`s${y}`}>
          {/* Left pin extending to x=248 */}
          <rect
            x={CHIP.x - 16}
            y={y}
            width="18"
            height="6"
            rx="1.5"
            fill="url(#s2r-pin)"
          />
          {/* Right pin extending to x=512 */}
          <rect
            x={CHIP.x + CHIP.w - 2}
            y={y}
            width="18"
            height="6"
            rx="1.5"
            fill="url(#s2r-pin)"
          />
        </g>
      ))}

      {/* Chip Top Face */}
      <rect
        x={CHIP.x}
        y={CHIP.y}
        width={CHIP.w}
        height={CHIP.h}
        rx="16"
        fill="url(#s2r-chip)"
        stroke="#818cf8"
        strokeOpacity="0.65"
        strokeWidth="1.5"
      />

      {/* Inner Bevel Border */}
      <rect
        x={CHIP.x + 12}
        y={CHIP.y + 12}
        width={CHIP.w - 24}
        height={CHIP.h - 24}
        rx="10"
        fill="none"
        stroke="#818cf8"
        strokeOpacity="0.3"
        strokeWidth="1"
      />

      {/* Pin 1 indicator dot */}
      <circle cx={CHIP.x + 25} cy={CHIP.y + 25} r="4" fill="#38bdf8" filter="url(#s2r-blur-sm)" />
      <circle cx={CHIP.x + 25} cy={CHIP.y + 25} r="2.4" fill="#ffffff" />

      {/* ── 6. RTL & VERILOG Label (Clean, Unobstructed, Gentle Glow) ── */}
      <text
        x={CHIP.x + CHIP.w / 2}
        y={CHIP.y + 116}
        textAnchor="middle"
        fontFamily={FONT}
        fontWeight="900"
        fontSize="74"
        letterSpacing="4"
        fill="url(#s2r-text)"
        filter="url(#s2r-text-gentle-glow)"
      >
        RTL
      </text>
      <text
        x={CHIP.x + CHIP.w / 2}
        y={CHIP.y + 152}
        textAnchor="middle"
        fontFamily={FONT}
        fontWeight="700"
        fontSize="11"
        letterSpacing="9"
        fill="#c7d2fe"
        opacity="0.88"
      >
        VERILOG
      </text>

      {/* ── 7. Emitted Bits (0s & 1s) Born at Pin Tips Traveling Along Traces ── */}
      {/* Bits start ONLY at pin tips and never cross the chip face or labels */}
      {!reduced &&
        TRACES.map((t, ti) => {
          const baseDelay = reduced ? 0 : 0.8;
          return Array.from({ length: t.bits }, (_, bi) => {
            const begin = `${((bi * t.dur) / t.bits + ti * 0.42 + baseDelay).toFixed(2)}s`;
            const bit = (ti + bi) % 2 === 0 ? "1" : "0";
            return (
              <text
                key={`bit-${ti}-${bi}`}
                textAnchor="middle"
                dominantBaseline="central"
                fontFamily={FONT}
                fontWeight="800"
                fontSize="14"
                fill="#a5f3fc"
                opacity="0"
                filter="url(#s2r-bit-glow)"
              >
                {bit}
                <animateMotion
                  path={t.bitPath || t.d}
                  dur={`${t.dur}s`}
                  begin={begin}
                  repeatCount="indefinite"
                  calcMode="linear"
                />
                <animate
                  attributeName="opacity"
                  values="0;1;1;0"
                  keyTimes="0;0.12;0.85;1"
                  dur={`${t.dur}s`}
                  begin={begin}
                  repeatCount="indefinite"
                />
              </text>
            );
          });
        })}

      {/* Static Bits for Users with prefers-reduced-motion */}
      {reduced && (
        <g fontFamily={FONT} fontWeight="700" fontSize="14" fill="#a5f3fc" textAnchor="middle">
          <text x="180" y="185" dy="-7">1</text>
          <text x="580" y="185" dy="-7">0</text>
          <text x="110" y="240" dy="-7">0</text>
          <text x="630" y="240" dy="-7">1</text>
          <text x="150" y="360">0</text>
          <text x="610" y="360">1</text>
          <text x="380" y="440">1</text>
          <text x="240" y="460">0</text>
          <text x="520" y="460">1</text>
        </g>
      )}
    </svg>
  );
}
