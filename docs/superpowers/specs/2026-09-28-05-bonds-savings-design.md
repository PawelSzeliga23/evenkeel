# Plan 5: Obligacje EDO i konta oszczędnościowe (decyzje projektowe)

> Uzupełnienie specyfikacji `2026-09-26-portfolio-tracker-design.md` (§4 `bond_holdings`, `bond_series`,
> `savings_*`; §6 „Obligacje skarbowe”, „Konto oszczędnościowe”; §7) dla planu 5. Ustalone w rozmowie 2026-09-28.
> Materiał źródłowy: notatki „Spike 2026-09-26: zasady obligacji skarbowych” w `plans/2026-09-26-00-roadmap.md`
> (list emisyjny EDO0936). Na tym dokumencie powstaje plan `plans/2026-09-28-05-bonds-savings.md`.

## Zakres

1. Obligacje **EDO** (10-letnie, inflacyjne, odsetki kapitalizowane): zakupy, wycena dzienna, wcześniejszy wykup,
   harmonogram okresów. Model danych gotowy na inne rodzaje (`bond_type`, `interest_mode`, `rate_basis` w serii),
   ale silnik odsetek i testy zgodności — tylko EDO.
2. **Konta oszczędnościowe**: historia sald i stawek, odsetki między saldami, podatek przy kapitalizacji.
3. Wpięcie obu w `daily_valuations`, przeliczanie w tle, pulpit, pozycje, historię, TWR i ekspozycję.

Poza zakresem: COI, TOS, ROR, DOR, ROS, ROD, OTS, DOS (kolejny plan: silnik odsetek danego rodzaju + weryfikacja
jego listu emisyjnego), import historii rachunku obligacji z pliku, automatyczne pobieranie ofert serii z MF.

## 1. Model danych

