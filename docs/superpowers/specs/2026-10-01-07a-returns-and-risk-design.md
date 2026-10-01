# Plan 7a — stopy zwrotu i ryzyko (decyzje projektowe)

**Data:** 2026-10-01
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §2 „Etap 2”, §6 „Analityka”

## Podział etapu 2 (ustalony 2026-10-01)

| # | Część |
|---|---|
| **7a** | **Stopy zwrotu i ryzyko** — ten dokument |
| 7b | Katalog popularnych instrumentów (ETF-y, akcje) z cenami i symulator „co by było, gdyby” na prawdziwych wpłatach właściciela (np. „zamiast S&P 500 wpłacałem w NASDAQ”, „co miesiąc dodatkowo 1000 zł w EDO”), z wykresem scenariusza obok prawdziwego portfela. Porównanie z benchmarkiem to szczególny przypadek symulatora. |
| 7c | Walory i struktura: ranking i wkład walorów, mapa cieplna, zysk per konto i per typ |
| 7d | Dywidendy i koszty w czasie |
| 7e | Wykres ceny waloru z transakcjami |
| 7f | Tagi i notatki |

Kolejność: 7a, potem 7b, reszta później.

## Decyzje właściciela (2026-10-01)

1. Analiza to osobny ekran `/analiza`, do którego prowadzi karta na Pulpicie. Pasek nawigacji bez zmian.
2. Okres wybierany przyciskami 1M / 3M / 1R / Od początku roku / Wszystko; filtr kont jak na innych ekranach.
3. Zwroty za okres krótszy niż rok pokazujemy **za okres**, nie przeliczone na rok.
4. Obliczenia na serwerze, w nowym module `analytics`. Gdzie się da — gotowe biblioteki zamiast własnego kodu.

## 1. Budowa

- Moduł `api/app/analytics/`: `metrics.py` (czyste funkcje, bez bazy i HTTP), `service.py` (dane + wywołania),
  `schemas.py`, `router.py`.
- Nowe zależności: `pandas`, `numpy`, `pyxirr`. Obraz Dockera trzeba przebudować
  (`docker compose build api worker`).
  - Odrzucone: `empyrical-reloaded` (ostatnie wydanie VI 2025, ciągnie scipy, bottleneck, peewee, a daje te same
    jednolinijkowce co pandas) i `quantstats` (matplotlib, seaborn, yfinance — biblioteka raportów, nie API).
- Własny kod zostaje tylko dla dziennego zwrotu skorygowanego o przepływy: istniejąca `twr_index` z
  `app/valuation/returns.py` (przepływ na początku dnia). Dzięki temu TWR w Analizie i na Pulpicie jest ten sam.
  Dalsze miary liczy pandas na serii dziennych zwrotów i indeksie TWR.
- Dane wejściowe: `_daily_totals` z `app/portfolio/service.py` (dzień, wartość „do wypłaty”, przepływ netto), z tym
  samym filtrem kont. Funkcję przenosimy do miejsca wspólnego dla obu modułów albo udostępniamy publicznie
  (bez podkreślenia); zachowanie się nie zmienia.
- Kwoty w `Decimal`; miary statystyczne (zmienność, Sharpe, procenty pośrednie) na `float`, zaokrąglane do
  2 miejsc dopiero w odpowiedzi.

## 2. Okres

- Koniec okresu: ostatni dzień z wyceną (`as_of`, jak na Pulpicie). Początek: koniec minus 1 / 3 / 12 miesięcy,
  1 stycznia roku końca (YTD) albo pierwszy dzień historii (Wszystko). Początek nie wcześniejszy niż pierwszy dzień
  historii.
- `days` = liczba dni kalendarzowych od początku do końca. `annualized` = `days >= 365`.
- Wartość na początku okresu to wartość z dnia poprzedzającego pierwszy dzień okresu (dla „Wszystko”: 0).

## 3. Miary

Dzienny zwrot dnia t: `r_t = V_t / (V_{t−1} + F_t) − 1` (reguła z `twr_index`); dni z mianownikiem ≤ 0 są pomijane.
Dni kalendarzowe, nie sesyjne: weekend daje zwrot ≈ 0, a mnożnik √365 zachowuje roczną wariancję; akcje, obligacje
i konto oszczędnościowe liczą się jednolicie.

| Miara | Definicja |
|---|---|
| Zysk (zł) | `V_koniec − V_początek − Σ F` w okresie |
| TWR | iloczyn `(1 + r_t)` − 1 w okresie; roczny: `(1+TWR)^(365/days) − 1` (tylko gdy `annualized`) |
| XIRR (MWR) | `pyxirr.xirr` na przepływach: `−V_początek` w dniu przed okresem (pomijany, gdy 0), `−F_t` w dniach przepływów, `+V_koniec` w ostatnim dniu. Za okres: `(1+x)^(days/365) − 1`. Brak rozwiązania lub brak przepływów → `null` |
| Zmienność | odchylenie standardowe `r_t` (próbkowe) × √365 |
| Sharpe | `(średnia(r_t − rf_t) / std(r_t)) × √365`; `rf_t` = stopa referencyjna NBP obowiązująca w dniu t (`nbp_ref_rates`) / 365. Brak stopy → ostatnia znana |
| Obsunięcie w czasie | indeks TWR / jego dotychczasowe maksimum − 1 (`cummax`), w % |
| Maks. obsunięcie | minimum serii; `peak_date` (ostatni szczyt przed dołkiem), `trough_date`, `recovered_on` (pierwszy dzień po dołku, gdy indeks wraca do szczytu; `null` = nieodrobione) |
| Obecne obsunięcie | ostatnia wartość serii |
| Najlepszy / najgorszy dzień | maks./min. `r_t`: data, %, zł (`V_t − V_{t−1} − F_t`) |
| Tabela miesiące × lata | **zawsze cała historia**, niezależnie od okresu: zwrot TWR miesiąca (indeks na koniec miesiąca / na koniec poprzedniego − 1), kolumna „Rok” złożona z miesięcy; pierwszy niepełny miesiąc oznaczony (`first_partial_month`) |

