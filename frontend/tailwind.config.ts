import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#eef2fb",
        ink: "#16182b",
        clay: "#c4324a",
        moss: "#0f7a6a",
        card: "#fbfcff",
        line: "#d4dced",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Segoe UI", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
      },
      boxShadow: {
        ticket: "0 16px 40px rgba(22, 24, 43, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
