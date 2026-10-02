# Plan 7e — Wykres ceny waloru z transakcjami (decyzje projektowe)

**Data:** 2026-10-02
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §7 ekran 2, „Szczegóły pozycji … wykres (etap 2)”.
**Makieta:** `.superpowers/brainstorm/5282-1790973470/content/wykres-ceny.html` (zaakceptowana 2026-10-02).

## Decyzje właściciela (2026-10-02)

1. Wykres pokazuje **cenę instrumentu w jego walucie, tak jak XTB** (SXR8.DE w €, CDR.PL w zł), a nie cenę w PLN ani wartość pozycji.
2. Na linii ceny są znaczniki operacji tej pozycji: **zakup ▲** (zielony), **sprzedaż ▼** (czerwony), **dywidenda „D”** (niebieska, przy osi dni). Do tego **przerywana pomarańczowa linia średniej ceny zakupu** (cena otwarcia jak w XTB).
3. **Gdzie:** nowa sekcja „Wykres ceny” w szczegółach pozycji, zaraz pod nagłówkiem. Reszta ekranu bez zmian.
4. **Zakresy:** Od zakupu (domyślny) · 6M · 1R · 5L · Maks, plus gesty przybliżania i przesuwania jak na wykresie wartości.
5. **Dotknięcie znacznika** pokazuje operację. Przy zakupie lub sprzedaży: data, ilość, cena, kwota w zł, cena z przewalutowaniem XTB (gdy było) i zmiana ceny od tej operacji do dziś. Przy dywidendzie: data i kwota.

## Dane

- **Ceny:**
  - dzienne zamknięcia z tabeli `prices` (waluta instrumentu, jak w wycenie);
  - jeśli aktualna cena pozycji (np. z importu XTB) ma nowszą datę niż ostatnie zamknięcie, dokładamy ją jako ostatni punkt;
  - przy długich zakresach serwer przerzedza punkty do najwyżej 800: co n-ty dzień, zawsze z pierwszym i ostatnim.
- **Znaczniki:**
  - transakcje `buy` / `sell` tej pozycji (konto + instrument) z ich ceną (`price`, waluta instrumentu) i ilością;
  - dywidendy (`dividend`) z kwotą w zł;
  - ceny i ilości sprzed splitu przeliczamy przez współczynnik splitów, tak samo jak partie (ceny z dostawcy są już po splitach), żeby znacznik leżał na linii;
  - transakcja bez ceny dostaje cenę zamknięcia z jej dnia;
  - pozycja po konwersji (z innego tickera) pokazuje tylko operacje na bieżącym instrumencie.
- **Cena z przewalutowaniem XTB:** jak w partiach, `open_price_with_fx`: cena × 1,005 przy zakupie i × 0,995 przy sprzedaży, gdy XTB przewalutowuje (waluta instrumentu ≠ waluta konta).
- **Średnia cena:** `average_price` ze szczegółów pozycji. Brak przy pozycji zamkniętej, wtedy linii nie ma.
- **„Od zakupu”:** od 14 dni przed pierwszym zakupem tej pozycji do dziś. Bez zakupów: 1R.
- **Zmiana w nagłówku sekcji:** ostatnia cena względem pierwszego punktu zakresu. Podpis „od 1. zakupu” dla zakresu „Od zakupu” (wtedy względem ceny pierwszego zakupu), „w zakresie” dla pozostałych.

## API

`GET /api/positions/{account_id}/{instrument_id}/prices?from=YYYY-MM-DD` (brak `from` = cała historia; cudze konto lub instrument bez pozycji na koncie → 404):

```
currency: "EUR"
points: [{date, close}]                        (rosnąco, ≤ 800)
markers: [{date, kind: "buy"|"sell"|"dividend", price, price_with_fx, quantity, amount_pln}]
          (price i quantity po splitach; dywidenda: price/quantity/price_with_fx = null)
first_buy: date | null
```

## Ekran

- **Sekcja „Wykres ceny”** pod nagłówkiem szczegółów pozycji:
  - tytuł z aktualną ceną i zmianą;
  - przełącznik zakresu;
  - wykres SVG: linia ceny, oś cen po prawej, daty u dołu, znaczniki, linia średniej z podpisem „średnia {cena}”;
  - legenda;
  - pod wykresem panel wybranej operacji;
  - podpowiedź „Szczypnij lub przesuń, żeby zmienić zakres; dotknij znacznika, żeby zobaczyć operację.”
- **Znaczniki** są przyciskami o nazwie, np. „Zakup 18.09.2026, 1 szt. po 609,10 €”. Gdy kilka operacji przypada na ten sam dzień, każda ma własny przycisk, a znaczniki lekko się przesuwają.
- **Za mało danych** (mniej niż 2 punkty): „Brak notowań dla tego instrumentu.”, sekcja bez wykresu.
- **Obligacje i konta oszczędnościowe:** bez zmian (to nie jest ich ekran szczegółów).

## Testy

- **API:**
  - punkty z `prices` w zakresie `from`, przerzedzenie do 800 z zachowaniem końców;
  - dołożona nowsza cena XTB;
  - znaczniki zakupu, sprzedaży i dywidendy z ceną z przewalutowaniem tylko przy obcej walucie;
  - split przelicza cenę i ilość znacznika;
  - transakcja bez ceny dostaje zamknięcie dnia;
  - `first_buy`;
  - cudze konto 404.
- **Web:**
  - zakres domyślny „Od zakupu” pyta o `from` = pierwszy zakup − 14 dni, a 1R o datę sprzed roku;
  - znaczniki są przyciskami z nazwami;
  - dotknięcie pokazuje panel operacji;
  - linia średniej z podpisem, brak linii przy zamkniętej pozycji;
  - zmiana w nagłówku;
  - komunikat bez notowań.
- **e2e:** w szczegółach pozycji widać wykres ceny ze znacznikiem zakupu; zrzut `wykres-ceny.png`.
