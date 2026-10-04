# Plan 9b — wysokość kafelków w jednostkach U (propozycja do akceptacji)

Data: 2026-10-04. Gałąź: `feature/dashboard-tiles` (plan 9, jeszcze nie scalony). Status: **zaakceptowane przez
właściciela 2026-10-04** („tak do wszystkich 3 pytań” + zasada wysokości Analizy niżej). Następny krok po /clear:
plan wykonania (writing-plans) i wykonanie bez kolejnych zgód (waiver planu 9), pytanie dopiero o scalenie.

## Ustalone z właścicielem

- Na komputerze kafelki mają wysokość w jednostkach **U** (jak w szafie serwerowej), żeby układały się bez przerw.
- **Wariant A:** wysokość **nie jest do wyboru** — wynika z rodzaju i wariantu kafelka. Żeby była elastyczność, każdy
  rodzaj ma **kilka wariantów** (szerokość × wysokość), wybieranych w ustawieniach kafelka zamiast samego S/M/L.
- Na telefonie wysokości nie ma (jedna kolumna, kafelek tak wysoki, jak jego treść); dwa kafelki S nadal obok siebie.
- W trybie edycji na komputerze widać skalę: poziome linie co 1U i na uchwycie każdego kafelka jego wymiar („M · 4U”).
  Lista „+ Dodaj kafelek” pokazuje warianty z wymiarami.

## Jednostka

- **1U = 72 px** wiersza siatki, odstęp 16 px. Kafelek n·U ma `n × 72 + (n − 1) × 16` px:
  1U 72 · 2U 160 · 3U 248 · 4U 336 · 5U 424 · 6U 512 · 8U 688.
- Szerokość bez zmian: S = 1 kolumna, M = 2, L = 4 (od 1100 px); średni ekran i telefon — 2 kolumny.
- Kafelki płyną w kolejności z listy (CSS grid, `grid-auto-rows: 72px`, `grid-row: span n`, bez `dense`), więc niższy
  kafelek dosuwa się pod niższego sąsiada; kolejność na telefonie się nie zmienia.
- Treść, która się nie mieści, przewija się wewnątrz kafelka (nie powinno się zdarzać przy dobrze dobranych wariantach).

## Warianty (szerokość · wysokość)

| Kafelek | Warianty | Co pokazuje dany wariant |
|---|---|---|
| Wartość portfela | **S·2U** nowy (bez pól) · **M** · **L** — wysokość z liczby pól (zasada niżej) | S: kwota i zmiana dziś; M: kwota, koszty wyjścia, dziś i pola po 2 w rzędzie; L: kwota po lewej, pola po 4 w rzędzie |
| Jedna miara | **S·1U** nowy · **S·2U** | 1U: nazwa i liczba w jednym wierszu; 2U: jak dziś (nazwa, liczba, dopisek) |
| Wykres wartości | **M·4U** · **L·4U** · **L·6U** | niski szeroki do pasa nad innymi; duży jak dziś |
| Wykres ceny | **M·5U** · **L·6U** | jak dziś; M bez legendy i podpowiedzi |
| Alokacja | **S·2U** · **M·4U** · **L·4U** | S: pasek + największa część; M: pasek + lista (do 5); L: pasek + lista w 2 kolumnach |
| Analiza | **M** · **L** · **L + wykres** — wysokość rośnie z liczbą miar (zasada niżej) | M: miary po 2 w rzędzie; L: po 4 w rzędzie; L + wykres: miary po 4 w rzędzie i wykres obsunięcia |
| Limity IKE/IKZE | **S·2U** nowy · **M·2U** | S: tylko % wykorzystania każdego limitu; M: jak dziś |
| Dziś najbardziej | **M** · **L** (2 kolumny) — wysokość z liczby pozycji (zasada niżej) | ustawienie „Ile pozycji” zostaje (3, 5, 10) |
| Walory | **M·3U** · **L·5U** nowy | mała / duża mapa cieplna |
| Dochód i koszty | **S·2U** nowy · **M·2U** | S: sam bilans od pocz. roku; M: dochód i koszty jak dziś |
| Tagi | **M·3U** | jak dziś (3 tagi) |
| Symulator | **M·4U** | jak dziś (3 scenariusze) |
| Przegląd AI | **M·4U** · **L·4U** | skrót „W skrócie”, przewijany w kafelku |

### Zasada: wysokość rośnie z liczbą pól (prośba właściciela)

