# Plan 7g — Przegląd AI: cała Analiza w paczce, „W skrócie” z propozycjami z różnych perspektyw (decyzje projektowe)

**Data:** 2026-10-04
**Poprzednio:**
- przegląd AI: `2026-10-02-ai-review-design.md`;
- notatki w paczce: `2026-10-03-07f-2-notes-design.md`.

**Zapis rozmowy:** `2026-10-03-07g-ustalenia-robocze.md`. Wiąże sekcja „Wyjaśnienie właściciela”; wcześniejsze propozycje w tym pliku są nieaktualne.

## Decyzje właściciela (2026-10-03/04)

1. **Do paczki trafia wszystko z Analizy, czyli z planu 7.**
   - Już tam jest:
     - 7a: miary i historia;
     - 7b: scenariusze;
     - 7f-2: notatki.
   - Dochodzi:
     - 7c Walory;
     - 7d Dochód i koszty;
     - 7f-1 Tagi.
   - 7e (wykres ceny) pomijamy. Liczby z wykresu i tak są w tabelach.
2. **Tagi i notatki to kontekst.**
   - Z tagów wynika, co jest trzonem (core), emeryturą, poduszką, a co spekulacją.
   - Notatki dodają powody i plany.
   - Claude **sam wnioskuje**, do czego zmierza właściciel. Nie dopytuje go i nie ma formularza „Mój plan”.
3. **Odpowiedź zaczyna się od krótkiej części.**
   - Podsumowanie ma 2–3 zdania.
   - Po nim jest 1–5 propozycji, każda z innej perspektywy. Przykłady:
     - „więcej ryzyka, ale potencjalnie większy zysk”;
     - „lepiej zabezpieczyć się na cały świat”.
   - Potem jest dotychczasowy długi przegląd, bez zmian.
4. **Krótka część jest widoczna od razu na karcie „Przegląd AI” w Analizie.** Długi przegląd jest po wejściu w przegląd.
5. Zostaje jedna paczka i jedna odpowiedź do wklejenia. Krótka część to początek tej samej odpowiedzi.
6. **Okresy w paczce:**
   - Walory:
     - ranking za 1 miesiąc, 1 rok i cały okres;
     - zysk według kont i typów za cały okres.
   - Dochód i koszty:
     - sumy za 12 miesięcy i za cały okres;
     - miesiące z ostatnich 12 miesięcy.

## Paczka

Wszystkie nowe sekcje:
- liczą się tymi samymi funkcjami co ekrany Analizy:
  - `analytics.holdings.holdings`;
  - `analytics.income.income`;
  - `analytics.tags.tag_analytics`;
  - `tags.lookup.TagLookup`;
- dzięki temu liczby zgadzają się z aplikacją co do grosza;
- respektują wybór kont przy paczce;
- liczą konta oszczędnościowe tak jak Analiza przy wyłączonym „Bez oszczędności”, czyli z nimi.

Kolejność sekcji:
1. Podsumowanie
2. Konta
3. Pozycje
4. Obligacje
5. Konta oszczędnościowe
6. Alokacja
7. **Tagi**
8. **Walory**
9. **Dochód i koszty**
10. Miary
11. Historia
12. Limity
13. Zamknięte
14. Notatki właściciela
15. Scenariusze

### Kolumna „Tagi”

- Dochodzi jako ostatnia kolumna do tabel „Pozycje”, „Obligacje” i „Konta oszczędnościowe”.
- Zawiera nazwy tagów oddzielone przecinkiem, np. `core, emerytura`. Bez tagów: „—”.
- Tagi są te same, które pokazują szczegóły waloru (`TagLookup.on(key, account_id)`):
  - tagi waloru na wszystkich kontach;
  - tagi tylko na tym koncie.
- Klucz waloru:
  - pozycja: `i:{instrument}` z kontem pozycji;
  - obligacja: `b:{seria}` z kontem obligacji;
  - konto oszczędnościowe: `s:` z jego kontem.

