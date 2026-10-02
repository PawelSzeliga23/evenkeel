# Plan 7d — Dochód i koszty w czasie (decyzje projektowe)

**Data:** 2026-10-02
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §2 „Etap 2” („dywidendy w czasie” i „prowizje/koszty w czasie”), rozszerzone decyzją właściciela.
**Makieta:** `.superpowers/brainstorm/5282-1790973470/content/dochod.html` (zaakceptowana 2026-10-02).

## Decyzje właściciela (2026-10-02)

1. **Zakres: dochód pasywny i koszty w czasie** zamiast samych dywidend i prowizji. Powód: w portfelu właściciela nie ma jeszcze dywidend ani prowizji. Realny dochód to odsetki z konta oszczędnościowego i z EDO, a realny koszt to przewalutowanie XTB i podatki.
2. **Odsetki liczymy jako naliczone,** czyli narastające codziennie, tak jak wycena na Pulpicie. EDO pokazuje więc dochód co miesiąc, a nie dopiero przy wykupie.
3. **Osobny ekran „Dochód i koszty”** (`/analiza/dochod`) oraz karta na Analizie.
4. **Liczby jak w XTB:** przewalutowanie 0,5 % przy zakupie i sprzedaży w obcej walucie, kwoty transakcji tak, jak pobrało je XTB.
5. **Koszty wyjścia nie są wliczane.** To, co XTB pobrałoby przy sprzedaży dziś, jest kosztem, który jeszcze nie wystąpił; widać je na Pulpicie.

## Co liczymy

Wszystko w PLN. Dzień transakcji to `local_day` (czas warszawski), kwoty transakcji przeliczamy przez `amount_pln`, jak na Pulpicie. Działa filtr kont jak wszędzie.

**Dochód (brutto):**
- **Odsetki z kont oszczędnościowych i obligacji (naliczone).**
  - Dla każdego wiersza `daily_valuations` z `savings_account_id` lub `bond_holding_id`: odsetki netto dnia = `value_pln(d) − value_pln(d−1) − net_flow_pln(d)`. Brak wiersza w dniu `d−1` oznacza 0.
  - Wycena tych pozycji jest już po podatku Belki (19 %, poza IKE/IKZE). Dla kont opodatkowanych: brutto = netto ÷ 0,81, podatek = brutto − netto. Dla IKE/IKZE: brutto = netto, podatek 0.
- **Odsetki od wolnych środków XTB:** transakcje `interest` (brutto) i `interest_tax` (podatek).
- **Dywidendy:** transakcje `dividend` (brutto) i `withholding_tax` (podatek u źródła), przypisane do instrumentu.

**Koszty** (kwoty dodatnie; w interfejsie pokazywane ze znakiem minus):
- **Przewalutowanie XTB.**
  - Dotyczy zakupów i sprzedaży (`buy`, `sell`) na kontach XTB, gdy waluta instrumentu albo konta jest obca. Reguła jest ta sama co w `ExitRules.fx_fee`.
  - Zakup: kwota pobrana = przeliczona × 1,005, więc koszt = |kwota| × 0,005 ÷ 1,005.
  - Sprzedaż: kwota otrzymana = przeliczona × 0,995, więc koszt = kwota × 0,005 ÷ 0,995.
  - Zaokrąglenie do grosza na transakcję.
- **Podatek od odsetek (Belka):** szacowany z odsetek naliczonych (wyżej) + transakcje `interest_tax`.
- **Podatek u źródła:** transakcje `withholding_tax`.
- **Prowizje i opłaty:** transakcje `fee` (z instrumentem i bez).

**Bilans** = dochód brutto − koszty. Podatki są tylko w kosztach, więc nic nie liczy się podwójnie.

**Okresy:**
- `12m`: od pierwszego dnia miesiąca sprzed 11 miesięcy do dziś (12 miesięcy kalendarzowych, w tym bieżący);
- `ytd`: od 1 stycznia;
- `all`: od pierwszej transakcji lub wyceny;
- koniec = ostatni dzień wyceny (dla transakcji: dziś).