Dotyczy **każdego kafelka, w którym właściciel sam wybiera liczbę pól albo pozycji** — kafelek nie ma pustego miejsca
ani przewijania. Wysokość = **część stała** (nagłówek, kwota, wykres) **+ 1U na każdy rząd pól**. Pole miary (nazwa,
liczba, dopisek „rocznie”) mieści się w 1U (72 px); wiersz listy (walor, operacja, konto) jest zwarty, 44 px, więc
w 1U mieszczą się 2 wiersze (2 × 44 = 88 px = 1U z odstępem).

| Kafelek (co się liczy) | Wariant | Pól / wierszy w rzędzie 1U | Wysokość | Przykłady |
|---|---|---|---|---|
| Analiza (miary 1–6) | M | 2 miary | 1U + ⌈n/2⌉U | 2 → 2U, 4 → 3U, 6 → 4U |
| | L | 4 miary | 1U + ⌈n/4⌉U | 4 → 2U, 6 → 3U |
| | L + wykres obsunięcia | 4 miary | 1U + ⌈n/4⌉U + 3U | 4 → 5U, 6 → 6U |
| Wartość portfela (pola 1–8; dotąd stałe 4) | M | 2 pola | 2U (kwota, dziś) + ⌈n/2⌉U | 4 → 4U, 6 → 5U, 8 → 6U |
| | L | 4 pola | 2U + ⌈n/4⌉U | 4 → 3U, 8 → 4U |
| Dziś najbardziej (3, 5, 10 pozycji) | M | 2 wiersze | 1U + ⌈n/2⌉U | 3 → 3U, 5 → 4U, 10 → 6U |
| | L (2 kolumny) | 4 wiersze | 1U + ⌈n/4⌉U | 5 → 3U, 10 → 4U |
| Ostatnie operacje (3, 5, 10) | M | 2 wiersze | 1U + ⌈n/2⌉U | 5 → 4U |
| | L (2 kolumny) | 4 wiersze | 1U + ⌈n/4⌉U | 10 → 4U |
| Najlepsze i najgorsze walory (po 2, 3, 5) | M (pod sobą: 2n wierszy) | 2 wiersze | 1U + nU | po 3 → 4U |
| | L (obok siebie: n wierszy) | 2 wiersze | 1U + ⌈n/2⌉U | po 3 → 3U |

Kafelki, w których liczba wierszy wynika z danych, a nie z wyboru (Alokacja — liczba typów/kont, Limity — liczba
limitów, Gotówka na kontach — liczba kont), mają **stałą wysokość z tabeli**, a nadmiar przewija się w kafelku.
W ustawieniach kafelka przy wyborze liczby pól widać wynik („3 miary · M · 3U”), a na uchwycie w trybie edycji —
aktualny wymiar.

Układ domyślny (bez zapisanego): Wartość portfela M·4U + Wykres wartości… — do ustalenia po akceptacji tabeli; cel:
dzisiejszy porządek bez przerw (np. Wartość portfela L·3U, Wykres wartości L·6U, Alokacja M·4U obok Analiza M·3U +
Limity… — dobrać tak, by sumy U w parach się zgadzały).

## Pełna lista kafelków po 9b (prośba właściciela: więcej wariantów S)

S = 1 kolumna (ćwiartka ekranu komputera, pół telefonu), M = 2, L = 4. „n” = wysokość z liczby pól (zasada wyżej).
**Nowe w 9b** oznaczone ★. Wariant S zawsze pokazuje jedną najważniejszą rzecz z kafelka i link do szczegółów.

