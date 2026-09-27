# Plan 4: Wycena i historia — szkic (przed rozpisaniem na taski)

> Szkic zbiera zakres, ustalenia przeniesione z planów 2–3 i pytania projektowe. Pełny plan z kodem
> (`2026-09-2X-04-valuation.md`) powstaje w osobnej sesji na podstawie tego pliku.
> Stan: **pytania zamknięte (2026-09-27)** — decyzje w sekcji „Decyzje”; następny krok na końcu pliku.

**Spec:** `docs/superpowers/specs/2026-09-26-portfolio-tracker-design.md` — §6 (Akcje/ETF, Splity i konwersje,
Zamknięte inwestycje, Ekspozycja walutowa, Limity IKE/IKZE, Historia wartości i zwrot), §4 (`corporate_actions`,
`wrapper_limits`, `daily_valuations`), §7 (co muszą pokazać Pulpit i Pozycje), §2 etap 1.
**Mapa:** `2026-09-26-00-roadmap.md`, wiersz 4: `daily_valuations`, API pulpitu/pozycji/szczegółów.

## Zakres wg specyfikacji

1. Wycena akcji/ETF w dniu D: ilość(D) × cena (ostatnia ≤ D) × kurs NBP(D) → PLN; koszt partii w PLN =
   faktyczna kwota operacji gotówkowej XTB; zysk niezrealizowany rozbity na efekt ceny i efekt walutowy.
2. Zysk zrealizowany: dopasowanie sprzedaży do partii po `xtb_position_id` (bez FIFO).
3. Dywidendy netto (dywidenda − podatek u źródła) per instrument i konto; gotówka = suma operacji gotówkowych.
4. Splity i konwersje (`corporate_actions`): ilość i cena zakupu partii od `effective_date`; konwersja przenosi partie.
5. Zamknięte inwestycje: zysk zrealizowany (cena + waluta + dywidendy − koszty), zwrot %, czas trzymania.
6. Ekspozycja walutowa wg waluty notowania, bieżąca i w czasie.
7. Limity IKE/IKZE: wpłaty w roku (deposit + transfer_in z własnego konta) vs `wrapper_limits` (seed).
8. `daily_valuations` od pierwszej transakcji, per konto i składnik; `net_flow_pln` dla deposit/withdrawal,
   transfery wewnętrzne się znoszą; wpłacony kapitał; TWR; przeliczanie od najwcześniejszej zmienionej daty.
9. API: pulpit, lista pozycji, szczegóły pozycji, zamknięte inwestycje, ekspozycja walutowa, limity.

## Ustalenia przeniesione z planów 2–3 (wiążące dla planu 4)

- Znaki kwot w `transactions.amount` (waluta konta): buy < 0, sell > 0, dividend > 0, withholding_tax < 0,
  deposit / transfer_in > 0, transfer_out / withdrawal < 0. `quantity` zawsze dodatnie; `price` w walucie notowania.
- Stan posiadania wyprowadzać z transakcji; `position_lots` tylko uzupełniająco (partie, SL/TP, konwersje).
- `xtb_snapshots`: dla konta brać najnowszy `taken_at`.
- `prices.close` jest **skorygowany o splity** (Yahoo, `split_adjusted = True`) → ilości z XTB trzeba przeliczać
  „na ten sam stan” co ceny (test na NVDA 10:1, 2024-06-07).
- Ceny w funtach dla instrumentów GBp/GBX (plan 3 dzieli przez 100); ceny XTB w GBX są prawdopodobnie w pensach
  (`implied_fx_rate` ×100) → skalować przy porównaniach z XTB.
- `instruments.currency` ustawia tylko plan 3 (z dostawcy); bywa NULL, gdy dostawca nie ma cen (brak symbolu / 404).
  Spec §5: brak ceny u dostawcy → wycena ostatnią ceną z importu XTB — potrzebna też waluta z innego źródła.
- Ręczna korekta symbolu może wskazać notowanie w innej walucie niż transakcje XTB (np. CSPX.L w USD zamiast SXR8.DE w EUR).
- Kursy NBP (`fx_rates`) pobierane tylko dla walut instrumentów → **gotówka w USD/EUR na koncie XTB nie ma kursów**;
  plan 4 musi rozszerzyć listę walut workera o waluty kont / transakcji.