- `bond_series` (wspólna, jak ceny): `series` (PK, np. `EDO0936`), `bond_type`, `issue_month` (miesiąc
  sprzedaży), `maturity_months` (EDO: 120), `first_period_rate` (%), `margin` (%), `early_redemption_fee`
  (zł za 1 szt. 100 zł), `interest_mode` (`capitalized` dla EDO), `rate_basis` (`cpi` dla EDO od 2. okresu).
  **Seed: EDO0936** — 5,35 % w 1. roku, marża 2,00 %, opłata 3,00 zł (oferta wrzesień 2026, list emisyjny
  sprawdzony w spike'u planu 2).
- `bond_holdings` (dane użytkownika, przez `UserScope`, konto `kind = 'bonds'`): `account_id`, `bond_type`,
  `series` (FK → `bond_series`), `quantity` (sztuki × 100 zł), `purchase_date` (dzień — okresy odsetkowe liczą się
  od dnia zakupu), `redeemed_at?` (wcześniejszy wykup), `note`.
- `savings_accounts` (1:1 z kontem `kind = 'savings'`): `capitalization` ∈ `daily | monthly | quarterly`.
  `savings_rates (valid_from, annual_rate)` — stawka **zawsze w skali roku**, jak podaje bank;
  `savings_balances (as_of_date, balance)` — saldo przepisane z banku.
- `daily_valuations` dostaje kolumny `bond_holding_id?` i `savings_account_id?` (zapowiedź z planu 4a); wiersz ma
  dokładnie jeden składnik (instrument / obligacja / konto oszczędnościowe) albo żaden (gotówka konta).

## 2. Wprowadzanie danych

- **Zakup obligacji**: rodzaj (EDO), liczba sztuk, dzień zakupu, konto. Seria wyliczana: EDO + miesiąc i rok
  wykupu (zakup 2026-09-x → `EDO0936`). Brak serii w tabeli → formularz przyjmuje `first_period_rate` i `margin`
  (opłata EDO domyślnie 3,00 zł) i dopisuje serię (wspólną; seria z tabeli jest tylko do odczytu).
- **Wcześniejszy wykup**: `redeemed_at` na zakupie — zawsze cały zakup. Wykup części sztuk jest poza zakresem
  (kolejny plan, gdy będzie potrzebny).
- **Konto oszczędnościowe**: kapitalizacja przy zakładaniu; stawki i salda dopisywane/usuwane w dowolnym momencie.

## 3. Wycena EDO (per zakup, każdy dzień)

- Okres k = rok od dnia zakupu (rocznica po rocznicy), k = 1…10; wykup w dniu 10. rocznicy.
- Stawka okresu: k = 1 → `first_period_rate`; k ≥ 2 → inflacja r/r ogłoszona przez GUS w miesiącu
  poprzedzającym pierwszy miesiąc okresu + `margin`; inflacja ujemna → 0. „Ogłoszona w miesiącu M−1” = wskaźnik
  za miesiąc M−2 z tabeli `cpi` (GUS publikuje dane za miesiąc w połowie następnego) — **do potwierdzenia przy
  pisaniu planu** na przykładzie ogłoszonej przez MF stawki 2. okresu którejś serii EDO.
- Wartość jednej obligacji w dniu d (list emisyjny, zał. 3): `WP_k = 100 · Π_{i<k}(1 + r_i) · (1 + r_k · a_k /
  ACT_k)`, `a_k` = dni od początku okresu k (włącznie) do d (wyłącznie), `ACT_k` = dni okresu k; na 1 szt.,
  zaokrąglone do grosza. W dniu wykupu: `100 · Π(1 + r_i)`.
- **Wartość bieżąca netto** (do portfela): `ilość × (WP − 19 % · (WP − 100))`, na IKE/IKZE bez podatku. Podatek
  liczony na 1 szt. i zaokrąglany do grosza — **do potwierdzenia** z kalkulatorem MF (per sztuka vs per zakup).
- **Wartość przy wykupie dziś**: opłata = min(`early_redemption_fee`, odsetki na 1 szt.); kwota = `WP − opłata −
  19 % · (odsetki − opłata)`; próg: `WP_k < 100 → 100` przed podatkiem (EDO nie traci kapitału).
- **Brak inflacji** potrzebnej do okresu (GUS nie ogłosił / worker nie pobrał): stawka poprzedniego okresu i flaga
  `rate_estimated` w wierszu i w API (jak `xtb_price`).
- Po `redeemed_at` lub wykupie zakup nie ma wartości; kwota wykupu jest wypłatą z konta.
- **Test akceptacyjny**: zgodność z kalkulatorem obligacjeskarbowe.pl do 0,01 zł na 1 szt. dla kilku dat
  (1. okres, po rocznicy, dzień przed wykupem, wcześniejszy wykup w 1. i w 3. roku).

## 4. Konto oszczędnościowe

- Saldo na dzień d = ostatnie wpisane saldo ≤ d + odsetki od tamtego dnia: w każdym dniu kapitalizacji
  (dziennie / ostatni dzień miesiąca / kwartału) dopisywane są odsetki netto = `saldo × stawka_roczna × dni /
  365` − 19 % podatku (na IKE/IKZE bez podatku), zaokrąglone do grosza; stawka dnia z `savings_rates`.
- Wpisane saldo różne od wyliczonego na ten dzień → różnica jest **wpłatą / wypłatą** użytkownika (`net_flow_pln`),
  więc wpłacony kapitał i TWR się zgadzają bez wpisywania każdej operacji. Pierwsze saldo = wpłata.

## 5. Przepływy i przeliczanie

- Zakup obligacji = wpłata na konto obligacji (`net_flow_pln = ilość × 100`), wykup = wypłata (kwota netto).
- Zapis zakupu / wykupu / serii / salda / stawki oznacza właściciela do przeliczenia od daty zmiany (znacznik
  `valuations_stale_from`, przeliczenie w tle jak po imporcie). Nowe wskaźniki CPI z workera oznaczają
  posiadaczy EDO od początku okresów, których stawka się zmieniła.
- Pulpit, alokacja (typy „Obligacje”, „Konta oszczędnościowe”), historia, TWR i ekspozycja (PLN) czytają
  `daily_valuations`, więc obejmują nowe składniki bez osobnej logiki.

## 6. API

| Endpoint | Co robi |
|---|---|
| `GET/POST /api/bonds`, `PATCH/DELETE /api/bonds/{id}` | zakupy obligacji; `PATCH` m.in. `redeemed_at` |
| `GET /api/bonds/{id}` | wartość bieżąca netto, wartość przy wykupie dziś, harmonogram okresów i stóp (flaga szacunku) |
| `GET/POST /api/bond-series` | serie (seed + dopisane); dopisana seria: stawka 1. roku, marża, opłata |
| `GET/POST/DELETE /api/savings-accounts/{account_id}/balances`, `…/rates` | historia sald i stawek |
| `GET /api/positions` | + pozycje obligacji (per zakup) i kont oszczędnościowych (spec §7) |

Izolacja jak dotąd: zakupy, salda i stawki przez `UserScope` (obce → 404); serie wspólne.

## Błędy i testy

404 dla cudzych zasobów, 422 z kodem dla złych danych (np. zakup na koncie innego typu, ilość ≤ 0, seria
niezgodna z rodzajem i datą), 409 dla duplikatu (saldo / stawka z tą samą datą). Testy silnika EDO na liczbach z
kalkulatora MF (sekcja 3), testy konta oszczędnościowego (kapitalizacja miesięczna z podatkiem, saldo jako
wpłata), testy przeliczania i API z izolacją użytkowników.
