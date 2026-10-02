# Plan 7c — Walory: mapa cieplna, ranking, zysk według kont i typów (decyzje projektowe)

**Data:** 2026-10-02
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §2 „Etap 2” (mapa cieplna, ranking walorów, zysk per konto i per typ)
**Makieta:** `.superpowers/brainstorm/4682-1790964202/content/walory.html`, zaakceptowana z przełącznikiem „Bez oszczędności i obligacji”.

## Decyzje właściciela (2026-10-02)

1. Osobny ekran **Analiza → Walory** (`/analiza/walory`), na Analizie karta „Walory” z małą mapą za dzień.
2. Jeden przełącznik okresu dla całego ekranu: **Dzień · Tydzień · Miesiąc · Rok · Od pocz. roku · Wszystko**, domyślnie Dzień.
3. Walory to wszystko poza gotówką: ETF-y i akcje, obligacje (seria), konta oszczędnościowe.
4. Instrument na kilku kontach to jeden kafelek i jeden wiersz rankingu; rozbicie na konta pokazuje się po dotknięciu.
5. Przełącznik **„Bez oszczędności i obligacji”** ukrywa je na mapie i w rankingu; udziały i wkład w zysk liczą się wtedy tylko z pokazanych walorów.
6. Liczby jak w XTB: wartość do wypłaty (po kosztach wyjścia), kwoty transakcji tak, jak pobrało je XTB.

## Jak liczymy (dla każdego waloru, okres = dni od `start` do `end`, baza = dzień przed `start`)

- `V(d)`: wartość do wypłaty waloru w dniu `d` (`value_pln − exit_cost_pln` z `daily_valuations`; 0, gdy go wtedy nie było).
- **Instrument:**
  - zakupy = −Σ kwot PLN zakupów, sprzedaże = Σ kwot PLN sprzedaży;
  - przychody = Σ kwot PLN dywidend, podatku u źródła i opłat przypisanych instrumentowi;
  - wszystko z transakcji z dniem w okresie, po kursie NBP z dnia, jak na Pulpicie.
- **Obligacje i konta oszczędnościowe:** przepływ = `net_flow_pln` ich wierszy w okresie (zakup obligacji, wypłata przy wykupie, wpłaty i wypłaty z konta).
- **Zysk** = `V(end) − V(baza) − (zakupy − sprzedaże) + przychody` (dla obligacji i kont: `V(end) − V(baza) − Σ przepływów`).
- **Zysk %** = zysk ÷ (`V(baza)` + zakupy w okresie); brak, gdy mianownik ≤ 0.
- **Udział** = `V(end)` ÷ suma `V(end)` pokazanych walorów; **wkład** = zysk ÷ suma zysków pokazanych walorów (liczone w aplikacji, bo zależą od przełącznika).
- **Okresy:**
  - `end` = ostatni dzień wyceny;
  - Dzień: baza = poprzednia sesja przed ostatnią sesją, jak „zmiana dnia” na Pulpicie;
  - Tydzień: baza = `end − 7 dni`;
  - Miesiąc, Rok, Od pocz. roku, Wszystko: jak w Analizie (`period_start`);
  - przy „Wszystko” baza jest przed historią, więc `V(baza) = 0`.
- **Klucze waloru:**
  - instrument → `i:{instrument_id}`, nazwa i ticker instrumentu;
  - obligacje → `b:{seria}` (zakupy jednej serii razem);
  - konto oszczędnościowe → `s:{id}`, nazwa konta.

## API

`GET /api/analytics/holdings?period=1d|1w|1m|1y|ytd|all&account_id=…` (konta jak wszędzie):

```
period: {start, end} | null
items: [{key, kind: "instrument"|"bond"|"savings", ticker, name, category, value_pln, gain_pln, gain_pct,
         accounts: [{account_id, name, value_pln, gain_pln}]}]   (posortowane po gain_pln malejąco)
by_account: [{key, name, value_pln, gain_pln, gain_pct}]
by_kind: [{key, name, value_pln, gain_pln, gain_pct}]   (ETF, Akcje, Inne, Obligacje, Oszczędności)
recalculating
```

Brak wyceny → `period: null`, puste listy.

## Ekran `/analiza/walory`

- Link powrotny „Analiza”, tytuł „Walory”, wybór kont, przełącznik okresu (dwa rzędy po trzy na telefonie), przełącznik „Bez oszczędności i obligacji”.
- **Mapa:**
  - kafelki w układzie „squarified treemap”, wielkość według udziału;
  - kolor według zysku %: zieleń lub czerwień, mocniejsza przy większej zmianie; pełne nasycenie przy ±3 % (dzień), ±5 % (tydzień), ±10 % (miesiąc), ±30 % (rok, od pocz. roku), ±50 % (wszystko); szary przy zerze;
  - ticker (albo nazwa) i zysk % na kafelku, gdy się mieści;
  - kafelek jest przyciskiem; dotknięcie pokazuje pod mapą nazwę, zysk w zł i %, wartość, udział i rozbicie na konta.
- **Ranking:**
  - lista posortowana po zysku w zł albo w % (przełącznik „zł / %”);
  - w wierszu: ticker i nazwa, zysk w zł i %, udział, wkład w zysk okresu.
- **Zysk według kont** oraz **zysk według typów:** tabele z wartością, zyskiem w zł i %; nie zależą od przełącznika „bez oszczędności”.
- **Karta „Walory” na Analizie:** mała mapa za Dzień (cały portfel według filtra kont) i link „Walory”.

## Testy

- **API:** zysk dnia instrumentu równy zmianie ceny, zakup w okresie nie jest zyskiem, dywidenda jest, sprzedaż z zyskiem zrealizowanym, obligacje i konto oszczędnościowe przez przepływy, łączenie instrumentu z dwóch kont, filtr kont i cudze konto 404, okresy, brak wyceny.
- **Web:** układ treemap (suma pól = pole mapy, kolejność według wielkości), kolor według okresu, dotknięcie kafelka, przełącznik bez oszczędności (udziały przeliczone), ranking zł/%, tabele, karta na Analizie.
- **e2e:** wejście z Analizy na Walory, mapa i ranking widoczne.
