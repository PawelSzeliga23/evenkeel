# Portfolio Tracker — specyfikacja projektu

- **Data:** 2026-09-26
- **Status:** do akceptacji
- **Autorzy:** właściciel produktu + Claude

## 1. Cel i kontekst

Aplikacja webowa (PWA) dająca łatwy, szczegółowy wgląd w cały portfel inwestycyjny: akcje i ETF-y
z XTB (rachunek zwykły i IKE), obligacje skarbowe, konta oszczędnościowe i gotówkę.

- **Najpierw dla właściciela**, potem dla znajomych — od początku wielu użytkowników z pełną izolacją danych.
- **Rejestracja publiczna**, z możliwością zamknięcia przełącznikiem konfiguracyjnym.
- **Szczegółowość ponad prostotę:** każda kolumna z eksportu XTB trafia do bazy; każda otwarta pozycja
  ma pełny widok szczegółów.
- **Mobile-first:** aplikacja jest dodawana do ekranu początkowego iPhone'a i ma działać jak natywna.

### Kryteria sukcesu (etap 1)

1. Wgranie eksportów XTB (pliki / ZIP / folder) odtwarza pełną historię obu rachunków bez duplikatów,
   a stan pozycji zgadza się z zakładką *Open Positions* z XTB.
2. Obligacje skarbowe wpisane jako (rodzaj, liczba sztuk, miesiąc zakupu) mają wartość bieżącą
   i wartość przy wcześniejszym wykupie zgodną z oficjalnym kalkulatorem co do 0,01 zł na obligację.
3. Wykres wartości całego portfela dzień po dniu od pierwszej transakcji, z podziałem na instrumenty
   i znacznikami wpłat/zakupów/sprzedaży/dywidend.
4. Użytkownik B nigdy nie widzi danych użytkownika A (test automatyczny).
5. Wygodne użycie na iPhonie jako PWA.

### Poza zakresem (na teraz)

- Rozliczenia podatkowe / PIT-38.
- Brokerzy inni niż XTB, połączenia API z brokerami.
- Wdrożenie na serwer domowy (Debian + Docker + Cloudflare Tunnel) — architektura ma to umożliwiać,
  ale etap 1 działa lokalnie.
- Jasny motyw, aplikacja natywna, powiadomienia.

## 2. Etapy

**Etap 1 — „widzę cały portfel”**
- Konta użytkowników (rejestracja, logowanie).
- Import XTB (XLSX, wiele plików, ZIP, folder) z podglądem przed zapisem.
- Obligacje skarbowe (ręcznie), konta oszczędnościowe (ręcznie), ręczne operacje.
- Codzienne dane rynkowe: ceny, kursy NBP, inflacja GUS, stopy NBP.
- Pulpit: łączna wartość, zmiana dzienna i łączna, **wykres wartości w czasie** (z wpłatami i wpłaconym kapitałem),
  alokacja, zysk/strata, dywidendy i odsetki.
- Lista pozycji i ekran szczegółów pozycji (partie, dywidendy, efekt walutowy).
- Historia operacji.

**Etap 2 — „analiza”**
- Wykres ceny instrumentu z zaznaczonymi zakupami/sprzedażami.
- Statystyki i ryzyko: zmienność, maksymalne obsunięcie (max drawdown), wskaźnik Sharpe'a,
  najlepszy/najgorszy dzień, porównanie z benchmarkiem (S&P 500, WIG).

## 3. Stack i architektura

| Warstwa | Technologia |
|---|---|
| Frontend | React + TypeScript + Vite, PWA (manifest + service worker), mobile-first |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| Baza | PostgreSQL 16 |
| Obliczenia | Python (decimal; pandas/numpy tam, gdzie pomagają przy szeregach czasowych) |
| Uruchomienie lokalne | `docker compose` (postgres, api, worker); frontend przez `npm run dev` |
| Docelowo (poza zakresem) | Debian + Docker Compose + Cloudflare Tunnel (`cloudflared`) |

