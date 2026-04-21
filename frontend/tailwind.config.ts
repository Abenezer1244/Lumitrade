import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "var(--color-bg-primary)",
        surface: "var(--color-bg-surface-solid)",
        elevated: "var(--color-bg-elevated-solid)",
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
      },
      fontFamily: {
        sans: ["Satoshi", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        display: ["Satoshi", "system-ui", "-apple-system", "sans-serif"],
      },
      borderRadius: {
        card: "var(--card-radius)",
      },
      backdropBlur: {
        glass: "16px",
      },
    },
  },
  plugins: [],
};
export default config;
