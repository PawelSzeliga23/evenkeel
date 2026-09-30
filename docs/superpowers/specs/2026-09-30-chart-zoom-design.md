# Wykres wartości: przybliżanie i czytelne osie (decyzje projektowe)

**Data:** 2026-09-30

## Problem

Wykres wartości na Pulpicie (`web/src/charts/ValueChart.tsx`) pokazuje stały zakres wybrany przyciskiem
1M / 3M / 1R / Wszystko i nie da się go przybliżyć. Oś X ma najwyżej 4 skróty miesięcy bez dni i roku
(w 1M jest jedno „wrz”). Tekst osi skaluje się razem z SVG (`viewBox` 350×190), więc na komputerze jest za duży.

## Decyzje właściciela (2026-09-30)

1. Na komputerze przybliża **Ctrl + kółko** (żeby nie przybliżać przypadkiem przy przewijaniu strony).
2. Na telefonie przybliża i przesuwa **dwoma palcami**. Jeden palec działa jak dziś (podgląd dnia, przewijanie strony).
3. Oś X ma przy mocnym przybliżeniu pokazywać **każdy dzień**.
4. Najmniejsze przybliżenie: **7 dni**.

## 1. Zachowanie

- **Komputer**
  - Ctrl + kółko przybliża / oddala wokół dnia pod kursorem. Szczypanie na touchpadzie przeglądarka zgłasza jako
    Ctrl + kółko, więc działa tak samo.
  - Przeciąganie myszą (wciśnięty przycisk) przesuwa widok w bok.
  - Najechanie bez wciśnięcia pokazuje wartości dnia w wierszu nad wykresem, jak dziś.
  - Samo kółko nad wykresem przewija stronę i na ~1,5 s pokazuje nad wykresem podpowiedź „Ctrl + kółko przybliża”.
- **Telefon**
  - Dwa palce: rozsunięcie / zsunięcie przybliża wokół środka między palcami, przesunięcie obu przesuwa widok.
  - Jeden palec: podgląd dnia i pionowe przewijanie strony, bez zmian (`touch-action: pan-y` zostaje).
- **Skala kwot (dodane 2026-09-30 na prośbę właściciela):** przeciąganie lewym przyciskiem po osi Y (pasek kwot po prawej) w górę rozszerza wykres, w dół go zmniejsza; środek przedziału zostaje. Ręczna skala zostaje przy przybliżaniu i przesuwaniu w bok, a przeciąganie po wykresie przesuwa ją wtedy też w górę i w dół. Podwójne kliknięcie, przycisk zakresu i zmiana kont wracają do skali automatycznej. Telefon bez zmian.
- **Cofnięcie przybliżenia:** podwójne kliknięcie / podwójne stuknięcie wraca do okna z bieżącego przycisku.
- **Przyciski 1M / 3M / 1R / Wszystko** ustawiają widoczne okno kończące się ostatnim dniem historii.
  Po ręcznym przybliżeniu lub przesunięciu żaden przycisk nie jest zaznaczony. Kliknięcie przycisku ustawia jego okno.
  Domyślnie jak dziś 1R.
- **Granice:** okno ma co najmniej 7 dni (lub całą historię, gdy jest krótsza) i najwyżej całą historię.
  Nie da się go wysunąć poza pierwszy ani ostatni dzień.
- **Oś Y** liczona tylko z punktów w widocznym oknie (wartość i wpłacony kapitał), jak dziś `yDomain`.
- **Kropka na końcu linii** rysowana tylko, gdy ostatni dzień historii jest w oknie.
- **Znaczniki wpłat** tylko w oknie; „duża / mała” wpłata liczona z mediany całej historii (nie zmienia się przy przybliżaniu).

## 2. Oś X

- Etykiety stoją na granicach kalendarza. Krok dobierany z listy, od najdrobniejszego, jako pierwszy, przy którym
  etykiety się nie nakładają (szerokość etykiety szacowana z liczby znaków × ~6,5 px + odstęp 8 px):
  1 dzień → 2 dni → tydzień (poniedziałki) → miesiąc (1. dzień) → 2 miesiące → kwartał → pół roku → rok → 2 lata → 5 lat.
