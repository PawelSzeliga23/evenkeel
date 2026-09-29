# Plan 6b: Dodaj, szczegóły obligacji i kont oszczędnościowych, Historia (decyzje projektowe)

> Uzupełnienie specyfikacji `2026-09-26-portfolio-tracker-design.md` (§4 model danych, §6 „Obligacje skarbowe”,
> „Konto oszczędnościowe”, §7 ekrany 2–4) i kontynuacja `2026-09-28-06a-frontend-foundation-design.md` (kierunek
> wizualny, architektura `web/`, zasady błędów i testów obowiązują bez zmian). Ustalone w rozmowie 2026-09-29.
> Na tym dokumencie powstaje plan `plans/2026-09-29-06b-add-and-history.md`.

## Zakres

Dawny plan 6b z roadmapy dzieli się na **6b** (ten dokument) i **6c**.

**6b:** dane, które użytkownik wprowadza sam, i ich przegląd:
1. Ekran **Dodaj** z wyborem: import XTB, obligacja, konto oszczędnościowe, operacja gotówkowa.
2. **Obligacje** (EDO): zakup z formularza, szczegóły, wykup przed terminem, usunięcie zakupu.
3. **Konto oszczędnościowe na wpłatach**: założenie z oprocentowaniem i kapitalizacją, wpłaty i wypłaty z datą,
   zmiana oprocentowania od daty, odsetki co do dnia.
4. **Ręczne operacje gotówkowe** na kontach typu „gotówka” (nowe API zapisu i usuwania).
5. **Historia**: wszystkie wpisy w jednej liście z filtrami i wyszukiwaniem (nowe API).

**6c (osobny plan):** Ustawienia (konta, mapowanie tickerów, profil), zamknięte inwestycje, ekspozycja walutowa
w czasie, limity IKE/IKZE.

**Poza 6b:** rodzaje obligacji inne niż EDO, edycja operacji (poprawka = usuń i dodaj), korekty na rachunkach
XTB, kupno/sprzedaż u innych brokerów, uwagi właściciela do wyceny instrumentów („zbyt optymistyczne wartości” —
rozmowa po 6b).

## 1. Ręczne operacje gotówkowe (API)

- `POST /api/transactions` — `{account_id, type, amount, date, comment?}`:
  - konto musi być typu **`cash`** (na koncie obligacji i oszczędnościowym wpłaty wynikają z zakupów i wpłat
    oszczędnościowych — ręczna operacja policzyłaby się podwójnie; rachunki XTB zasila import) → inaczej
    `422 wrong_account_kind`;
  - `type ∈ deposit | withdrawal | interest | fee`; `amount` dodatnie (> 0, 2 miejsca po przecinku), znak nadaje
    API: `deposit`, `interest` → +, `withdrawal`, `fee` → −; waluta = waluta konta;
  - `date` nie z przyszłości (`422 date_in_future`); `occurred_at` = północ tego dnia w strefie aplikacji;
  - zapis: `xtb_type = "manual"`, `external_id = "manual:<uuid>"`, `import_id = null`, `raw = {}`,
    `comment` = opis (do 200 znaków);
  - odpowiedź `201` z `TransactionOut`; wycena przeliczana w tle od `date` (jak po imporcie).
- `DELETE /api/transactions/{id}` — tylko `xtb_type = "manual"`; inaczej `409 not_manual`
  („Operacji z importu XTB nie można usunąć.”); cudza lub nieistniejąca → `404`. Przeliczenie od daty operacji.
- `TransactionOut` dostaje pole `manual: bool`.

## 2. Konto oszczędnościowe na wpłatach

### Model
- Nowa tabela **`savings_flows`**: `id, savings_account_id (FK, cascade), date, amount (MONEY, ≠ 0; + wpłata,
  − wypłata), note, created_at`. Wiele wpisów tego samego dnia dozwolone.
