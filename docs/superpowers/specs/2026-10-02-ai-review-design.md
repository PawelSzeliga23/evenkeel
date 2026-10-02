# Przegląd portfela przez Claude (kopiowanie) i Analiza w dolnym pasku — decyzje projektowe

**Data:** 2026-10-02
**Wcześniej:** pomysł właściciela z 29.09 w roadmapie („Na później — podpowiedzi AI po przeglądzie portfela”). Zasada właściciela: liczby jak w XTB (pamięć `mirror-xtb-numbers`).

## Cel

Właściciel chce co jakiś czas dostać od Claude przegląd swojego portfela: ocenę, mocne strony i ryzyka, sytuację na rynku dotyczącą tego, co ma, informacje o każdym instrumencie, pomysły i propozycje. Liczby mają pochodzić z naszej wyceny, a informacje rynkowe z aktualnych stron branżowych, ze źródłami. Przegląd ma zostać w aplikacji, żeby można było do niego wrócić i wygodnie go czytać.

Analiza się rozrasta (Symulator, Przegląd AI, potem plany 7c–7f), więc dostaje stałe miejsce w dolnym pasku.

## Decyzje właściciela (2026-10-02)

1. Przegląd **na żądanie**, bez automatycznych.
2. **Sam przegląd**, bez rozmowy i dopytywania.
3. Obszary: struktura, ryzyko, wyniki, koszty i podatki, **rynek** (trendy z sieci) oraz **twoje instrumenty** (każdy osobno: plusy i minusy, prognozy ze stron branżowych).
4. **Najpierw kopiowanie przez Claude Pro, bez API.** Aplikacja przygotowuje jeden plik z poleceniem i danymi, a właściciel wkleja go w claude.ai. Claude Pro nie daje dostępu przez API, więc integracja z API to możliwość na później (roadmapa).
5. **Dwie osobne sekcje:** „Pomysły do rozważenia” oraz „Propozycje”. Propozycje są konkretne, z wyraźnym zastrzeżeniem, że to nie porada inwestycyjna.
6. **Pełne dane:** cały stan kont i wszystkie miary, które wyliczamy. Bez numerów rachunków i bez e-maila.
7. Odpowiedź Claude w formie **README**: nagłówki, tabele, listy, w jednym bloku ` ```markdown `, żeby kopiowała się jednym kliknięciem. W aplikacji odpowiedź jest zapisywana i ładnie wyświetlana. Raport jest zwykłym tekstem; kolor ma tylko znacznik przy nagłówku sekcji.
8. **Dolny pasek na telefonie:** Analiza zamiast Ustawień (Pozycje zostają). Ustawienia przechodzą do nowego górnego wiersza Pulpitu: logo Evenkeel po lewej, koło zębate po prawej (makieta, wariant A). Odnośnik do Analizy na Pulpicie zostaje.

## 1. Nawigacja

- Telefon, dolny pasek: `Pulpit · Pozycje · [+] Dodaj · Historia · Analiza`.
- Komputer, boczny pasek: Pulpit, Pozycje, Dodaj, Historia, **Analiza**, Ustawienia (Ustawienia zostają w pasku bocznym, bo jest miejsce).
- Pulpit na telefonie dostaje górny wiersz: znak i wordmark Evenkeel po lewej, przycisk-ikona „Ustawienia” (koło zębate, cel dotyku 44 px) po prawej. Pod nim obecny wiersz (wybór kont, godzina odświeżenia, ⟳) bez zmian.
  - Na komputerze ten wiersz jest ukryty, bo logo i Ustawienia są w pasku bocznym.
- Aktywna zakładka „Analiza” obejmuje też podstrony `/analiza/*`.
- Ekran Ustawień (`/ustawienia`) dostaje na telefonie link powrotny „Pulpit”, bo nie ma już zakładki.

## 2. Pakiet dla Claude (plik `.md`)

Budowany na serwerze: `GET /api/reviews/package?account_id=…`. Odpowiedź to `text/markdown` z nagłówkiem `Content-Disposition: attachment; filename="evenkeel-przeglad-RRRR-MM-DD.md"`. Zakres kont jest taki jak we wspólnym filtrze kont.

### A. Polecenie

- **Rola:** doświadczony znajomy, który zna się na inwestowaniu; po polsku, konkretnie, bez żargonu (trudniejsze pojęcia wyjaśnia jednym zdaniem).
- **Zasady:**
  - liczby o portfelu wyłącznie z danych w pliku; nie przelicza ich inaczej, nie wymyśla kursów;
  - informacje o rynku i instrumentach tylko z wyszukiwania w sieci (ostatnie 1–3 miesiące), każda z linkiem i datą; gdy czegoś nie znajdzie, pisze to wprost;
  - kwoty po polsku („1 234,56 zł”), procenty z przecinkiem;
  - w „Propozycjach” dopisek, że to nie porada inwestycyjna i że decyzja należy do właściciela.
- **Wyszukiwanie:**
  - dla każdego instrumentu z pozycji: wiadomości, prognozy, opinie;
  - kontekst: główne indeksy, w które inwestuje portfel, kursy EUR/PLN i USD/PLN, inflacja w Polsce, stopy NBP (dla EDO i kont oszczędnościowych).
- **Format odpowiedzi:** wyłącznie jeden blok ` ```markdown `, a w nim dokładnie te nagłówki drugiego poziomu, w tej kolejności:
  1. `## Ocena ogólna`
  2. `## Mocne strony`
  3. `## Ryzyka`
  4. `## Rynek`
  5. `## Twoje instrumenty` (każdy instrument jako `### TICKER — nazwa`: co to jest, plusy, minusy, prognozy i opinie ze źródłami)
  6. `## Pomysły do rozważenia`
  7. `## Propozycje`
  8. `## Pytania do przemyślenia`
  9. `## Źródła`

  Przed blokiem i po nim nie ma żadnego tekstu.

### B. Dane

Stan na dzień przygotowania, dla wybranych kont, w tabelach Markdown. Każda tabela ma podpis z datą „stan na”.

1. **Podsumowanie:** wartość do wypłaty, wartość rynkowa, koszty wyjścia, gotówka, wpłacono, zysk łącznie (zł i %), zmiana dnia, dywidendy i odsetki netto, opłaty, TWR od początku.
2. **Konta:** nazwa, typ (IKE / IKZE / zwykłe), rodzaj (makler, obligacje, oszczędnościowe, gotówka), waluta, wartość, udział.
3. **Pozycje:**
   - ticker, nazwa, rodzaj, waluta, liczba sztuk;
   - cena zakupu jak w XTB (średnia) i z przewalutowaniem XTB, cena bieżąca i jej data;
   - wartość, koszt, zysk (zł i %), efekt ceny, efekt waluty, dywidendy, udział, zmiana dnia;
   - flaga „cena z XTB”, gdy brak notowań.
   - **Partie:** dla każdej data zakupu, sztuki, cena jak w XTB, dni trzymania.
4. **Obligacje:** seria, liczba, data zakupu, oprocentowanie bieżącego okresu, wartość, data wykupu, konto (IKE czy nie).
5. **Konta oszczędnościowe:** saldo, oprocentowanie, kapitalizacja, odsetki dopisane.
6. **Alokacja:** według rodzaju, waluty i konta (zł i %).
7. **Miary z Analizy** za „Wszystko” i „1R”: XIRR i TWR (okresowe i roczne), zysk, zmienność, Sharpe, maks. obsunięcie (z datami), obecne obsunięcie, najlepszy i najgorszy dzień.
8. **Historia:** na koniec każdego miesiąca wartość i wpłacono; miesięczne stopy zwrotu (siatka z Analizy).
9. **Limity IKE/IKZE** w bieżącym roku: wpłacono, limit, zostało.
10. **Zamknięte inwestycje:** instrument, zrealizowany zysk (zł i %), daty.
11. **Scenariusze z Symulatora:** nazwa, punkt wyjścia, różnica względem portfela (wartość i XIRR, cały okres).

**Nigdy w pakiecie:** numery rachunków (`external_account_number`), e-mail, identyfikatory z bazy, identyfikatory pozycji XTB.

## 3. Zapisane przeglądy

- **Tabela `ai_reviews`:** `id`, `user_id` (FK, cascade), `created_at`, `account_ids` (JSONB, pusta lista = cały portfel), `account_label` (np. „Cały portfel”, „IKE”), `content` (tekst Markdown, najwyżej 200 000 znaków), `sections` (liczba rozpoznanych nagłówków z listy).
- **API:**
  - `GET /api/reviews` (lista bez treści: id, data, zakres, sekcje);
  - `POST /api/reviews {content, account_ids}` → 201;
  - `GET /api/reviews/{id}`, `DELETE /api/reviews/{id}`;
  - tylko własne przeglądy (cudzy → 404);
  - pusta treść → 422; za długa → 422 „Przegląd jest za długi (najwyżej 200 000 znaków).”
- **Wklejanie:**
  - serwer zdejmuje otaczający blok ` ```markdown … ``` ` (z samymi ` ``` ` także) i białe znaki;
  - liczy rozpoznane nagłówki; gdy jest 0, i tak zapisuje, a ekran pokazuje uwagę „Nie rozpoznano sekcji przeglądu. Czy to na pewno odpowiedź na pakiet?”.

## 4. Ekrany

- **Analiza:** karta „Przegląd AI”: data ostatniego przeglądu (albo „Jeszcze nie ma przeglądu”) i link „Przegląd portfela”.
- **`/analiza/przeglad`:**
  - wybór kont;
  - **Krok 1:** „Pobierz plik” i „Kopiuj do schowka”, z instrukcją: „Załącz plik albo wklej treść w claude.ai. Claude przeszuka sieć i odpowie blokiem Markdown — skopiuj go przyciskiem Copy.”;
  - **Krok 2:** pole „Wklej odpowiedź Claude” i przycisk „Zapisz przegląd”; po zapisie przejście do przeglądu;
  - **Zapisane przeglądy:** lista (data, zakres kont, „9/9 sekcji”).
- **`/analiza/przeglad/:id`:**
  - przegląd wyświetlany jak README: `react-markdown` z `remark-gfm` (tabele), bez wykonywania HTML;
  - linki otwierane w nowej karcie (`rel="noopener noreferrer"`);
  - nagłówki sekcji z kolorowym znacznikiem: Ocena ogólna — bursztyn, Mocne strony — zieleń, Ryzyka — czerwień, Rynek — niebieski, Twoje instrumenty — niebieski, Pomysły — fiolet, Propozycje — bursztyn, Pytania — szary, Źródła — szary;
  - tekst zwykły, tabele w stylu aplikacji, bez poziomego przewijania strony (szeroka tabela przewija się we własnym pudełku);
  - „Usuń przegląd” z potwierdzeniem.

## 5. Testy

- **API:**
  - zawartość pakietu na danych z `valuation_seed`: liczby z naszych wyliczeń, nagłówki odpowiedzi w poleceniu, brak numeru rachunku i e-maila, filtr kont, nazwa pliku;
  - zapis z blokiem i bez, liczba sekcji, limit długości, lista, izolacja użytkowników, usuwanie.
- **Web:**
  - pasek nawigacji (Analiza zamiast Ustawień na telefonie), koło zębate na Pulpicie prowadzi do Ustawień;
  - pobranie i kopiowanie pakietu;
  - wklejenie i zapis;
  - widok przeglądu (nagłówki ze znacznikami, tabela, link w nowej karcie, brak wykonania HTML);
  - usuwanie, stany pusty i błąd.
- **e2e:** z Analizy przygotowanie pakietu, wklejenie przykładowej odpowiedzi, zapis i widok.

## Na później (roadmapa)

- **Przegląd przez API Anthropic:** przycisk „Przejrzyj przez API” wysyła ten sam pakiet (Claude Opus 5.5 z narzędziem `web_search`), z kluczem API w ustawieniach serwera. Szacunek z 2026-10-02: ok. 0,30 USD za przegląd.
- **Rozmowa o przeglądzie** (dopytywanie).
