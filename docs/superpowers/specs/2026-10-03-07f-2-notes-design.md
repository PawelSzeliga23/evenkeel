# Plan 7f-2 — Notatki: teza waloru, dziennik decyzji i dziennik portfela (decyzje projektowe)

**Data:** 2026-10-03
**Specyfikacja główna:** `2026-09-26-portfolio-tracker-design.md` §2 „Etap 2” („Notatki do pozycji i operacji”), §4 szkic tabeli `notes`.
**Poprzednio:** 7f-1 tagi (`2026-10-03-07f-1-tags-design.md`). Sposób wskazywania waloru (instrument, seria obligacji, konto oszczędnościowe) jest ten sam.
**Makieta:** `.superpowers/brainstorm/9040-1790984044/content/notatki.html` (zaakceptowana 2026-10-03).

## Decyzje właściciela (2026-10-03)

1. Notatki służą do trzech rzeczy:
   - **teza waloru:** jeden tekst poprawiany co jakiś czas („po co to trzymam, kiedy sprzedam”);
   - **dziennik decyzji przy walorze:** krótkie wpisy z datą;
   - **dziennik całego portfela:** wpisy z datą niezwiązane z jednym walorem.
2. **Komentarzy do pojedynczych operacji nie ma.** Szkic z głównej specyfikacji („notatki do operacji”, `target_type = transaction | position_lot`) odpada.
3. **Poziom: walor, wspólnie dla wszystkich kont:**
   - instrument (ETF, akcja);
   - obligacje według **serii**, jak w tagach;
   - konto oszczędnościowe jako całość.

   Nie ma poziomu „tylko na tym koncie” ani pola „dotyczy konta”.
4. W szczegółach waloru u góry jest **teza**, pod nią **dziennik**.
5. **Wspólny dziennik** jest w **Więcej → Dziennik**.
6. Wpisy pokazują się jako znacznik **„N” na wykresie ceny waloru**. Wykres wartości na Pulpicie się nie zmienia.
7. **Przegląd AI:** paczka dostaje **tezy i wpisy z ostatnich 12 miesięcy**. Decyduje o tym przełącznik „Dołącz notatki”, domyślnie włączony.

Szkic polimorficznej tabeli `notes` z głównej specyfikacji (`target_type`, `target_id`) jest zastąpiony poniższym układem. Prawdziwe klucze obce dają spójność danych i sprzątanie przy usunięciu.

## Dane

Migracja `0015_notes`.

```
theses           id, user_id → users (CASCADE),
                 instrument_id? → instruments (CASCADE) | bond_series? → bond_series (CASCADE)
                   | account_id? → accounts (CASCADE)            dokładnie jedno (CHECK num_nonnulls = 1)
                 body text, updated_at
                 unikalne (user_id, instrument_id, bond_series, account_id) NULLS NOT DISTINCT

journal_entries  id, user_id → users (CASCADE), entry_date date, body text,
                 instrument_id? | bond_series? | account_id?     najwyżej jedno (CHECK num_nonnulls <= 1);
                                                                 żadne = wpis o portfelu
                 created_at, updated_at
                 indeks (user_id, entry_date DESC, id DESC)
```

- **Cel** („walor”) to jedno z pól:
  - `instrument_id` dla instrumentu;
  - `bond_series` dla serii obligacji;
  - `account_id` dla konta oszczędnościowego.

  W API i w kodzie zapisujemy go kluczem jak w `TagLookup`: `i:{id}`, `b:{seria}`, `s:{account_id}`, a dla portfela `portfolio`.
- **Treść:**
  - przycięta ze spacji na końcach, z zachowanymi podziałami linii;
  - teza ma 1–5000 znaków, wpis 1–2000 znaków;
  - to zwykły tekst bez formatowania, wyświetlany z zachowaniem nowych linii (`white-space: pre-wrap`), nigdy jako HTML.
- **Data wpisu:**
  - domyślnie dzisiejsza (`local_today()`);
  - nie może być późniejsza niż dziś ani wcześniejsza niż 2000-01-01, inaczej 422 `entry_date`.
