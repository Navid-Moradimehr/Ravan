"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-border bg-surface-2 px-4 text-sm font-medium text-secondary transition-colors duration-150 hover:bg-surface-3 hover:text-primary"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? <Sun aria-hidden="true" className="size-4" /> : <Moon aria-hidden="true" className="size-4" />}
      {isDark ? "Light mode" : "Dark mode"}
    </button>
  );
}
