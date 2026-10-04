# Plan 8b — Ustawienia: motyw jasny i ciemny, kolory w dwóch plikach (decyzje projektowe)

**Data:** 2026-10-04
**Część:** 8b z Ustawień (8a zrobione; 8c dane i kopia, 8d konto — później).
**Makieta:** `.superpowers/brainstorm/1710-1791107673/content/jasny-motyw-v3.html` (wybrana wersja A).

## Decyzje właściciela (2026-10-04)

1. **Po co:** jasny motyw jest do czytania w dzień, na słońcu albo w jasnym pokoju.
2. **Przełączanie ręczne** w Ustawieniach: **Ciemny** (domyślny, jak dziś) albo **Jasny**. Bez opcji „systemowy”.
3. **Zapis na każdym urządzeniu osobno**, w przeglądarce (jak ukrywanie kwot).
4. **Wygląd jasnego motywu: wersja A „Ciepły papier”** — kremowe tło, białe karty, ciemniejszy bursztyn, zysk i strata
   w ciemniejszej zieleni i czerwieni.
5. **Wszystkie kolory w dwóch plikach**, żeby kiedyś łatwo zmienić wygląd:
   - `web/src/styles/theme.css` — kolory aplikacji;
   - `web/src/styles/chart-colors.css` — kolory wykresów.
   Poza tymi plikami w kodzie nie ma żadnego koloru (hex, `rgba(...)`), tylko nazwy zmiennych `var(--…)`.
6. Właściciel zatwierdził projekt w rozmowie i poprosił o spec, plan i wykonanie bez kolejnych pytań.

## 1. Kolory aplikacji — `theme.css`

Zastępuje `tokens.css`. Ma dwa zestawy: `:root` (ciemny, domyślny) i `:root[data-theme="light"]`. Nazwy zmiennych
zostają te same co dziś, więc ekrany nie zmieniają się poza miejscami z kolorem wpisanym na sztywno.

| zmienna | ciemny (dziś) | jasny |
|---|---|---|
| `--night` (tło) | `#0E1116` | `#F6F3EC` |
| `--slab` (karty) | `#161A21` | `#FFFDF8` |
| `--rule` (linie) | `#242A33` | `#E4DED1` |
| `--ink` (tekst) | `#E7E9EC` | `#1D2127` |
| `--dim` (tekst drugi) | `#8B94A1` | `#6B7280` |
| `--amber` (akcent: linie, kropki, wypełnienia) | `#F0A43A` | `#D98A1C` |
| `--amber-text` (bursztyn w tekście i aktywnych zakładkach) — nowa | `#F0A43A` | `#A9620A` |
| `--amber-soft` | `rgba(240,164,58,.14)` | `rgba(217,138,28,.14)` |
| `--amber-line` (obrys otwartego wyboru) — nowa | `rgba(240,164,58,.45)` | `rgba(217,138,28,.55)` |
| `--gain` | `#5DB98A` | `#1F8556` |
| `--loss` | `#E0676E` | `#C2414A` |
| `--loss-soft` | `rgba(224,103,110,.14)` | `rgba(194,65,74,.12)` |
| `--info` (wpisy portfela w Dzienniku) — nowa | `#7FB6E6` | `#2F72B8` |
| `--nav-bg` (pasek nawigacji, półprzezroczysty) — nowa | `rgba(14,17,22,.92)` | `rgba(246,243,236,.92)` |
| `--shadow` (cień okienek) — nowa | `rgba(0,0,0,.45)` | `rgba(60,45,20,.16)` |
| `--on-accent` (tekst na kolorowym znaczniku) — nowa | `#0B1220` | `#FFFFFF` |

Oprócz tego `color-scheme: dark` / `light` (pola formularzy, paski przewijania) i stałe kolory znaku Evenkeel,
**takie same w obu motywach**: `--brand-tile-from #1C2129`, `--brand-tile-to #0E1116`, `--brand-tile-border #242A33`,
`--brand-bar-from #8A5A1C`, `--brand-bar-to #FFC266`, `--brand-base #3A424E`.

**Bursztyn w tekście:** wszędzie, gdzie bursztyn jest kolorem tekstu (`color:`), używamy `--amber-text`; `--amber` zostaje
dla linii, kropek, obramowań i wypełnień. W ciemnym motywie oba są równe, więc ciemny wygląda tak samo jak dziś.

## 2. Kolory wykresów — `chart-colors.css`

Ten sam układ: `:root` ciemny, `:root[data-theme="light"]` jasny. Kod wykresów używa tylko nazw (`var(--chart-…)`).
Palety jasne sprawdzone walidatorem kontrastu (dataviz, tło `#FFFDF8`).