- **Kolejność wpisów:** `entry_date` malejąco, potem `id` malejąco.
- **Własność:** walor sprawdzamy tak samo jak przy przypinaniu tagu „dla waloru”, inaczej 404:
  - instrument musi być widoczny (`scope.get_instrument`);
  - seria musi należeć do którejś z obligacji użytkownika;
  - `account_id` musi wskazywać konto oszczędnościowe użytkownika. Samo zwykłe konto daje 422 `note_target`.

  Cudzy wpis albo cudza teza też dają 404.
- **Usunięcie:**
  - konto oszczędnościowe usunięte razem z kontem zabiera swoje notatki (kaskada). `GET /api/accounts/{id}/usage` dostaje pole `notes` (teza i wpisy konta), więc potwierdzenie usunięcia konta wymienia je jak resztę („…, 3 notatki”);
  - instrumentów się nie usuwa;
  - seria obligacji jest wspólna, więc notatki serii zostają, nawet gdy użytkownik nie ma już jej obligacji. W dzienniku są wtedy widoczne jako walor zamknięty.

## API

- **Teza:**
  - `PUT /api/theses {instrument_id? | bond_series? | account_id?, body}` → 200 `{id, target, body, updated_at}`;
  - **pusty `body`** (po przycięciu) usuwa tezę i zwraca 204. To samo dzieje się, gdy tezy nie było;
  - zero albo kilka celów → 422 `note_target`.
- **Wpisy:**
  - `GET /api/journal?target=i:12|b:EDO0936|s:5|portfolio` → `{entries: [JournalEntryOut], count}`. Bez `target` zwraca wszystkie wpisy użytkownika;
  - `POST /api/journal {entry_date?, body, instrument_id? | bond_series? | account_id?}` → 201;
  - `PATCH /api/journal/{id} {entry_date?, body?, instrument_id? | bond_series? | account_id? | portfolio: true}` → 200. Pozwala też przenieść wpis na inny walor albo na portfel;
  - `DELETE /api/journal/{id}` → 204.
- **`JournalEntryOut`:**
  ```
  id, entry_date, body, created_at, updated_at
  target: {key, label, sublabel?, closed, link} | null      (null = portfel)
    label     ticker XTB instrumentu (sublabel: nazwa); seria (np. „EDO0936”); nazwa konta oszczędnościowego
    closed    instrument: brak otwartej pozycji na żadnym koncie; seria: brak niewykupionej obligacji;
              konto oszczędnościowe: nigdy
    link      {kind: position | bond | savings, account_id?, instrument_id?, bond_holding_id?}:
              instrument — ostatnie konto z operacją na tym walorze; seria — najnowsza obligacja tej serii;
              konto oszcz. — to konto; null, gdy nie da się ustalić (np. seria bez obligacji)
  ```
- **Cele do wyboru:** `GET /api/journal/targets` → `[{key, label, sublabel, closed}]`. Zawiera walory, które użytkownik ma albo miał:
  - instrumenty z jego operacjami;
  - serie jego obligacji;
  - jego konta oszczędnościowe.

  Najpierw otwarte, potem zamknięte, w każdej grupie alfabetycznie.
- **Notatki w szczegółach:** pole `notes: {thesis: {body, updated_at} | null, recent: [{id, entry_date, body, created_at, updated_at}] (najwyżej 3, bez `target` — to ten walor), count}`. Dochodzi do:
  - `GET /api/positions/{a}/{i}` (także dla pozycji zamkniętej);
  - szczegółów obligacji (seria tej obligacji);
  - szczegółów konta oszczędnościowego.
- **Wykres ceny:** `GET /api/positions/{a}/{i}/prices` dostaje pole `notes: [{date, entries: [{id, body}]}]`, osobne od `markers`, żeby nie zmieniać kształtu znaczników operacji:
  - wpisy danego instrumentu z zakresu wykresu, zgrupowane według dnia;
  - **dzień bez notowania** (weekend, święto) przesuwa się na najbliższy następny dzień z ceną;
  - wpis późniejszy niż ostatnie notowanie trafia na ostatni dzień z ceną;
  - wpis sprzed początku zakresu (`from`) jest pomijany, a przy „Maks” wpis sprzed pierwszego notowania. Wpis między `from` a pierwszym notowaniem trafia na pierwsze notowanie.
