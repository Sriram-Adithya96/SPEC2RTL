/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0a0e14",
        panel: "rgba(16, 22, 32, 0.82)",
        line: "#243044",
        lavender: "#a78bfa",
        lilac: "#c4b5fd",
        violet: "#818cf8",
        primary: "#7dd3fc",
        indigo: "#d6deeb",
        muted: "#7d8aa3",
        lime: "#4ade80",
        soft: "#243044",
        "ice-blue": "rgba(125, 211, 252, 0.15)",
        "mint-green": "rgba(74, 222, 128, 0.15)",
        azure: "#7dd3fc",
        emerald: "#4ade80",
        "amber-warn": "#fbbf24",
        "status-run": "#7dd3fc",
        "status-ok": "#4ade80",
        "status-fail": "#f87171",
        "status-warn": "#fbbf24",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 16px 40px rgba(117, 64, 197, 0.10), 0 0 28px rgba(197, 166, 242, 0.28)",
        glow: "0 10px 28px rgba(117, 64, 197, 0.32)",
        glass: "0 8px 32px rgba(99,51,191,0.07), 0 1px 0 rgba(255,255,255,0.8) inset",
        "glass-lg": "0 16px 48px rgba(99,51,191,0.10), 0 1px 0 rgba(255,255,255,0.9) inset",
        "chip-3d": "0 20px 60px rgba(124,58,237,0.4), 0 8px 24px rgba(124,58,237,0.2)",
      },
      animation: {
        float: "float 5s ease-in-out infinite",
        "pulse-node": "pulse-node 1.5s ease-in-out infinite",
        aurora: "aurora 20s ease infinite",
        "spin-slow": "spin 8s linear infinite",
      },
      keyframes: {
        float: {
          "0%,100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-12px)" },
        },
        "pulse-node": {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(59,130,246,0.5)" },
          "50%": { boxShadow: "0 0 0 8px rgba(59,130,246,0)" },
        },
        aurora: {
          "0%,100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
    },
  },
  plugins: [],
};
