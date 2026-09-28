# Plan 4b: Wycena — rozszerzenia (decyzje projektowe)

> Uzupełnienie specyfikacji `2026-09-26-portfolio-tracker-design.md` dla planu 4b. Ustalone w rozmowie 2026-09-28.
> Kontekst: szkic `plans/2026-09-27-04-valuation-draft.md`, plan 4a `plans/2026-09-27-04a-valuation-core.md`
> (sekcja „Decyzje” i „Poza zakresem (4b)”). Na tym dokumencie powstaje plan `plans/2026-09-28-04b-valuation-extensions.md`.

## Zakres

1. Konwersje walorów i ręczne zdarzenia korporacyjne (splity, scalenia, konwersje, wyłączenie splitu) z API.
2. Koszty (opłaty `fee`) jako osobna pozycja rozbicia zysku.
3. Zamknięte inwestycje: sprzedaże, podsumowanie per walor i konto, ogółem.
4. Ekspozycja walutowa: dziś i w czasie.
5. Limity IKE/IKZE: tabela `wrapper_limits` z seedem IKE od 2026.
6. TWR: od początku (pulpit) i per punkt historii.

Poza zakresem: rozpoznawanie konwersji w imporcie XTB (brak przykładów w danych — operacje nierozpoznane
zostają `unknown`), stopy zwrotu w okresach i XIRR (etap 2), ekspozycja przez aktywa bazowe ETF (backlog),
wariant IKZE dla samozatrudnionych w koncie (dojdzie razem z seedem IKZE).

## Podejście

Wszystko liczone na bieżąco z danych, które już są — bez nowych tabel-cache:

| Funkcja | Źródło |
|---|---|
| Zamknięte inwestycje, koszty | odtworzenie historii (`load_inputs` + `replay`), jak szczegóły pozycji w 4a |
| Ekspozycja walutowa | `daily_valuations` + `instruments.currency` / waluta konta |
| TWR | `daily_valuations` (`value_pln`, `net_flow_pln`) |
| Limity | transakcje kont `ike`/`ikze` + `wrapper_limits` |
| Konwersje, ręczne zdarzenia | silnik (`engine.py`) + `corporate_actions` |

Uzasadnienie: skala jednego portfela (lata × dziesiątki pozycji) pozwala liczyć w locie; dodatkowe cache
trzeba by unieważniać po każdym imporcie i zmianie danych rynkowych.

## 1. Zdarzenia korporacyjne

**Model.** `corporate_actions` dostaje `user_id` (NULL = wpis wspólny). Reguła: `source = 'manual'` ⇔ `user_id`
NOT NULL (CHECK). Wpisy `provider` (Yahoo) i `xtb` są wspólne dla wszystkich użytkowników; wpis ręczny działa
**tylko na konta jego autora** (decyzja: więcej użytkowników w przyszłości, poprawka jednej osoby nie może
zmienić wyceny innym). Nowy typ `suppress` — „tego dnia dla tego waloru nie ma zdarzenia”. Unikalność:
`(instrument_id, effective_date, source, user_id)` z `NULLS NOT DISTINCT` (jeden wpis na walor, dzień i źródło;
dla ręcznych — na użytkownika).

**Pierwszeństwo.** Dla użytkownika silnik bierze wpisy wspólne i jego własne ręczne. Dla tego samego
`(instrument_id, effective_date)` liczy się jeden wpis: ręczny użytkownika > `xtb` > `provider`. Ręczny
`suppress` przykrywa błędny split dostawcy; synchronizacja Yahoo (`replace_provider_splits`) zmienia tylko wpisy
`provider`, więc go nie nadpisze.

**Konwersja** (`type = 'conversion'`, `instrument_id` = A, `target_instrument_id` = B, `ratio_from:ratio_to`,
`effective_date` = D; CHECK: `target_instrument_id` NOT NULL ⇔ `type = 'conversion'`, B ≠ A). Na początku dnia D
każda partia A na każdym koncie użytkownika przechodzi na B: ilość × `ratio_to / ratio_from`, **koszt w PLN,
`fx_open`, data zakupu i `xtb_position_id` bez zmian**. Od D pozycja A nie istnieje; dywidendy, sprzedaże i wiersze
`daily_valuations` A sprzed D zostają przy A. Sprzedaż B dopasowuje partie po `xtb_position_id` jak w 4a.
Kurs zakupu (`fx_open`) partii = kurs NBP waluty notowania B z dnia zakupu partii, więc efekt ceny + efekt walutowy = wartość − koszt także przy różnych walutach A i B.
Konwersja jest wpisem ręcznym (brak przykładów w eksportach XTB).

**Przeliczenie.** Dodanie, zmiana lub usunięcie wpisu ręcznego oznacza autora do przeliczenia od
`effective_date` (przy zmianie daty — od wcześniejszej z dwóch), w tej samej transakcji co zapis.

**API** (`/api/corporate-actions`):
- `GET ?instrument_id=` — wpisy walorów, które użytkownik ma lub miał (wspólne + własne ręczne), z polem
  `active` (czy wygrywa pierwszeństwo) i `editable` (własny ręczny).
- `POST` — nowy wpis ręczny: `split` / `reverse_split` / `conversion` / `suppress`. Walor musi należeć do
  użytkownika (`scope.get_instrument`); cel konwersji podaje się tickerem XTB (`target_ticker`) — brakujący walor jest tworzony (wspólny, jak przy imporcie), a użytkownik go widzi, bo jest celem jego konwersji.