- Format:
  - kroki dzienne i tygodniowe: `24`, a pierwszy dzień miesiąca i pierwsza etykieta osi: `1 paź` / `22 wrz`;
  - kroki miesięczne: `kwi`, a styczeń i pierwsza etykieta osi: `2026` (pogrubione) / `lip 2025`;
  - kroki roczne: `2025`.
- Etykiety oznaczające większą jednostkę (nowy miesiąc na osi dni, nowy rok na osi miesięcy) są pogrubione.
- Przy każdej etykiecie delikatna pionowa linia siatki (styl `.grid`).
- Każdy dzień historii ma swoje miejsce na osi (punkty są dzienne, także w weekendy — sprawdzone na danych
  właściciela 2026-09-30).
- Wiersz podglądu nad wykresem pokazuje datę z rokiem (`formatDate`, bez zmian).

## 3. Budowa (tylko `web/`, API bez zmian)

- **Dane — `DashboardScreen.tsx`:** historia pobierana raz bez `from` (`api.history(accountIds, null)`),
  klucz zapytania bez zakresu. Przycisk zakresu przestaje pobierać dane; stan `range` (lub `null` po ręcznym
  przybliżeniu) i okno idą do wykresu. `rangeFrom` zostaje do liczenia początku okna z przycisku.
- **`charts/viewport.ts` (nowy, czyste funkcje):** okno `{ from: number; to: number }` (indeksy punktów, `to` włącznie);
  `windowForRange`, `zoomAt(window, anchorIndex, factor, count)`, `pan(window, deltaIndex, count)`, `clampWindow`
  (min 7 dni, granice historii).
- **`charts/timeTicks.ts` (nowy):** `timeTicks(points, window, plotWidthPx)` → `{ index, label, strong }[]`
  według sekcji 2. Zastępuje `monthTicks`.
- **`charts/geometry.ts`:** `scales` i ścieżki liczone dla okna; rysowane punkty okna plus po jednym z każdej strony
  (przycięte `clipPath` do obszaru wykresu), żeby linia dochodziła do krawędzi.
- **`charts/useChartGestures.ts` (nowy hook):** `wheel` (listener z `passive: false`, `preventDefault` tylko przy
  Ctrl), pointer events do przeciągania myszą i dwóch palców (śledzenie aktywnych `pointerId`), `dblclick` i
  podwójne stuknięcie (dwa `pointerup` jednego palca w < 300 ms). Zwraca handlery i stan podpowiedzi.
- **`ValueChart.tsx`:** mierzy szerokość kontenera (`ResizeObserver`) i rysuje SVG w pikselach
  (`viewBox` = rzeczywista szerokość × wysokość), więc tekst osi ma stałe ~11 px na każdym ekranie. Wysokość
  rośnie z szerokością jak dziś (0,45 × szerokość), w granicach 190–300 px.
  Przyjmuje `points`, `window`, `onWindowChange`.
- Animacja rysowania linii (`draw`) tylko przy pierwszym wyświetleniu, nie przy każdym przybliżeniu.

## 4. Testy

- `viewport.test.ts`: okno z przycisku, zoom wokół kotwicy, pan, granice, minimum 7 dni, historia krótsza niż 7 dni.
- `timeTicks.test.ts`: każdy dzień przy 7 dniach, poniedziałki przy miesiącu, „1 paź” przy przejściu miesiąca,
  rok przy styczniu, same lata dla kilku lat, brak nakładania przy wąskim wykresie.
- `ValueChart.test.tsx`: Ctrl + kółko zmienia okno, samo kółko pokazuje podpowiedź, podwójne kliknięcie wraca.
- Test Pulpitu: zmiana przycisku nie wywołuje nowego zapytania o historię.
- Ręcznie w przeglądarce: szerokość telefonu (375 px) i komputera, emulacja dotyku dla dwóch palców.

## Poza zakresem

- Przybliżanie innych wykresów (ekspozycja w czasie, udziały).
- Zapamiętywanie przybliżenia między wizytami.
