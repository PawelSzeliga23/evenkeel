# Plan 6d — wycena „do wypłaty” i drobiazgi: decyzje projektowe

**Data:** 2026-09-30
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §6 „Akcje / ETF-y” (uzupełnienie), §7.
**Diagnoza:** roadmapa, „Diagnoza zawyżonej wyceny (2026-09-29)”.
**Poprzednie decyzje:** `2026-09-28-06a-frontend-foundation-design.md`, `2026-09-29-06b-add-and-history-design.md`,
`2026-09-29-06c-overview-and-settings-design.md`.

## Cel

Aplikacja wycenia pozycje w walucie obcej po średnim kursie NBP i cenie zamknięcia, więc pokazuje o ok. 0,5–0,8 %
więcej niż XTB (właściciel: aplikacja ≈ 1 723 zł, XTB ≈ 1 710 zł). XTB przy sprzedaży pobiera 0,5 %
za przewalutowanie, a sprzedaje się po cenie bid. Plan 6d wprowadza **wartość do wypłaty**: wartość rynkowa minus
koszty wyjścia. Wartość do wypłaty ma się zgadzać z tym, co pokazuje XTB (bez podatku Belki, którego XTB nie
odejmuje). Przy okazji: trzy poprawki wyglądu zgłoszone przez właściciela i wybrane drobiazgi z przeglądów 6a–6c.

## Decyzje właściciela (2026-09-30)

1. „Do wypłaty” = tyle, ile pokazuje XTB: wartość minus przewalutowanie i ewentualny spread. Bez podatku.
2. Wartość do wypłaty obowiązuje wszędzie: główna liczba, wykres, TWR, Pozycje. Koszty wyjścia liczymy dla każdego
   dnia i zapisujemy.
3. Spread nie jest zgadywany. Automatycznie odejmujemy tylko przewalutowanie 0,5 %. Spread można wpisać ręcznie
   per instrument; domyślnie brak.
4. Drobiazgi: te widoczne dla właściciela i te, które mogą coś zepsuć (lista w §3). Reszta zostaje w roadmapie.

## Podział na plany

Trzy plany na jednej gałęzi `feature/plan-6d`, wykonywane po kolei:

- `6d-backend`: migracja, silnik wyceny, API, blokada wypłat z konta oszczędnościowego.
- `6d-frontend-1`: Pulpit, Pozycje, szczegóły pozycji, spread w Ustawieniach.
- `6d-frontend-2`: pozostałe drobiazgi, test e2e, roadmapa.

## 1. Backend

### 1.1 Dane
- Migracja `0009`:
  - `daily_valuations.exit_cost_pln NUMERIC(20,4) NOT NULL DEFAULT 0`.
  - `instruments.spread_pct NUMERIC(6,4) NULL`: ręczny połowiczny spread w procentach (np. `0.1000` = 0,10 %).
    `NULL` znaczy brak. Dozwolony zakres 0–5.
- Instrumenty są wspólne dla wszystkich użytkowników, tak jak `price_symbol`, więc spread też jest wspólny.

### 1.2 Reguła kosztów wyjścia
- Stała `XTB_FX_FEE = Decimal("0.005")` w module wyceny.
- **Pozycja** (wiersz z `instrument_id`), wartość rynkowa `V`:
  - przewalutowanie: `V × 0,005`, jeśli konto ma `broker == "xtb"` **i** waluta notowania instrumentu albo waluta
    rachunku jest różna od PLN;
  - spread: `V × spread_pct / 100`, jeśli instrument ma `spread_pct`;
  - `exit_cost_pln = money(przewalutowanie + spread)`.
- **Pozycja wyceniona z liczb XTB** (brak ceny od dostawcy, flaga `xtb_price`): bez kosztów wyjścia. Wartość z
  eksportu XTB jest już wyceną XTB. Do sprawdzenia przy pisaniu planu, czy tak jest w eksporcie; jeśli nie, plan
  opisuje, co zmienić.
