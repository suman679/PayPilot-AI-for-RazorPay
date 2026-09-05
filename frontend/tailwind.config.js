/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0E1420",       // near-black navy base
        ledger: "#141C2B",    // panel background
        line: "#25314A",      // hairline borders
        paper: "#F7F5EF",     // light surface for cards on dark
        signal: "#2FBF8F",    // single accent - "go/allowed" teal-green
        caution: "#E0A63A",   // policy/blocked amber
        danger: "#E0563A",
        muted: "#8592AC",
      },
      fontFamily: {
        display: ["'Fraunces'", "serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