```
web/ (React PWA) ── HTTP/JSON ──► api/ (FastAPI)
                                   ├─ auth        rejestracja, logowanie, JWT
                                   ├─ imports     parser XTB → podgląd → zapis
                                   ├─ holdings    konta, transakcje, partie, obligacje, oszczędności
                                   ├─ valuation   wycena na dzień, zysk/strata, TWR
                                   ├─ bonds       silnik obligacji skarbowych
                                   ├─ market      dostawcy danych rynkowych (interfejsy)
                                   └─ analytics   (etap 2) statystyki i ryzyko
                                  worker (ten sam obraz, inne polecenie)
                                   └─ harmonogram: dane rynkowe → przeliczenie daily_valuations
                                  postgres
```

### Zasady architektoniczne

1. **Transakcje są źródłem prawdy.** Pozycje, zyski i historia wartości są wyliczane z transakcji
   i danych rynkowych. `daily_valuations` to wyłącznie pamięć podręczna, którą można skasować i odbudować.
2. **Import idempotentny.** Każda operacja XTB ma unikalny `external_id` w obrębie konta; ponowny import niczego nie dubluje.
3. **Nic nie ginie przy imporcie.** Każdy wiersz jest zapisywany także w postaci surowej (`raw JSONB`).
4. **Silnik wyceny i obligacji to czyste funkcje** (bez bazy i HTTP) — testowalne na przykładach.
5. **Pieniądze jako `NUMERIC` / `Decimal`**, nigdy float.
6. **Izolacja użytkowników w jednej warstwie dostępu** — każde zapytanie o dane użytkownika przechodzi
   przez wspólny mechanizm filtrujący po `user_id`, nie ręcznie w endpointach.
7. **Źródła danych rynkowych za interfejsami** (`PriceProvider`, `FxProvider`, `InflationProvider`,
   `RefRateProvider`) — wymiana źródła nie zmienia reszty kodu.

## 4. Model danych

### Dane użytkownika

```
users              id, email (unique), password_hash, base_currency='PLN', created_at

accounts           id, user_id, name, kind (broker|bonds|savings|cash),
                   wrapper (regular|ike|ikze), broker ('xtb'|null),
                   external_account_number (np. '56216965'), currency, created_at
                   UNIQUE (user_id, broker, external_account_number)

instruments        id, xtb_ticker ('SXR8.DE'), name, category (stock|etf|...),
                   currency, exchange_suffix, price_symbol (symbol u dostawcy cen),
                   price_symbol_overridden (bool), isin?        ← wspólne dla wszystkich

transactions       id, account_id, instrument_id?, type, xtb_type (oryginalny tekst),
                   occurred_at (UTC), amount (w walucie konta), currency,
                   quantity?, price? (w walucie instrumentu), implied_fx_rate?,
                   xtb_position_id?, external_id, comment, raw JSONB,
                   transfer_pair_id? (powiązanie transferu wewnętrznego), import_id
                   UNIQUE (account_id, external_id)
   type ∈ buy | sell | dividend | withholding_tax | interest | interest_tax |
          deposit | withdrawal | transfer_in | transfer_out | fee | unknown

position_lots      id, account_id, instrument_id, xtb_position_id, side, quantity,
                   open_price, opened_at, open_commission, swap, rollover, margin,
                   stop_loss, take_profit, closed_at?, close_price?, close_origin?,
                   open_conversion_rate?, close_conversion_rate?, raw JSONB
                   UNIQUE (account_id, xtb_position_id)

xtb_snapshots      id, import_id, account_id, instrument_id?, xtb_position_id?,
                   row_kind (instrument_summary|lot|account_summary),
                   volume, value, current_price, net_profit, net_profit_pct,
                   gross_profit, taken_at, raw JSONB        ← do kontroli zgodności

bond_holdings      id, account_id, bond_type (OTS|ROR|DOR|DOS|TOS|COI|EDO|ROS|ROD),
                   series ('EDO0336'), quantity (szt. × 100 zł), purchase_date,
                   redeemed_at?, note

savings_accounts   id, account_id, capitalization (daily|monthly|quarterly)
savings_balances   id, savings_account_id, as_of_date, balance     (historia sald)
savings_rates      id, savings_account_id, valid_from, annual_rate (historia stawek)

imports            id, user_id, account_id, filename, file_hash, report_from, report_to,
                   imported_at, rows_added, rows_duplicate, rows_unknown, status
```

