# Plan 7b — katalog instrumentów i symulator „co by było, gdyby” (decyzje projektowe)

**Data:** 2026-10-01
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §2 „Etap 2” (porównanie z benchmarkiem)
**Poprzednia część:** `2026-10-01-07a-returns-and-risk-design.md` (miary `analyze`, ekran Analiza, dymki `InfoTip`)

## Cel

Właściciel chce sprawdzać, jak wyglądałby jego portfel przy innych decyzjach, na jego prawdziwych wpłatach:
„gdybym zamiast w S&P 500 wpłacał w NASDAQ”, „gdybym co miesiąc dokładał 1000 zł w obligacje”, „gdyby każda
wpłata szła w MSCI World”. Wynik to linia wartości w czasie obok prawdziwego portfela i te same miary co w Analizie.

## Decyzje właściciela (2026-10-01)

1. Wszystkie trzy klocki: A „te same wpłaty, inny cel”, B „podmień instrument”, C „dopłacaj co miesiąc”.
2. Scenariusze są zapisywane (nazwa, wracanie, kilka naraz na wykresie).
3. Katalog: gotowa lista ok. 40 popularnych instrumentów + dopisanie własnego tickera (bez wyszukiwarki Yahoo —
   „wyjdzie na to samo”; można dołożyć później).
4. Historia emisji EDO od 2016 r. zapisana w aplikacji (dokładne obligacje w scenariuszach).
5. Scenariusze liczone tym samym silnikiem wyceny co prawdziwy portfel (w pamięci, bez zapisu).
6. Szczegóły ekranów do doszlifowania po wdrożeniu.

## 1. Katalog instrumentów

- Tabela `instruments` (wspólna) dostaje kolumny:
  - `in_catalog bool` (domyślnie false),
  - `catalog_group varchar(40) null` — grupa wyświetlania,
  - `accumulating bool null` — ETF akumulujący (dywidendy w cenie); null dla akcji i nieznanych.
- Grupy: „ETF: USA”, „ETF: świat”, „ETF: rynki wschodzące i Europa”, „ETF: Polska”, „Akcje USA”, „Akcje GPW”,
  „Surowce”, „Dodane przez Ciebie”.
- Lista startowa (~40 pozycji) w pliku danych w repozytorium, wczytywana migracją (upsert po `xtb_ticker`; istniejący
  instrument dostaje tylko `in_catalog`, grupę i `accumulating`). Preferowane notowania europejskie dostępne w XTB
  (np. SXR8.DE — S&P 500, SXRV.DE — NASDAQ-100, EUNL.DE — MSCI World, IS3N.DE — EM IMI). Każda pozycja przed wpisaniem
  na listę sprawdzona pobraniem notowań z Yahoo (`YahooPriceProvider`).
- Instrumenty z portfela użytkownika są pokazywane w katalogu w grupie „Twój portfel” (bez zmiany `in_catalog`).
- Dopisanie tickera (`POST /api/catalog`): symbol Yahoo (np. `VWCE.DE`); serwer pobiera historię; brak notowań →
  422 „Yahoo nie zna tego tickera”; jest → instrument z `in_catalog=true`, grupa „Dodane przez Ciebie”, nazwa i waluta
  z odpowiedzi Yahoo, ceny zapisane od razu (pełna historia). Ticker już w katalogu → 200 z istniejącym.
- Worker: instrumenty `in_catalog` są traktowane jak używane (`_referenced` rozszerzone) — pełna historia przy pierwszym
  razie, potem dzienne i śróddzienne odświeżanie jak dla portfela.

## 2. Historia emisji EDO

- Plik danych w repozytorium: `series, issue_month, first_period_rate, margin, early_redemption_fee` dla każdej emisji
  EDO od 01.2016. Migracja wstawia brakujące wiersze do `bond_series` (nie nadpisuje istniejących).
