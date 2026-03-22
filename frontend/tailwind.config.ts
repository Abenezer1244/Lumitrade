import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "var(--color-bg-primary)",
        surface: "var(--color-bg-surface)",
        elevated: "var(--color-bg-elevated)",
        input: "var(--color-bg-input)",
        border: {
          DEFAULT: "var(--color-border)",
          accent: "var(--color-border-accent)",
        },
        primary: "var(--color-text-primary)",
        secondary: "var(--color-text-secondary)",
        tertiary: "var(--color-text-tertiary)",
        accent: "var(--color-accent)",
        profit: "var(--color-profit)",
        loss: "var(--color-loss)",
        warning: "var(--color-warning)",
        gold: "var(--color-gold)",
      },
      fontFamily: {
        sans: ["DM Sans", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
        display: ["Space Grotesk", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