### Dane rynkowe (wspólne)

```
prices             instrument_id, date, close, source          PK (instrument_id, date)
fx_rates           currency, date, rate_pln (NBP tabela A)     PK (currency, date)
cpi                year_month, yoy                              (GUS, r/r)
nbp_ref_rates      valid_from, rate                             (stopa referencyjna NBP)
bond_series        series, bond_type, issue_month, maturity_months, first_period_rate,
                   margin, early_redemption_fee (za 100 zł), interest_mode
                   (capitalized|paid_annually|paid_monthly|fixed_at_maturity), rate_basis
                   (fixed|cpi|nbp_ref)
```

### Pamięć podręczna wyceny

```
daily_valuations   user_id, account_id, instrument_id? | bond_holding_id? | savings_account_id?,
                   date, quantity, value_pln, cost_pln, net_flow_pln, flags
                   ← przeliczana od najwcześniejszej zmienionej daty
```

## 5. Import XTB

### Ustalony format (na podstawie prawdziwych eksportów)

- **Nazwa pliku:** `{PLN|IKE}_{nr_rachunku}_{od}_{do}.xlsx`.
- **Zakładki:** `Closed Positions`, `Cash Operations`, `Open Positions`.
- Każda zakładka ma **4–8 wierszy metadanych** przed tabelą (`Account number`, zakres dat lub
  „Data as of report generated”, podsumowanie wartości) oraz **wiersz sumy na końcu** (`Total`, `Profit/loss`).
  Parser lokalizuje wiersz nagłówków **po nazwach kolumn**, a wiersze sum pomija.
- **Pułapka:** w pliku IKE zakładka *Open Positions* zawiera w metadanych numer rachunku **zwykłego**.
  Rachunek ustala się z nazwy pliku i z *Cash Operations*; niezgodność jest ignorowana, a nie traktowana jako błąd.

**Cash Operations** — kolumny: `Type, Instrument, Ticker, Category, Time, Amount, ID, Comment, Product, Position ID`.

| `Type` (XTB) | Komentarz (wzorzec) | Typ w aplikacji |
|---|---|---|
| `Stock purchase` | `OPEN BUY {qty} @ {price}` | `buy` |
| `Stock sale` * | `CLOSE BUY {qty}/{total} @ {price}` | `sell` |
| `Deposit` | `… BLIK/PAYU deposit …` | `deposit` |
| `IKE deposit` | `Transfer out operation on account with id {n}` | `transfer_out` |
| `IKE deposit` | `Transfer in operation on account with id {n}` | `transfer_in` |
| `DIVIDENT`/`Dividend` * | — | `dividend` |
| `Withholding tax` * | — | `withholding_tax` |
| `Free-funds Interest` * | — | `interest` |
| `Free-funds Interest Tax` * | — | `interest_tax` |
| `Withdrawal` * | — | `withdrawal` |
| inne | — | `unknown` (+ ostrzeżenie w UI) |

\* typy niewystępujące jeszcze w eksportach właściciela — reguły oparte na znanym formacie XTB,
do potwierdzenia pierwszym prawdziwym wystąpieniem. Każdy nierozpoznany typ lub komentarz zapisuje się
jako `unknown` z pełnymi surowymi danymi; nigdy nie jest odrzucany po cichu.

