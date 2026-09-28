# Plan 6a: Frontend — fundament, pulpit, pozycje, import (decyzje projektowe)

> Uzupełnienie specyfikacji `2026-09-26-portfolio-tracker-design.md` (§3 stack, §5 „Przepływ w UI”, §7 ekrany
> i kierunek wizualny, §9, §10 „Frontend”) dla planu 6a. Ustalone w rozmowie 2026-09-28 (brainstorming + sesja
> `frontend-design`). Na tym dokumencie powstaje plan `plans/2026-09-28-06a-frontend-foundation.md`.
> Plan 6 z roadmapy dzieli się na **6a** (ten dokument) i **6b** (reszta ekranów etapu 1).

## Zakres

**6a:**
1. Logowanie i rejestracja, sesja odnawiana w tle.
2. Pulpit.
3. Pozycje (lista).
4. Szczegóły pozycji instrumentu (akcje / ETF).
5. Import XTB z podglądem i zapisem (pod „Dodaj”).
6. Szkielet aplikacji: nawigacja, ekran „Więcej” z wylogowaniem, PWA (manifest, ikony, service worker).

**Przesunięte do 6b:** szczegóły obligacji i konta oszczędnościowego (na liście pozycji 6a są widoczne, jeśli są
w bazie, ale bez ekranu szczegółów), dodawanie obligacji / kont oszczędnościowych / ręcznych operacji, Historia,
Ustawienia (konta, mapowanie tickerów, profil), zamknięte inwestycje, ekspozycja walutowa w czasie, limity IKE/IKZE.
6b dopisze też brakujące API: zapis ręcznej operacji i filtry historii (instrument, daty, wyszukiwanie) —
`/api/transactions` dziś tylko czyta i filtruje po koncie i typie.

**Odłożone, otwarty punkt w roadmapie:** sprawdzenie PWA na iPhonie (ekran początkowy, tryb standalone, service
worker przez HTTPS — tymczasowy tunel `cloudflared tunnel --url` albo `mkcert`, safe-area na prawdziwym
urządzeniu). W 6a PWA jest budowane, ale sprawdzane wyłącznie w przeglądarce na komputerze.

Backend: 6a **nie zmienia API** poza ewentualnym wsparciem testu e2e (osobna baza, patrz §6).

## 1. Kierunek wizualny

