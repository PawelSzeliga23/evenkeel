/** What each measure means and how it is counted, in plain words; keyed by the name shown on screen (spec 7a §5). */
export interface Help { what: string; how: string }

export const HELP: Record<string, Help> = {
  "Zysk": {
    what: "Ile zarobiłeś w okresie, nie licząc tego, co sam dopłaciłeś.",
    how: "wartość na koniec okresu − wartość na początku − wpłaty netto w okresie.",
  },
  "TWR": {
    what: "Jak radziły sobie same inwestycje, niezależnie od terminów wpłat; tę miarę porównuje się z funduszami.",
    how: "zwrot każdego dnia liczony bez wpływu wpłat (wpłata liczy się na początku dnia), a zwroty dni mnożone przez siebie; od roku wzwyż przeliczony na rok.",
  },
  "XIRR": {
    what: "Twój osobisty zwrot z uwzględnieniem tego, kiedy i ile wpłacałeś; jak oprocentowanie lokaty o tym samym wyniku.",
    how: "stopa, przy której Twoje wpłaty, wypłaty i dzisiejsza wartość się równoważą (jak XIRR w Excelu); dla okresu krótszego niż rok przeliczona na okres.",
  },
  "Maks. obsunięcie": {
    what: "Największy spadek od szczytu do dołka w okresie.",
    how: "z dziennych zwrotów (TWR), więc wpłaty nie zasłaniają spadków: najniższy poziom względem najwyższego wcześniejszego.",
  },
  "Obecne obsunięcie": {
    what: "Ile dziś brakuje do najwyższego poziomu.",
    how: "dzisiejszy poziom TWR względem najwyższego w okresie.",
  },
  "Zmienność": {
    what: "Jak mocno wartość skacze; 15 % znaczy, że typowy rok mieści się mniej więcej w ±15 %.",
    how: "odchylenie standardowe dziennych zwrotów × √365; potrzeba co najmniej 30 dni.",
  },
  "Sharpe": {
    what: "Ile zysku przypada na jednostkę ryzyka ponad bezpieczną lokatę; powyżej 1 dobrze, poniżej 0 lokata wypadła lepiej.",
    how: "(średni dzienny zwrot − dzienna stopa referencyjna NBP) ÷ odchylenie dziennych zwrotów × √365; potrzeba co najmniej 30 dni.",
  },
  "Najlepszy dzień": {
    what: "Największy dzienny wzrost w okresie.",
    how: "dzień z najwyższym zwrotem; kwota to zmiana wartości tego dnia bez wpłat i wypłat.",
  },
  "Najgorszy dzień": {
    what: "Największy dzienny spadek w okresie.",
    how: "dzień z najniższym zwrotem; kwota to zmiana wartości tego dnia bez wpłat i wypłat.",
  },
  "Obsunięcie w czasie": {
    what: "Jak głęboko i jak długo portfel był poniżej swojego najwyższego poziomu; 0 % to nowy rekord.",
    how: "każdego dnia poziom TWR względem najwyższego wcześniejszego w okresie.",
  },
  "Zwrot w miesiącach": {
    what: "Zwrot w każdym miesiącu i roku, za całą historię, niezależnie od wybranego okresu.",
    how: "dzienne zwroty TWR mnożone w obrębie miesiąca; rok to iloczyn jego miesięcy.",
  },
  "Zysk łącznie": {
    what: "Ile zarobiłeś od początku.",
    how: "dzisiejsza wartość do wypłaty − wpłaty netto (wpłaty minus wypłaty).",
  },
  "Stopa zwrotu (TWR)": {
    what: "Jak radziły sobie same inwestycje od początku, niezależnie od terminów wpłat.",
    how: "zwrot każdego dnia liczony bez wpływu wpłat, a zwroty dni od pierwszego dnia historii mnożone przez siebie.",
  },
  "Wpłacono": {
    what: "Ile pieniędzy włożyłeś w portfel.",
    how: "suma wpłat na wybrane konta minus wypłaty, w złotych.",
  },
  "Wartość": {
    what: "Ile byłoby do wypłaty na koniec okresu.",
    how: "wartość do wypłaty ostatniego dnia: po kosztach sprzedaży i przewalutowania, tak jak na Pulpicie.",
  },
  "Dywidendy i odsetki": {
    what: "Dochód, który wpłynął na konta.",
    how: "dywidendy i odsetki po pobranym podatku, w złotych po kursie NBP z dnia wpływu.",
  },
};
