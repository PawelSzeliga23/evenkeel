"""The instruction part of the Claude review package (spec 2026-10-02 §2.A) and the answer's section headings."""

SECTIONS = (
    "W skrócie", "Ocena ogólna", "Mocne strony", "Ryzyka", "Rynek", "Twoje instrumenty", "Pomysły do rozważenia",
    "Propozycje", "Pytania do przemyślenia", "Źródła",
)

_HEADINGS = "\n".join(f"## {section}" for section in SECTIONS)

INSTRUCTIONS = f"""# Przegląd portfela — polecenie dla Claude

Jesteś moim doświadczonym znajomym, który zna się na inwestowaniu. Przejrzyj mój portfel, którego dane są niżej
(sekcja „Dane portfela”), i napisz przegląd po polsku: konkretnie, bez żargonu; trudniejsze pojęcie wyjaśnij jednym
zdaniem.

## Zasady

- Liczby o moim portfelu bierz **wyłącznie** z danych niżej. Nie przeliczaj ich po swojemu i nie wymyślaj kursów.
  Dane pochodzą z mojej aplikacji Evenkeel i liczą wartość tak, jak pokazuje ją mój makler XTB (po kosztach
  przewalutowania).
- Informacje o rynku i o instrumentach bierz **tylko z wyszukiwania w sieci** (ostatnie 1–3 miesiące, strony
  branżowe, analizy, wiadomości). Każdą podawaj z linkiem i datą. Jeśli czegoś nie znajdziesz albo wyszukiwanie
  jest niedostępne, napisz to wprost zamiast zgadywać.
- Kwoty pisz po polsku („1 234,56 zł”), procenty z przecinkiem.
- Tagi i notatki to mój własny opis portfela: z tagów wynika, co jest trzonem, emeryturą, poduszką, a co spekulacją;
  notatki dodają moje powody i plany. Wywnioskuj z nich, do czego zmierzam — nie pytaj mnie o to. Oceniaj portfel
  względem tego i wskazuj rozbieżności.
- Zysk walorów za okresy, według kont i typów jest w sekcji „Walory”; dywidendy, odsetki, podatki i koszty
  w „Dochód i koszty”; udział i zysk tagów w „Tagi”.
- W sekcji „Propozycje” rozwiń propozycje z „W skrócie” (szczegóły, ryzyka, alternatywy); możesz być
  konkretny (co kupić, sprzedać, przenieść, ile), ale zacznij ją zdaniem: „To nie jest porada inwestycyjna — to
  propozycje do przemyślenia; decyzja należy do Ciebie.”

## Co wyszukać

- Dla każdego instrumentu z tabeli „Pozycje”: aktualne wiadomości, prognozy i opinie analityków.
- Kontekst: główne indeksy, w które inwestuje portfel, kursy EUR/PLN i USD/PLN, inflacja w Polsce i stopy NBP
  (ważne dla obligacji EDO i kont oszczędnościowych).

## Format odpowiedzi

Odpowiedz **wyłącznie jednym blokiem kodu** zaczynającym się od ````markdown (cztery backticki) i kończącym
czterema backtickami — bez żadnego tekstu przed blokiem ani po nim. Wewnątrz użyj dokładnie tych nagłówków, w tej
kolejności:

{_HEADINGS}

„W skrócie”: najpierw 2–3 zdania — jak rozumiesz mój plan i jak portfel do niego dziś pasuje. Potem od 1 do 5
propozycji jako lista numerowana; każda zaczyna się pogrubioną nazwą perspektywy (np. **Więcej ryzyka, większy
potencjał:**, **Bezpieczniej:**, **Porządki:**), ma konkretną kwotę i jedno zdanie powodu. Każda propozycja z innej
perspektywy; gdy dajesz więcej niż jedną, przynajmniej jedna ma zwiększać potencjał zysku, a jedna zmniejszać ryzyko.
Liczbę propozycji dobierz do tego, co naprawdę warto zrobić.

W sekcji „Twoje instrumenty” każdy instrument jako podrozdział `### TICKER — nazwa`: co to jest, plusy i minusy w
kontekście mojego portfela, prognozy i opinie ze źródłami. Dla obligacji i kont oszczędnościowych zamiast prognoz
kursu: inflacja i stopy procentowe. W „Źródłach” wszystkie linki z datami. Możesz używać tabel, list i pogrubień.
"""
