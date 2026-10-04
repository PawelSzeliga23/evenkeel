import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { THEME_COLORS, THEME_KEY, ThemeProvider, useTheme, type Theme } from "./theme";

let setTheme: (theme: Theme) => void = () => {};
function Probe() {
  const [theme, set] = useTheme();
  setTheme = set;
  return <p>{theme}</p>;
}
const meta = (name: string) => document.querySelector(`meta[name="${name}"]`)!.getAttribute("content");

beforeEach(() => {
  for (const [name, content] of [["theme-color", THEME_COLORS.dark], ["color-scheme", "dark"]]) {
    const tag = document.createElement("meta");
    tag.name = name!;
    tag.content = content!;
    document.head.append(tag);
  }
});
afterEach(() => document.head.querySelectorAll("meta").forEach((tag) => tag.remove()));

describe("theme", () => {
  it("is dark by default", () => {
    const { container } = render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(container).toHaveTextContent("dark");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(meta("theme-color")).toBe(THEME_COLORS.dark);
  });

  it("starts light when this browser chose light", () => {
    localStorage.setItem(THEME_KEY, "light");
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(meta("theme-color")).toBe(THEME_COLORS.light);
    expect(meta("color-scheme")).toBe("light");
  });

  it("switches, remembers the choice and goes back to dark", () => {
    const { container } = render(<ThemeProvider><Probe /></ThemeProvider>);
    act(() => setTheme("light"));
    expect(container).toHaveTextContent("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");

    act(() => setTheme("dark"));
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(meta("color-scheme")).toBe("dark");
  });

  it("stays dark and works when the browser storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    const { container } = render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(container).toHaveTextContent("dark");
    act(() => setTheme("light"));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    vi.restoreAllMocks();
  });
});
