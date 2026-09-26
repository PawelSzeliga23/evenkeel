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

## Testy

```bash
docker compose run --rm api pytest
```

## Baza danych

```bash
docker compose exec db psql -U portfolio      # konsola SQL bazy deweloperskiej
```