| rola | zmienne | ciemny (dziś) | jasny |
|---|---|---|---|
| serie (waluty, symulator, nagłówki przeglądu AI) | `--series-1..4` | `#F0A43A #3987e5 #d55181 #9085e9` | `#C77E12 #2A6FC9 #C03D70 #6C5FD0` |
| znaczniki na wykresie ceny | `--mark-buy/sell/dividend/average/note` | `#5DB98A #E0676E #7FB6E6 #F0A43A #C98BD9` | `#1F8556 #C2414A #2F72B8 #C2780F #9B4FB0` |
| dochód i koszty | `--income-interest/dividends/fx/taxes/fees` | `#5DB98A #7FB6E6 #E0676E #B07FE0 #F0A43A` | `#1F8556 #2F72B8 #C2414A #8A4FC8 #C2780F` |
| alokacja na Pulpicie | `--alloc-1..5` | `var(--amber) #C9B48A #7C8898 #4A5361 #39414C` | `var(--amber) #B39459 #7C8898 #A3ABB6 #C9CED6` |
| „bez tagu” | `--untagged` | `#4A525E` | `#A3ABB6` |
| mapa cieplna i miesiące | `--heat-gain`, `--heat-loss` | `#5DB98A #E0676E` | `#3FA874 #D9545C` |
| tagi (8 kolorów) | `--tag-1..8` | `#F0A43A #7FB6E6 #5DB98A #C98BD9 #E0C36A #E0676E #6FC7C0 #B0B7C3` | `#C2780F #2F72B8 #1F8556 #9B4FB0 #9A7A10 #C2414A #00877E #6B7280` |

Wyniki walidatora (jasne): serie, znaczniki, dochód — kontrast ≥ 3:1 i rozróżnialność dla zwykłego wzroku. Zakup i
sprzedaż są słabo rozróżnialne przy daltonizmie (jak w ciemnym), ale mają różny kształt (▲/▼). Tagi zawsze stoją obok
nazwy, a szary jest celowo neutralną opcją — jak w ciemnym.

**Mapa cieplna i miesięczne stopy:** zamiast `rgba(93,185,138,α)` liczonego w kodzie —
`color-mix(in srgb, var(--heat-gain) N%, transparent)`, więc odcień dopasowuje się do motywu.

**Tagi:** serwer trzyma kolor tagu jako hex z ciemnej palety (`#F0A43A` itd.) i to się nie zmienia. W przeglądarce
funkcja `tagColor(hex)` zamienia hex z palety na `var(--tag-N)`; nieznany hex przechodzi bez zmian. Wybór koloru tagu
w Ustawieniach pokazuje próbki w kolorach bieżącego motywu, a zapisuje hex z palety.

**Kolory w TS** (`SHARE_COLORS`, `MARKER_COLORS`, `ALLOCATION_COLORS`, `PORTFOLIO_COLOR`, `SLOTS`, `UNTAGGED_COLOR`,
części dochodu, nagłówki przeglądu) stają się nazwami `var(--…)` z `chart-colors.css`.

## 3. Przełącznik

- Ustawienia → istniejąca grupa „Wygląd i prywatność” → nowy wiersz **„Motyw”**, na podstronie `/ustawienia/wyglad`
  na samej górze: dwa przyciski „Ciemny” / „Jasny” (radio). Na liście Ustawień wiersz pokazuje bieżący motyw
  („ciemny” / „jasny”). Wyszukiwarka znajduje go po „motyw”, „jasny”, „ciemny”, „kolor”, „tryb”.
- Podpowiedź pod przełącznikiem: „Tylko na tym urządzeniu.”
- Zapis w `localStorage` pod kluczem `evenkeel.theme` (`"light"` albo brak / `"dark"`).
- `ThemeProvider` (jak `PrivacyProvider`) trzyma motyw i ustawia `document.documentElement.dataset.theme`,
  `<meta name="theme-color">` (`#0E1116` / `#F6F3EC`) i `<meta name="color-scheme">`.
- **Bez mignięcia:** mały skrypt w `index.html` przed aplikacją czyta `evenkeel.theme` i ustawia `data-theme`
  i oba `meta`, zanim cokolwiek się narysuje (też ekran logowania i splash). Brak dostępu do `localStorage` → ciemny.

## 4. Znak, splash, ikona

- Kafelek znaku i bursztynowe słupki są takie same w obu motywach (stałe `--brand-*`).
- Napis: „Even” w `--ink` (w jasnym ciemny), „keel” w `--amber-text`.
- Splash: tło `--night` (w jasnym kremowe), na nim ten sam ciemny kafelek.
- Ikona aplikacji i `manifest` (`theme_color`, `background_color`) zostają ciemne — telefon czyta je przy instalacji.

## 5. Strażnik „żadnych kolorów poza dwoma plikami”

Test Vitest przegląda `web/src/**/*.{ts,tsx,css}` (bez testów i bez `theme.css` / `chart-colors.css`) i nie przepuszcza
hexów kolorów ani `rgb(a)(`. Dzięki temu nowy kod nie wpisze koloru na sztywno. Dane testowe (`test/fixtures.ts`)
są wyłączone.

## 6. Testy i sprawdzenie

- `ThemeProvider`: odczyt, zapis, `data-theme`, meta; brak `localStorage` → ciemny.
- Ekran Wygląd: przełączenie zmienia motyw i zapis; lista Ustawień pokazuje motyw; wyszukiwanie „motyw”.
- `tagColor`, `heatColor`, `cellBackground` — nowe wartości.
- Test zmiennych: oba pliki definiują każdą zmienną w obu motywach.
- Strażnik z punktu 5.
- Na koniec zrzuty ekranów (Pulpit, Pozycje, szczegół pozycji z wykresem ceny, Historia, Analiza, Walory, Tagi,
  Dochód, Symulator, Ustawienia, logowanie) w obu motywach na telefonie i komputerze, obejrzane przeze mnie.

## Poza zakresem

- Motyw „systemowy” i automatyczne przełączanie.
- Zapis motywu na serwerze.
- Jasna ikona aplikacji.
