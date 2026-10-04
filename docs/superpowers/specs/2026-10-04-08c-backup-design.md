# Plan 8c — Ustawienia: kopia portfela i opis odświeżania cen (decyzje projektowe)

**Data:** 2026-10-04
**Część:** 8c z Ustawień (8a, 8b zrobione; 8d konto — później).

## Decyzje właściciela (2026-10-04)

1. **Po co kopia:** zabezpieczenie (odzyskanie danych po awarii lub pomyłce) i przeprowadzka (z wersji lokalnej
   na przyszłą internetową albo na inne konto).
2. **Wczytanie zastępuje wszystkie dane** użytkownika, po wpisaniu słowa **ZASTĄP**.
3. **Odświeżanie cen tylko do podglądu:** harmonogram jest wspólny dla całej aplikacji (proces w tle), więc w
   Ustawieniach jest jego opis i godzina ostatniego odświeżenia, bez zmiany.
4. **Plik bez hasła:** zwykły JSON.
5. Właściciel zatwierdził projekt w rozmowie i poprosił o spec, plan i wykonanie bez kolejnych pytań.

## 1. Ekran

Ustawienia, nowa grupa **„Dane”** (przed „O aplikacji”), dwa wiersze:

- **Kopia portfela** (`/ustawienia/kopia`):
  - **Pobierz kopię** — przeglądarka zapisuje `evenkeel-kopia-RRRR-MM-DD.json`. Podpowiedź: „Cały portfel w jednym
    pliku: konta, operacje, obligacje, oszczędności, tagi, notatki, scenariusze, przeglądy i ustawienia. Bez hasła —
    trzymaj go jak inne prywatne dokumenty.”
  - **Wczytaj kopię** — wybór pliku. Serwer sprawdza plik i zwraca, co w nim jest; ekran pokazuje: „Kopia z
    4.10.2026, 14:30 (Evenkeel 0.1.0)” i listę liczb (konta, operacje, obligacje, konta oszczędnościowe, tagi,
    notatki, scenariusze, przeglądy). Pod spodem ostrzeżenie „Zastąpi wszystkie Twoje obecne dane. Tego nie da się
    cofnąć — najpierw pobierz kopię obecnych danych.”, pole „Wpisz ZASTĄP” i przycisk **Wczytaj** (aktywny dopiero
    po wpisaniu słowa). Błąd pliku pokazuje się zamiast podglądu.
  - Po wczytaniu: przejście na Pulpit z komunikatem „Wczytano kopię. Przeliczam wycenę…” (Pulpit sam pokazuje
    przeliczanie, jak po imporcie XTB).
- **Odświeżanie cen** (`/ustawienia/odswiezanie`), tylko do odczytu:
  - „Co 30 minut w dni robocze, 9:00–22:30.”
  - „Pełna aktualizacja codziennie o 23:00.”
  - „Ostatnio: 4 paź 2026, 14:30.” (albo „jeszcze nie odświeżano”)
  - „Na Pulpicie możesz odświeżyć ceny od razu przyciskiem ⟳.”
  Na liście Ustawień wiersz ma wartość „co 30 min”.
- Wyszukiwarka: „kopia eksport backup zapisz wczytaj przywróć plik przeprowadzka” → Kopia portfela;
  „odświeżanie ceny kursy godziny harmonogram” → Odświeżanie cen.

## 2. Plik kopii

```json
{
  "format": "evenkeel-backup",
  "version": 1,
  "exported_at": "2026-10-04T12:30:00+00:00",
  "app_version": "0.1.0",
  "data": {
    "user": {"base_currency": "PLN", "preferences": {…}},
    "instruments": [{"id": 1, "xtb_ticker": "SXR8.DE", "name": "…", …}],
    "bond_series": [{"series": "EDO0936", …}],
    "accounts": [...], "imports": [...], "transactions": [...], "position_lots": [...], "xtb_snapshots": [...],
    "bond_holdings": [...], "savings_accounts": [...], "savings_rates": [...], "savings_balances": [...],
    "savings_flows": [...], "tags": [...], "tag_links": [...], "theses": [...], "journal_entries": [...],
    "scenarios": [...], "ai_reviews": [...], "corporate_actions": [...]
  }
}
```

- Każda tabela to lista wierszy ze wszystkimi kolumnami modelu poza `user_id`. `id` to **numer w pliku**; powiązania
  (`account_id`, `instrument_id`, `import_id`, `transfer_pair_id`, `savings_account_id`, `tag_id`,
  `target_instrument_id`) wskazują numery w pliku. Liczby dziesiętne jako tekst (bez utraty groszy), daty ISO.
- **Instrumenty i serie obligacji są wspólne**, więc w pliku są tylko te, do których odwołują się dane użytkownika
  (też scenariusze i ręczne korekty), z pełnymi kolumnami (bez `price_checked_at`, `price_error`, `created_at`).
- **Numery w JSON-ach:** `scenarios.allocation/steps` (`instrument_id`, `from_instrument_id`, `to_instrument_id`),
  `ai_reviews.account_ids`, `preferences.accounts_fixed` — też numery w pliku, zamieniane przy wczytaniu.
