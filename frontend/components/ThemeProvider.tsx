"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

export type AppTheme = "grey" | "dark" | "light" | "contrast";

type ThemeContextValue = {
  theme: AppTheme;
  setTheme: (theme: AppTheme) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = "agrinox_theme";
const THEMES: AppTheme[] = ["grey", "dark", "light", "contrast"];

function applyDocumentTheme(theme: AppTheme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme === "light" ? "light" : "dark";
}

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<AppTheme>("grey");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as AppTheme | null;
    const initial = saved && THEMES.includes(saved) ? saved : "grey";
    setThemeState(initial);
    applyDocumentTheme(initial);
  }, []);

  function setTheme(next: AppTheme) {
    setThemeState(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyDocumentTheme(next);
  }

  const value = useMemo(() => ({ theme, setTheme }), [theme]);
  return <ThemeContext.Provider value={value}><div className="app-theme min-h-screen" data-theme={theme}>{children}</div></ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
