import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f3eee6",
        ink: "#1c1712",
        clay: "#c4491d",
        moss: "#1f6b45",
        card: "#fffaf3",
        line: "#e4d7c6",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Segoe UI", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
      },
      boxShadow: {
        ticket: "0 16px 40px rgba(68, 42, 18, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
