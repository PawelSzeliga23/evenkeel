# Plan 6c — przegląd i ustawienia: decyzje projektowe

**Data:** 2026-09-29
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §5 „Mapowanie tickerów”, §6 „Zamknięte inwestycje”,
„Ekspozycja walutowa”, „Limity IKE/IKZE”, §7 ekran 5.
**Poprzednie decyzje frontendu:** `2026-09-28-06a-frontend-foundation-design.md`, `2026-09-29-06b-add-and-history-design.md`.

## Cel

Domknąć etap 1 od strony użytkownika. Widoki, które mają już API z planu 4b (zamknięte inwestycje, ekspozycja
walutowa w czasie, limity IKE/IKZE), dostają ekrany. Ekran „Więcej” zamienia się w Ustawienia: profil ze zmianą
hasła, konta i źródła cen. Przy okazji poprawiamy ważne dla użytkownika błędy z przeglądów 6a i 6b. Pozostałe
drobiazgi z tych przeglądów przechodzą do planu 6d.

## Podział na plany

Trzy plany na jednej gałęzi `feature/plan-6c`, wykonywane po kolei: `6c-backend`, `6c-frontend-1` (Ustawienia),
`6c-frontend-2` (przegląd i poprawki).

## 1. Backend

### 1.1 Zmiana hasła
- `POST /api/auth/password` z treścią `{current_password, new_password}`. Nowe hasło ma te same zasady co przy
  rejestracji (10–128 znaków). Odpowiedź to `204`.
- Złe obecne hasło → `400 wrong_password` („Obecne hasło jest nieprawidłowe.”). Próby liczy ten sam limiter co
  logowanie, a po przekroczeniu jest `429 rate_limited`.
- Po zmianie wszystkie tokeny odświeżania użytkownika są unieważnione **oprócz** tego z ciasteczka bieżącego
  żądania. Ta sesja zostaje, a inne urządzenia wylogują się przy najbliższym odświeżeniu, czyli najpóźniej po
  15 minutach, kiedy wygaśnie ich token dostępu. Świadomie nie unieważniamy tokenów dostępu, bo są bezstanowe.

### 1.2 Konta: co zniknie przy usunięciu
- `GET /api/accounts/{id}/usage` zwraca `{transactions, imports, bond_holdings, savings_entries}`, czyli liczby
  rekordów, które usunięcie konta skasuje kaskadowo. `savings_entries` to suma wpłat i wypłat, sald i stawek konta
  oszczędnościowego. Cudze konto daje `404`.
- `DELETE /api/accounts/{id}` dodatkowo oznacza wycenę do przeliczenia (`mark_stale` od `date.min`) i przelicza ją
  w tle. Dziś tego nie robi, więc podsumowania mogłyby zostać nieaktualne.

### 1.3 Limity IKE/IKZE
- Migracja `0008` dopisuje do `wrapper_limits` limity na lata 2023–2026 dla `ike`, `ikze` i `ikze_self_employed`.
  Wiersz IKE 2026 już istnieje i zostaje. Kwoty pochodzą z obwieszczeń MRPiPS i trzeba je sprawdzić przy przeglądzie:

  | rok | IKE | IKZE | IKZE (samozatrudnieni) |
  |---|---|---|---|
  | 2023 | 20 805 | 8 322 | 12 483 |
  | 2024 | 23 472 | 9 388,80 | 14 083,20 |
  | 2025 | 26 019 | 10 407,60 | 15 611,40 |
  | 2026 | 28 260 | 11 304 | 16 956 |

- Wariantu „IKZE samozatrudniony” nie ma w wyborze typu konta (YAGNI). Wiersze w tabeli są tylko na przyszłość.

### 1.4 Szczegóły pozycji (poprawki z przeglądu 6a)
Przyczyna „Ceny —”: walutę instrumentu podaje tylko Yahoo. Gdy dostawca nie ma notowań, `instrument.currency` jest
puste, więc brakuje kursu zakupu (`fx_open`), a z nim ceny otwarcia partii. Dodatkowo wycena z danych XTB nigdy
nie ma ceny (`Quote.price = None`).
- `PositionOut.price_currency`: dla wyceny od dostawcy to waluta instrumentu, a `price` to kurs zamknięcia. Dla
  wyceny z danych XTB `price` to wartość jednej sztuki w PLN (`Quote.unit_pln`, 4 miejsca po przecinku), a
  `price_currency = "PLN"`. Bez wyceny oba pola są `null`.
- Cena otwarcia partii: gdy silnik jej nie zna, bierzemy `position_lots.open_price` z XTB (partia o tym samym
  `position_id`), ale tylko wtedy, gdy ilość XTB równa się ilości partii w bieżących jednostkach. Po splicie ceny
  z XTB nie można porównać, więc wtedy jest `null`.
- `PositionDetailOut.average_price` to średnia cena otwarcia ważona ilością partii, w walucie instrumentu. Wynosi
  `null`, gdy którakolwiek partia nie ma ceny otwarcia albo nie ma otwartych partii.

## 2. Frontend — Ustawienia (6c-frontend-1)

