# 7g — przegląd AI: ustalenia robocze (szkic, NIE zatwierdzony)

**Data:** 2026-10-03
**Status:** rozmowa przerwana na prośbę właściciela, który ma poczucie, że nie zostało dobrze zrozumiane, o co mu chodzi. To zapis rozmowy, a nie specyfikacja.

## Punkt wyjścia

- Wiersz 7g w roadmapie (810a368) przewidywał trzy rzeczy:
  - dane z 7c (walory), 7d (dochód i koszty) i 7f-1 (tagi) w paczce;
  - notatki z 7f-2;
  - przepisany prompt.
- Do tej pory zapisano jeden przegląd, z 2026-10-02 (ok. 18 tys. znaków, 9 sekcji). Był rzetelny, ale ogólny („mało akcji przy długim horyzoncie”, „co z gotówką”), bo Claude nie znał celu właściciela.

## Co powiedział właściciel (dosłownie albo prawie dosłownie)

1. **Co ma być lepsze:** zaznaczył „Konkretne kroki” i „Krótszy, czytelniejszy”. Nie zaznaczył „Ocena względem planu” ani „Rozliczenie wyników”.
2. **Plan i cel:** „z tagów i notatek ma się domyślić, a nie że plan jest taki i siaki”. Odrzucił formularz „Mój plan”, cele przy tagach i dopytywanie przez Claude.
3. **Układ odpowiedzi:** wybrał wariant „Kroki na górze” z dopiskiem: „ale zachowaj też długi; możesz zrobić krótki, który się wyświetla od razu w Analiza, i długi po wejściu w raporty”.
4. Zaraz potem napisał: „ogólnie ja nie chcę dużo zmieniać, chcę dokładnie to samo, tylko dodaj tagi i notatki, żeby był kontekst”.
5. Na pytanie, czy krótki raport dołączyć do 7g, czy zrobić osobno, odpowiedział: „tak, jest to jedno zadanie”.

## Jak Claude to zrozumiał (ostatnia propozycja, niezatwierdzona)

- **A. Tagi w paczce:**
  - kolumna „Tagi” w tabelach Pozycje, Obligacje i Konta oszczędnościowe;
  - sekcja „## Tagi” po „Alokacji”, czyli udział i zysk per tag za cały okres, z wierszem „Bez tagu” i z filtrem kont;
  - notatki zostają jak w 7f-2.
- **B. Prompt:**
  - zdanie, że plan ma wywnioskować z tagów i notatek, napisać w „Ocenie ogólnej”, jak go rozumie, i wskazać rozbieżności;
  - nowa sekcja „## W skrócie” na początku: 3–5 zdań, wniosek i 1–3 kroki z kwotami;
  - pozostałe 9 sekcji bez zmian.
- **C. Analiza:**
  - karta „Przegląd AI” pokazuje „W skrócie” z ostatniego przeglądu, a pełny przegląd jest po wejściu w raport;
  - licznik sekcji zmienia się z /9 na /10.
- **Pominięte:** dane z 7c i 7d w paczce (wynika z punktu 4).

## Miejsca, gdzie mogło dojść do nieporozumienia (do wyjaśnienia)

- **„Krótki raport” to:**
  - (a) sekcja „W skrócie” w tej samej odpowiedzi Claude, czy
  - (b) dwa osobne przeglądy (dwie paczki albo dwa prompty: krótki i długi)?
- **„Wyświetla się od razu w Analiza”:**
  - czy chodzi o kartę na ekranie Analiza,
  - czy o to, żeby krótki przegląd był od razu po wklejeniu odpowiedzi,
  - czy jeszcze coś innego?
- **„Raporty”:** w aplikacji nie ma ekranu o tej nazwie. Pełne przeglądy są pod Analiza → Przegląd portfela.
- **„Dokładnie to samo”:**
  - czy dotyczy tylko odpowiedzi Claude (te same sekcje),
  - czy także paczki, czyli żadnych nowych tabel, tylko tagi przy walorach i notatki?
- **„Konkretne kroki” i „krótszy”:** czy mają nadal obowiązywać dla długiego przeglądu, skoro ma zostać „dokładnie to samo”?
- **Dane z 7c/7d:** czy na pewno mają nie trafić do paczki?

## Wyjaśnienie właściciela (2026-10-03, później) — wiążące

> „chodziło mi o to, aby wszystkie informacje z modułu analizy, czyli praktycznie cały plan 7, trafiały do prompta;
> co za tym idzie trafiłyby tam też tagi i notatki. Z tagów powinno wynikać, co jest core, emeryturą, a co jest
> spekulacją i tak dalej, z notatek jakieś dodatkowe rzeczy — daje to dużo kontekstu dla analizy przez AI, bo wie
> wtedy, do czego użytkownik zmierza. Dodatkowo niech najpierw napisze krótkie 2–3-zdaniowe podsumowanie i do tego
> 1–5 propozycji poprawienia sytuacji w portfelu, ale z różnych perspektyw: np. że warto zainwestować w to czy to,
> bo będzie większe ryzyko, ale potencjalnie większy zysk, a w innym punkcie, że warto lepiej hedgować na cały świat.”

Wcześniej: krótka część widoczna od razu w Analizie, długi przegląd po wejściu w raport.

Zrozumienie Claude (do potwierdzenia):
- Paczka = wszystko z Analizy (plan 7). Już jest: 7a (miary, historia), 7b (scenariusze), 7f-2 (notatki).
  Dochodzi: 7c Walory (zysk za okresy, według kont i typów, ranking), 7d Dochód i koszty, 7f-1 Tagi
  (tagi przy walorach, udział i zysk per tag). 7e (wykres ceny) nie wnosi nic ponad tabele — pomijamy.
- Tagi i notatki mówią, do czego zmierzam (core / emerytura / spekulacja / poduszka…); Claude wnioskuje plan sam.
- Odpowiedź Claude: najpierw część krótka — podsumowanie 2–3 zdania + 1–5 propozycji, każda z innej perspektywy
  (np. „więcej ryzyka, większy potencjał”, „lepsze zabezpieczenie / szersza dywersyfikacja na cały świat”),
  potem dotychczasowy długi przegląd bez zmian.
- Krótka część widoczna od razu na karcie „Przegląd AI” w Analizie; długi po wejściu w przegląd.
- Nadal jedna paczka i jedna wklejana odpowiedź (założenie).