- `Amount` jest w walucie rachunku (PLN); cena w komentarzu jest w walucie instrumentu.
  `implied_fx_rate = |amount| / (qty × price)` — faktyczny kurs XTB dla danej transakcji.
- `transfer_out` i `transfer_in` z różnych rachunków tego samego użytkownika są łączone
  (`transfer_pair_id`) po kwocie, czasie i numerach rachunków z komentarza; nie są wpłatą z zewnątrz.

**Open Positions** — kolumny: `Product, Instrument/Position, Ticker, Category, Type, Volume, Value,
Current price, Open price, Open time (UTC), Stop Loss, Take Profit, Net Profit %, Net Profit,
Gross Profit, Margin, Open Commission, Swap, Rollover`. Dwa rodzaje wierszy:
- **wiersz zbiorczy instrumentu:** pusty `Type`, `Instrument/Position` = nazwa instrumentu, `Category` wypełnione
  → `xtb_snapshots(row_kind=instrument_summary)` + uzupełnienie nazwy/kategorii instrumentu;
- **wiersz partii:** `Type=BUY`, `Instrument/Position` = numer pozycji → `position_lots` + `xtb_snapshots(row_kind=lot)`.
- Wiersze podsumowania rachunku z metadanych (`Open position value`, `Open position profit`)
  → `xtb_snapshots(row_kind=account_summary)`.

**Closed Positions** — kolumny: `Instrument, Ticker, Category, Type, Volume, Open Price, Open Time (UTC),
Close Price, Close Time (UTC), Product, Profit/Loss, Gross Profit, Purchase Value, Sale Value, Stop Loss,
Take Profit, Commission, Margin, Swap, Rollover, Open Conversion Rate, Close Conversion Rate,
Close Origin, Position ID, Comment` → uzupełnia `position_lots` (zamknięcie, kursy przewalutowania).

### Uzgodnienie
Po imporcie: ilości na instrument wyliczone z transakcji muszą się zgadzać z wierszami zbiorczymi
*Open Positions*. Niezgodność → ostrzeżenie widoczne przy imporcie i na pozycji (nie blokuje zapisu).

### Przepływ w UI
1. Wybór: drag & drop (desktop) lub wybór plików (mobile); akceptowane: `.xlsx`, `.zip`, wiele plików, folder.
2. Serwer rozpakowuje ZIP w pamięci (limity: rozmiar spakowany, rozpakowany, liczba plików), rozpoznaje
   rachunek każdego pliku, parsuje.
3. **Podgląd** per rachunek: nowe / duplikaty / nierozpoznane / ostrzeżenia uzgodnienia; przy nowym
   rachunku propozycja utworzenia konta (typ `ike` dla prefiksu `IKE`).
4. Zatwierdzenie → zapis w jednej transakcji bazodanowej → przeliczenie `daily_valuations`.
5. Plik nie jest przechowywany; zostaje `file_hash` i wynik importu.

### Mapowanie tickerów
Ticker XTB (`SXR8.DE`, `EIMI.UK`, `VIE.FR`, `.US`, `.PL`) → symbol dostawcy cen przez regułę sufiksów,
z możliwością ręcznej korekty w ustawieniach. Brak cen u dostawcy → wycena ostatnią ceną z importu XTB,
z oznaczeniem „wycena przybliżona”.

## 6. Silnik wyceny

### Akcje / ETF-y
- Wartość w dniu D = ilość(D) × cena zamknięcia (ostatnia ≤ D) × kurs NBP(D) → PLN.
- Koszt partii w PLN = faktyczna kwota z operacji gotówkowej XTB.
- Zysk niezrealizowany partii = wartość − koszt, rozbity na **efekt ceny** i **efekt walutowy**:
  - efekt ceny = qty × (cena_D − cena_zakupu) × kurs_zakupu
  - efekt walutowy = qty × cena_D × (kurs_D − kurs_zakupu)
