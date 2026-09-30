# Wybór kilku kont — decyzje projektowe

**Data:** 2026-09-30
**Poprzednie decyzje:** `2026-09-28-06a-frontend-foundation-design.md` (filtr konta na Pulpicie),
`2026-09-29-06c-overview-and-settings-design.md` (zamknięte, ekspozycja).

## Cel

Dziś filtr kont pozwala wybrać „Cały portfel” albo jedno konto. Właściciel chce oglądać dowolny zestaw kont
naraz, np. konto oszczędnościowe razem z IKE. Filtr staje się wyborem kilku kont z checkboxami, wspólnym dla całej
aplikacji.

## Decyzje właściciela (2026-09-30)

1. Wybór kilku kont działa wszędzie, gdzie jest filtr kont, i jest jeden wspólny: to, co zaznaczysz na Pulpicie,
   obowiązuje też w Pozycjach, Historii i Ekspozycji. Wybór jest zapamiętany.
2. Wygląd: przycisk z opisem wyboru, a po kliknięciu lista z checkboxami. Ten sam element zastępuje listę
   rozwijaną (Pulpit, Ekspozycja) i chipsy (Pozycje, Historia).

## 1. Backend

- Parametr `account_id` w zapytaniach można podać wiele razy: `?account_id=1&account_id=4`. Jedno wystąpienie działa
  jak dotąd; brak parametru oznacza cały portfel. Stare wywołania z jednym kontem dalej działają.
- Dotyczy: `GET /api/portfolio/summary`, `/api/portfolio/history`, `/api/positions`, `/api/portfolio/exposure`,
  `/api/portfolio/closed`, `GET /api/history` (Historia operacji). Szczegóły pozycji i limity IKE/IKZE bez zmian.
- Każde konto na liście musi należeć do użytkownika, inaczej `404 not_found` (jak dziś przy jednym koncie).
  Powtórzone id liczy się raz. Dozwolone id: 1…2³¹−1, jak dziś.
- Funkcje usług przyjmują `account_ids: frozenset[int] | None` zamiast `account_id: int | None` (`None` = cały portfel).
  Filtrowanie to `DailyValuation.account_id.in_(...)` w zapytaniach i `in` w filtrach w pamięci.
- Obliczenia bez zmian, tylko po sumie wybranych kont: wartość do wypłaty, wpłacony kapitał, zmiana dnia, TWR
  (z przepływów wybranych kont), alokacja, udziały pozycji, ekspozycja, zamknięte.

## 2. Frontend

- Nowy komponent `AccountSelect` w `web/src/ui/AccountPicker.tsx` (zastępuje `AccountPicker` i `AccountChips`):
  - przycisk z opisem: „Cały portfel” (nic nie wybrane albo wszystkie konta), nazwy kont oddzielone przecinkiem przy
    1–2 kontach, „N konta” / „N kont” przy 3 i więcej (polska odmiana przez `pluralPl`);
  - po kliknięciu panel z checkboxami: „Cały portfel” na górze, pod nim konta w kolejności z `/api/accounts`;
  - zaznaczenie „Cały portfel” czyści wybór; odznaczenie ostatniego konta też wraca do całego portfela;
    zaznaczenie wszystkich kont po kolei to również „Cały portfel” (wybór pusty);
  - zmiana działa od razu; panel zamyka klik poza nim i Esc; przycisk ma `aria-expanded`, checkboxy są prawdziwymi
    `input type="checkbox"` z etykietami.
- Wspólny wybór: hook `useAccountSelection()` zwraca `[ids: number[], setIds]`, trzymany w kontekście aplikacji,
  zapamiętany w `localStorage` pod kluczem `portfolio.accounts.<userId>`. Odczyt i zapis w `try/catch` (tryb prywatny).
  Id kont, których nie ma już w `/api/accounts`, są pomijane; gdy nic nie zostaje, wybór jest pusty („Cały portfel”).
- Klucze zapytań i wywołania API przyjmują listę id (posortowaną, żeby ten sam wybór dawał ten sam klucz cache) i
  wysyłają powtórzony `account_id`.
- Ekrany: Pulpit, Ekspozycja, Pozycje (Otwarte i Zamknięte), Historia korzystają z `AccountSelect` i
  `useAccountSelection()`.

## 3. Testy

- API: dla każdego z sześciu endpointów dwa konta naraz — wynik jest sumą (albo połączeniem) wyników pojedynczych
  kont; cudze konto na liście → 404; powtórzone id liczy się raz; brak parametru = cały portfel.
- Frontend: opis na przycisku (0, 1, 2, 3+ kont); zaznaczanie i odznaczanie, „Cały portfel”, Esc i klik poza;
  wysłane zapytania z powtórzonym `account_id`; zapamiętanie po ponownym renderze i przejście Pulpit → Pozycje z tym
  samym wyborem; konto usunięte z `/api/accounts` wypada z wyboru.

## Podział

Jeden plan: `2026-09-30-account-selection.md`, na gałęzi `feature/account-selection`.
