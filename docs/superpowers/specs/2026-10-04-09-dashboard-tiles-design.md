# Plan 9 — Pulpit z kafelków

Data: 2026-10-04. Prośba właściciela: Pulpit złożony z kafelków, które można układać, dodawać, usuwać i edytować
(np. wykres ceny jednego instrumentu, Analiza na samej górze, Sharpe zamiast „Wpłacono” w górnych polach).

## Co ustaliliśmy z właścicielem

- Każdy kafelek ma ramkę.
- **Telefon:** na górze Pulpitu ikonka „Edytuj”. W trybie edycji (jak na iPhonie) „+ Dodaj kafelek”, przy każdym
  kafelku X do usunięcia, przeciąganie w górę i w dół. Jeden wygląd każdego kafelka.
- **Komputer:** „Edytuj pulpit” w pasku bocznym nad Ustawieniami. Te same funkcje, ale kafelki przesuwa się po siatce
  w dowolną stronę i są w kilku rozmiarach (np. mały i duży wykres).
- Każdy kafelek ma ustawienia (np. które miary pokazuje Analiza).
- **Jeden wspólny układ** dla telefonu i komputera; telefon czyta go rzędami (od góry, w rzędzie od lewej).
- Katalog kafelków jak niżej; czego zabraknie, właściciel powie po zbudowaniu.

## Model układu

Układ to **uporządkowana lista kafelków**; położenie wynika z kolejności i rozmiaru (jak widżety na iPhonie: kafelki
płyną rzędami po siatce, bez dziur ustawianych ręcznie). Dzięki temu jeden układ działa na każdej szerokości:

| Rozmiar | Komputer (4 kolumny) | Średni ekran (2 kolumny) | Telefon (2 kolumny) |
|---|---|---|---|
| S | 1 kolumna | 1 kolumna | 1 kolumna (dwa S obok siebie) |
| M | 2 kolumny | 2 kolumny | cała szerokość |
| L | 4 kolumny | 2 kolumny | cała szerokość |

Przeciągnięcie kafelka na komputerze w dowolne miejsce siatki zmienia jego miejsce na liście; na telefonie to samo
w pionie. Kolejność na telefonie jest więc zawsze kolejnością z komputera.

```ts
type TileSize = "S" | "M" | "L";
interface Tile { id: string; kind: TileKind; size: TileSize; settings: TileSettings[kind] }
interface DashboardLayout { version: 1; tiles: Tile[] }  // najwyżej 40 kafelków
```

`id` to losowy krótki ciąg nadany przy dodaniu (klucz Reacta i przeciągania). Każdy rodzaj ma listę dozwolonych
rozmiarów i domyślne ustawienia.

## Katalog kafelków

| Rodzaj (`kind`) | Rozmiary | Ustawienia | Treść |
|---|---|---|---|
| `summary` Wartość portfela | M, L | `fields`: 4 miary pod kwotą | dzisiejsza góra Pulpitu: kwota, koszty wyjścia, zmiana dziś, 4 pola, flagi |
| `metric` Jedna miara | S | `metric` | nazwa z „?”, wartość, dopisek (np. „rocznie”) |
| `value_chart` Wykres wartości | M, L | `range` (1M/3M/1R/Wszystko) | wykres wartości z zakresem, jak dziś |
| `price_chart` Wykres ceny | M, L | `account_id`, `instrument_id`, `range` | wykres z sekcji „Wykres ceny” w szczegółach pozycji, z tytułem waloru i linkiem do szczegółów |
| `allocation` Alokacja | S, L | `by` (konta / typ / waluta) | S: tytuł i pasek z największą pozycją; L: pasek i lista, jak dziś |
| `analysis` Analiza | M, L | `metrics` (1–6), `period` | wybrane miary z „?” za okres; L: także mały wykres obsunięcia |
| `limits` Limity IKE/IKZE | M | — | dzisiejsza karta |
| `movers` Dziś najbardziej | M, L | `count` (3/5/10) | dzisiejsza lista |
| `holdings` Walory | M | — | karta z Analizy (mała mapa cieplna) |
| `income` Dochód i koszty | M | — | karta z Analizy |
| `tags` Tagi | M | — | karta z Analizy |
| `simulator` Symulator | M | — | karta z Analizy |
| `review` Przegląd AI | M | — | karta z Analizy |

**Miary** (wspólna lista dla `summary.fields`, `metric.metric` i `analysis.metrics`):

- z podsumowania (`/api/portfolio/summary`, cała historia): `total_gain` Zysk łącznie, `twr_total` Stopa zwrotu
  (TWR), `invested` Wpłacono, `income` Dywidendy i odsetki, `cash` Gotówka, `day_change` Zmiana dziś, `fees` Opłaty;
- z analizy (`/api/analytics`, okres kafelka; dla `summary` i `metric` — cała historia): `profit` Zysk w okresie,
  `twr` TWR, `xirr` XIRR, `volatility` Zmienność, `sharpe` Sharpe, `max_drawdown` Maks. obsunięcie,
  `current_drawdown` Obecne obsunięcie, `best_day` Najlepszy dzień, `worst_day` Najgorszy dzień.

Każda miara ma etykietę i dymek „?” z istniejącego `HELP` oraz sposób formatowania (kwota albo procent, z kolorem).

**Układ domyślny** = dzisiejszy Pulpit: `summary` L (Zysk łącznie, TWR, Wpłacono, Dywidendy i odsetki),
`value_chart` L, `allocation` L (typ), `analysis` M (XIRR, Maks. obsunięcie; cała historia), `limits` M,
`movers` L (5). Bez zapisanego układu Pulpit wygląda tak jak przed planem 9.

