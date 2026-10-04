# Plan 8a — Ustawienia: lista w stylu iPhone'a z wyszukiwarką, ukrywanie kwot, ekran startowy, domyślne widoki (decyzje projektowe)

**Data:** 2026-10-04
**Zakres całości (Ustawienia):**
- **8a** — ten dokument;
- **8b** — motyw jasny, ciemny albo systemowy;
- **8c** — dane i kopia: eksport i wczytanie portfela, godziny odświeżania cen;
- **8d** — konto użytkownika: zmiana e-maila, wylogowanie z innych urządzeń, usunięcie konta.

Części 8b–8d dopisują się później do grup z 8a.

## Decyzje właściciela (2026-10-04)

1. **Co przeszkadza:** długa, płaska lista i brakujące ustawienia.
2. **Ustawienia jak na iPhonie:**
   - na górze wyszukiwarka;
   - pod nią lista wierszy w grupach: Profil, Konta, Źródła cen…;
   - wiersz otwiera podstronę.
3. **Wyszukiwarka** przeszukuje też opcje w środku, np. „hasło” → „Zmień hasło · Profil”.
4. **Nawigacja na komputerze:**
   - 5 zakładek razem: Pulpit, Pozycje, Dodaj, Historia, Analiza;
   - **Ustawienia na dole paska bocznego**, a nie jako szósta pozycja.
   - Na telefonie bez zmian: 5 zakładek i zębatka na Pulpicie.
5. **Zapis ustawień jest mieszany:**
   - ekran startowy i domyślne widoki są na serwerze, wspólne dla urządzeń;
   - ukrywanie kwot jest w przeglądarce, osobno na każdym urządzeniu.
6. **Ukrywanie kwot:**
   - kwoty wyglądają jak „•••• zł”;
   - procenty, ilości, ceny jednostkowe i kształt wykresów zostają widoczne;
   - przełącznik „oko” jest na Pulpicie, a ta sama opcja w Ustawieniach.

## Rejestr ustawień

Jedna lista w kodzie (`web/src/settings/registry.ts`) opisuje każdy wiersz i każdą opcję. Pola:
- `id`;
- grupa;
- nazwa;
- ikona;
- słowa kluczowe;
- adres (`to`, z kotwicą `#…` dla opcji w środku podstrony);
- opcjonalna wartość po prawej, liczona z danych;
- opcjonalna nazwa „rodzica” do wyników wyszukiwania.

Z rejestru powstają zarówno lista główna, jak i wyniki wyszukiwania. Kolejne części (8b–8d) dopisują swoje pozycje tutaj.

## Ekran Ustawienia (`/ustawienia`)

- **Pole „Szukaj w ustawieniach”** (`type="search"`) na górze.
- **Grupy z wierszami.** Każdy wiersz ma ikonę, nazwę, wartość po prawej (szarą) i `›`. Cały wiersz jest linkiem.

| Grupa | Wiersz | Wartość po prawej | Dokąd |
|---|---|---|---|
| Konto | Profil | e-mail | `/ustawienia/profil` |
| Portfel | Konta | liczba kont | `/ustawienia/konta` |
| Portfel | Źródła cen | „N do sprawdzenia” albo „w porządku” | `/ustawienia/zrodla-cen` |
| Portfel | Tagi walorów | liczba tagów | `/ustawienia/tagi` |
| Portfel | Dziennik | — | `/ustawienia/dziennik` |
| Wygląd i prywatność | Ukrywanie kwot | „wł.” / „wył.” | `/ustawienia/wyglad` |
| Wygląd i prywatność | Ekran startowy | nazwa ekranu | `/ustawienia/wyglad#start` |
| Domyślne widoki | Domyślne widoki | — | `/ustawienia/domyslne` |
| O aplikacji | O aplikacji | wersja | `/ustawienia/o-aplikacji` |