### „## Tagi”

Tabela z `tag_analytics(scope, account_ids, "all")`:

| Tag | Wartość | Udział w portfelu | Zysk (cały okres) | Zysk % | Walorów |

- Kolejność wierszy taka jak w Analiza → Tagi.
- Pod tagami są dwa wiersze, jeśli dotyczą portfela:
  - „Bez tagu”;
  - „Gotówka” (tylko wartość i udział).
- Pod tabelą jedno zdanie: „Walor może mieć kilka tagów, więc udziały mogą sumować się do ponad 100 %.”
- Bez tagów w ogóle sekcja ma tylko zdanie: „Brak tagów.”

### „## Walory”

- **„### Ranking walorów”:** jedna tabela.

  | Walor | Typ | Wartość | Zysk 1 mies. | % | Zysk 1 rok | % | Zysk cały okres | % |

  - Liczy się z `holdings(..., "1m")`, `holdings(..., "1y")` i `holdings(..., "all")`, połączonych po `key`.
  - Walor to ticker (albo seria, albo nazwa konta oszczędnościowego) i nazwa.
  - Wartość pochodzi z okresu „all”.
  - Wiersze są ułożone według zysku za cały okres, malejąco.
  - Walor, którego nie ma w danym okresie, ma tam „—”.
  - Jeśli `holdings(..., "1m")` zwraca `period`, pod tabelą jest zdanie z datami okresów, np. „1 mies.: 04.09.2026–04.10.2026”. Tak samo dla „1 rok” i „cały okres”.
- **„### Według kont”:** `by_account` z okresu „all”.

  | Konto | Wartość | Zysk | Zysk % |

- **„### Według typów”:** `by_kind` z okresu „all”, z tymi samymi kolumnami.
- Bez danych sekcja ma jedno zdanie: „Brak danych.”

### „## Dochód i koszty”

- **„### Suma”:**

  | Okres | Dochód | Koszty | Bilans |

  - Dwa wiersze: „Ostatnie 12 miesięcy” (`income(..., "12m")`) i „Cały okres” (`income(..., "all")`).
- **„### Źródła dochodu (cały okres)”:** `sources` z okresu „all”.

  | Źródło | Rodzaj | Brutto | Podatek | Netto |

  - Rodzaj to jedno z: „konto oszczędnościowe”, „obligacje”, „odsetki XTB”, „dywidenda”.
- **„### Koszty (cały okres)”:** `costs` z okresu „all”.

  | Koszt | Kwota | Liczba |

- **„### Miesiące (ostatnie 12)”:** `months` z okresu „12m”.

  | Miesiąc | Odsetki | Dywidendy | Przewalutowanie | Podatki | Opłaty | Bilans |

  - Miesiąc zapisujemy jako „wrz 2026”.
- Bez danych sekcja ma jedno zdanie: „Brak danych.”

### Pozostałe sekcje

- Pozostałe sekcje się nie zmieniają.
- Przełącznik „Dołącz notatki” działa jak w 7f-2.
- Tagi i nowe sekcje są w paczce zawsze.

## Polecenie (`prompt.py`)

- **`SECTIONS`:**
  - „W skrócie” dochodzi na pierwsze miejsce;
  - dalej idzie dotychczasowe 9 sekcji w tej samej kolejności;
  - razem 10 sekcji.
- **W „Zasadach”:**
  - zdanie o notatkach z 7f-2 zastępuje to:
    > Tagi i notatki (sekcje „Tagi” i „Notatki właściciela”) to mój własny opis portfela: z tagów wynika, jaką rolę pełni każdy walor (np. trzon, emerytura, poduszka, spekulacja, region), a notatki dodają moje powody i plany. Wywnioskuj z nich, do czego zmierzam — nie pytaj mnie o to. Oceniaj portfel względem tego i wskazuj rozbieżności.
  - dochodzi zdanie:
    > Zysk walorów za okresy, według kont i typów jest w sekcji „Walory”; dywidendy, odsetki, podatki i koszty w „Dochód i koszty”; udział i zysk tagów w „Tagi”.
