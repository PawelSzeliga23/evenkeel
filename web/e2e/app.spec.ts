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

test("konto oszczędnościowe: założenie, odsetki, historia i usunięcie wpłaty", async ({ page }) => {
  await page.goto("/rejestracja");
  await page.getByLabel("E-mail").fill(`e2e-savings-${Date.now()}@portfolio.dev`);
  await page.getByLabel("Hasło").fill("e2e-haslo-12345");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeVisible();

  await page.getByRole("navigation", { name: "Główna" }).getByRole("link", { name: "Dodaj" }).click();
  await page.getByRole("link", { name: /Konto oszczędnościowe/ }).click();
  await page.getByLabel("Nazwa konta").fill("Konto w banku");
  await page.getByLabel("Oprocentowanie roczne (%)").fill("5");
  await page.getByLabel("Obowiązuje od").fill("2026-01-01");
  await page.getByLabel("Pierwsza wpłata").fill("10 000");
  await page.getByLabel("Data wpłaty").fill("2026-01-01");
  await page.getByRole("button", { name: "Załóż konto" }).click();

  await expect(page.getByRole("heading", { name: "Konto w banku" })).toBeVisible();
  await expect(page.getByText("Odsetki dopisane (netto)")).toBeVisible();
  await page.getByRole("button", { name: "Wpłata lub wypłata" }).click();
  await page.getByLabel("Kwota").fill("500");
  await page.getByLabel("Data").fill("2026-02-10");
  await page.getByRole("button", { name: "Zapisz" }).click();
  await expect(page.getByRole("button", { name: "Zapisz" })).toHaveCount(0);
  await page.screenshot({ path: `${SCREENS}/oszczednosci.png`, fullPage: true });

  await page.getByRole("navigation", { name: "Główna" }).getByRole("link", { name: "Historia" }).click();
  await expect(page.getByText("Odsetki dopisane").first()).toBeVisible();
  const deposit = page.getByRole("listitem").filter({ hasText: "500,00" }).first();
  await deposit.getByRole("button", { name: "Usuń" }).click();
  await page.getByRole("group", { name: "Potwierdzenie" }).getByRole("button", { name: "Usuń" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "500,00" })).toHaveCount(0);
  await page.screenshot({ path: `${SCREENS}/historia.png`, fullPage: true });
});