- Silnik (`savings/interest.py`, `savings_days`): saldo startuje od **pierwszego wpisu** (wpłaty albo salda
  z banku); w dniu wpłaty/wypłaty saldo zmienia się o jej kwotę i to jest przepływ dnia (`net_flow`); odsetki
  narastają dziennie `saldo × stawka / 100 / 365` według historii stawek i są dopisywane w dniu kapitalizacji
  (dziennie / ostatni dzień miesiąca / ostatni dzień kwartału), zaokrąglone do grosza, minus 19 % podatku
  (0 na IKE/IKZE).
  - Kolejność w dniu: odsetki za dzień (od salda z końca poprzedniego dnia), kapitalizacja, potem wpłaty/wypłaty
    tego dnia — wpłata zarabia od następnego dnia.
  - Saldo z banku (`savings_balances`) zostaje jako **korekta**: w swoim dniu ustawia saldo, a różnica jest
    przepływem (jak dziś). W interfejsie 6b saldo z banku nie występuje; istniejące dane liczą się dalej tak samo.
- Wypłata większa niż saldo wyliczone na jej dzień → `422 insufficient_balance` („Wypłata jest większa niż saldo
  z dnia …: … zł.”); sprawdzane przy zapisie, także gdy usunięcie wpłaty sprawiłoby, że późniejsza wypłata
  przekracza saldo (`409 flow_needed`).

### API
- `POST /api/savings-accounts` — **zakłada wszystko w jednej transakcji bazodanowej**:
  `{name, wrapper, capitalization, annual_rate, rate_valid_from, first_deposit: {date, amount}}` → konto
  (`kind = savings`, PLN), ustawienia, pierwsza stawka, pierwsza wpłata. `201` z pełnym odczytem (niżej).
- `GET /api/savings-accounts/{account_id}` — rozszerzony odczyt:
  - `capitalization`, `rates[]`, `flows[]` (id, date, amount, note), `balances[]` (korekty, jak dziś);
  - `summary` na dziś (lub `?date=`): `balance`, `deposits` (suma wpłat − wypłat), `interest_net` (odsetki
    dopisane netto od początku), `tax` (podatek potrącony od początku), `accrued` (narosłe od ostatniej
    kapitalizacji, brutto, jeszcze niedopisane), `current_rate`;
  - `capitalizations[]` — jeden wpis na **miesiąc** (kapitalizacja dzienna i miesięczna) albo na **kwartał**
    (kwartalna): `period_end`, `gross`, `tax`, `net`.
- `POST /api/savings-accounts/{account_id}/flows` — `{date, amount (≠ 0), note?}`; `DELETE …/flows/{id}`.
- `POST …/rates` (zmiana oprocentowania od daty) i `PUT` (kapitalizacja) — bez zmian.
- Każdy zapis/usunięcie przelicza wycenę w tle od daty wpisu.

## 3. Historia (API)

`GET /api/history?account_id&type&instrument_id&from&to&q&cursor&limit=50`

- Źródła złączone w jedną listę, sortowane od najnowszych (data malejąco, w dniu stała kolejność):
  - transakcje (XTB i ręczne);
  - zakupy obligacji (data zakupu, kwota **−** liczba × 100 zł — jak kupno akcji) oraz wypłata przy wykupie przed
    terminem albo w dniu zapadalności (data wypłaty, kwota **+** wypłata netto; tylko gdy ten dzień już minął);
  - wpłaty i wypłaty oszczędnościowe;
  - kapitalizacje oszczędnościowe (po miesiącu/kwartale, jak w odczycie konta; tylko okresy zakończone do dziś).
- Wpis: `id` (stabilny, np. `tx:12`, `bond:7:purchase`, `bond:7:payout`, `sflow:3`, `scap:5:2026-09`),
  `kind` (`transaction` | `bond_purchase` | `bond_payout` | `savings_flow` | `savings_interest`), `type` (typ
  transakcji albo rodzaj wpisu), `date`, `account_id`, `account_name`, `title` (np. nazwa instrumentu, „EDO0936”,
  „Wpłata”), `subtitle` (np. „2 szt. po 250,00 PLN”, opis), `amount` + `currency` (waluta konta), `amount_pln`,
  `delete` — `null` albo `{target: "transaction" | "bond" | "savings_flow", id}` (co usunąć, gdy wolno:
  ręczna transakcja, zakup obligacji, wpłata/wypłata oszczędnościowa).