Miesiące bez żadnych zdarzeń są w odpowiedzi jako zera, żeby wykres miał ciągłą oś.

## API

`GET /api/analytics/income?period=12m|ytd|all&account_id=…`

```
period: {start, end} | null            (null = brak transakcji i wycen)
totals: {income_pln, costs_pln, balance_pln}
months: [{month: "2026-09", interest_pln, dividends_pln, fx_pln, taxes_pln, fees_pln,
          income_pln, costs_pln, balance_pln}]       (rosnąco)
sources: [{key, kind: "savings"|"bond"|"xtb_interest"|"dividend", name, gross_pln, tax_pln, net_pln, taxed}]
          (savings: s:{id}, nazwa konta; bond: b:{seria}; xtb_interest: x:{account_id}, „Odsetki od wolnych środków · {konto}”;
           dividend: d:{instrument_id}, ticker i nazwa; posortowane po brutto malejąco; bez źródeł z samymi zerami)
costs: [{key: "fx"|"interest_tax"|"withholding_tax"|"fees", name, amount_pln, count}]
          (zawsze cztery pozycje, w tej kolejności; count = liczba transakcji, dla Belki z odsetek naliczonych liczy się tylko transakcje)
recalculating
```

## Ekran `/analiza/dochod`

- **Nagłówek i filtry:** link powrotny „Analiza”, tytuł „Dochód i koszty”, wybór kont, okres (12 mies. · Od pocz. roku · Wszystko, domyślnie Od pocz. roku).
- **Kafelki:** Dochód (brutto, zielony), Koszty (czerwony, z minusem), Bilans (kolor według znaku).
- **Wykres „Miesiąc po miesiącu”:**
  - słupki nad kreską zera: odsetki i dywidendy, ułożone na sobie;
  - słupki pod kreską: przewalutowanie, podatki i opłaty, ułożone na sobie;
  - legenda; dotknięcie słupka pokazuje miesiąc z rozbiciem;
  - przy ponad 24 miesiącach słupki są grupowane w lata (liczone w aplikacji z `months`).
- **„Skąd dochód”:** wiersz na źródło z brutto, podatkiem i netto („brutto 58,10 zł − Belka 11,04 zł”; w IKE/IKZE „bez podatku”); po prawej netto. Brak dywidend → wiersz „Dywidendy · na razie brak”.
- **„Na co koszty”:** cztery wiersze z kwotą i krótkim opisem (np. „0,5 % przy zakupach w EUR · 12 transakcji”, „XTB: 0 % do 100 tys. € obrotu”).
- **Tabela „Miesiące”:** od najnowszego, z kolumnami Dochód, Koszty i Bilans.
- **Puste stany:** brak wyceny i transakcji → „Nie ma jeszcze danych do pokazania.”
- **Karta na Analizie** „Dochód i koszty”: dochód i koszty od początku roku, link „Szczegóły”. Karta jest ukryta, gdy brak danych albo zapytanie się nie uda.

## Testy

- **API:**
  - odsetki naliczone z konta oszczędnościowego (wpłata to nie dochód) i z EDO na IKE (bez podatku) oraz na koncie zwykłym (brutto ÷ 0,81);
  - przewalutowanie przy zakupie i sprzedaży instrumentu w EUR na koncie XTB, brak przy instrumencie w PLN;
  - dywidenda i podatek u źródła;
  - odsetki od wolnych środków i ich podatek;
  - opłata;
  - okresy i miesiące z zerami;
  - filtr kont i cudze konto 404;
  - brak danych.
- **Web:** kafelki i znaki, wybór okresu, wykres (nazwa dostępna z sumami, dotknięcie miesiąca), źródła z rozbiciem brutto/podatek, koszty, tabela, grupowanie w lata, karta na Analizie, pusty stan.
- **e2e:** z Analizy wejście w „Dochód i koszty”; kafelki i wykres widoczne; zrzut `dochod.png`.