- `PUT /{id}` (pełne dane wpisu), `DELETE /{id}` — tylko własne ręczne. Cudzy wpis ręczny albo wspólny wpis waloru, którego
  użytkownik nie ma → 404 (nie zdradzamy istnienia). Wspólny wpis waloru użytkownika (widoczny na liście) →
  409 `shared_action` z polskim komunikatem „Wpis z Yahoo/XTB można tylko przykryć własnym wpisem”.
- Walidacja: stosunek > 0, `split` ⇒ `ratio_to > ratio_from`, `reverse_split` ⇒ odwrotnie, `suppress` bez stosunku
  (zapis 1:1), drugi ręczny wpis na ten sam walor i dzień → 409.

## 2. Koszty

Operacje `fee` powiązane z walorem (`instrument_id`) są kosztami tego waloru na koncie: pomniejszają zysk
łączny pozycji i zamkniętej inwestycji; w API pole `fees_pln` (wartość ujemna lub 0, w PLN kursem z dnia operacji,
jak dywidendy). Opłaty bez waloru — tylko w sumie na pulpicie (`fees_pln` w podsumowaniu). Spread przewalutowania
XTB jest w kwocie zakupu i zostaje w koszcie partii. Przy pisaniu planu sprawdzić na eksportach z `samples/xtb`,
czy wiersze `fee` mają symbol.

## 3. Zamknięte inwestycje

`GET /api/portfolio/closed?account_id=` zwraca:
1. **Sprzedaże** (każda `Sale` z silnika): konto, walor, data wejścia (najwcześniejsza data otwarcia sprzedanych
   partii) i wyjścia, ilość, koszt PLN, przychód PLN, zysk zrealizowany rozbity na efekt ceny i walutowy (te same
   wzory co dla otwartych partii, z ceną sprzedaży i kursem NBP dnia sprzedaży; efekt ceny = reszta, więc suma
   zgadza się co do grosza; przy wycenie awaryjnej / braku `fx_open` efekt walutowy = 0), zwrot %, dni trzymania,
   flaga `matched` z 4a.
2. **Per walor i konto** (każdy walor z co najmniej jedną sprzedażą): zysk zrealizowany, dywidendy netto,
   koszty, zysk łączny = suma trzech, zwrot % = zysk łączny / koszt sprzedanych partii, okres pierwszy zakup →
   ostatnia sprzedaż, status `closed` (ilość 0) lub `partial`. Dywidendy i koszty — całego waloru na koncie
   (przy `partial` obejmują też część wciąż trzymaną; tak to pokazujemy, bez dzielenia).
3. **Ogółem:** sumy z pkt 2 i zwrot % ogółem.

## 4. Ekspozycja walutowa

`GET /api/portfolio/exposure?account_id=&from=&to=` — z `daily_valuations`: waluta wiersza = `instruments.currency`
(waluta notowania), gotówka = waluta konta, instrument bez waluty (brak ceny u dostawcy) → grupa `unknown`.
Odpowiedź: `current` (dzień jak w pulpicie: kwota PLN i udział % per waluta) i `history` (per dzień z zakresu `from`–`to`, jak
historia wartości: kwota PLN per waluta). Zmiana waluty instrumentu (ręczny symbol)
przepisuje ekspozycję w całej historii — świadome uproszczenie.

## 5. Limity IKE/IKZE

Tabela `wrapper_limits (year, wrapper, limit_pln)`, PK `(year, wrapper)`, `wrapper ∈ ike | ikze |
ikze_self_employed`; seed w migracji: IKE 2026 (kwota z komunikatu MRPiPS, zweryfikowana przy pisaniu planu —
nie z pamięci). Co roku nowy wiersz (migracja).

Limit jest na osobę: wpłaty ze wszystkich kont użytkownika o tym samym `wrapper` sumują się w roku kalendarzowym
(dzień warszawski). Wpłata = `deposit` + `transfer_in` na konto IKE/IKZE (także z własnego zwykłego rachunku);
wypłaty i `transfer_out` limitu nie przywracają. Konto `ikze` porównujemy z `wrapper = 'ikze'`.

`GET /api/portfolio/limits` → per `wrapper` i rok (od pierwszej wpłaty do bieżącego): `paid_pln`, `limit_pln`
(null, gdy brak w tabeli), `remaining_pln` (null lub ≥ 0), `exceeded`, rozbicie `paid_pln` per konto.

## 6. TWR

Z dziennych sum `daily_valuations` (portfel albo jedno konto): `r_t = (V_t − F_t) / V_{t−1} − 1`, gdzie `V` =
suma `value_pln` dnia, `F` = suma `net_flow_pln` dnia (przepływ na koniec dnia). Dzień z `V_{t−1} = 0` pomijany
(pusty portfel). TWR = Π(1 + r_t) − 1. Przelewy między kontami użytkownika znoszą się w portfelu; przy filtrze
konta są przepływem tego konta. `summary` dostaje `twr_pct` (od początku, null bez danych), `history` — `twr_pct`
w każdym punkcie, skumulowany od pierwszego dnia historii (nie od początku zakresu), żeby ten sam dzień miał
tę samą wartość w każdym zakresie. Procent z 2 miejscami, `ROUND_HALF_UP`.

## Błędy i testy

Jak w 4a: cudzy / nieistniejący zasób → 404, walidacja → 422 z kodem, konflikt → 409 z polskim komunikatem.
Testy silnika na prostych liczbach (konwersja z zachowaniem kosztu i daty, pierwszeństwo źródeł, `suppress`,
rozbicie zysku sprzedaży co do grosza, TWR z wpłatą w środku okresu), testy API z izolacją użytkowników
(ręczny wpis A nie zmienia wyceny B), test limitu z dwoma kontami IKE.
