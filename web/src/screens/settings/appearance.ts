import type { StartScreen } from "../../api/types";

export const START_SCREENS: { value: StartScreen; label: string; path: string }[] = [
  { value: "dashboard", label: "Pulpit", path: "/" }, { value: "positions", label: "Pozycje", path: "/pozycje" },
  { value: "history", label: "Historia", path: "/historia" }, { value: "analysis", label: "Analiza", path: "/analiza" },
];
