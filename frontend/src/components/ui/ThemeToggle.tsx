"use client";

import { useTheme } from "next-themes";
import { useState, useEffect } from "react";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="w-9 h-9" />;

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="w-9 h-9 flex items-center justify-center rounded-lg glass hover:bg-[var(--color-bg-elevated)] transition-colors"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? (
        <Sun size={15} className="text-[var(--color-text-secondary)]" />
      ) : (
        <Moon size={15} className="text-[var(--color-text-secondary)]" />
      )}
    </button>
  );
}
