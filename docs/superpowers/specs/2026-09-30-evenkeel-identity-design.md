# Evenkeel: nazwa, logo i ekran ładowania (decyzje projektowe)

**Data:** 2026-09-30
**Makiety (git-ignored):** `.superpowers/brainstorm/5291-1790783670/content/`. Logo: `logo-bars-line.html`, wariant 4. Animacja: `splash-animation-v5.html`.

## Cel

Aplikacja dostaje własną tożsamość w miejsce roboczej nazwy „Portfel”: nazwę, znak, ikony i animowany ekran
ładowania przy starcie. Charakter ma być spokojny i rzetelny, a przy tym konkretny i techniczny. Nazwa jest
angielska. To raczej nie będzie produkt, więc znaki towarowe nie mają znaczenia.

## Decyzje właściciela (2026-09-30)

1. Nazwa: **Evenkeel** (od „on an even keel”, czyli stabilnie, w równowadze).
2. Znak: cztery rosnące słupki na ciemnym kafelku, na cienkiej podstawie, bez linii trendu.
3. Napis: „Even” w kolorze tekstu i „keel” w bursztynie.
4. Ekran ładowania: znak z napisem pod nim, na środku ekranu (telefon i komputer). Słupki zawsze rosną i się
   przesuwają.
   - Znika po zalogowaniu i po pobraniu wartości portfela.
   - Przy każdym uruchomieniu jest widoczny co najmniej 3 sekundy (zmiana z 2 s, 2026-09-30). Przy wejściu logo się powiększa, jakby się wchodziło do aplikacji.
5. Logo w aplikacji: na ekranie logowania i rejestracji, w pasku bocznym na komputerze i w stopce „O aplikacji” na
   dole Ustawień (telefon i komputer). Stopkę łatwo usunąć, jeśli się nie spodoba.

## 1. Znak i napis

- Nowy moduł `web/src/brand/` z trzema komponentami:
  - `Mark` (znak, rozmiar w pikselach),
  - `Wordmark` (napis),
  - `Logo` (znak z napisem; układ `stacked` = napis pod znakiem, `inline` = napis obok).
- Znak (SVG, siatka 64×64):
  - Kafelek: `rx 15`, gradient od `#1C2129` do `#0E1116` po skosie, obwódka `#242A33`.
  - Słupki: szerokość 8, `rx 1.5`, gradient pionowy od `#8A5A1C` (dół) do `#FFC266` (góra). Przezroczystość po kolei
    0,55 / 0,7 / 0,85 / 1.
  - Wysokości słupków: 12 / 19 / 25 / 38. Pozycje x: 11 / 22 / 33 / 44. Podstawa słupków: y = 52.
  - Linia podstawy: od x 8 do 56, na y = 52, kolor `#3A424E`, grubość 1,5.
- Napis: font aplikacji, grubość 600, bez rozstrzelenia. Słowo „Even” ma kolor `--ink`, a słowo „keel” kolor
  `--amber`.
- Dostępność:
  - `Logo` ma dostępną nazwę „Evenkeel”; znak w środku ma `aria-hidden`.
  - Na ekranie logowania nagłówek `h1` ma nazwę „Evenkeel”.

## 2. Nazwa i ikony

- Nazwa „Portfel” zmienia się na „Evenkeel” w:
  - manifeście: `name`, `short_name`;
  - `description`: „Cały portfel inwestycyjny w jednym miejscu.” (bez zmian);
  - `web/index.html`: `<title>` i `apple-mobile-web-app-title`.
- `web/public/icon.svg` to znak z punktu 1.
- Ikony PNG (favicon, apple-touch, pwa-64/192/512, maskable) generuje `npm run icons`
  (`@vite-pwa/assets-generator`, już w projekcie). Wersja maskable ma margines bezpieczeństwa, żeby telefon nie przyciął
  słupków. Wygenerowane pliki trafiają do repozytorium.
- Zmieniają się teksty ekranów logowania i rejestracji: nagłówek „Portfel” zastępuje `Logo` (`stacked`). Zdania w
  rodzaju „zobaczyć swój portfel” zostają.

## 3. Ekran ładowania

- Nowy komponent `StartupSplash` (w `web/src/brand/`) pokazywany nad całą aplikacją przy każdym jej uruchomieniu.
  Przy późniejszych przejściach między ekranami się nie pokazuje.