- Filtry: `account_id`; `type` — lista typów transakcji oraz `bond_purchase`, `bond_payout`,
  `savings_deposit`, `savings_withdrawal`, `savings_interest`; `instrument_id`; `from`/`to` (włącznie);
  `q` — tekst bez rozróżniania wielkości liter w nazwie instrumentu, tickerze, serii obligacji, nazwie konta
  i opisie/komentarzu.
- Stronicowanie kursorem (`next_cursor` w odpowiedzi, `null` na końcu): `{items, next_cursor}`.
- Dane zawsze w obrębie użytkownika (jak reszta API); cudze `account_id`/`instrument_id` → `404`.
- `GET /api/transactions` zostaje bez zmian (poza polem `manual`).

## 4. Ekrany

Kierunek wizualny, zapis kwot, stany (ładowanie, pusto, błąd sekcji z „Spróbuj ponownie”), dostępność i zasady
tekstów — jak w 6a (§1, §5 dokumentu 6a).

- **Dodaj** (`/dodaj`) — lista czterech akcji: „Import z XTB” (`/dodaj/xtb`, dotychczasowy ekran importu),
  „Obligacja” (`/dodaj/obligacja`), „Konto oszczędnościowe” (`/dodaj/konto-oszczednosciowe`), „Operacja
  gotówkowa” (`/dodaj/operacja`). Puste stany z 6a („Wgraj pliki z XTB”) prowadzą do `/dodaj/xtb`.
- **Formularz obligacji** — rodzaj (EDO, jedyna opcja), liczba sztuk (z podpowiedzią wartości nominalnej
  „= 1 000,00 zł”), data zakupu, konto obligacji albo „Nowe konto obligacji” (nazwa + zwykłe / IKE / IKZE, zakładane
  przed zapisem zakupu). Odpowiedź `422 series_unknown` → pojawiają się pola „Oprocentowanie w pierwszym roku”
  i „Marża” z wyjaśnieniem, że podaje je list emisyjny serii; ponowny zapis wysyła je razem z zakupem. Po zapisie →
  szczegóły obligacji.
- **Nowe konto oszczędnościowe** — nazwa, wariant (zwykłe / IKE / IKZE), oprocentowanie roczne %, obowiązuje
  od, kapitalizacja (dzienna / miesięczna / kwartalna), pierwsza wpłata (kwota, data). Jedno wywołanie
  `POST /api/savings-accounts`. Po zapisie → szczegóły konta.
- **Operacja gotówkowa** — konto gotówkowe albo „Nowe konto gotówkowe” (nazwa), typ (Wpłata, Wypłata, Odsetki,
  Opłata), kwota, data (domyślnie dziś), opis. Po zapisie → komunikat i powrót do Dodaj albo Historii.
- **Szczegóły konta oszczędnościowego** (`/pozycje/oszczednosci/:accountId`, z listy Pozycje):
  - nagłówek: nazwa, wariant, saldo (duża kwota), pod nim „Odsetki narosłe od … : … zł”;
  - podsumowanie: wpłacono, odsetki dopisane netto, podatek, oprocentowanie teraz, kapitalizacja;
  - akcje „Wpłata lub wypłata” i „Zmień oprocentowanie” (formularze w rozwijanym panelu na tym ekranie);
  - listy: wpłaty i wypłaty (z „Usuń”), historia stawek, odsetki po miesiącach/kwartałach.
- **Szczegóły obligacji** (`/pozycje/obligacje/:holdingId`) — według makiety: seria, liczba sztuk, konto,
  wartość bieżąca netto (duża kwota), wartość przy wykupie dziś, daty zakupu i wykupu, status; okresy (nr, od–do,
  stopa, dopisek „szacunkowa”, gdy brakuje inflacji GUS); akcje „Wykup przed terminem” (data, potwierdzenie) /
  „Cofnij wykup” oraz „Usuń zakup” (potwierdzenie).
