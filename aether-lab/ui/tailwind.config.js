/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#04060b", 900: "#070b13", 800: "#0c1220", 700: "#121a2c" },
        line: "rgba(130,180,255,0.13)",
        cyan: { glow: "#5fe1ff" },
        violet: { glow: "#a78bfa" },
        ok: "#5eead4", warn: "#fbbf77", bad: "#fb7185",
      },
      fontFamily: {
        display: ["Space Grotesk", "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
      },
      boxShadow: {
        glass: "0 24px 70px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.05)",
        glow: "0 0 24px rgba(95,225,255,.35)",
      },
      keyframes: {
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        floatin: { "0%": { opacity: 0, transform: "translateY(8px)" }, "100%": { opacity: 1, transform: "none" } },
      },
      animation: { shimmer: "shimmer 1.6s linear infinite", floatin: "floatin .25s ease-out" },
    },
  },
  plugins: [],
};