- **Gotówka** na koncie XTB w walucie innej niż PLN: `money(V × 0,005)`. Gotówka w PLN: 0.
- **Obligacje, konta oszczędnościowe, konta gotówkowe spoza XTB:** 0.
- Wartość ujemna albo zero: koszt 0.

### 1.3 Silnik i odczyty
- `PositionView` i `Row` dostają `exit_cost_pln`. `LotView` też, proporcjonalnie do wartości partii, a suma partii
  równa się kosztowi pozycji co do grosza (reszta z zaokrągleń trafia do ostatniej partii).
- Podział zysku niezrealizowanego: `efekt ceny + efekt waluty − koszty wyjścia = wartość do wypłaty − koszt zakupu`.
  Sumuje się co do grosza.
- Nazwy w API: `value_pln` zostaje wartością rynkową. Nowe pola to `exit_cost_pln` i `payout_pln`
  (= `value_pln − exit_cost_pln`). `unrealized_pln` i procent zysku liczą się od `payout_pln`.
- **Od wartości do wypłaty liczą się:** podsumowanie Pulpitu (wartość, zmiana dnia, zysk), historia wartości
  (wykres), TWR, lista pozycji, szczegóły pozycji, alokacja na Pulpicie.
- **Bez zmian:** ekspozycja walutowa (wartość rynkowa, bo to udziały), zamknięte inwestycje (faktyczne kwoty
  sprzedaży), limity IKE/IKZE, wartości obligacji i kont oszczędnościowych (ich koszt wyjścia jest 0).
- `SummaryOut` dostaje `market_value_pln` i `exit_cost_pln` obok obecnej wartości, która staje się wartością do
  wypłaty.

### 1.4 Spread w API
- `PATCH /api/instruments/{id}` (tam, gdzie dziś zmienia się symbol ceny) przyjmuje `spread_pct: Decimal | null`.
  Poza zakresem 0–5 → `422 validation_error`.
- Zmiana spreadu oznacza do przeliczenia wyceny posiadaczy instrumentu (`holders` + `mark_stale` od `date.min`) i
  przelicza je w tle, tak jak zmiana symbolu.
- Instrument w odpowiedziach dostaje `spread_pct`.

### 1.5 Blokada wypłat z konta oszczędnościowego (drobiazg 7)
- `_check_balance` w `api/app/savings/router.py` najpierw bierze `lock_user` dla właściciela. Dwie równoczesne
  wypłaty nie mogą obie przejść. Test: dwie wypłaty w dwóch sesjach, druga dostaje `422 insufficient_balance`.

### 1.6 Po wdrożeniu
- Migracja, a potem przeliczenie wycen wszystkich użytkowników od początku (`mark_stale` od `date.min`), żeby cała
  historia wykresu była „do wypłaty”. Na bazie właściciela robimy to za jego zgodą.

## 2. Frontend: wycena

### 2.1 Pulpit
- Duża liczba to wartość do wypłaty.
- Pod nią przyciemniony wiersz „Wartość rynkowa X · koszty wyjścia −Y”, tylko gdy `exit_cost_pln > 0`.
- Wykres i odczyt dnia pokazują wartość do wypłaty. Linia wpłaconego kapitału bez zmian.
- Wiersz odczytu pod wykresem ma stałą wysokość (poprawka właściciela: Pulpit nie skacze przy najechaniu).

### 2.2 Pozycje
- Wartość i zysk każdej pozycji liczone od wartości do wypłaty. Bez nowych kolumn.

### 2.3 Szczegóły pozycji
- Sekcja „Do wypłaty”: wartość rynkowa, „Przewalutowanie XTB 0,5 %” (gdy jest), „Spread (ręczny N %)” (gdy jest),
  „Do wypłaty”. Sekcja pojawia się tylko, gdy koszty wyjścia są większe od zera.
