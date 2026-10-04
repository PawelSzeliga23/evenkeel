/** Every Ustawienia row and the options inside its subpages (plan 8a): one list for the main screen and the search.
 * Later parts (8b–8d) add their rows here. */
export type Group = "Konto" | "Portfel" | "Wygląd i prywatność" | "Domyślne widoki" | "Dane" | "O aplikacji";
export const GROUPS: Group[] = ["Konto", "Portfel", "Wygląd i prywatność", "Domyślne widoki", "Dane", "O aplikacji"];

export interface SettingItem {
  id: string;
  group: Group;
  title: string;
  keywords: string;
  to: string;
  /** an option inside a subpage: shown only in the search, as „title · parent” */
  parent?: string;
}

export const SETTINGS: SettingItem[] = [
  { id: "profile", group: "Konto", title: "Profil", keywords: "e-mail email użytkownik", to: "/ustawienia/profil" },
  { id: "password", group: "Konto", title: "Zmień hasło", keywords: "hasło", to: "/ustawienia/haslo", parent: "Profil" },
  { id: "logout", group: "Konto", title: "Wyloguj", keywords: "wyjdź", to: "/ustawienia/profil#wyloguj", parent: "Profil" },
  { id: "accounts", group: "Portfel", title: "Konta", keywords: "rachunki IKE IKZE XTB obligacje oszczędnościowe", to: "/ustawienia/konta" },
  { id: "sources", group: "Portfel", title: "Źródła cen", keywords: "ceny notowania symbol Yahoo spread", to: "/ustawienia/zrodla-cen" },
  { id: "tags", group: "Portfel", title: "Tagi walorów", keywords: "tag kolor kategorie", to: "/ustawienia/tagi" },
  { id: "journal", group: "Portfel", title: "Dziennik", keywords: "notatki teza wpisy", to: "/ustawienia/dziennik" },
  { id: "theme", group: "Wygląd i prywatność", title: "Motyw", keywords: "jasny ciemny kolor kolory tryb wygląd", to: "/ustawienia/wyglad#motyw" },
  { id: "hide", group: "Wygląd i prywatność", title: "Ukrywanie kwot", keywords: "prywatność ukryj oko kwoty", to: "/ustawienia/wyglad" },
  { id: "start", group: "Wygląd i prywatność", title: "Ekran startowy", keywords: "start pierwszy ekran po zalogowaniu", to: "/ustawienia/wyglad#start" },
  { id: "defaults", group: "Domyślne widoki", title: "Domyślne widoki", keywords: "domyślne okres zakres", to: "/ustawienia/domyslne" },
  { id: "accounts_start", group: "Domyślne widoki", title: "Konta na starcie", keywords: "wybór kont cały portfel", to: "/ustawienia/domyslne#konta", parent: "Domyślne widoki" },
  { id: "analysis_period", group: "Domyślne widoki", title: "Okres w Analizie i Symulatorze", keywords: "okres analiza symulator", to: "/ustawienia/domyslne#analiza", parent: "Domyślne widoki" },
  { id: "holdings_period", group: "Domyślne widoki", title: "Okres w Walorach i Tagach", keywords: "okres walory tagi", to: "/ustawienia/domyslne#walory", parent: "Domyślne widoki" },
  { id: "value_range", group: "Domyślne widoki", title: "Zakres wykresu wartości", keywords: "wykres pulpit ekspozycja zakres", to: "/ustawienia/domyslne#wykres-wartosci", parent: "Domyślne widoki" },
  { id: "price_range", group: "Domyślne widoki", title: "Zakres wykresu ceny", keywords: "wykres cena zakres pozycja", to: "/ustawienia/domyslne#wykres-ceny", parent: "Domyślne widoki" },
  { id: "fixed_income", group: "Domyślne widoki", title: "Walory bez oszczędności i obligacji", keywords: "walory oszczędności obligacje", to: "/ustawienia/domyslne#bez-oszczednosci", parent: "Domyślne widoki" },
  { id: "backup", group: "Dane", title: "Kopia portfela", keywords: "kopia eksport backup zapisz pobierz wczytaj przywróć plik przeprowadzka", to: "/ustawienia/kopia" },
  { id: "refresh", group: "Dane", title: "Odświeżanie cen", keywords: "odświeżanie ceny kursy godziny harmonogram notowania", to: "/ustawienia/odswiezanie" },
  { id: "about", group: "O aplikacji", title: "O aplikacji", keywords: "Evenkeel wersja", to: "/ustawienia/o-aplikacji" },
];

export interface SearchHit { title: string; place: string; to: string }
const LIMIT = 20;

export function fold(text: string): string {
  return text.toLowerCase().replace(/ł/g, "l").normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/** Settings, then the owner's accounts and tags, whose name or keywords contain the query. */
export function searchSettings(
  query: string, accounts: { id: number; name: string }[], tags: { id: number; name: string }[],
): SearchHit[] {
  const q = fold(query.trim());
  if (!q) return [];
  const hits: SearchHit[] = [
    ...SETTINGS.filter((s) => fold(`${s.title} ${s.keywords}`).includes(q))
      .map((s) => ({ title: s.title, place: s.parent ?? s.group, to: s.to })),
    ...accounts.filter((a) => fold(a.name).includes(q))
      .map((a) => ({ title: a.name, place: "Konta", to: `/ustawienia/konta/${a.id}` })),
    ...tags.filter((t) => fold(t.name).includes(q)).map((t) => ({ title: t.name, place: "Tagi walorów", to: "/ustawienia/tagi" })),
  ];
  return hits.slice(0, LIMIT);
}
