import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "dark" | "light";
/** Also read by the boot script in index.html, which applies the theme before the app draws anything. */
export const THEME_KEY = "evenkeel.theme";
/** The browser bar colour of each theme: --night of theme.css (the meta tag cannot read a CSS variable).
 * index.html repeats the light one. */
export const THEME_COLORS: Record<Theme, string> = { dark: "#0E1116", light: "#F6F3EC" }; // colour-guard: allow

export function storedTheme(): Theme {
  try { return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark"; } catch { return "dark"; }
}

/** Switches the colour sets of theme.css and chart-colors.css, the browser bar and the form controls. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "light") root.dataset.theme = "light";
  else delete root.dataset.theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme]);
  document.querySelector('meta[name="color-scheme"]')?.setAttribute("content", theme);
}

export const ThemeContext = createContext<[Theme, (theme: Theme) => void]>(["dark", () => {}]);

/** The theme (plan 8b), chosen by hand in Ustawienia and kept per browser. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState(storedTheme);
  useLayoutEffect(() => applyTheme(theme), [theme]);
  const set = useCallback((next: Theme) => {
    setTheme(next);
    try { localStorage.setItem(THEME_KEY, next); } catch { /* storage unavailable: lasts this visit */ }
  }, []);
  const value = useMemo<[Theme, (theme: Theme) => void]>(() => [theme, set], [theme, set]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