- Limit IKE: `transfer_in` na IKE z własnego rachunku liczy się jako wpłata.
- Przeliczanie `daily_valuations` po nowych danych rynkowych — plan 3 zostawił to planowi 4 (worker → przeliczenie).
- Plan 3: `price_on(db, instrument_id, day)`, `fx_on(db, currency, day)` (PLN → 1), `latest_prices(db, ids)` w `app/market/store.py`.

## Pytania projektowe

1. Podział zakresu (jeden plan vs 4a/4b).
2. Źródło splitów: ręcznie vs automatycznie z Yahoo.
3. Cena zastępcza przy braku ceny u dostawcy.
4. Gotówka w walutach obcych i jej kursy.
5. Przechowywanie `daily_valuations` (tabela-cache vs liczenie w locie) i moment przeliczenia.
6. TWR w planie 4 czy w etapie 2.
7. Limity IKE/IKZE — lata i źródło kwot w seedzie.

## Decyzje

1. **Podział: dwa plany.** 4a — rdzeń: stan posiadania, wycena dzienna (`daily_valuations`), gotówka, dywidendy, zysk, API pulpitu i pozycji. 4b — splity/konwersje, zamknięte inwestycje, ekspozycja walutowa, limity IKE/IKZE, TWR.
2. **Splity: automatycznie z Yahoo + ręczna korekta.** Worker pobiera zdarzenia splitów (`events=split` w chart API,
   to samo zapytanie co ceny) do `corporate_actions` (`source=provider`); użytkownik może dodać/poprawić ręcznie.
   *Wniosek dla podziału:* pobieranie splitów i przeliczanie ilości „na stan cen” trafia do **4a** (bez tego wycena
   po splicie jest błędna); konwersje i ręczna edycja zdarzeń — **4b**. Test: NVDA 10:1, 2024-06-07.
3. **Brak ceny u dostawcy → ostatnia cena z XTB + znacznik.** Cena z najnowszego importu (`xtb_snapshots.current_price`,
   awaryjnie cena ostatniej transakcji), waluta z transakcji XTB (uwaga na GBX w pensach); pozycja oznaczona
   „cena z importu XTB z dnia X” (flaga w `daily_valuations.flags` i w API).
4. **Gotówka w walutach obcych:** lista walut workera = waluty instrumentów (referencjonowanych) ∪ waluty kont ∪
   waluty transakcji, bez PLN (zmiana `update_fx` z planu 3, w 4a). Gotówka wyceniana kursem NBP z dnia;
   ekspozycja walutowa (4b) liczy gotówkę w jej walucie.
5. **`daily_valuations` jako tabela-cache przeliczana w tle** (per konto i składnik), od najwcześniejszej zmienionej
   daty: po imporcie (zaraz po commicie importu) i po nowych danych rynkowych (worker). Pulpit czyta gotowe wiersze.
6. **TWR w 4b** (z `daily_valuations` i `net_flow_pln`); XIRR i stopy zwrotu w okresach zostają w etapie 2.
7. **Limity: seed tylko dla IKE** (kwoty z komunikatów MRPiPS, zweryfikowane przy pisaniu planu, nie z pamięci),
   ale model gotowy na IKZE: `wrapper_limits.wrapper` przyjmuje `ike | ikze | ikze_self_employed`, a konto `ikze`
   liczy się tak samo jak IKE — dodanie IKZE to później tylko nowe wiersze seedu (+ wybór wariantu samozatrudnienia w koncie).

## Następny krok

Na nowym limicie: skill `superpowers:writing-plans` → pełny plan **4a** z kodem (`docs/superpowers/plans/…-04a-valuation-core.md`)
na podstawie tego szkicu i specyfikacji; plan **4b** po realizacji 4a. Przed pisaniem przeczytać modele z planów 2–3
(`api/app/models/ledger.py`, `instrument.py`, `market.py`) i `app/market/store.py`, `app/market/update.py`.
Uzupełnić mapę planów (`2026-09-26-00-roadmap.md`): wiersz 3 → ✅, wiersz 4 → 4a/4b.
