# Portfolio Tracker

Aplikacja do śledzenia portfela inwestycyjnego (XTB, obligacje skarbowe, konta oszczędnościowe).
Specyfikacja: `docs/superpowers/specs/2026-09-26-portfolio-tracker-design.md`.

## Wymagania

- Docker Desktop (z Docker Compose)

## Uruchomienie

```bash
cp .env.example .env        # i ustaw JWT_SECRET
docker compose up --build   # API: http://localhost:8000, dokumentacja: http://localhost:8000/docs
```

Bez pliku `.env` z ustawionym `JWT_SECRET` (min. 32 znaki) `docker compose` odmówi startu.

## Testy

```bash
docker compose run --rm api pytest
```

## Baza danych

```bash
docker compose exec db psql -U portfolio      # konsola SQL bazy deweloperskiej
```

## Worker i dane rynkowe

`docker compose up` uruchamia też usługę `worker` (ten sam obraz, `python -m app.worker`):

- przy starcie i codziennie o `MARKET_DAILY_AT` (domyślnie 23:00, Europe/Warsaw): ceny instrumentów, które
  ktoś posiada lub którymi handlował (Yahoo), kursy NBP (tabela A), inflacja GUS r/r, stopa referencyjna NBP;
  usuwa refresh tokeny wygasłe lub unieważnione ponad 30 dni temu;
- co 5 minut: pełna historia cen dla nowych instrumentów (np. po imporcie XTB lub po zmianie symbolu).

Błąd źródła nie zatrzymuje workera — jest w logach (`docker compose logs -f worker`) i w polu `price_error`
instrumentu. Testy nie łączą się z siecią.

## API (plan 1)

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/api/health` | stan API i bazy |
| POST | `/api/auth/register` | rejestracja `{email, password, invite_code?}` |
| POST | `/api/auth/login` | logowanie → `access_token` + ciasteczko `refresh_token` |
| POST | `/api/auth/refresh` | nowy `access_token` (rotacja ciasteczka) |
| POST | `/api/auth/logout` | wylogowanie |
| GET | `/api/auth/me` | zalogowany użytkownik |
| GET/POST | `/api/accounts` | lista / utworzenie konta |
| GET/PATCH/DELETE | `/api/accounts/{id}` | konto |
| POST | `/api/imports/preview` | podgląd importu XTB (multipart `files`: XLSX / ZIP / wiele plików) — nic nie zapisuje |
| POST | `/api/imports` | zapis importu XTB (te same pliki); całość albo nic |
| GET | `/api/imports` | historia importów |
| GET | `/api/transactions` | operacje (`account_id`, `type`, `limit`, `offset`) |
| GET | `/api/instruments` | instrumenty użytkownika: waluta, symbol u dostawcy cen, ostatnia cena i jej data, błąd cen |
| PATCH | `/api/instruments/{id}` | ręczny symbol u dostawcy cen `{price_symbol}` (`null` = automatyczny); historia pobierze się ponownie |
| GET | `/api/portfolio/summary` | pulpit: wartość, gotówka, wpłacony kapitał, zysk łączny, zmiana dzienna, dywidendy i odsetki netto, alokacja wg kont i typów (`account_id`) |
| GET | `/api/portfolio/history` | wartość dzień po dniu z wpłaconym kapitałem i operacjami (`account_id`, `from`, `to`) |
| GET | `/api/positions` | pozycje i gotówka na dzień (`account_id`, `date`): wartość, koszt, zysk (efekt ceny / waluty), dywidendy, udział, źródło ceny |
| GET | `/api/positions/{account_id}/{instrument_id}` | szczegóły pozycji: partie z SL/TP, sprzedaże, dywidendy, operacje, zgodność z XTB (`date`) |

### Wycena

Wartość portfela dzień po dniu jest w tabeli `daily_valuations` (pamięć podręczna — można ją skasować i odbudować).
Przelicza się w tle: zaraz po zapisie importu, po zmianie symbolu instrumentu i po każdej aktualizacji danych rynkowych
w workerze (od najwcześniejszej zmienionej daty). `recalculating: true` w `/api/portfolio/summary` oznacza, że przeliczenie
jeszcze trwa. Pozycja bez cen u dostawcy jest wyceniana ostatnią wartością z XTB i ma flagę `xtb_price`.

Chronione endpointy wymagają nagłówka `Authorization: Bearer <access_token>`.
Błędy mają format `{"code": "...", "message": "...", "details": {...}}`.
