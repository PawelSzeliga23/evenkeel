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

Chronione endpointy wymagają nagłówka `Authorization: Bearer <access_token>`.
Błędy mają format `{"code": "...", "message": "...", "details": {...}}`.