- Źródło: listy emisyjne z obligacjeskarbowe.pl (PDF-y z archiwum). Plan zawiera osobne zadanie zebrania danych i
  sprawdzenia ich na emisjach już wpisanych przez właściciela.
- CPI (GUS) musi obejmować okres od 2016 r.; jeśli tabela `cpi` zaczyna się później, worker dociąga starszą historię.

## 3. Scenariusz

Tabela `scenarios`: `id, user_id (FK, cascade), name varchar(80), base ('portfolio'|'deposits'), allocation JSONB,
steps JSONB, created_at, updated_at`. Liczony zawsze dla kont wybranych we wspólnym filtrze kont.

**Punkt wyjścia:**
- `portfolio` („Mój portfel”) — prawdziwe transakcje; działają klocki B i C.
- `deposits` („Moje wpłaty”, klocek A) — z prawdziwych transakcji zostają tylko przepływy zewnętrzne (wpłaty, wypłaty,
  przelewy z i na wybrane konta) z ich datami i kwotami w PLN. `allocation` = lista `{target, share_pct}` (suma 100):
  każda wpłata tego samego dnia jest dzielona i kupowana; wypłata sprzedaje proporcjonalnie z każdej części (EDO —
  wcześniejszy wykup z opłatą). Klocek C można dołożyć; B nie ma sensu (brak prawdziwych zakupów).

**Klocki (`steps`):**
- B `replace {from_instrument_id, to_instrument_id}` — zakup X → zakup Y za tę samą kwotę PLN tego samego dnia;
  sprzedaż X → sprzedaż tego samego ułamka pozycji Y; dywidendy X znikają. Tylko przy `portfolio`.
- C `recurring {amount_pln, day_of_month 1–28, start (miesiąc), end (miesiąc) | null, target, ike bool}` — co miesiąc
  zewnętrzna wpłata + zakup w pierwszy dzień sesji od dnia `day_of_month`.

**Cel (`target`):** `{instrument_id}` z katalogu albo `{bond: "EDO"}`.

**Zasady udawanych zakupów:**
- Cena zamknięcia z dnia zakupu; kurs NBP z tego dnia; +0,5 % przewalutowania XTB dla instrumentu w walucie innej niż
  PLN; ułamkowe jednostki; bez prowizji.
- EDO: całe obligacje po 100 zł z emisji z miesiąca zakupu; reszta zostaje gotówką; `ike=true` → bez podatku Belki
  przy wykupie (jak `wrapper` IKE/IKZE).
- Wartość liczona „do wypłaty” (koszty wyjścia z planu 6d), jak prawdziwy portfel.

**Liczenie:** klocki → lista `Entry` (udawane transakcje) i `Holding` (udawane obligacje) → istniejący silnik
(`replay`, `daily_rows`, `bond_rows`) w pamięci → dzienne sumy (dzień, wartość, przepływ) → `analytics.analyze`.
Na żądanie, bez cache'u (jeden właściciel, kilkaset dni).

**Dopiski (`notes`) zamiast błędów:**
- brak notowania celu w dniu zakupu (np. przed debiutem ETF-u) → kwota zostaje gotówką; dopisek „SXRV.DE ma notowania
  od 01.2017; wcześniejsze kwoty zostały w gotówce”;
- brak emisji EDO z danego miesiąca → kwota zostaje gotówką; dopisek „Brak parametrów emisji EDO z 11.2026 — dodaj ją w
  Dodaj → obligacja”;
- cel to akcja albo ETF dystrybuujący → dopisek „Dywidendy udawanych instrumentów nie są liczone”.

## 4. API

- `GET /api/catalog` → grupy z pozycjami `{id, ticker, name, currency, group, accumulating, prices_from}`.
- `POST /api/catalog {ticker}` → 201 / 200 / 422 (pkt 1).
- `GET /api/scenarios`, `POST /api/scenarios`, `GET/PATCH/DELETE /api/scenarios/{id}` — tylko własne (cudzy → 404).
  Walidacja: nazwa 1–80 znaków; `allocation` przy `deposits` niepusta, udziały > 0, suma 100; `replace` tylko przy
  `portfolio`; instrumenty muszą istnieć i być w katalogu albo w portfelu; `amount_pln` > 0; `day_of_month` 1–28;
  `end` ≥ `start`. Błędy 422 w formacie API.