| # | Kafelek | S | M | L |
|---|---|---|---|---|
| 1 | Wartość portfela | S·2U kwota i zmiana dziś | M·n kwota + pola po 2 (1–8 pól) | L·n kwota + pola po 4 |
| 2 | Jedna miara | S·1U nazwa i liczba w wierszu · S·2U z dopiskiem | — | — |
| 3 | Wykres wartości | ★S·2U wartość, zmiana w zakresie i mała linia (bez osi) | M·4U | L·4U · L·6U |
| 4 | Wykres ceny waloru | ★S·2U cena, zmiana od 1. zakupu, mała linia | M·5U | L·6U |
| 5 | Alokacja | S·2U pasek + największa część | M·4U pasek + lista | L·4U lista w 2 kolumnach |
| 6 | Analiza | ★S·n miary jedna pod drugą (1–3 miary, 1U + nU) | M·n miary po 2 | L·n po 4 · L·n + wykres obsunięcia |
| 7 | Limity IKE/IKZE | S·2U % wykorzystania | M·2U | — |
| 8 | Dziś najbardziej | ★S·2U największy wzrost i największy spadek | M·n (3/5/10) | L·n w 2 kolumnach |
| 9 | Walory (mapa cieplna) | ★S·3U mała mapa bez podpisów | M·3U | L·5U |
| 10 | Dochód i koszty | S·2U bilans od pocz. roku | M·2U | — |
| 11 | Tagi | ★S·2U największy tag i jego udział | M·3U | — |
| 12 | Symulator | ★S·2U najlepszy scenariusz i różnica wobec portfela | M·4U | — |
| 13 | Przegląd AI | ★S·2U data ostatniego przeglądu i liczba sekcji | M·4U | L·4U |
| 14 | ★Ekspozycja walutowa | S·2U udział największej waluty obcej | M·3U pasek walut + lista | — |
| 15 | ★Ostatnie operacje | S·2U ostatnia operacja | M·n (3/5/10) | L·n w 2 kolumnach |
| 16 | ★Najlepsze i najgorsze walory | S·2U najlepszy i najgorszy za okres | M·n (po 2/3/5) | L·n obok siebie |
| 17 | ★Gotówka na kontach | S·2U gotówka razem | M·3U per konto | — |
| 18 | ★Obligacje | S·2U wartość obligacji i najbliższy wykup | M·3U lista serii z wartością i datą wykupu | — |
| 19 | ★Konta oszczędnościowe | S·2U saldo i oprocentowanie | M·3U lista kont z saldem, stawką i odsetkami | — |
| 20 | ★Dziennik | S·2U data i początek ostatniego wpisu | M·3U 3 ostatnie wpisy (teza / dziennik) | — |

Kafelki 18–20 to propozycje z tej samej rozmowy (dane już są w API: `/api/bonds`, `/api/savings-accounts`,
`/api/journal` / notatki z planu 7f-2); do potwierdzenia przez właściciela razem z tą listą.

## Decyzje właściciela (2026-10-04)

1. **1U = 72 px** — tak.
2. **Warianty z tabeli** — tak; tam, gdzie wybiera się liczbę pól lub pozycji, wysokość rośnie z ich liczbą (zasada wyżej).
3. **Nowe rodzaje kafelków** — tak, wszystkie cztery:
   - **Ekspozycja walutowa** — S·2U (udział największej waluty obcej w %), M·3U (pasek walut i lista); dane:
     `/api/portfolio/exposure` (dzisiejszy podział), link do `/ekspozycja`;
   - **Ostatnie operacje** — M albo L, 3/5/10 operacji, wysokość z zasady wyżej; dane: `/api/history` (pierwsza strona), link do
     Historii;
   - **Najlepsze i najgorsze walory** — M albo L, po 2/3/5 najlepszych i najgorszych, wysokość z zasady wyżej; okres
     (1 dzień … wszystko) w ustawieniach; dane: `/api/analytics/holdings`, link do Walorów;
   - **Gotówka na kontach** — S·2U (gotówka razem), M·3U (gotówka per konto); dane: `/api/positions` (pozycje
     `kind = "cash"`).

## Zmiany w kodzie (po akceptacji)

- Model: `Tile.size` zastąpione wariantem `variant: "S2" | "M4" | …` (szerokość + wysokość); API (`preferences/schemas.py`)
  waliduje dozwolone warianty rodzaju; zapisany układ z planu 9 (S/M/L) mapowany na najbliższy wariant w `normalize` i
  w API (stary zapis czytany jak nowy, bez migracji bazy).
- `DashboardGrid`: `grid-auto-rows: 72px`, `grid-row: span n` od 1100 px, tło edycji z liniami co 88 px, napis wymiaru
  na uchwycie; `TileSettings`: wybór wariantu (z wymiarem) zamiast rozmiaru; `AddTileSheet`: warianty z wymiarami.
- Kafelki: treść dopasowana do wariantu (np. Wartość portfela L·3U w jednym rzędzie, Alokacja L w 2 kolumnach).
- Testy: model wariantów, mapowanie S/M/L → wariant, API odrzuca zły wariant, e2e: zrzut komputera bez przerw.

## Stan gałęzi przed 9b (do wznowienia po /clear)

- `feature/dashboard-tiles`: plan 9 + poprawki właściciela (ikonka edycji obok zębatki, pasek edycji na telefonie,
  kafelek w ustawieniach nie drży i ma pełną szerokość, mała Alokacja mieści się na telefonie). API 875, web 534,
  e2e 6 zielone. Nie scalone — właściciel chce najpierw dopracować logikę kafelków.
