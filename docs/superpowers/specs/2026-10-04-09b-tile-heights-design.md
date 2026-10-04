# Plan 9b — wysokość kafelków w jednostkach U (propozycja do akceptacji)

Data: 2026-10-04. Gałąź: `feature/dashboard-tiles` (plan 9, jeszcze nie scalony). Status: **czeka na akceptację
wysokości przez właściciela** — dopiero potem plan i wykonanie.

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

## Proponowane warianty (szerokość · wysokość) — DO AKCEPTACJI

| Kafelek | Warianty | Co pokazuje dany wariant |
|---|---|---|
| Wartość portfela | **S·2U** nowy · **M·4U** · **L·3U** | S: kwota i zmiana dziś; M: kwota, koszty wyjścia, dziś, 4 pola 2×2; L: kwota po lewej, 4 pola w jednym rzędzie |
| Jedna miara | **S·1U** nowy · **S·2U** | 1U: nazwa i liczba w jednym wierszu; 2U: jak dziś (nazwa, liczba, dopisek) |
| Wykres wartości | **M·4U** · **L·4U** · **L·6U** | niski szeroki do pasa nad innymi; duży jak dziś |
| Wykres ceny | **M·5U** · **L·6U** | jak dziś; M bez legendy i podpowiedzi |
| Alokacja | **S·2U** · **M·4U** · **L·4U** | S: pasek + największa część; M: pasek + lista (do 5); L: pasek + lista w 2 kolumnach |
| Analiza | **M·3U** · **L·3U** · **L·6U** | M: do 4 miar 2×2; L·3U: do 6 miar w jednym/dwóch rzędach; L·6U: miary + wykres obsunięcia |
| Limity IKE/IKZE | **S·2U** nowy · **M·2U** | S: tylko % wykorzystania każdego limitu; M: jak dziś |
| Dziś najbardziej | **M·4U** (3 poz.) · **M·5U** (5 poz.) · **L·5U** (5 poz. w 2 kolumnach) · **L·8U** (10 poz.) | liczba pozycji wynika z wariantu (znika ustawienie „Ile pozycji”) |
| Walory | **M·3U** · **L·5U** nowy | mała / duża mapa cieplna |
| Dochód i koszty | **S·2U** nowy · **M·2U** | S: sam bilans od pocz. roku; M: dochód i koszty jak dziś |
| Tagi | **M·3U** | jak dziś (3 tagi) |
| Symulator | **M·4U** | jak dziś (3 scenariusze) |
| Przegląd AI | **M·4U** · **L·4U** | skrót „W skrócie”, przewijany w kafelku |

Układ domyślny (bez zapisanego): Wartość portfela M·4U + Wykres wartości… — do ustalenia po akceptacji tabeli; cel:
dzisiejszy porządek bez przerw (np. Wartość portfela L·3U, Wykres wartości L·6U, Alokacja M·4U obok Analiza M·3U +
Limity… — dobrać tak, by sumy U w parach się zgadzały).

## Do decyzji właściciela przy akceptacji

1. Czy 1U = 72 px pasuje (może 64 albo 80)?
2. Czy warianty w tabeli wystarczą; co dodać / usunąć.
3. Nowe rodzaje kafelków (propozycje, niekonieczne): **Ekspozycja walutowa** (S·2U %, M·3U pasek), **Ostatnie operacje**
   (M·4U, 5 ostatnich z Historii), **Najlepsze i najgorsze walory** (M·4U, z Walorów za okres), **Gotówka na kontach**
   (S·2U).

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
