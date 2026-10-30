/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#010203", 900: "#05070b", 800: "#0a0d14", 700: "#11151f" },
        line: "rgba(255,255,255,0.09)",
        cyan: { glow: "#5fe1ff" },
        magenta: { glow: "#ff4fd8" },
        volt: "#4d7cff",
        ok: "#5eead4", warn: "#fbbf77", bad: "#fb7185",
        silver: "#9aa4b2",
      },
      fontFamily: {
        display: ["\"Space Grotesk Variable\"", "\"Inter Variable\"", "system-ui", "sans-serif"],
        sans: ["\"Inter Variable\"", "system-ui", "\"Segoe UI\"", "sans-serif"],
        mono: ["\"JetBrains Mono Variable\"", "ui-monospace", "Consolas", "monospace"],
      },
      boxShadow: {
        glass: "0 24px 60px -18px rgba(0,0,0,.85), inset 0 1px 0 rgba(255,255,255,.10), inset 0 0 0 1px rgba(255,255,255,.035)",
        glow: "0 0 18px rgba(95,225,255,.35)",
        inner: "inset 0 0 14px rgba(95,225,255,.22)",
      },
      keyframes: {
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        wave: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        sweep: { "0%": { left: "-30%" }, "100%": { left: "100%" } },
      },
      animation: { shimmer: "shimmer 1.6s linear infinite", wave: "wave 1.2s linear infinite", sweep: "sweep 1.4s ease-in-out infinite" },
    },
  },
  plugins: [],
};