- Zysk zrealizowany: dokładne dopasowanie sprzedaży do partii po `xtb_position_id` (bez FIFO).
- Dywidendy netto = dywidenda − podatek u źródła, przypisane do instrumentu i konta.
- Gotówka na rachunku = suma operacji gotówkowych rachunku.
- Konto `ike`/`ikze`: bez naliczania podatku Belki.

### Obligacje skarbowe
- Wejście: rodzaj, liczba sztuk (lub kwota ÷ 100), miesiąc zakupu, konto. Seria wyliczana z rodzaju i daty.
- Oprocentowanie okresu: stałe (OTS, TOS, DOS, 1. okres pozostałych) / inflacja GUS r/r + marża
  (COI, EDO, ROS, ROD od 2. okresu) / stopa referencyjna NBP + marża (ROR, DOR).
- Tryb odsetek: kapitalizacja (EDO, TOS, ROS, ROD), wypłata roczna (COI), miesięczna (ROR, DOR),
  w dniu wykupu (OTS). Wypłacone odsetki są przychodem (jak dywidenda).
- Wyniki:
  - **wartość bieżąca netto** = nominał + naliczone odsetki − podatek 19% od odsetek (0 na IKE/IKZE);
  - **wartość przy wykupie dziś** = nominał + naliczone odsetki − opłata za wcześniejszy wykup
    (za sztukę, nie więcej niż naliczone odsetki) − podatek od (odsetki − opłata).
- **Do weryfikacji przed implementacją** (z listów emisyjnych MF, nie z pamięci): dokładna reguła wyboru
  miesiąca inflacji, naliczanie odsetek w trakcie okresu (dni rzeczywiste / dni okresu), zaokrąglenia,
  aktualne opłaty za wcześniejszy wykup per seria, dostępność wcześniejszego wykupu per rodzaj.
- Test akceptacyjny: zgodność z kalkulatorem obligacjeskarbowe.pl do 0,01 zł na obligację dla
  reprezentatywnego zestawu (każdy rodzaj, różne daty).

### Konto oszczędnościowe
- Saldo z historii sald + naliczone odsetki od ostatniego salda wg historii stawek i kapitalizacji,
  z potrąceniem 19% przy każdej kapitalizacji.

### Historia wartości i zwrot
- `daily_valuations` dla każdego dnia od pierwszej transakcji, per konto i składnik.
- Przepływy zewnętrzne (`deposit`, `withdrawal`) oznaczone w `net_flow_pln`; transfery wewnętrzne się znoszą.
- **Wpłacony kapitał** = skumulowane przepływy zewnętrzne.
- **Zwrot TWR** (time-weighted) liczony z dziennych wartości i przepływów — podstawa porównań z benchmarkiem.
- Przeliczanie: po imporcie / edycji → od najwcześniejszej zmienionej daty; po nowych danych rynkowych → od najwcześniejszej nowej daty.

### Dane rynkowe (worker)
- Codziennie po zamknięciu sesji: ceny (dostawca domyślny: Stooq), kursy NBP (tabela A), inflacja GUS,
  stopa referencyjna NBP. Przy nowym instrumencie — pobranie pełnej historii.
- **Ryzyko do sprawdzenia na starcie implementacji:** dostępność darmowego pobierania ze Stooq
  i pokrycie tickerów z giełd DE/UK/FR. Plan B: `yfinance`. Wybór za interfejsem `PriceProvider`.
- Brak notowania w dniu D → ostatnia znana cena. Błąd źródła → ponowienie, log, UI pokazuje „ceny z dnia X”.

## 7. Ekrany (mobile-first)

Nawigacja: dolny pasek (mobile), boczne menu (desktop).

1. **Pulpit** — łączna wartość, zmiana dzienna i łączna (zł, %), wykres wartości (1M/3M/1R/wszystko)
   z linią wpłaconego kapitału i znacznikami wpłat, alokacja (typ aktywa / waluta / konto),
   największe wzrosty i spadki dnia.
