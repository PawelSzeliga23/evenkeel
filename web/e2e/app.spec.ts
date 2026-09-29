import { expect, test } from "@playwright/test";
import { resolve } from "node:path";

const EXPORT = resolve(import.meta.dirname, "../../api/.e2e/IKE_56216965_2006-01-01_2026-09-26.xlsx");
const SCREENS = resolve(import.meta.dirname, "screens");

test("rejestracja, import eksportu XTB, pulpit, pozycje i szczegóły pozycji", async ({ page }) => {
  await page.goto("/rejestracja");
  await page.getByLabel("E-mail").fill(`e2e-${Date.now()}@portfolio.dev`);
  await page.getByLabel("Hasło").fill("e2e-haslo-12345");
  await page.getByRole("button", { name: "Załóż konto" }).click();

  await expect(page.getByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeVisible();
  await page.getByRole("link", { name: "Wgraj pliki z XTB" }).click();

  await page.getByLabel("Wybierz pliki").setInputFiles(EXPORT);
  await expect(page.getByText(/Zostanie założone konto/)).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/import.png`, fullPage: true });
  await page.getByRole("button", { name: "Zapisz import" }).click();

  await expect(page.getByRole("heading", { name: "Import zapisany" })).toBeVisible();
  await page.getByRole("link", { name: "Zobacz pulpit" }).click();

  await expect(page.getByText("Wartość portfela")).toBeVisible();
  await expect(page.getByRole("img", { name: /Wykres wartości portfela/ })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText("Przeliczam wycenę…")).toBeHidden({ timeout: 45_000 });
  await page.screenshot({ path: `${SCREENS}/pulpit.png`, fullPage: true });

  await page.getByRole("navigation", { name: "Główna" }).getByRole("link", { name: "Pozycje" }).click();
  await expect(page.getByRole("heading", { name: "Akcje i ETF-y" })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/pozycje.png`, fullPage: true });

  await page.getByRole("link", { name: /CD Projekt/ }).click();
  await expect(page.getByRole("heading", { name: "CD Projekt" })).toBeVisible();
  await expect(page.getByText("Zgodne z XTB")).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/pozycja.png`, fullPage: true });
});
