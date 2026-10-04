# Plan 8d — Ustawienia: sesje i urządzenia, usunięcie konta (decyzje projektowe)

**Data:** 2026-10-04
**Część:** 8d z Ustawień (8a–8c zrobione).

## Decyzje właściciela (2026-10-04)

1. **Zmiany e-maila nie robimy.** Wymagałaby linku potwierdzającego, a aplikacja nie wysyła e-maili. Wraca razem z
   wysyłką e-maili (roadmapa, „na później”).
2. **Sesje jako lista:** urządzenie i przeglądarka, kiedy zalogowano, kiedy ostatnio użyto, „Wyloguj” przy każdej
   innej sesji, „Wyloguj wszystkie inne”; bieżąca oznaczona „To urządzenie”.
3. **Usunięcie konta:** hasło + wpisanie „USUŃ KONTO”, nad formularzem przypomnienie z „Pobierz kopię” (8c); po
   usunięciu ekran logowania z „Konto zostało usunięte.”
4. Właściciel zatwierdził projekt w rozmowie i poprosił o spec, plan i wykonanie bez kolejnych pytań.

## 1. Ekrany

- **Profil** (`/ustawienia/profil`): e-mail, „Zmień hasło”, nowe linki **„Sesje i urządzenia”** i **„Usuń konto”**,
  „Wyloguj”.
- **Sesje i urządzenia** (`/ustawienia/sesje`): lista aktywnych sesji, bieżąca pierwsza, potem od ostatnio
  używanej. Wiersz: opis urządzenia („iPhone · Safari”), „Zalogowano 2 paź 2026 · ostatnio 4 paź, 14:30”;
  bieżąca ma znacznik „To urządzenie” i nie ma przycisku; inne mają „Wyloguj”. Pod listą „Wyloguj wszystkie inne”
  (gdy są inne). Dopisek: „Wylogowane urządzenie traci dostęp najpóźniej po 15 minutach.”
- **Usuń konto** (`/ustawienia/usun-konto`): „Usunięcie skasuje Twoje konto i wszystkie dane: konta, operacje,
  obligacje, oszczędności, tagi, notatki, scenariusze i przeglądy. Tego nie da się cofnąć.”, przycisk
  „Pobierz kopię” (ten sam co w 8c), pola „Hasło” i „Wpisz USUŃ KONTO”, czerwony „Usuń konto” aktywny po frazie
  i niepustym haśle. Sukces → `/logowanie` z komunikatem „Konto zostało usunięte.”.
- Rejestr: „Sesje i urządzenia” (grupa Konto, rodzic Profil; słowa: sesje urządzenia wyloguj telefon komputer
  przeglądarka) i „Usuń konto” (Konto, rodzic Profil; słowa: usuń skasuj konto dane zamknij).
- **Opis urządzenia** liczy przeglądarka z user-agenta (`describeDevice`): system — iPhone, iPad, Android, Windows,
  Mac, Linux; przeglądarka — Edge, Firefox, Chrome, Safari (w tej kolejności sprawdzania); np. „Android · Chrome”;
  brak user-agenta → „Nieznane urządzenie”; nic nie rozpoznane → „Przeglądarka”.

## 2. Sesje (API)

- **Migracja 0017** — `refresh_tokens`: `session_id` UUID NOT NULL (istniejące wiersze: `gen_random_uuid()`, każdy
  osobna sesja), `user_agent` VARCHAR(300) NULL, `session_started_at` TIMESTAMPTZ NOT NULL (istniejące:
  `created_at`); indeks na `session_id`.
- **Logowanie i rejestracja** zakładają nową sesję: nowy `session_id`, `user_agent` z nagłówka (obcięty do 300),
  `session_started_at = now`. **Odświeżenie** przenosi `session_id`, `user_agent` i `session_started_at` z
  zajętego klucza na nowy. Zmiana hasła — bez zmian (kończy inne sesje).
- **Aktywna sesja** = ma klucz niewycofany i niewygasły. „Ostatnio” = `created_at` tego klucza (klucz wymienia się
  przy każdym odświeżeniu, co najwyżej co 15 minut aktywności).
- `GET /api/auth/sessions` → `[{id, user_agent, started_at, last_used_at, current}]` (bieżąca = klucz z ciasteczka
  tej prośby).
- `DELETE /api/auth/sessions/{id}` → wycofuje klucze tej sesji użytkownika; cudza lub nieznana → 404; bieżąca →
  400 „To jest ta sesja — użyj Wyloguj.”.
- `POST /api/auth/sessions/revoke-others` → wycofuje klucze wszystkich sesji użytkownika poza bieżącą; 204.

## 3. Usunięcie konta (API)

- `DELETE /api/auth/account` z `{password, confirm}`: limit prób jak przy logowaniu (429); `confirm` ≠
  „USUŃ KONTO” → 422 „Wpisz USUŃ KONTO, żeby usunąć konto.”; złe hasło → 400 „Hasło jest nieprawidłowe.”;
  sukces → usunięcie użytkownika (baza kasuje kaskadą konta i ich wiersze, tagi, notatki, scenariusze, przeglądy,
  ręczne korekty, klucze sesji, wyceny), wyczyszczenie ciasteczka, 204. Wspólne instrumenty, serie, ceny zostają.
- Test pilnuje, że po usunięciu nie zostaje żaden wiersz z `user_id` tego użytkownika ani konta, a drugi
  użytkownik jest nietknięty.

## 4. Testy

- API: numer sesji przetrwa odświeżenie; lista tylko własnych aktywnych sesji z `current`; wylogowanie jednej
  (jej odświeżenie potem 401), wszystkich innych (bieżąca działa dalej); cudza sesja 404; bieżąca 400; usunięcie
  konta (dane znikają, drugi użytkownik zostaje); złe hasło / fraza nic nie usuwa; migracja (stare klucze mają
  numer i początek).
- Web: `describeDevice` dla typowych user-agentów; lista z „To urządzenie”, „Wyloguj” i „Wyloguj wszystkie inne”;
  usunięcie konta: przycisk aktywny po frazie, sukces → logowanie z komunikatem, błąd hasła widoczny; wyszukiwanie.
- e2e: drugi kontekst przeglądarki loguje się tym samym kontem, pierwszy wylogowuje go z listy, drugi po
  odświeżeniu ląduje na logowaniu; na koniec usunięcie konta i próba zalogowania kończy się błędem.

## Poza zakresem

- Zmiana e-maila i wysyłka e-maili.
- Adres IP i miejsce logowania przy sesji.