- **W „Formacie odpowiedzi”** dochodzi opis sekcji „W skrócie”:
  > „W skrócie”: najpierw 2–3 zdania — jak rozumiesz mój plan i jak portfel do niego dziś pasuje. Potem od 1 do 5 propozycji jako lista numerowana; każda zaczyna się pogrubioną nazwą perspektywy (np. **Więcej ryzyka, większy potencjał:**, **Bezpieczniej:**, **Porządki:**), ma konkretną kwotę i jedno zdanie powodu. Każda propozycja z innej perspektywy; gdy dajesz więcej niż jedną, przynajmniej jedna ma zwiększać potencjał zysku, a jedna zmniejszać ryzyko. Liczbę propozycji dobierz do tego, co naprawdę warto zrobić.
- **Sekcja „Propozycje”:** dochodzi zdanie, że rozwija propozycje z „W skrócie”: szczegóły, ryzyka i alternatywy. Zdanie „To nie jest porada inwestycyjna…” na jej początku zostaje.

## Aplikacja

- **API:**
  - `GET /api/reviews` (lista) dostaje w każdym elemencie pole `summary: str | null`. To treść sekcji „## W skrócie” zapisanej odpowiedzi:
    - tekst od nagłówka do następnego nagłówka `## `, bez samego nagłówka;
    - przycięty na końcach;
    - `null`, gdy sekcji nie ma albo jest pusta.
  - Nagłówek rozpoznajemy tak samo jak przy liczeniu sekcji w `clean.py`, bez względu na wielkość liter.
  - Liczenie sekcji (`sections`) liczy teraz do 10.
- **Web:**
  - **Karta „Przegląd AI” w Analizie:**
    - pod „Ostatni przegląd: {data}” pokazuje `summary` ostatniego przeglądu tym samym komponentem Markdown co pełny przegląd;
    - pod spodem jest mały, stały dopisek: „To nie jest porada inwestycyjna.”;
    - link „Przegląd portfela” zostaje.
    - Bez `summary` karta wygląda jak dziś, czyli pokazuje tylko datę. Dotyczy to przeglądu z 2.10.
  - **Licznik przy przeglądach:** `SECTION_COUNT` = 10. Stary przegląd pokaże „9/10 sekcji”.

## Testy

- **API, paczka:**
  - kolumna „Tagi”:
    - przy pozycji, obligacji i koncie oszczędnościowym;
    - tag tylko na jednym koncie jest widoczny tylko przy tym koncie;
    - bez tagów jest „—”;
  - sekcja „Tagi”:
    - wiersz tagu z udziałem i zyskiem;
    - „Bez tagu”;
    - filtr kont;
    - „Brak tagów.”;
  - sekcja „Walory”:
    - ranking z trzema okresami i kolejnością według zysku za cały okres;
    - „—” dla waloru spoza okresu;
    - „Według kont” i „Według typów”;
  - sekcja „Dochód i koszty”:
    - suma 12 miesięcy i całego okresu;
    - źródło dywidendy z podatkiem;
    - koszt przewalutowania;
    - wiersz miesiąca;
  - kolejność sekcji;
  - polecenie:
    - nowe zdania;
    - „W skrócie” jako pierwsza z 10 sekcji.
- **API, przeglądy:**
  - `summary` wycięte z odpowiedzi;
  - `null` bez sekcji;
  - liczenie do 10.
- **Web:**
  - karta pokazuje „W skrócie” z listą propozycji i dopisek;
  - bez `summary` karta pokazuje tylko datę;
  - licznik „/10”.

## Poza zakresem

- Dwa osobne przeglądy (krótki i długi) albo dwie paczki.
- Dane z 7e (wykres ceny).
- Formularz celu albo planu.
- Zmiana pozostałych 9 sekcji odpowiedzi.
