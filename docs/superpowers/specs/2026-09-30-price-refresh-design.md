# Odświeżanie cen w ciągu dnia (decyzje projektowe)

**Data:** 2026-09-30

## Problem

Worker pobiera ceny (Yahoo) i kursy (NBP) raz dziennie o 23:00 oraz przy starcie, jeśli ten przebieg przegapił.
Przez cały dzień Pulpit pokazuje więc ceny zamknięcia z poprzedniej sesji. Pobieranie już obsługuje bieżący dzień:
Yahoo podaje bieżącą cenę sesji, a wieczorny przebieg nadpisuje ostatnie 5 dni ceną zamknięcia.

## Decyzje właściciela (2026-09-30)

1. Odświeżanie jest ręczne i automatyczne.
2. W prawym górnym rogu Pulpitu stoi data i godzina ostatniego odświeżenia cen, a obok ikonka odświeżania.

## 1. Automatycznie (worker)

- Nowy przebieg w ciągu dnia: w dni robocze (pon.–pt.) od 9:00 do 22:30 czasu `market_timezone`, co 30 minut.
  - Pobiera ceny wszystkich używanych instrumentów (`update_all_prices`) i kursy NBP (`update_fx`), zaznacza zmiany
    (`mark_market_changes`) i przelicza wyceny (`recompute_stale`, jak w każdym takcie).
  - Inflacja, stopy NBP i sprzątanie tokenów zostają tylko w przebiegu wieczornym.
- Przebieg wieczorny (23:00) ma pierwszeństwo, gdy oba są należne. Liczy się też jako świeże odświeżenie, więc
  przebieg dzienny nie rusza tuż po nim.
- Ustawienia (`Settings`): `market_intraday_minutes` = 30, `market_intraday_from` = "09:00",
  `market_intraday_to` = "22:30". Takt workera zostaje (`worker_poll_seconds` = 300 s).

## 2. Ręcznie (API)

- `POST /api/portfolio/refresh` (zalogowany) pobiera od razu ceny instrumentów użytkownika (`scope.instruments()`)
  oraz kursy NBP. Potem zaznacza zmiany, zapisuje i uruchamia przeliczenie wyceny użytkownika w tle
  (`recompute_in_background`). Zwraca `{ "refreshed_at": <czas>, "fetched": true }`.
- Ochrona: jeśli ceny instrumentów użytkownika sprawdzano mniej niż 60 s temu, nic nie jest pobierane. Odpowiedź to
  `{ "refreshed_at": <ostatni czas>, "fetched": false }`.
- Użytkownik bez instrumentów dostaje `{ "refreshed_at": null, "fetched": false }` bez pobierania.
- Błędy dostawcy nie są błędem odpowiedzi. Instrument dostaje `price_error`, jak w workerze, a odpowiedź to 200.
  Błąd połączenia z samym API obsługuje frontend.
- Dostawcy są wstrzykiwani zależnością (`get_market_providers`), żeby testy podmieniały ich na atrapy z
  `tests/market_fakes.py`.
- `SummaryOut` dostaje pole `prices_refreshed_at: datetime | None`: najpóźniejsze `price_checked_at` instrumentów
  użytkownika (null, gdy ich nie ma).

## 3. Pulpit

- W pasku nad wartością, po prawej:
  - Zamiast samej daty wyceny: „śr., 30 września, 14:32”, czyli data i godzina `prices_refreshed_at` w czasie
    lokalnym przeglądarki.
  - Obok przycisk z ikonką odświeżania (`aria-label="Odśwież ceny"`, co najmniej 44 × 44 px).
  - Gdy `prices_refreshed_at` jest null: sama data wyceny, jak dziś, bez przycisku.
- Kliknięcie: ikonka się obraca, dopóki trwa zapytanie albo wycena jest przeliczana (`summary.recalculating`).
  - Po sukcesie odświeżane są wszystkie zapytania portfela, a dalej działa istniejące odpytywanie „Przeliczam
    wycenę…”.
  - Przycisk jest wyłączony, dopóki trwa zapytanie.
- Błąd: pod paskiem `role="alert"`: „Nie udało się odświeżyć cen. Spróbuj ponownie.”. Liczby zostają.
- Przy „ogranicz ruch” ikonka się nie obraca.

## 4. Testy

- Worker:
  - przebieg dzienny jest należny tylko w dni robocze w oknie 9:00–22:30 i nie częściej niż co 30 minut;
  - przebieg wieczorny liczy się jako świeży;
  - przebieg dzienny pobiera ceny i kursy, ale nie inflację.
- API:
  - odświeżenie pobiera ceny tylko instrumentów użytkownika;
  - drugie w ciągu 60 s nic nie pobiera;
  - użytkownik bez instrumentów;
  - błąd dostawcy daje 200 i `price_error`;
  - `prices_refreshed_at` w podsumowaniu;
  - przeliczenie zostaje zaznaczone.
- Pulpit:
  - data i godzina odświeżenia;
  - kliknięcie wysyła zapytanie i obraca ikonkę;
  - komunikat o błędzie;
  - brak przycisku bez instrumentów.

## Podział

Jeden plan: `docs/superpowers/plans/2026-09-30-price-refresh.md`, wykonywany samodzielnie, na gałęzi
`feature/price-refresh`.