- Pozycja paska „Więcej” zmienia się w **„Ustawienia”** (ikona zębatki, trasa `/ustawienia`; `/wiecej`
  przekierowuje). Lista „Wkrótce” znika.
- Ekran Ustawień ma trzy sekcje:
  - **Profil**: e-mail, „Zmień hasło” (`/ustawienia/haslo`) i „Wyloguj”.
  - **Konta**: lista kont z nazwą, rodzajem i typem (zwykłe / IKE / IKZE). Wiersz prowadzi do
    `/ustawienia/konta/:id`.
  - **Źródła cen**: licznik problemów („1 instrument bez cen” albo „Wszystkie instrumenty mają ceny”) i link do
    `/ustawienia/zrodla-cen`.
- **Zmiana hasła**: obecne hasło, nowe i powtórzone nowe. Sprawdzamy w przeglądarce długość i zgodność obu pól.
  Po sukcesie pokazujemy komunikat „Hasło zmienione. Inne urządzenia zostaną wylogowane.” i wracamy do Ustawień.
- **Konto** (`/ustawienia/konta/:id`): zmiana nazwy i typu (zwykłe / IKE / IKZE); zmiana typu przelicza wycenę.
  Na dole jest strefa „Usuń konto”. Po kliknięciu pokazujemy, co zniknie (z `usage`, np. „42 operacje, 3 importy”),
  a przycisk usuwania jest aktywny dopiero po wpisaniu dokładnej nazwy konta. Po usunięciu unieważniamy zapytania
  portfela i wracamy do Ustawień. Nowych kont nie dodajemy ręcznie, bo powstają przy imporcie, dodaniu obligacji
  i dodaniu konta oszczędnościowego.
- **Źródła cen** (`/ustawienia/zrodla-cen`): wszystkie instrumenty, na górze te z problemem (`price_error` albo
  brak ceny). Wiersz pokazuje ticker XTB, nazwę, symbol Yahoo (z dopiskiem „ręczny”, gdy
  `price_symbol_overridden`), datę ostatniej ceny albo komunikat błędu. Kliknięcie rozwija edycję: pole symbolu,
  „Zapisz” i „Przywróć automatyczny” (`price_symbol: null`). Błąd walidacji symbolu pokazujemy po polsku.

## 3. Frontend — przegląd i poprawki (6c-frontend-2)

- **Zamknięte inwestycje**: Pozycje dostają przełącznik „Otwarte / Zamknięte” (`?widok=zamkniete`), a filtr konta
  działa w obu widokach. Widok zamknięty zaczyna się podsumowaniem (zysk zrealizowany, dywidendy, koszty, razem,
  zwrot %). Pod nim są wiersze per instrument (ticker, konto, status „sprzedane” lub „częściowo”, daty, razem i %).
  Rozwinięcie wiersza pokazuje sprzedaże tego instrumentu na tym koncie (data, ilość, czas trzymania, zysk). Pusty
  stan: „Nie masz jeszcze zamkniętych inwestycji.”
- **Ekspozycja w czasie** (`/ekspozycja`): na Pulpicie, w Alokacji w trybie „waluta”, pojawia się link „Zobacz
  w czasie”. Ekran ma bieżące udziały (jak na Pulpicie), wykres udziałów walut w czasie (skumulowane pola 100 %,
  zakresy 3M / 1R / wszystko), filtr konta i objaśnienie „waluta notowania, nie waluta aktywów bazowych”.
- **Limity** (`/limity`): na Pulpicie karta „Limity IKE/IKZE”, pokazywana tylko wtedy, gdy są konta IKE lub IKZE.
  Ma pasek „wpłacono X z Y zł w RRRR” dla bieżącego roku, a przy przekroczeniu stonowane ostrzeżenie. Ekran
  szczegółów pokazuje dla każdego typu bieżący rok z podziałem na konta i wcześniejsze lata. Przy braku limitu na
  dany rok wyświetla „brak limitu w danych”.
- **Poprawki z przeglądów:**
  - Formularz gotówki: podpowiedź kwoty pokazuje walutę wybranego konta zamiast „W złotych”. Po sukcesie są linki
    do Dodaj i do Historii.
  - Szczegóły pozycji: cena z `price_currency`, „Średnia cena” z `average_price`, a partie bez ceny pokazują
    „2 szt.” bez „po —”.
  - Sesja przy starcie: brak sieci pokazuje „Brak połączenia”. Błąd serwera (5xx) pokazuje osobny stan „Serwer ma
    problem” z przyciskiem ponowienia. `401` z `me()` tuż po odświeżeniu prowadzi do logowania.
- Test e2e: zmiana hasła, ponowne logowanie nowym hasłem i otwarcie widoku zamkniętych. Aktualizacja roadmapy:
  6c jako zrobiony, a pozostałe drobiazgi z 6a i 6b przechodzą do 6d.

## Poza zakresem
- Ręczne dodawanie kont, usuwanie użytkownika, „wyloguj wszędzie” (backlog).
- Wariant IKZE dla samozatrudnionych w wyborze typu konta.
- Drobne poprawki z przeglądów 6a i 6b spoza listy wyżej (idą do 6d).