Progi danych:
- Mniej niż 30 dni zwrotów w okresie: zmienność i Sharpe = `null` (ekran: „za mało danych”).
- Zmienność i Sharpe są zawsze w ujęciu rocznym (standard, porównywalny z kartą funduszu). Gdy okres < 1 roku,
  `short_sample = true`, a ekran dopisuje „orientacyjnie”.
- Zasada „za okres” dotyczy tylko zwrotów (TWR, XIRR).

## 4. API

`GET /api/analytics?period=1m|3m|1y|ytd|all&account_id=…` (powtarzany `account_id`, jak w innych endpointach;
bez niego cały portfel).

```
period            { start, end, days, annualized }
profit_pln
twr               { period_pct, annual_pct | null }
xirr              { period_pct | null, annual_pct | null }
volatility_pct    | null
sharpe            | null
short_sample      bool
max_drawdown      { pct, peak_date, trough_date, recovered_on | null } | null
current_drawdown_pct | null
best_day, worst_day   { date, pct, pln } | null
drawdown_series   [{ date, pct }]
monthly           [{ year, months: [pct | null] × 12, year_pct, first_partial_month: 1–12 | null }]
recalculating     bool (jak w podsumowaniu Pulpitu)
```

- Pusty portfel albo okres bez danych: 200 z `null` i pustymi listami.
- Nieznany `period`: 422. Cudze lub nieistniejące konto: 404 (wspólny mechanizm zakresu użytkownika).

## 5. Ekran

- **Pulpit:** karta „Analiza” z XIRR i maks. obsunięciem za całą historię (jedno zapytanie `period=all`) i linkiem do
  `/analiza`, w stylu karty Ekspozycji.
- **`/analiza`:** tytuł, wybór kont, przyciski okresu (domyślnie „Wszystko”).
  1. Kafelki (2 kolumny na telefonie, 4 na komputerze): Zysk, TWR, XIRR, Maks. obsunięcie, Obecne obsunięcie,
     Zmienność, Sharpe, Najlepszy dzień, Najgorszy dzień. Pod liczbą podpis „za okres” / „rocznie” (i „orientacyjnie”
     przy `short_sample`). Przycisk „?” rozwija jednozdaniowe wyjaśnienie prostym językiem.
  2. Wykres obsunięcia: obszar pod zerem w kolorze `--loss`, oś czasu z `timeTicks`, bez przybliżania.
  3. Zwrot w miesiącach, bez poziomego przewijania:
     - telefon (< 900 px): osobna karta na każdy rok (najnowszy na górze), w nagłówku rok i zwrot roczny, pod nim
       siatka 4 × 3 miesięcy (skrót miesiąca + zwrot); pusty miesiąc to „–”;
     - komputer (≥ 900 px): tabela, wiersze = lata, kolumny I–XII + „Rok”, mieści się bez przewijania;
     - tło komórki zielone/czerwone z intensywnością rosnącą z wartością (nasycenie przy ±5 % miesięcznie);
       niepełny pierwszy miesiąc w przerywanej ramce.
- Stany: ładowanie, błąd, „za mało danych”, „wycena się przelicza” — jak na innych ekranach.

Teksty „?”:
- Zysk — ile zarobiłeś w okresie, nie licząc tego, co sam dopłaciłeś.
- TWR — jak radziły sobie same inwestycje, niezależnie od terminów wpłat; tę miarę porównuje się z funduszami.
- XIRR — Twój osobisty zwrot z uwzględnieniem tego, kiedy i ile wpłacałeś; jak oprocentowanie lokaty o tym samym wyniku.
- Maks. obsunięcie — największy spadek od szczytu do dołka w okresie.
- Obecne obsunięcie — ile dziś brakuje do najwyższego poziomu.
- Zmienność — jak mocno wartość skacze; 15 % znaczy, że typowy rok mieści się mniej więcej w ±15 %.
- Sharpe — ile zysku przypada na jednostkę ryzyka ponad bezpieczną lokatę (stopa NBP); powyżej 1 dobrze, poniżej 0
  lokata wypadła lepiej.
- Najlepszy / najgorszy dzień — największy dzienny wzrost i spadek, bez wpłat.

## 6. Testy

- `metrics.py`: przykłady liczone ręcznie (TWR z przepływem, obsunięcie z odrobieniem i bez, tabela z niepełnym
  pierwszym miesiącem, zmienność i Sharpe na krótkiej serii, XIRR zgodny z wynikiem `XIRR` z Excela dla tych samych
  przepływów, przeliczenie „za okres”).
- API: filtr kont, izolacja użytkowników, pusty portfel, okres krótszy niż 30 dni, nieznany okres, YTD.
- Web (Vitest): karta na Pulpicie, ekran z danymi, podpisy „za okres” / „rocznie”, „?”, stany pusty i błąd.
- e2e: przejście z karty Pulpitu do Analizy w istniejącym teście.

## Poza zakresem

- Analiza per walor (tabela miesięczna dla instrumentu) — przy 7c.
- Porównanie z indeksem — w 7b (symulator).
- Przybliżanie wykresu obsunięcia.
- Własny zakres dat.
