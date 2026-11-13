import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#07090d", 900: "#0b0f16", 800: "#111826", 700: "#1a2334", 600: "#243043", 500: "#34425a" },
        felt: { 900: "#0f2a22", 800: "#143a2e", 700: "#1a4a3a", 600: "#215a46" },
        accent: { DEFAULT: "#5eead4", dim: "#2dd4bf" },
        gold: "#f5c451",
        danger: "#f87171",
        ok: "#4ade80",
        warn: "#fbbf24",
      },
      boxShadow: { glow: "0 0 0 1px rgba(94,234,212,0.35), 0 0 24px rgba(94,234,212,0.15)" },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
};
export default config;