- **Historia** (`/historia`; w nawigacji aktywna, bez dopisku „wkrótce”) — wpisy pogrupowane po dniach
  (nagłówek dnia jak „sob., 26 września”); wiersz: znacznik rodzaju, tytuł, podtytuł (konto, szczegóły), kwota
  z kolorem znaku; filtry: kafelki kont, typ (lista), zakres dat, wyszukiwarka (z opóźnieniem ~300 ms);
  „Pokaż więcej” dociąga kolejną stronę; wpis z `delete` ma akcję „Usuń” z potwierdzeniem nazywającym wpis.
- **Pozycje** — wiersze obligacji i kont oszczędnościowych prowadzą do ich szczegółów.
- **Więcej** — z listy „wkrótce” znikają „Historia operacji” i „Obligacje i konta oszczędnościowe”.

## 5. Formularze, błędy, odświeżanie

- Kwoty wpisywane po polsku: przecinek lub kropka dziesiętna, spacje (także twarde) ignorowane, najwyżej 2 miejsca
  po przecinku; parser w `format/` zwraca tekst dziesiętny dla API („1234.50”) — **nigdy przez `Number`**.
  Oprocentowanie: do 4 miejsc. Liczba obligacji: liczba całkowita ≥ 1.
- Walidacja w przeglądarce (puste pole, zła kwota, data z przyszłości) i błędy z API przy polu, którego dotyczą
  (mapowanie `code`/`details` → pole); błąd ogólny nad przyciskiem. Odrzucony formularz zachowuje wpisane dane.
  Przycisk zapisu nieaktywny w trakcie wysyłania.
- Usuwanie zawsze z potwierdzeniem nazywającym wpis („Usunąć wpłatę 5 000,00 zł z 03.03.2026?”).
- Po każdym zapisie i usunięciu: unieważnienie `["portfolio"]`, `["accounts"]`, historii i szczegółów danego
  konta/obligacji; wycena przelicza się w tle, a pulpit wykrywa to jak po imporcie (`recalculating`).
- Brak połączenia / błąd serwera — jak w 6a.

## 6. Testy

- **API (pytest):**
  - ręczne operacje: zapis każdego typu ze znakiem, tylko konto `cash`, data z przyszłości, usuwanie ręcznej,
    zakaz usuwania z XTB (`409`), izolacja użytkowników, przeliczenie wyceny;
  - konto oszczędnościowe: odsetki co do grosza dla kapitalizacji dziennej, miesięcznej i kwartalnej, zmiana
    stawki w trakcie okresu, wpłata w dniu kapitalizacji, wypłata, IKE bez podatku, zgodność z istniejącymi
    danymi opartymi na saldach; `insufficient_balance`; założenie konta w jednym wywołaniu (wszystko albo nic);
    podsumowanie i kapitalizacje po miesiącach/kwartałach;
  - Historia: złączenie wszystkich źródeł, każdy filtr, wyszukiwanie, kursor (bez duplikatów i dziur na granicy
    stron), pole `delete`, izolacja użytkowników.
- **Frontend (Vitest):** parser kwot; każdy formularz (zapis, błąd z API przy polu, nowa seria obligacji,
  nowe konto w formularzu); szczegóły obligacji i konta oszczędnościowego; Historia (filtry → parametry zapytania,
  „Pokaż więcej”, usuwanie z potwierdzeniem).
- **e2e (Playwright):** do istniejącego scenariusza dochodzi: założenie konta oszczędnościowego z wpłatą →
  szczegóły z saldem i odsetkami → wpis w Historii → usunięcie wpłaty.

## Kryteria odbioru

1. Z ekranu Dodaj można kupić obligację EDO (także nowej serii), założyć konto oszczędnościowe z wpłatą i dodać
   operację gotówkową; każda rzecz pojawia się w Pozycjach, na Pulpicie (po przeliczeniu) i w Historii.
2. Szczegóły konta oszczędnościowego pokazują saldo i odsetki co do dnia zgodnie z testami API; zmiana
   oprocentowania od daty zmienia odsetki od tej daty.
3. Szczegóły obligacji pokazują wartość bieżącą, wartość przy wykupie dziś i okresy ze stopami.
4. Historia pokazuje wszystkie wpisy z filtrami i wyszukiwaniem; ręczne wpisy da się usunąć, wpisów z XTB nie.
5. `pytest`, `npm test` i `npm run e2e` przechodzą.