- **Ręczne korekty** (`corporate_actions` ze `source = 'manual'` użytkownika) wchodzą; wspólne (XTB, dostawca) nie.
- **Nie wchodzą:** ceny, kursy, CPI, stopy NBP, limity IKE/IKZE (wspólne), `daily_valuations` (przeliczane),
  e-mail, hasło i sesje.

## 3. Wczytanie (API)

- `GET /api/backup` → plik (nagłówek `Content-Disposition: attachment; filename="evenkeel-kopia-RRRR-MM-DD.json"`).
- `POST /api/backup/check` (plik) → `{exported_at, app_version, counts: {accounts, transactions, bond_holdings,
  savings_accounts, tags, notes, scenarios, ai_reviews}}` (notes = tezy + wpisy dziennika).
- `POST /api/backup/restore` (plik + pole `confirm`) → te same liczby; `confirm` różne od „ZASTĄP” → 422.
- **Sprawdzenie pliku** (wspólne dla `check` i `restore`), komunikaty po polsku:
  - nie JSON / nie `format: evenkeel-backup` → „To nie jest plik kopii Evenkeel.”;
  - `version` > 1 → „Kopia pochodzi z nowszej wersji Evenkeel. Zaktualizuj aplikację.”;
  - nieznana tabela lub kolumna, brak wymaganej kolumny, powiązanie do numeru, którego nie ma w pliku →
    „Plik kopii jest uszkodzony: <co i gdzie>.”;
  - powyżej 20 MB → 413 „Plik jest za duży (maks. 20 MB).”.
- **Zastąpienie w jednej transakcji bazy:** usunięcie danych użytkownika (konta z kaskadą, tagi, tezy, dziennik,
  scenariusze, przeglądy, ręczne korekty, wyceny), dopisanie instrumentów i serii, których brak (istniejących nie
  zmieniamy — są wspólne), wstawienie wierszy z nowymi numerami, ustawienie `preferences` i `base_currency`,
  `mark_stale(od zawsze)`, zatwierdzenie; potem przeliczenie w tle (jak po usunięciu konta). Błąd bazy przy
  wstawianiu (np. zła wartość) → wycofanie całości, 422 „Plik kopii jest uszkodzony: …”, stare dane zostają.
- Nowe instrumenty mają `price_checked_at = NULL`, więc proces w tle pobiera ich historię cen (`backfill`).
- **Wybór kont w przeglądarce** (`localStorage`) po wczytaniu traci znaczenie; ekran po sukcesie zapisuje „Cały
  portfel” dla tego użytkownika.

## 4. Odświeżanie cen (API)

`GET /api/market/schedule` → `{intraday_every_minutes, intraday_from, intraday_to, daily_at, timezone,
last_refreshed_at}` z ustawień (`market_*` w `config.py`, te same co proces w tle) i `prices_refreshed_at`
użytkownika.

## 5. Kod

- `api/app/backup/`: `tables.py` (opis tabel: model, powiązania, kolejność), `export.py`, `restore.py`
  (sprawdzenie + zastąpienie), `schemas.py`, `router.py`. Opis tabel jest jeden dla zapisu i wczytania, a test
  pilnuje, że każda tabela z `user_id` albo `account_id` jest w kopii albo świadomie pominięta — nowa tabela w
  przyszłości nie zginie po cichu.
- `api/app/market/` (albo `portfolio`) — `GET /api/market/schedule`.
- Web: `screens/settings/BackupScreen.tsx`, `screens/settings/RefreshScreen.tsx`, rejestr, trasy, `api/endpoints.ts`.

## 6. Testy

- **Tam i z powrotem:** użytkownik A z danymi każdego rodzaju (import XTB, operacje ręczne z parą przelewu,
  obligacje, oszczędności, tagi na wszystkich poziomach, tezy, dziennik, scenariusz z instrumentem, przegląd z
  kontem, ręczny split, preferencje z kontem) → kopia → wczytanie do B → kopia B równa kopii A (poza `exported_at`
  i numerami, porównane po zamianie numerów na kolejne).
- Wczytanie zastępuje: dane B sprzed wczytania znikają; dane innych użytkowników nietknięte; wycena oznaczona do
  przeliczenia.
- Przeprowadzka: instrument z pliku, którego nie ma w bazie, zostaje założony z `price_checked_at = NULL`.
- Odrzucenia: nie JSON, inny format, wersja 2, nieznana kolumna, zły numer powiązania, brak „ZASTĄP”, za duży plik,
  zła wartość w środku pliku (stare dane zostają).
- `GET /api/market/schedule`.
- Web: podgląd po wyborze pliku, przycisk aktywny dopiero po „ZASTĄP”, sukces → Pulpit, błąd pliku; ekran
  odświeżania; wyszukiwanie.
- e2e: pobranie kopii po imporcie XTB, wczytanie jej na nowym koncie, ta sama wartość na Pulpicie.

## Poza zakresem

- Szyfrowanie pliku, automatyczne kopie, łączenie kopii z obecnymi danymi.
- Zmiana harmonogramu odświeżania.
- Kopia całej bazy (wszyscy użytkownicy) — to `pg_dump` w `backups/`.