2. **Pozycje** — lista instrumentów, obligacji, kont oszczędnościowych i gotówki: wartość, zysk, udział;
   filtr po koncie. **Szczegóły pozycji:** podsumowanie (ilość, średnia cena, wartość, udział), zysk rozbity
   na cenę / walutę / dywidendy / koszty, lista partii (data, cena, ilość, zysk, czas trzymania, SL/TP),
   dywidendy, historia operacji, status zgodności z XTB, wykres (etap 2). Dla obligacji: wartość bieżąca,
   wartość przy wykupie dziś, harmonogram okresów i stóp.
3. **Historia** — wszystkie operacje, filtry (konto, typ, instrument, daty), wyszukiwanie.
4. **Dodaj** — import XTB, obligacja, konto oszczędnościowe (saldo, stawka), ręczna operacja.
5. **Ustawienia** — konta, mapowanie tickerów, profil.

### Kierunek wizualny (realizuje skill `frontend-design`)
- Ciemny, spokojny, nowoczesny (w duchu Linear / Vercel); tylko motyw ciemny na start.
- **Jeden akcent: pomarańczowy/bursztynowy** — interakcje, aktywne elementy, linia portfela na wykresach.
  Musi być wyraźnie odróżnialny od czerwieni straty.
- Zysk/strata: stonowana zieleń / czerwień.
- Cyfry tabelaryczne (tabular numbers) w kwotach.
- PWA: manifest, ikony, `display: standalone`, obsługa safe-area iPhone'a.

## 8. Bezpieczeństwo

- Rejestracja publiczna; `REGISTRATION_MODE=open|invite` w konfiguracji (domyślnie `open`).
- Hasła: Argon2. Access token JWT (15 min) + refresh token (30 dni) w ciasteczku `httpOnly`, `Secure`, `SameSite=Lax`.
- Rate limiting logowania i rejestracji.
- Izolacja danych w jednej warstwie dostępu + test „B nie widzi A” dla każdego zasobu.
- Upload: limity rozmiaru pliku, ZIP-a (spakowany i rozpakowany) i liczby plików; tylko `.xlsx` w środku;
  parsowanie w pamięci; pliki nie są przechowywane.
- Sekrety wyłącznie w `.env` (poza gitem); `samples/` poza gitem.

## 9. Obsługa błędów

- Import transakcyjny (całość albo nic) z podglądem przed zapisem.
- Brak ceny / kursu / inflacji → wycena z flagą „przybliżona” i powodem, bez przerywania.
- Nierozpoznane operacje → `unknown`, widoczne w UI do wyjaśnienia.
- Błędy API w spójnym formacie (`{code, message, details}`), komunikaty dla użytkownika po polsku.

## 10. Testy

- **Parser XTB:** zanonimizowane kopie prawdziwych eksportów (struktura prawdziwa, liczby podmienione)
  w `api/tests/fixtures/` + ręcznie przygotowane przypadki (sprzedaż, dywidenda, podatek, nieznany typ, transfer IKE).
- **Silnik wyceny:** przykłady z oczekiwanym wynikiem — obligacje vs oficjalny kalkulator, rozbicie efektu
  ceny/waluty, TWR na scenariuszu z wpłatą, konto oszczędnościowe z kapitalizacją.
- **API:** pytest + Postgres w Dockerze; izolacja użytkowników; idempotencja importu.
- **Frontend:** Vitest (logika, formatowanie kwot/dat); Playwright e2e: rejestracja → import → pulpit.

## 11. Struktura repozytorium

```
founder/
  api/                  FastAPI + worker (Python 3.12), Alembic, testy
  web/                  React + TS + Vite (PWA)
  samples/              prywatne eksporty XTB (w .gitignore)
  docs/superpowers/specs/
  docker-compose.yml    postgres + api + worker
  .env.example
```