- **Podstrony** mają u góry link „‹ Ustawienia”.
  - Nowe podstrony:
    - **Profil** (`/ustawienia/profil`): e-mail, „Zmień hasło”, „Wyloguj”;
    - **Konta** (`/ustawienia/konta`): dzisiejsza lista kont z ekranu Ustawień, każde konto prowadzi do `/ustawienia/konta/{id}` jak dziś;
    - **Wygląd i prywatność** (`/ustawienia/wyglad`);
    - **Domyślne widoki** (`/ustawienia/domyslne`);
    - **O aplikacji** (`/ustawienia/o-aplikacji`): logo, wersja.
  - Istniejące adresy zostają: `/ustawienia/haslo`, `/ustawienia/zrodla-cen`, `/ustawienia/tagi`, `/ustawienia/dziennik`, `/ustawienia/konta/{id}`.
  - „‹ Ustawienia” w tych podstronach dalej prowadzi do `/ustawienia`, a konto `/ustawienia/konta/{id}` wraca do `/ustawienia/konta`.

## Wyszukiwarka

- **Wyniki filtrują się od pierwszego znaku.** Bez wpisanego tekstu widać zwykłą listę grup.
- **Porównanie** nie zależy od wielkości liter ani od polskich znaków: „haslo” znajduje „Zmień hasło”, „lodz” znajduje „Łódź”.
- **Przeszukiwane są:**
  - nazwy i słowa kluczowe z rejestru:
    - opcje: „Zmień hasło”, „Wyloguj”, „Ukrywanie kwot”, „Ekran startowy”, „Konta na starcie”, „Okres w Analizie”, „Okres w Walorach i Tagach”, „Zakres wykresu wartości”, „Zakres wykresu ceny”, „Walory bez oszczędności i obligacji”, „Wersja”;
    - słowa kluczowe, np. „prywatność, ukryj, oko” przy ukrywaniu kwot, „start, pierwszy ekran” przy ekranie startowym;
  - **nazwy Twoich kont** (wynik „XTB IKE · Konta” → strona konta);
  - **nazwy tagów** (wynik „emerytura · Tagi walorów” → `/ustawienia/tagi`).
- **Wynik:**
  - wiersz z nazwą i szarym miejscem, np. „Zmień hasło · Profil”;
  - prowadzi prosto do opcji: podstrona, a dla opcji w środku kotwica, która przewija do niej.
- **Bez wyników:** „Brak wyników dla „{tekst}”.”
- Najwyżej 20 wyników, w kolejności rejestru, po nich konta, po nich tagi.

## Nawigacja (komputer)

- Pasek boczny ma 5 zakładek u góry.
- Pod nimi jest wolne miejsce, a **„Ustawienia” są przypięte na dole paska** (`margin-top: auto`).
- Na telefonie bez zmian.

## Ukrywanie kwot

- **Gdzie się włącza:**
  - przycisk „oko” na Pulpicie obok zębatki, z etykietą dostępności „Ukryj kwoty” albo „Pokaż kwoty”;
  - opcja „Ukrywanie kwot” (przełącznik) w Wygląd i prywatność.
- **Zapis:**
  - w przeglądarce, `localStorage` `evenkeel.hideAmounts`;
  - brak dostępu do pamięci działa jak „wył.”, a wybór trwa wtedy do końca wizyty.
- **Działanie:**
  - wszystkie kwoty w PLN i w walutach z wspólnych funkcji formatujących (`formatMoney` i pokrewne) pokazują się jako `•••• zł` (albo `•••• EUR` dla waluty);
  - dotyczy też podpisów osi i dymków na wykresach;
  - procenty, liczby sztuk, ceny jednostkowe (`formatPrice`), daty i kształt wykresów zostają widoczne.
- **Nie** ukrywa:
  - wartości w polach formularzy (Dodaj, edycja operacji, salda), bo tam je wpisujesz;
  - paczki przeglądu AI.

## Ekran startowy

- Do wyboru: Pulpit (domyślnie), Pozycje, Historia, Analiza.
- Po zalogowaniu i przy wejściu na adres `/` w nowej sesji przeglądarki aplikacja przechodzi na wybrany ekran.
  - Raz na sesję karty: znacznik w `sessionStorage`.
  - Kliknięcie zakładki „Pulpit” w tej samej sesji dalej prowadzi na Pulpit.

## Domyślne widoki

Domyślne wartości to te, z którymi ekran się otwiera. Zmiana na samym ekranie działa tylko na tę chwilę, tak jak dziś.