- W podziale zysku trzecia linia „Koszty wyjścia” obok „Efekt ceny” i „Efekt waluty”.

### 2.4 Ustawienia → Źródła cen
- Przy instrumencie opcjonalne pole „Spread (%)”. Podpowiedź: „Połowa różnicy między ceną kupna a sprzedaży.
  Zostaw puste dla płynnych ETF-ów.” Puste pole zapisuje `null`. Zapis pokazuje ten sam komunikat co zmiana symbolu.

## 3. Drobiazgi

1. **Wygląd (zgłoszenia właściciela):**
   - Boczne menu na komputerze (`web/src/shell/shell.module.css`, `.item` przy ≥900px): ikonka i napis w jednej
     linii, wyrównane do środka w pionie.
   - Wykres: stała wysokość wiersza odczytu (§2.1).
   - Dodaj → obligacja („liczba obligacji” + data) i Dodaj → operacja gotówkowa (kwota + data): pola w `forms.row`
     wyrównane do góry; podpowiedź pod jednym polem nie przesuwa sąsiedniego pola.
2. **Bez migania szkieletu:** Pulpit (podsumowanie, historia, pozycje) i Zamknięte zachowują poprzednie dane
   podczas przełączania konta lub zakresu (`placeholderData: keepPreviousData`).
3. **Historia:** cena z 2 miejscami po przecinku i walutą („po 250,00 PLN”).
4. **Konto oszczędnościowe:**
   - Napis „Wpłacono (netto)”.
   - Gdy pierwsze oprocentowanie zaczyna się po dzisiejszym dniu: dopisek „Oprocentowanie od DD.MM.RRRR, do tego
     czasu 0 %”.
5. **Szczegóły pozycji:** przy nieznanej walucie instrumentu „Średnia cena” i ceny zakupu partii mają dopisek
   „w walucie instrumentu”.
6. **Ustawienia:**
   - „Zapisz zmiany” bez zmian pokazuje „Brak zmian do zapisania”.
   - Nowe hasło dłuższe niż 128 znaków: „Hasło może mieć najwyżej 128 znaków.”
7. **Blokada wypłat** (§1.5).
8. **Wylogowanie przy niedziałającym serwerze:** sesja jest czyszczona we wszystkich kartach (ten sam kanał co
   odświeżanie), a ekran logowania pokazuje „Wylogowano na tym urządzeniu. Serwer był niedostępny, więc sesja na
   serwerze wygaśnie sama.”

Pozostałe punkty z sekcji „Carried from …” w roadmapie zostają tam na później.

## 4. Testy

- **Silnik (czyste funkcje):**
  - pozycja w EUR na koncie XTB w PLN: koszt 0,5 %;
  - pozycja w PLN na koncie XTB: 0; pozycja w walucie obcej na koncie spoza XTB: 0;
  - gotówka na rachunku XTB w USD: 0,5 %;
  - ręczny spread dodaje się do przewalutowania;
  - pozycja wyceniona z liczb XTB: 0;
  - partie sumują się do kosztu pozycji; podział zysku sumuje się co do grosza.
- **API:**
  - podsumowanie, historia, TWR, lista i szczegóły pozycji liczą od wartości do wypłaty;
  - ekspozycja i zamknięte bez zmian;
  - `PATCH` spreadu: zapis, walidacja, przeliczenie wycen;
  - blokada wypłat (§1.5).
- **Frontend:** wiersz „Wartość rynkowa · koszty wyjścia” tylko przy kosztach > 0; sekcja „Do wypłaty”; pole
  spreadu; każdy drobiazg z §3 ma test.
- **e2e:** istniejące przechodzą; import XTB pokazuje na Pulpicie wiersz z kosztami wyjścia.
- **Na żywych danych:** po przeliczeniu wartości pozycji właściciela porównane z ostatnim eksportem XTB.
  Oczekiwana różnica ≤ ok. 0,3 % na pozycję (reszta to różnica czasu ceny).