Makieta zaakceptowana 2026-09-28: artefakt „Makieta portfela” (https://claude.ai/artifact/NBPYQ1danFfjZsfnybjyrg)
— Pulpit, Pozycje, szczegóły obligacji. Jej zmienne i układ są wzorcem dla 6a.

- **Tylko ciemny motyw.** Tokeny kolorów:

  | Token | Wartość | Rola |
  |---|---|---|
  | `--night` | `#0E1116` | tło aplikacji (chłodny grafit, nie czysta czerń) |
  | `--slab` | `#161A21` | warstwy: przełączniki, filtry, pola porównań |
  | `--rule` | `#242A33` | cienkie linie, siatka wykresu |
  | `--ink` | `#E7E9EC` | tekst |
  | `--dim` | `#8B94A1` | tekst drugorzędny, osie, grosze i „zł” |
  | `--amber` | `#F0A43A` | **jedyny akcent**: linia wartości, aktywne zakładki i filtry, przycisk „Dodaj”, fokus |
  | `--amber-soft` | `rgba(240,164,58,.14)` | tło aktywnego elementu, pole zysku na wykresie |
  | `--gain` | `#5DB98A` | zysk (przygaszona zieleń) |
  | `--loss` | `#E0676E` | strata (różowa czerwień, wyraźnie inna niż bursztyn) |

  Kolory alokacji: bursztyn dla akcji i ETF-ów, potem odcienie neutralne (`#C9B48A`, `#7C8898`, `#4A5361`) —
  akcent nie ma konkurentów.
- **Pismo:** jeden krój **Instrument Sans** (oś szerokości 75–100, wagi 400–700), plik fontu dostarczany przez
  aplikację (nie z Google Fonts), z zapasowym `system-ui`. Duże kwoty w szerokości ~88 %. Wszystkie kwoty
  `font-variant-numeric: tabular-nums`.
- **Kwoty:** zapis polski — spacja tysięcy **zawsze** (także „1 204,50”), przecinek dziesiętny, „zł” po kwocie,
  minus typograficzny `−`, znak `+` przy zysku. W dużej kwocie grosze i „zł” są mniejsze i w kolorze `--dim`.
  Procenty „+0,66 %” (spacja przed %).
- **Układ:** bez kart z cieniami; sekcje rozdzielają odstępy i cienkie linie `--rule`. Ramką/`--slab` wyróżnione są
  tylko elementy do porównania lub sterowania. Treść wyrównana do lewej, kwoty w listach do prawej.
- **Nawigacja:** dolny pasek (5 miejsc: Pulpit, Pozycje, **Dodaj** — pełny bursztynowy przycisk w środku,
  Historia, Więcej) na wąskim ekranie; to samo jako boczne menu od 900 px. Historia w 6a: wyłączona z dopiskiem
  „wkrótce”.
- **Ruch:** jeden moment — rysowanie linii wartości przy pierwszym wyświetleniu wykresu; szanuje
  `prefers-reduced-motion`. Poza tym ruch tylko jako odpowiedź na akcję (rozwinięcie, zatwierdzenie).
- **Dostępność:** widoczny fokus (obrys `--amber`), kontrast tekstu `--dim` na `--night` ≥ 4.5:1 dla tekstu
  ≥ 13 px, przyciski ≥ 44 px wysokości dotyku, safe-area iPhone'a (`env(safe-area-inset-*)`) w pasku i nagłówku.
- **Teksty:** po polsku, zdania od wielkiej litery bez wersalików w etykietach, przyciski mówią, co zrobią
  („Wgraj pliki z XTB”, „Zapisz import”); błędy mówią, co się stało i co zrobić, bez przepraszania.

## 2. Ekrany

**Logowanie / Rejestracja** — e-mail, hasło; pole kodu zaproszenia pokazywane dopiero, gdy API odpowie 403 `invite_required`
(`REGISTRATION_MODE=invite`). Po rejestracji od razu zalogowany. Błędy z API przy polu, którego dotyczą.

**Pulpit** (`/api/portfolio/summary`, `/api/portfolio/history`, `/api/portfolio/exposure`, `/api/positions`):
- nagłówek: wybór „Cały portfel” / jedno konto (`account_id` na wszystkich zapytaniach) i data wyceny (`as_of`);
- wartość portfela (duża kwota), zmiana dzienna zł i %, siatka: zysk łącznie, TWR, wpłacono, dywidendy i odsetki;
- wykres (§3) z zakresami 1M / 3M / 1R / Wszystko (domyślnie 1R; „Wszystko” od pierwszego punktu);
- alokacja z przełącznikiem Typ (`by_kind`) / Konto (`by_account`) / Waluta (bieżąca część `exposure`): pasek
  proporcji + wiersze (kolor, nazwa, kwota, udział);
- „Dziś najbardziej”: 3 pozycje (instrumenty) o największej bezwzględnej zmianie dnia w %
  (`day_change_pln / (value_pln − day_change_pln)`), z kwotą zmiany; link do listy pozycji;
- `approximate_positions > 0` → dopisek „N pozycji wycenionych w przybliżeniu”;
- `recalculating` → dyskretna informacja „Przeliczam wycenę…” i ponowne pobieranie co 3 s aż do `false`.

**Pozycje** (`/api/positions`): filtry-kafelki kont (Wszystkie + konta użytkownika); grupy: Akcje i ETF-y
(`kind = instrument`), Obligacje (`bond`), Konta i gotówka (`savings`, `cash`), każda z sumą. Wiersz: symbol
(`ticker`, dla obligacji „EDO”, dla konta „%”, dla gotówki „zł”), nazwa, konto + ilość + udział, wartość, zysk
niezrealizowany (kolor). Flagi (`flags`) → bursztynowy dopisek („cena przybliżona”, „brak kursu” itp. — słownik
flag po stronie frontendu z domyślnym „wycena przybliżona”). Dotknięcie instrumentu → szczegóły; obligacja /
konto / gotówka w 6a bez przejścia.

**Szczegóły pozycji** (`/api/positions/{account_id}/{instrument_id}`): nagłówek (nazwa, ticker, konto, wartość,
zysk), podsumowanie (ilość, średnia cena, cena i jej data/źródło, udział), rozbicie zysku (cena / waluta /
dywidendy / koszty), partie (data, cena, ilość, zysk, czas trzymania, SL/TP), sprzedaże, dywidendy, operacje,
status zgodności z XTB (zgodne / rozbieżność z opisem / brak migawki).

**Import XTB** (`/api/imports/preview`, `/api/imports`): wybór plików (`.xlsx`, `.zip`, wiele naraz; na komputerze
także przeciągnij i upuść) → podgląd per plik/rachunek: konto (istniejące albo „zostanie założone: IKE …”),
okres raportu, nowe / duplikaty / nierozpoznane, partie otwarte/zamknięte, ostrzeżenia uzgodnienia; błędy
plików (`errors`) i pominięte (`skipped`) osobno przy nazwie pliku → „Zapisz import” (wysyła te same pliki) →
podsumowanie zapisu → przejście na pulpit. Jeśli nic nowego, przycisk zapisu nieaktywny z wyjaśnieniem.

**Więcej:** e-mail zalogowanego (`/api/auth/me`), „Wyloguj”, lista pozycji z 6b jako wyłączone („wkrótce”).

## 3. Wykres wartości

- Seria z `/api/portfolio/history` (`from` wg zakresu, `account_id` wg wyboru): linia `value_pln` (`--amber`,
  2 px), **schodki** `invested_pln` (`--dim`, linia pozioma, potem pionowa — kapitał zmienia się skokiem w dniu
  wpłaty), pole między nimi `--amber-soft` (zysk) — gdy wartość spada poniżej kapitału, pole w odcieniu `--loss`.
- Znaczniki wpłat pod osią X: dni z `net_flow_pln > 0` (kreska, wyższa dla dużych wpłat — powyżej mediany).
- Oś Y po prawej: 3 zaokrąglone poziomy („150 tys.”), oś X: 4 etykiety miesięcy po polsku; punkt końcowy
  zaznaczony. Dotknięcie / najechanie pokazuje dzień: data, wartość, wpłacono.
- Czyste funkcje (`charts/`): skala, zaokrąglone poziomy siatki, ścieżka linii, ścieżka schodków, pole różnicy,
  wybór znaczników — testowane w Vitest. Komponent tylko je rysuje (SVG, `viewBox`, skalowanie do szerokości).

## 4. Architektura

- Katalog **`web/`**: React + TypeScript (strict) + Vite; `npm run dev` na porcie 5173 z **proxy `/api` →
  `http://localhost:8000`** (jedno źródło dla przeglądarki; ciasteczko `refresh_token` bez CORS).
- Biblioteki: React Router (trasy), TanStack Query (pobieranie, pamięć podręczna, unieważnianie),
  `vite-plugin-pwa` (manifest + service worker). **Style: CSS Modules + zmienne z §1, bez Tailwinda** i bez
  biblioteki komponentów; wykresy własne w SVG.
- Moduły (każdy z jednym zadaniem):
  - `api/` — `request()` (token w nagłówku, po 401 jedno odświeżenie `/api/auth/refresh` i powtórzenie, błąd
    `{code, message, details}` → `ApiError` z polskim komunikatem; błąd sieci → „Brak połączenia z serwerem”),
    ręcznie pisane typy odpowiedzi (kwoty jako `string`, jak w JSON), funkcja na endpoint.
  - `auth/` — access token tylko w pamięci, refresh w ciasteczku `httpOnly` (API); przy starcie aplikacji próba
    odświeżenia; ochrona tras; ekrany logowania i rejestracji.
  - `format/` — kwoty z `string` bez zamiany na float (dzielenie na złote i grosze na tekście; do skal wykresu
    `Number` wolno, bo to tylko piksele), procenty, daty po polsku, znak.
  - `charts/` — §3.
  - `ui/` — Kwota (duża z mniejszymi groszami / zwykła), przełącznik segmentowy, filtr kont, wiersz listy,
    stan ładowania (zarysy), stan pusty, stan błędu z „Spróbuj ponownie”, informacja o przeliczaniu.
  - `screens/` — Pulpit, Pozycje, SzczegółyPozycji, Import, Więcej, Logowanie, Rejestracja.
  - `styles/` — tokeny, reset, font.
- **PWA:** manifest (`name` „Portfel”, `display: standalone`, `background_color`/`theme_color` `#0E1116`, ikony
  192/512 + maskable + `apple-touch-icon`), meta `apple-mobile-web-app-*`, `viewport-fit=cover`; service worker
  zapamiętuje tylko pliki aplikacji (`/api` zawsze z sieci — żadnych nieaktualnych kwot offline).

## 5. Stany i błędy

- Ładowanie: zarysy wierszy i wykresu w miejscu treści.
- Pusty portfel (brak kont/transakcji): „Wgraj eksport z XTB, żeby zobaczyć swój portfel.” + przycisk
  „Wgraj pliki z XTB”.
- Błąd sekcji: komunikat z API w miejscu sekcji + „Spróbuj ponownie”; reszta ekranu działa.
- Sesja: nieudane odświeżenie → ekran logowania z „Sesja wygasła, zaloguj się ponownie.”
- Import: błąd jednego pliku nie blokuje podglądu pozostałych; błąd zapisu (całość albo nic) → komunikat, pliki
  zostają wybrane.

## 6. Testy

- **Vitest** (`npm test`): `format/`, `charts/`, `api/request` (podmieniony `fetch`: odświeżenie po 401, błąd
  API, błąd sieci), komponenty w React Testing Library — Pulpit na przykładowej odpowiedzi, stan pusty, podgląd
  importu z błędem jednego pliku, ochrona tras.
- **Playwright e2e** (`npm run e2e`): rejestracja → import syntetycznego eksportu → pulpit pokazuje wartość
  i wykres → pozycje → szczegóły pozycji. Plik XLSX generowany przez `api/tests/xtb_factory.py` (nie prawdziwe
  eksporty). Test działa na **osobnej bazie** (np. `portfolio_e2e`) i osobnej instancji API, żeby nie dotykać
  danych właściciela; bez połączeń z siecią zewnętrzną (worker nie jest uruchamiany).
- **Kontrola wyglądu:** zrzuty Playwright w szerokości 390 px (Pulpit, Pozycje, Szczegóły, Import) porównane
  z makietą przy odbiorze planu.

## Kryteria odbioru

1. Po `docker compose up` i `npm run dev` rejestracja, logowanie i wylogowanie działają; odświeżenie strony nie
   wylogowuje (sesja z ciasteczka).
2. Wgranie eksportów XTB przez ekran importu pokazuje podgląd zgodny z API i po zapisie pulpit z wartością,
   wykresem ze schodkami kapitału i alokacją.
3. Pozycje i szczegóły pozycji pokazują wszystkie pola z API w polskim zapisie kwot.
4. `npm test` i `npm run e2e` przechodzą; `pytest` bez zmian (API nietknięte poza wsparciem e2e).
5. Ekrany w 390 px odpowiadają makiecie (kolory, krój, kwoty, pasek).