- Wygląd: tło `--night`, na środku znak (ok. 84 px) z napisem pod spodem, taki sam na telefonie i komputerze.
- Animacja słupków (jak w `splash-animation-v5.html`):
  - Widoczne są 4 słupki, każdy wyższy od poprzedniego. Kroki są nierówne: następna wartość to poprzednia × (1,12 do
    1,45, losowo).
  - Wysokości przelicza się względem najwyższego (najnowszego) słupka i płynnie przechodzą do nowych wartości.
  - Co ok. 1,4 s nowy słupek wysuwa się spod linii podstawy po prawej. Najstarszy chowa się pod nią po lewej, a reszta
    przesuwa się o jedno miejsce.
  - Ruch trwa ok. 0,9 s z łagodnym przyspieszeniem i hamowaniem.
- Kiedy znika: po spełnieniu wszystkich warunków naraz.
  - Od startu minęły co najmniej **3 s**.
  - Sesja jest rozstrzygnięta (zalogowany, niezalogowany, brak połączenia albo błąd serwera).
  - Jeśli użytkownik jest zalogowany i aplikacja startuje na Pulpicie (`/`), pierwsze zapytanie o podsumowanie
    portfela (`["portfolio", "summary", …]`) zakończyło się sukcesem albo błędem. Na innych ekranach wystarczy sesja.
- Znikanie: znak z napisem powiększa się (ok. 7×, ok. 0,75 s) i gaśnie, a tło gaśnie razem z nim, odsłaniając
  aplikację. Potem komponent znika z drzewa.
- Pod spodem aplikacja działa normalnie: logowanie, komunikat o braku połączenia i Pulpit ze szkieletami. Dzisiejszy
  prosty `Splash` w `RequireAuth.tsx` zostaje tylko jako ciemne tło.
- „Ogranicz ruch” (`prefers-reduced-motion: reduce`): znak stoi nieruchomo, a znikanie to samo zgaszenie, bez powiększania. Warunki
  i minimum 3 s obowiązują tak samo.
- Dostępność: w czasie ładowania `aria-busy="true"` i etykieta „Wczytuję Evenkeel”. Znikający ekran nie przechwytuje
  kliknięć.
- Testowalność:
  - Minimalny czas i takty animacji są parametrami komponentu (domyślnie 3000 ms).
  - `StartupSplash` jest montowany w `App.tsx`, więc testy ekranów (`renderApp`) go nie widzą i nie zwalniają.

## 4. Logo w aplikacji

- Ekran logowania i rejestracji: `Logo` (`stacked`) zamiast nagłówka „Portfel”.
- Pasek boczny na komputerze (≥ 900 px): `Logo` (`inline`, mały znak ok. 28 px) nad pozycjami menu. Na telefonie
  dolny pasek zostaje bez logo.
- Stopka „O aplikacji” na dole Ustawień (telefon i komputer): `Logo` (`inline`) i pod spodem drobnym, przygaszonym
  tekstem „Wersja 0.1.0”. Wersja pochodzi z `web/package.json`, wstrzykiwana przez Vite (`define`).

## 5. Testy

- `Mark` i `Logo`: dostępna nazwa „Evenkeel”; układy `stacked` i `inline`.
- `StartupSplash`:
  - trzyma się co najmniej 3 s, nawet gdy sesja i podsumowanie przychodzą od razu (fałszywe zegary);
  - czeka na podsumowanie, gdy start jest na `/` i użytkownik jest zalogowany;
  - na innych ekranach i dla niezalogowanego wystarczy sesja;
  - znika też po błędzie podsumowania albo braku połączenia;
  - po zniknięciu nie ma go w drzewie;
  - przy „ogranicz ruch” nie uruchamia animacji słupków.
- Manifest: nazwa i `short_name` to „Evenkeel” (test `pwa.config.test.ts`).
- Logowanie: nagłówek „Evenkeel” (dotychczasowy test szukający „Portfel” się zmienia).
- Pasek boczny i Ustawienia: logo jest w drzewie, a stopka pokazuje „Wersja 0.1.0”.

## Podział

Jeden plan: `docs/superpowers/plans/2026-09-30-evenkeel-identity.md`, na gałęzi `feature/evenkeel-identity`.
