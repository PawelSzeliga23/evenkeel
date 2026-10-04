import { expect, test } from "@playwright/test";
import { execSync } from "node:child_process";
import { resolve } from "node:path";

const EXPORT = resolve(import.meta.dirname, "../../api/.e2e/IKE_56216965_2006-01-01_2026-09-26.xlsx");
/** E2E_THEME=light runs every test in the light theme (plan 8b) and keeps its screenshots apart, to compare by eye. */
const LIGHT = process.env.E2E_THEME === "light";
const SCREENS = resolve(import.meta.dirname, LIGHT ? "screens/light" : "screens");

test.beforeEach(async ({ page }) => {
  if (LIGHT) await page.addInitScript(() => localStorage.setItem("evenkeel.theme", "light"));
});

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
  // The e2e sample holds only a PLN instrument, so there are no exit costs to show.
  await expect(page.getByText(/Wartość rynkowa .* · koszty wyjścia/)).toBeHidden();
  await page.screenshot({ path: `${SCREENS}/pulpit.png`, fullPage: true });

  await page.getByRole("navigation", { name: "Główna" }).getByRole("link", { name: "Pozycje" }).click();
  await expect(page.getByRole("heading", { name: "Akcje i ETF-y" })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/pozycje.png`, fullPage: true });

  // The e2e API has no market provider: weekly closes for the price chart are written straight to its database.
  execSync("docker compose --profile e2e exec -T api-e2e python -m tests.e2e_prices", { cwd: resolve(import.meta.dirname, "../..") });

  await page.getByRole("link", { name: /CD Projekt/ }).click();
  await expect(page.getByRole("heading", { name: "CD Projekt" })).toBeVisible();
  await expect(page.getByText("Zgodne z XTB")).toBeVisible();
  const priceChart = page.getByRole("region", { name: "Wykres ceny" });
  await expect(priceChart.getByRole("img", { name: /^Wykres ceny/ })).toBeVisible({ timeout: 45_000 });
  await expect(priceChart.getByRole("button", { name: /^Zakup/ }).first()).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/pozycja.png`, fullPage: true });
  await priceChart.getByRole("button", { name: /^Zakup/ }).first().click();
  await expect(priceChart.getByRole("status")).toContainText("zapłacone");
  await priceChart.screenshot({ path: `${SCREENS}/wykres-ceny.png` });

  const tags = page.getByRole("region", { name: "Tagi" });
  await tags.getByRole("button", { name: "+ Dodaj tag" }).click();
  await tags.getByPlaceholder("Nowy tag…").fill("emerytura");
  await tags.getByPlaceholder("Nowy tag…").press("Enter");
  await expect(tags.getByRole("group", { name: "Walor — na wszystkich kontach" }).getByText("emerytura")).toBeVisible();
  const notes = page.getByRole("region", { name: "Notatki" });
  await notes.getByRole("button", { name: "+ Dodaj tezę" }).click();
  await notes.getByLabel("Treść tezy").fill("Trzymam do premiery kolejnej gry.");
  await notes.getByRole("button", { name: "Zapisz" }).click();
  await expect(notes.getByText("Trzymam do premiery kolejnej gry.")).toBeVisible();
  await notes.getByRole("button", { name: "+ Wpis" }).click();
  await notes.getByLabel("Treść", { exact: true }).fill("Dokupiłem po spadku.");
  await notes.getByRole("button", { name: "Zapisz" }).click();
  await expect(notes.getByRole("button", { name: "Dokupiłem po spadku." })).toBeVisible();
  await page.goto("/analiza/tagi");
  const shares = page.getByRole("list", { name: "Udział w portfelu" });
  await expect(shares.getByRole("listitem").filter({ hasText: "emerytura" })).toContainText("1 walor");
  await expect(shares.getByRole("listitem").filter({ hasText: "Gotówka" })).toBeVisible();
  await expect(shares.getByText("bez tagu")).toHaveCount(0);
  await expect(page.getByRole("status", { name: "Wczytuję Evenkeel" })).toHaveCount(0, { timeout: 10_000 }); // the startup splash after goto
  await page.screenshot({ path: `${SCREENS}/tagi.png`, fullPage: true });
  await page.goto("/ustawienia/dziennik");
  await expect(page.getByRole("link", { name: "CDR.PL" })).toBeVisible();
  await page.getByRole("button", { name: "+ Wpis" }).click();
  await page.getByLabel("Treść", { exact: true }).fill("Plan na rok: dopłaty co miesiąc.");
  await page.getByRole("button", { name: "Zapisz" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Plan na rok" })).toContainText("Portfel");
  await expect(page.getByRole("status", { name: "Wczytuję Evenkeel" })).toHaveCount(0, { timeout: 10_000 });
  await page.screenshot({ path: `${SCREENS}/dziennik.png`, fullPage: true });

  await page.goto("/ekspozycja");
  await expect(page.getByRole("img", { name: /Udział walut w czasie/ })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/ekspozycja.png`, fullPage: true });

  await page.goto("/");
  await page.getByRole("link", { name: "Szczegóły analizy" }).click();
  await expect(page.getByRole("heading", { name: "Analiza" })).toBeVisible();
  await expect(page.getByRole("group", { name: "TWR" })).toBeVisible();

  await page.getByRole("region", { name: "Walory" }).getByRole("link", { name: "Walory" }).click();
  await expect(page.getByRole("heading", { name: "Walory", level: 1 })).toBeVisible();
  await expect(page.getByRole("group", { name: "Mapa walorów" }).getByRole("button").first()).toBeVisible();
  await expect(page.getByRole("list", { name: "Ranking" }).getByRole("listitem").first()).toBeVisible();
  await page.getByRole("group", { name: "Mapa walorów" }).getByRole("button").first().click();
  await page.screenshot({ path: `${SCREENS}/walory.png`, fullPage: true });
  await page.getByRole("link", { name: "Analiza" }).first().click();
  await expect(page.getByRole("heading", { name: "Analiza", level: 1 })).toBeVisible();

  await page.getByRole("link", { name: "Szczegóły dochodu i kosztów" }).click();
  await expect(page.getByRole("heading", { name: "Dochód i koszty", level: 1 })).toBeVisible();
  await expect(page.getByRole("img", { name: "Dochód i koszty w miesiącach" })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/dochod.png`, fullPage: true });
  await page.getByRole("link", { name: "Analiza" }).first().click();
  await expect(page.getByRole("heading", { name: "Analiza", level: 1 })).toBeVisible();

  await page.getByRole("link", { name: "Nowy scenariusz" }).click();
  await expect(page.getByRole("heading", { name: "Nowy scenariusz" })).toBeVisible();
  await page.getByLabel("Nazwa").fill("Wszystko w EDO");
  await page.getByRole("button", { name: "Moje wpłaty" }).click();
  await expect(page.getByText(/Względem portfela: \+/)).toBeVisible();
  await expect(page.getByRole("img", { name: /Porównanie wartości: Mój portfel, Wszystko w EDO/ })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/scenariusz.png`, fullPage: true });
  await page.getByRole("button", { name: "Zapisz scenariusz" }).click();
  await expect(page.getByRole("heading", { name: "Symulator" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Linie na wykresie" }).getByRole("button", { name: "Wszystko w EDO" }))
    .toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("img", { name: /Porównanie wartości: Mój portfel, Wszystko w EDO/ })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/symulator.png`, fullPage: true });

  await page.goto("/analiza/przeglad");
  await expect(page.getByRole("heading", { name: "Przegląd portfela" })).toBeVisible();
  const answer = ["Ocena ogólna", "Mocne strony", "Ryzyka", "Rynek", "Twoje instrumenty", "Pomysły do rozważenia",
    "Propozycje", "Pytania do przemyślenia", "Źródła"].map((s) => `## ${s}\n\nTreść.`).join("\n\n");
  const fence = "`".repeat(4);
  await page.getByLabel("Wklej odpowiedź Claude").fill(`${fence}markdown\n${answer}\n${fence}`);
  await page.getByRole("button", { name: "Zapisz przegląd" }).click();
  await expect(page.getByRole("heading", { name: "Ryzyka" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Wczytuję Evenkeel" })).toHaveCount(0, { timeout: 10_000 }); // the startup splash after goto
  await page.screenshot({ path: `${SCREENS}/przeglad.png`, fullPage: true });

  await page.goto("/limity");
  await expect(page.getByRole("heading", { name: "Limity IKE i IKZE" })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/limity.png`, fullPage: true });
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

  // The narrowest phones: forms with two fields in a row must not scroll sideways.
  await page.setViewportSize({ width: 320, height: 700 });
  for (const path of ["/dodaj/konto-oszczednosciowe", "/dodaj/obligacja", "/dodaj/operacja"]) {
    await page.goto(path);
    await expect(page.getByRole("button", { name: /Załóż konto|Zapisz/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth), path).toBeLessThanOrEqual(320);
  }
});

test("ustawienia: zmiana hasła, logowanie nowym hasłem, zamknięte inwestycje i limity", async ({ page }) => {
  const email = `e2e-settings-${Date.now()}@portfolio.dev`;
  await page.goto("/rejestracja");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Hasło").fill("e2e-haslo-12345");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeVisible();

  await page.getByRole("main").getByRole("link", { name: "Ustawienia" }).click(); // the gear on Pulpit (phone)
  await expect(page.getByRole("searchbox", { name: "Szukaj w ustawieniach" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Wczytuję Evenkeel" })).toHaveCount(0, { timeout: 10_000 });
  await page.screenshot({ path: `${SCREENS}/ustawienia.png`, fullPage: true });
  await page.getByRole("searchbox", { name: "Szukaj w ustawieniach" }).fill("hasło");
  await page.getByRole("link", { name: /Zmień hasło/ }).click();
  await expect(page).toHaveURL(/\/ustawienia\/haslo$/);
  await page.getByLabel("Obecne hasło").fill("e2e-haslo-12345");
  await page.getByLabel("Nowe hasło", { exact: true }).fill("e2e-nowe-haslo-678");
  await page.getByLabel("Powtórz nowe hasło").fill("e2e-nowe-haslo-678");
  await page.getByRole("button", { name: "Zmień hasło" }).click();
  await expect(page.getByText("Hasło zmienione. Inne urządzenia zostaną wylogowane.")).toBeVisible();
  await page.getByRole("link", { name: /Profil/ }).click();

  await page.getByRole("button", { name: "Wyloguj" }).click();
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Hasło").fill("e2e-haslo-12345");
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByLabel("Hasło").fill("e2e-nowe-haslo-678");
  await page.getByRole("button", { name: "Zaloguj się" }).click();
  // the login returns to the page the user was on (Profil)
  await expect(page.getByRole("heading", { name: "Profil", level: 1 })).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/ustawienia");
  await expect(page.getByRole("status", { name: "Wczytuję Evenkeel" })).toHaveCount(0, { timeout: 10_000 });
  await page.screenshot({ path: `${SCREENS}/ustawienia-desktop.png` });
  await page.setViewportSize({ width: 390, height: 844 });

  await page.getByRole("navigation", { name: "Główna" }).getByRole("link", { name: "Pozycje" }).click();
  await page.getByRole("button", { name: "Zamknięte" }).click();
  await expect(page.getByText("Nie masz jeszcze zamkniętych inwestycji.")).toBeVisible();

  await page.goto("/limity");
  await expect(page.getByText("Nie masz konta IKE ani IKZE.")).toBeVisible();
});

test("kopia portfela: pobranie i wczytanie na nowym koncie daje ten sam Pulpit", async ({ page, browser }) => {
  const heroValue = async (p: typeof page) => {
    await expect(p.getByRole("img", { name: /Wykres wartości portfela/ })).toBeVisible({ timeout: 45_000 });
    await expect(p.getByText("Przeliczam wycenę…", { exact: true })).toBeHidden({ timeout: 45_000 });
    return (await p.locator("body").innerText()).match(/Wartość portfela\s*\n([^\n]+)/)![1];
  };
  await page.goto("/rejestracja");
  await page.getByLabel("E-mail").fill(`e2e-backup-${Date.now()}@portfolio.dev`);
  await page.getByLabel("Hasło").fill("e2e-haslo-12345");
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await page.getByRole("link", { name: "Wgraj pliki z XTB" }).click();
  await page.getByLabel("Wybierz pliki").setInputFiles(EXPORT);
  await page.getByRole("button", { name: "Zapisz import" }).click();
  await page.getByRole("link", { name: "Zobacz pulpit" }).click();
  const original = await heroValue(page);

  await page.goto("/ustawienia/kopia");
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz kopię" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toMatch(/^evenkeel-kopia-\d{4}-\d{2}-\d{2}\.json$/);
  const backup = await download.path();

  const other = await browser.newPage({ viewport: { width: 390, height: 844 } });
  if (LIGHT) await other.addInitScript(() => localStorage.setItem("evenkeel.theme", "light"));
  await other.goto("/rejestracja");
  await other.getByLabel("E-mail").fill(`e2e-restore-${Date.now()}@portfolio.dev`);
  await other.getByLabel("Hasło").fill("e2e-haslo-12345");
  await other.getByRole("button", { name: "Załóż konto" }).click();
  await expect(other.getByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeVisible();
  await other.goto("/ustawienia/kopia");
  await other.getByLabel("Plik kopii").setInputFiles(backup);
  await expect(other.getByRole("group", { name: "Zawartość kopii" })).toContainText("1 konto");
  await expect(other.getByRole("status", { name: "Wczytuję Evenkeel" })).toHaveCount(0, { timeout: 10_000 }); // the startup splash after goto
  await other.screenshot({ path: `${SCREENS}/kopia.png`, fullPage: true });
  await other.getByLabel("Wpisz ZASTĄP").fill("ZASTĄP");
  await other.getByRole("button", { name: "Wczytaj" }).click();

  await expect(other.getByText("Wczytano kopię. Przeliczam wycenę…")).toBeVisible();
  expect(await heroValue(other)).toBe(original);
  await other.close();
});