- **Przegląd AI:** `GET /api/reviews/package?…&notes=true|false`, domyślnie `true`. Przy `true` paczka dostaje sekcję **„## Notatki właściciela”** przed sekcją scenariuszy:
  - **„### Tezy”:** lista `- **SXR8.DE — Core S&P 500:** treść`, tylko dla walorów obecnych w paczce, czyli otwartych pozycji, obligacji i kont oszczędnościowych z wybranych kont;
  - **„### Dziennik (ostatnie 12 miesięcy)”:** lista `- 03.10.2026 · SXR8.DE: treść` albo `- 01.10.2026 · portfel: treść`, chronologicznie od najstarszego. Obejmuje wpisy o portfelu i o walorach obecnych w paczce, z datą od dziś minus 12 miesięcy;
  - kolejne linie treści są wcięte, żeby lista się nie rozpadła;
  - bez tez i wpisów sekcja ma jedno zdanie: „Brak notatek.”;
  - instrukcje (`prompt.py`) dostają zdanie: „Jeśli są notatki właściciela, oceń, czy portfel jest zgodny z jego tezami i planem, i wskaż rozbieżności.”

## Ekrany

- **Sekcja „Notatki”** w szczegółach pozycji, obligacji i konta oszczędnościowego, zaraz pod sekcją „Tagi”:
  - nagłówek „Notatki” z dopiskiem „wspólne dla wszystkich kont”. Przy koncie oszczędnościowym dopisku nie ma;
  - **„Teza”:**
    - bez tezy: przycisk „+ Dodaj tezę”;
    - z tezą: tekst w ramce z bursztynowym paskiem z lewej, pod nim „zaktualizowano {data}”, obok przycisk „Edytuj”;
    - edycja odbywa się w miejscu: pole tekstowe, licznik przy zbliżaniu się do limitu, „Zapisz” i „Anuluj”. Zapisanie pustego pola usuwa tezę;
  - **„Dziennik”:**
    - „+ Wpis” otwiera w miejscu formularz z datą (domyślnie dziś), treścią, „Zapisz” i „Anuluj”;
    - pod formularzem są 3 najnowsze wpisy (data, treść);
    - przy więcej niż 3 wpisach jest link „Wszystkie wpisy ({count}) ›” do `/ustawienia/dziennik?target={key}`;
    - bez wpisów: „Zapisuj, dlaczego kupujesz i sprzedajesz.”;
  - **dotknięcie wpisu** otwiera go w miejscu do edycji, z „Zapisz”, „Anuluj” i „Usuń”. Usunięcie potwierdza się w aplikacji, bez okna przeglądarki: „Usunąć wpis z {data}?”.
- **Więcej → Dziennik** (`/ustawienia/dziennik`):
  - na ekranie Ustawień jest sekcja „Dziennik” z opisem „Teza i decyzje przy walorach oraz wpisy o całym portfelu.” i linkiem, tak jak „Tagi walorów”;
  - link powrotny „Ustawienia” (jak w Tagach: ekran żyje pod `/ustawienia`), tytuł „Dziennik”;
  - **filtr:** lista „Wszystkie / Portfel / walory” z `GET /api/journal/targets`, zamknięte walory z dopiskiem „zamknięty”. Wartość filtra jest w adresie (`?target=`);
  - **„+ Wpis”** otwiera formularz z polami data, treść i „Dotyczy” (lista jak filtr, bez „Wszystkie”). Domyślnie „Dotyczy” to walor z filtra, a przy „Wszystkie” portfel;
  - **oś czasu:**
    - wpisy pogrupowane według miesięcy („październik 2026”), najnowsze u góry;
    - przy każdym wpisie dzień i miesiąc, etykieta celu i treść;
    - etykieta „Portfel” jest niebieska, etykieta waloru szara i prowadzi do szczegółów (`link`), a bez linku jest zwykłym tekstem;
    - zamknięty walor ma dopisek „zamknięty”;
  - dotknięcie wpisu otwiera edycję jak w sekcji, z dodatkowym polem „Dotyczy”;
  - **wybór kont nie filtruje dziennika**. Kontrolki wyboru kont na tym ekranie nie ma;
  - **pusty stan:** „Zapisuj, dlaczego kupujesz i sprzedajesz — za rok to bezcenne.” oraz „+ Wpis”;
  - wszystkie wpisy są ładowane naraz, bez stronicowania (jeden właściciel, setki wpisów).