## Tryb edycji

- Wejście: telefon — ikonka „Edytuj” w nagłówku Pulpitu (obok zębatki); komputer — przycisk „Edytuj pulpit”
  w pasku bocznym nad Ustawieniami (z innego ekranu przenosi na Pulpit w trybie edycji, `/?edycja`).
- W trybie edycji nagłówek pokazuje: „+ Dodaj kafelek”, „Przywróć domyślny”, „Anuluj”, „Gotowe”.
- Każdy kafelek: X w rogu (usuń) i przycisk „Ustaw” (ustawienia); treść kafelka nie reaguje na kliknięcia (linki
  i wykresy są wyłączone), kafelki lekko „drżą” jak na iPhonie (wyłączone przy `prefers-reduced-motion`).
- Przeciąganie: biblioteka `@dnd-kit` (core + sortable). Mysz: od przesunięcia o 5 px. Palec: po przytrzymaniu
  200 ms (krótki ruch przewija stronę). Klawiatura: spacja chwyta, strzałki przesuwają (KeyboardSensor). W
  ustawieniach kafelka są też „Przesuń wcześniej / później” — dostępne bez przeciągania.
- „+ Dodaj kafelek” otwiera listę rodzajów z opisem; wybrany trafia na **początek** układu z domyślnymi ustawieniami
  (wykres ceny od razu otwiera ustawienia, bo trzeba wybrać walor).
- Ustawienia kafelka: panel w miejscu (nie okno przeglądarki): rozmiar (tylko na komputerze, gdy rodzaj ma kilka),
  pola danego rodzaju, „Przesuń wcześniej / później”, „Gotowe”.
- Zmiany są robocze do „Gotowe” (zapis) albo „Anuluj” (powrót do zapisanego). „Przywróć domyślny” podmienia roboczy
  układ na domyślny (zapis dopiero przy „Gotowe”).

## Zapis

Układ jest w `users.preferences` jako klucz `dashboard` (jak ustawienia z planu 8a; bez migracji — kolumna JSON już
jest). `PATCH /api/preferences` z `{"dashboard": {...}}` albo `{"dashboard": null}` (= domyślny). API sprawdza:
wersję, najwyżej 40 kafelków, unikalne `id` (1–20 znaków), znany rodzaj, dozwolony rozmiar, ustawienia tego rodzaju
(`extra="forbid"`, wartości z list; `account_id`/`instrument_id` jako liczby — **nie** sprawdza, czy walor należy do
użytkownika: kafelek i tak pyta API przez `UserScope`, więc cudzy walor da 404 jak wszędzie). Kopia portfela (8c)
zawiera `preferences`, więc i układ.

Klient czyta układ przez `usePreferences()`; nieznany rodzaj lub zepsute ustawienia kafelka (np. po zmianie wersji)
są pomijane przy wyświetlaniu, a reszta układu działa.

## Dane i błędy

- Wybór kont na górze Pulpitu dotyczy wszystkich kafelków (jak dziś).
- Kafelki tego samego źródła dzielą zapytania (React Query po kluczu), więc trzy kafelki miar z analizy = jedno
  zapytanie na okres.
- Każdy kafelek ma własny stan ładowania (szkielet), błędu („Nie udało się wczytać · Ponów”) i braku danych (krótki
  komunikat zamiast znikania, np. „Brak kont IKE/IKZE”, „Ten walor nie jest już w portfelu — wybierz inny”).
- Pusty portfel (przed importem) pokazuje jak dziś zaproszenie do importu zamiast kafelków.
- „Ukryj kwoty” (8a) działa w kafelkach jak w reszcie aplikacji (przez `Money`).

## Struktura kodu (web)

- `src/dashboard/layout.ts` — typy, katalog rodzajów (rozmiary, domyślne ustawienia, nazwa, opis), układ domyślny,
  czyste funkcje: `normalize` (odrzuca złe kafelki), `move`, `remove`, `add`, `resize`.
- `src/dashboard/metrics.ts` — lista miar: etykieta, źródło, wartość z danych, format.
- `src/dashboard/tiles/*.tsx` — po jednym komponencie na rodzaj (z ustawieniami w osobnym `*Settings`), wydzielone
  z dzisiejszego `DashboardScreen` i kart z Analizy (karty Analizy dostają ramkę kafelka, ich treść bez zmian).
- `src/dashboard/TileGrid.tsx` — siatka, ramka kafelka, tryb edycji, przeciąganie (`@dnd-kit`).
- `DashboardScreen.tsx` — nagłówek (konta, odświeżanie, oko, Edytuj), puste/ładowanie, `TileGrid`.

API: `preferences/schemas.py` — model `DashboardLayout` z kafelkami jako unią po `kind`.

## Testy

- API: zapis i odczyt układu, odrzucenie złych układów (rodzaj, rozmiar, ustawienia, 41 kafelków, powtórzone id),
  `null` przywraca domyślny, kopia portfela niesie układ.
- Web: czyste funkcje układu i miar; Pulpit bez zapisanego układu wygląda jak dziś (istniejące testy Pulpitu
  przechodzą); tryb edycji: dodanie, usunięcie, zmiana ustawień (np. Sharpe zamiast Wpłacono), przesunięcie
  przyciskami, Anuluj, Gotowe zapisuje `PATCH`; kafelek wykresu ceny; kafelek z błędem ma „Ponów”; przycisk w pasku
  bocznym.
- e2e: wejście w edycję, dodanie kafelka miary, Gotowe, odświeżenie strony — kafelek jest.
