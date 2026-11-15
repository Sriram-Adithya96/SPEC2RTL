/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F8F5FF",
        lavender: "#C5A6F2",
        lilac: "#DCCBFA",
        violet: "#A879E5",
        primary: "#7540C5",
        indigo: "#35145D",
        muted: "#4A3566",
        lime: "#C8F52F",
        soft: "#E9DDFB",
        "ice-blue": "#e0f2fe",
        "mint-green": "#d1fae5",
        azure: "#3b82f6",
        emerald: "#10b981",
        "amber-warn": "#f59e0b",
        "status-run": "#3b82f6",
        "status-ok": "#22c55e",
        "status-fail": "#ef4444",
        "status-warn": "#f59e0b",
      },
      fontFamily: {
        sans: ["Inter", "Manrope", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "ui-monospace", "monospace"],
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
