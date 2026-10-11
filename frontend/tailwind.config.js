/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        midnight: { DEFAULT: "#102A2A", 900: "#0B1F1F", 800: "#102A2A", 700: "#173838", 600: "#1F4646" },
        graphite: { DEFAULT: "#202927", 700: "#2E3836", 500: "#5B6663", 400: "#7D8784", 300: "#A3AAA7" },
        ivory: { DEFAULT: "#F5F2EA", 50: "#FBFAF6", 100: "#F5F2EA", 200: "#ECE7DA", 300: "#DDD6C5" },
        teal: { DEFAULT: "#2D7771", 50: "#E8F1EF", 100: "#CFE3E0", 400: "#3E8E87", 500: "#2D7771", 600: "#236460", 700: "#1B4F4C" },
        brass: { DEFAULT: "#C29B58", 50: "#F7F0E2", 100: "#EEDFC1", 400: "#CDAA6D", 500: "#C29B58", 600: "#A57F3F", 700: "#7F6131" },
        alert: { DEFAULT: "#C4552B", 50: "#F9EAE3", 100: "#F1D1C3", 500: "#C4552B", 600: "#A54621" },
        line: "#DDD6C5",
      },
      fontFamily: {
        display: ['"Newsreader"', "Georgia", "serif"],
        sans: ['"IBM Plex Sans"', "Segoe UI", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "Consolas", "monospace"],
      },
      letterSpacing: { eyebrow: "0.18em" },
      boxShadow: {
        hair: "0 0 0 1px rgba(16,42,42,0.08)",
        lift: "0 1px 0 rgba(16,42,42,0.04), 0 12px 32px -16px rgba(16,42,42,0.25)",
      },
      keyframes: {
        rise: { "0%": { opacity: 0, transform: "translateY(6px)" }, "100%": { opacity: 1, transform: "none" } },
        sweep: { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "translateX(100%)" } },
      },
      animation: { rise: "rise .45s cubic-bezier(.2,.7,.2,1) both", sweep: "sweep 1.4s ease-in-out infinite" },
    },
  },
  plugins: [],
};