| Ustawienie | Klucz | Opcje | Domyślnie (= dziś) |
|---|---|---|---|
| Konta na starcie | `accounts_start` | `last` (ostatnio wybrane) · `all` (zawsze cały portfel) · `fixed` (wybrane konta, lista `accounts_fixed`) | `last` |
| Okres w Analizie i Symulatorze | `analysis_period` | `1m`, `3m`, `1y`, `ytd`, `all` | `all` |
| Okres w Walorach i Tagach | `holdings_period` | `1d`, `1w`, `1m`, `1y`, `ytd`, `all` | `all` |
| Zakres wykresu wartości (Pulpit, Ekspozycja) | `value_range` | `1M`, `3M`, `1R`, `ALL` | `1R` |
| Zakres wykresu ceny | `price_range` | `buy`, `6m`, `1y`, `5y`, `max` | `buy` |
| Walory bez oszczędności i obligacji | `holdings_without_fixed_income` | `true` / `false` | `false` |

- Walory startowały dotąd od „Dzień”. Teraz startują od `holdings_period`, domyślnie `all`, tak samo jak Tagi.
- **„Konta na starcie”:**
  - `last` to dzisiejsze zapamiętywanie ostatniego wyboru w przeglądarce;
  - `all` oznacza, że przy otwarciu aplikacji wybór jest pusty, czyli cały portfel; zmiany w trakcie działają do końca sesji;
  - `fixed` oznacza, że przy otwarciu wybór to `accounts_fixed`. Konta usunięte są pomijane, a gdy nie zostanie żadne, pokazuje się cały portfel.
- **Podstrona „Domyślne widoki”:**
  - każde ustawienie to pole wyboru albo przełącznik z opisem;
  - przy `fixed` są pola do zaznaczenia kont;
  - zapis następuje od razu po zmianie, z komunikatem „Zapisano.” w `role="status"`.

## API

- **Migracja `0016_user_preferences`:** `users.preferences JSONB NOT NULL DEFAULT '{}'`.
- **`GET /api/auth/me`:** `UserOut` dostaje `preferences: PreferencesOut`, czyli wszystkie klucze z tabeli. Brakujący klucz dostaje wartość domyślną.
- **`PATCH /api/me/preferences`:**
  - przyjmuje dowolny podzbiór kluczy;
  - zwraca pełne `PreferencesOut`;
  - walidacja:
    - nieznana wartość → 422 `validation_error`;
    - nieznany klucz → 422 (`extra="forbid"`);
    - `accounts_fixed` to lista id kont użytkownika, a cudze albo nieistniejące konto → 404.
- **Ekran startowy:** klucz `start_screen`, wartości `dashboard`, `positions`, `history`, `analysis`, domyślnie `dashboard`.

## Testy

- **API:**
  - domyślne ustawienia nowego użytkownika;
  - zapis części kluczy bez ruszania reszty;
  - zła wartość, nieznany klucz → 422;
  - `accounts_fixed` z cudzym kontem → 404;
  - usunięte konto znika z `accounts_fixed` w odpowiedzi.
- **Web:**
  - lista grup z wartościami po prawej;
  - wyszukiwanie:
    - „haslo” znajduje „Zmień hasło · Profil”;
    - nazwa konta, nazwa tagu;
    - brak wyników;
  - pasek boczny: Ustawienia na końcu, z klasą przypięcia do dołu;
  - ukrywanie kwot:
    - „oko” na Pulpicie ukrywa kwotę wartości portfela;
    - procent zostaje;
    - formularz Dodaj pokazuje wpisaną kwotę;
    - stan przetrwa przeładowanie;
  - ekran startowy: `start_screen = "analysis"` → po zalogowaniu Analiza, a klik w Pulpit → Pulpit;
  - domyślne widoki:
    - `analysis_period` na Analizie;
    - `holdings_period` na Walorach i Tagach;
    - `value_range` na Pulpicie;
    - `price_range` w szczegółach pozycji;
    - `holdings_without_fixed_income` na Walorach;
    - `accounts_start = all` i `fixed`.
- **e2e:** wyszukiwanie „hasło” w Ustawieniach prowadzi do zmiany hasła; zrzut `ustawienia.png`.

## Poza zakresem

- Motyw (8b), kopia i godziny odświeżania (8c), zmiana e-maila, sesje i usunięcie konta (8d).
- Ukrywanie kwot w paczce AI i w formularzach.
- Zmiana układu na telefonie.