- `GET /api/scenarios/{id}/result?period=…&account_id=…` i `POST /api/scenarios/preview` (body = scenariusz bez
  zapisu, te same parametry w query) →
  ```
  points   [{date, portfolio_pln, scenario_pln, invested_pln, scenario_invested_pln}]
  portfolio, scenario   miary jak AnalyticsOut z 7a (bez monthly i drawdown_series)
  notes    [string]
  recalculating bool
  ```
  Okres i filtr kont jak w `/api/analytics`.

## 5. Ekrany

- **Analiza:** nowa sekcja „Symulator” — do 3 ostatnich scenariuszy z różnicą względem portfela i link „Wszystkie
  scenariusze” + przycisk „Nowy scenariusz”.
- **`/analiza/symulator`:** wybór kont, przyciski okresu (układ z 7a), wykres porównawczy (portfel bursztynowy,
  scenariusze innymi kolorami, wpłacony kapitał cienką linią; legenda z przełącznikami widoczności), porównanie miar
  (wartość dziś, zysk, XIRR, TWR, maks. obsunięcie, zmienność; komputer: tabela miary × linie; telefon: karta na linię,
  bez poziomego przewijania; dymki „?”), lista scenariuszy z różnicą („+1 240 zł · +3,1 pkt XIRR”) → edycja.
  Wykres pokazuje wybrane scenariusze — każdy to osobne zapytanie `result`.
- **`/analiza/symulator/nowy` i `/:id`:** nazwa, punkt wyjścia (segment „Mój portfel” / „Moje wpłaty” + podział %),
  lista klocków z „Dodaj klocek” (Podmień / Dopłacaj), wybór instrumentu z katalogu (grupy, „Dodaj ticker”), podgląd
  wykresu na żywo (`preview`, z opóźnieniem po zmianie), Zapisz / Usuń (potwierdzenie), dopiski pod wykresem.
- Nowy `ComparisonChart` (kilka linii, mierzona szerokość jak `DrawdownChart`, bez przybliżania).

## 6. Testy

- Katalog: migracja listy (upsert), `POST /api/catalog` z atrapą dostawcy (znany, nieznany, istniejący), worker bierze
  instrumenty z katalogu.
- EDO: plik danych wczytany, istniejące serie nienadpisane; test na znanej emisji (np. EDO0616: 5,25 % w 1. roku).
- Klocki (czyste funkcje): podmiana zakupu i sprzedaży częściowej, wpłaty z podziałem i wypłata proporcjonalna,
  dopłaty miesięczne z dniem sesji, EDO w całych obligacjach z resztą w gotówce, 0,5 % przewalutowania, brak notowania
  → gotówka + dopisek, brak emisji → dopisek.
- Scenariusz bez klocków przy `portfolio` daje dokładnie linię prawdziwego portfela (test zgodności z `/api/analytics`).
- API: CRUD z izolacją użytkowników, walidacja, `result` i `preview`, filtr kont, okres.
- Web: lista i porównanie, edycja z podglądem, katalog z dopisaniem tickera, stany pusty/błąd; e2e: utworzenie
  scenariusza i jego linia na wykresie.

## Plany

Trzy plany pod tą specyfikacją: (1) dane — katalog, historia EDO, worker; (2) silnik scenariuszy i API; (3) ekrany.

## Poza zakresem

- Wyszukiwarka Yahoo (podpowiedzi przy wpisywaniu).
- Dywidendy udawanych instrumentów (ceny skorygowane o dywidendy).
- Inne obligacje niż EDO w scenariuszach, lokaty i konta oszczędnościowe jako cel.
- Przybliżanie wykresu porównawczego.