- **Wykres ceny** (szczegóły pozycji):
  - znacznik „N” w kółku w kolorze `#C98BD9`, nad linią ceny w dniu wpisu, obok ▲ ▼ „D”;
  - kilka wpisów jednego dnia daje jeden znacznik;
  - znacznik jest przyciskiem z etykietą dostępności „Notatka {data}”;
  - po dotknięciu „N” panel pod wykresem pokazuje wpisy tego dnia („N” + treść), a pod nimi operacje z tego samego dnia; dotknięcie znacznika operacji działa jak dziś;
  - legenda dostaje „N Notatka”, gdy na wykresie są wpisy;
  - gesty, zakresy i zoom się nie zmieniają.
- **Przegląd AI** (Analiza → Przegląd):
  - przy „Przygotuj paczkę” jest przełącznik „Dołącz notatki” z podpisem „tezy + wpisy z 12 miesięcy”, domyślnie włączony;
  - stan przełącznika jest zapamiętany w przeglądarce;
  - kopiowanie i pobieranie paczki biorą go pod uwagę.

## Testy

- **API:**
  - teza:
    - utworzenie, zmiana (ta sama teza, nowe `updated_at`), pusta treść usuwa, ponowne puste 204;
    - limit 5000;
    - zero albo dwa cele → 422 `note_target`, zwykłe konto → 422;
    - cudzy instrument, seria, konto → 404;
  - wpisy:
    - dodanie z domyślną datą, data z przyszłości → 422, limit 2000;
    - zmiana treści i daty, przeniesienie na portfel i na inny walor, usunięcie;
    - cudzy wpis → 404;
    - kolejność;
    - filtr `target` dla każdego rodzaju i `portfolio`;
    - `count`;
    - `label`, `closed` i `link` dla każdego rodzaju celu, w tym zamkniętego instrumentu i serii bez obligacji (`link` null);
  - `GET /api/journal/targets`: walory z operacjami, serie, konta oszczędnościowe; otwarte przed zamkniętymi;
  - `notes` w szczegółach pozycji, także zamkniętej, oraz obligacji i konta oszczędnościowego: teza, 3 najnowsze, `count`;
  - usunięcie konta oszczędnościowego zabiera jego tezę i wpisy;
  - wykres ceny: wpisy według dni, weekend przesunięty na poniedziałek, wpis po ostatnim notowaniu na ostatnim dniu, wpis sprzed zakresu pominięty;
  - paczka AI:
    - sekcja z tezami tylko walorów z paczki, przy filtrze kont bez walorów innych kont;
    - wpisy z 12 miesięcy (starszy pominięty), wpis o portfelu;
    - wcięcie wielu linii;
    - „Brak notatek.”;
    - `notes=false` bez sekcji.
- **Web:**
  - sekcja Notatki:
    - dodanie, edycja i usunięcie (puste) tezy;
    - dodanie wpisu, 3 najnowsze i link z liczbą;
    - edycja i usunięcie wpisu z potwierdzeniem;
    - ta sama sekcja w obligacji i koncie oszczędnościowym;
  - Więcej → Dziennik:
    - grupy miesięcy, etykiety (portfel, walor z linkiem, zamknięty bez linku);
    - filtr z adresu;
    - dodanie z „Dotyczy”, przeniesienie wpisu na portfel;
    - pusty stan;
    - wpis na ekranie Ustawień;
  - wykres ceny: znacznik „N”, jeden na dzień, panel z treścią wpisu przed operacjami;
  - przegląd AI: przełącznik domyślnie włączony, zapamiętany, `notes=false` w zapytaniu po wyłączeniu.
- **e2e:**
  - w szczegółach CD Projekt dodanie tezy i wpisu z dzisiejszą datą;
  - Więcej → Dziennik pokazuje wpis z etykietą „CDR.PL”;
  - dodanie wpisu o portfelu;
  - zrzut `dziennik.png`.

## Poza zakresem

- Komentarze do operacji i partii.
- Notatki „tylko na tym koncie”.
- Formatowanie (markdown), załączniki, wyszukiwanie po treści.
- Znaczniki wpisów o portfelu na wykresie wartości na Pulpicie.
- Wpisy dla walorów, których użytkownik nigdy nie miał (lista obserwowanych).
