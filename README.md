# Fakturnik

Program dla Windows do tworzenia i drukowania rachunków i faktur oraz do przechowywania
wrzuconych dokumentów (faktury kosztowe, skany), dla gabinetu zwolnionego z VAT
(usługi medyczne, art. 43 ust. 1 pkt 19 ustawy o VAT).

## Pobranie i instalacja

**Instalator (zalecany):** https://github.com/OnlineKot/Fakturnik/releases/latest/download/FakturnikSetup.exe
Wymaga uprawnień administratora (Windows zapyta raz, przy instalacji) i daje najmocniejszą ochronę:
- program trafia do `Program Files`, więc zwykłe konto ani żaden program uruchomiony na nim nie może
  go zmienić ani usunąć,
- **odinstalowanie wymaga hasła Fakturnika**, a dane i kopie zostają na dysku także po odinstalowaniu,
- działa **usługa kopii** (Harmonogram zadań, konto SYSTEM): co godzinę i po każdym starcie komputera
  kopiuje dane do `C:\ProgramData\Fakturnik\kopie`, skąd można je przywrócić, ale nie da się ich
  usunąć bez uprawnień administratora; ta sama usługa instaluje aktualizacje,
- skrót w Menu Start (opcjonalnie na pulpicie) i start w tle razem z Windows.
Instalator sam usuwa poprzednią wersję zainstalowaną bez administratora; dane zostają.

**Wersja przenośna:** https://github.com/OnlineKot/Fakturnik/releases/latest/download/Fakturnik.exe

Python i inne programy są spakowane do środka pliku, więc nic więcej nie trzeba instalować.
Przy pierwszym uruchomieniu Windows SmartScreen może pokazać ostrzeżenie (program nie jest
podpisany certyfikatem): „Więcej informacji” → „Uruchom mimo to”.

### Norton i inne antywirusy

Program jest zbudowany tak, żeby nie wyglądał podejrzanie dla antywirusów: plik ma wpisanego
wydawcę i wersję, nie jest kompresowany UPX-em, nie instaluje sterowników ani haków klawiatury,
nie uruchamia skryptów przy aktualizacji, a zmiany w rejestrze dotyczą tylko bieżącego
użytkownika. Mimo to nowe, niepodpisane programy bywają przez Nortona oznaczane z ostrożności
(„mała liczba użytkowników”). Wtedy:
1. Norton → Bezpieczeństwo → Historia → wybierz Fakturnik → **Przywróć i wyklucz ten plik**,
   albo Ustawienia → Antywirus → Skanowania i zagrożenia → **Elementy do wykluczenia** →
   dodaj folder `%LOCALAPPDATA%\Programs\Fakturnik`.
2. Zgłoś fałszywy alarm na https://submit.norton.com (Norton zwykle zdejmuje oznaczenie w ciągu
   kilku dni, co pomaga wszystkim użytkownikom).

Ostrzeżenia znikają całkowicie dopiero po podpisaniu programu certyfikatem Code Signing
(płatny, np. Certum, albo darmowy dla otwartych projektów przez SignPath).

## Co potrafi

- **Ustawienia wydruku w programie** przed każdym drukiem (F5 lub Ctrl+P): drukarka, liczba
  egzemplarzy, oryginał i kopia, data wydruku, PESEL oraz opcje sterownika drukarki
  (np. dwustronnie). Okno można wyłączyć w Ustawieniach, wtedy drukuje od razu. Zapis do PDF.
- **Numeracja** `nr/miesiąc/rok` (np. `3/10/2026`): program pamięta kolejny numer
  w każdym miesiącu; numer można poprawić ręcznie.
- **Podpowiedzi nazwisk** dopiero po wpisaniu 2 liter (bez listy „ostatnio”, żeby nikt przy biurku
  nie zobaczył nazwisk innych pacjentów).
- **Szybkie usługi**: przyciski z nazwą i ceną.
- **Rachunek albo faktura**: przełącznik przy każdym nowym dokumencie. Faktury mają osobną
  numerację `FV/nr/miesiąc/rok` (format do zmiany w Ustawieniach).
- **Kompletne faktury** (art. 106e ustawy o VAT): data wystawienia i wykonania usługi, kolejny numer,
  dane i NIP sprzedawcy i nabywcy, nazwa usługi, jednostka miary, ilość, cena jednostkowa, wartość,
  zestawienie według stawki (zw, VAT 0,00), kwota do zapłaty (też słownie), podstawa zwolnienia z VAT,
  sposób płatności i termin przelewu (liczba dni w Ustawieniach) z numerem konta. Program nie wystawi
  faktury, jeśli brakuje obowiązkowych danych (np. NIP gabinetu albo adresu nabywcy), i powie, czego brakuje.
- **Faktura korygująca** (art. 106j): w Historii zaznacz fakturę → „Korekta”, popraw pozycje i podaj
  przyczynę. Wydruk zawiera numer i datę korygowanej faktury, przyczynę, pozycje przed i po korekcie
  oraz kwotę do zwrotu lub dopłaty. Korekty mają własną numerację `KOR/nr/miesiąc/rok`, a sumy
  przychodów uwzględniają różnicę.
- **Pliki**: wrzucanie PDF-ów i zdjęć (przycisk albo przeciągnięcie na okno) z datą, rodzajem
  (faktura kosztowa, dokument pacjenta…), pacjentem lub kontrahentem i opisem; wyszukiwanie po
  roku, miesiącu, rodzaju i nazwisku; podgląd, drukowanie, zapis kopii. Pliki są przechowywane
  zaszyfrowane (AES-256), a podmiana pliku poza programem jest wykrywana.
- **Kartoteka pacjentów**: program pamięta pacjentów (także dodanych ręcznie, bez dokumentu);
  okno „Wybierz…” pozwala wyszukać, dodawać, poprawiać
  i usuwać pacjentów (usuwanie z hasłem; wystawione dokumenty zostają bez zmian).
- **Edycja rachunków i faktur**: numer zostaje, każda poprzednia wersja trafia do historii zmian
  (z opisem, co poprawiono), a podgląd pokazuje datę poprawki. Edycja wymaga hasła.
- **Własny podgląd dokumentu**: strony A4, powiększanie (Ctrl +/–), druk, PDF i edycja.
- **Automatyczna blokada** po dowolnej liczbie minut bezczynności (1–240, do ustawienia w Ustawieniach).
- **Tylko szybkie wyszukiwanie**: Historia, Pliki i lista pacjentów nie pokazują niczego, dopóki nie
  wpiszesz nazwiska, numeru lub PESEL; pełną listę pokazuje „Pokaż wszystko” po podaniu hasła.
- **Wybór pacjenta** z listy wszystkich pacjentów (przycisk „Wybierz…” lub F2), alfabetycznie
  po nazwisku, z wyszukiwaniem po nazwisku, imieniu lub PESEL; dane pacjenta wpisują się same.
- **Sprawdzanie numerów**: PESEL i NIP nabywcy oraz NIP i numer konta gabinetu są sprawdzane
  sumą kontrolną, więc literówka nie trafi na dokument.
- **Cennik usług** edytowany w tabeli (dodawanie, usuwanie, kolejność).
- **Przychody na osobnej karcie**, domyślnie zasłonięte (pacjent przy biurku nie widzi zarobków):
  kwoty, wykres 12 miesięcy i ostatnie dokumenty pokazują się po kliknięciu i haśle,
  a po wyjściu z zakładki znów się chowają.
- **Dwa tryby wystawiania**: prowadzący (krok po kroku: pacjent, usługi, sprawdź i drukuj)
  i zaawansowany (wszystko w jednym oknie); przełącznik jest zawsze widoczny nad formularzem.
- **Kreator pierwszego uruchomienia**: dane gabinetu (ze sprawdzaniem NIP i konta), hasło
  (obowiązkowe, ze wskaźnikiem siły), cennik, tryb pracy i integracja z Windows.
  Program startuje bez żadnych wpisanych danych.
- **Działanie w tle**: ikona obok zegara, zamknięcie okna chowa program, start razem z Windows,
  jedna działająca kopia (kolejne uruchomienie otwiera okno). Wyłączenie programu wymaga hasła.
- **Ochrona przed przejęciem**: okna programu (także okno hasła) są niewidoczne dla zrzutów
  i nagrań ekranu innych programów, np. narzędzi AI „sterujących komputerem” i programów zdalnego
  dostępu (można wyłączyć w Ustawieniach, np. na czas zdalnej pomocy). Program nie ma żadnego
  zdalnego dostępu ani interfejsu dla innych aplikacji; jedyne polecenia z zewnątrz to „pokaż okno”
  i „dodaj plik” (sprawdzane), a każda ważna operacja wymaga hasła. Uwaga: program działający
  z uprawnieniami administratora może zawsze więcej niż zwykła aplikacja, dlatego hasło i
  szyfrowanie są tu najważniejszą ochroną.
- **Windows**: po restarcie komputera przez aktualizację Windows program wraca sam (w tle),
  przy wyłączaniu komputera zamyka się poprawnie (zapis i kopia danych), ma własną ikonę na
  pasku zadań i w powiadomieniach.
- **Menu prawego przycisku**: „Dodaj do Fakturnika” przy plikach PDF i zdjęciach w Eksploratorze.
- **Strażnik integralności** (co minutę): wykrywa zmieniony lub usunięty plik danych i odtwarza go
  z aktualnych danych programu, przywraca usunięte pliki z kopii, sprawdza dziennik logowań.
- **Hasło chroni**: ustawienia (zablokowane do odblokowania), przychody, usuwanie plików,
  anulowanie dokumentów, przywracanie kopii, eksport odszyfrowany i wyłączenie programu.
- **Podgląd wydruku na żywo** przy wystawianiu dokumentu. Skróty: Ctrl+N nowy dokument,
  F5 / Ctrl+P drukuj, F2 wybór pacjenta.
- **Historia** z wyszukiwaniem po nazwisku, imieniu, numerze lub PESEL (bez względu na polskie
  znaki) i filtrami **rok** i **miesiąc**; podsumowanie wyników z podziałem na gotówkę, kartę i przelew.
- **Zestawienie wyników** (np. za miesiąc, dla księgowej): drukowanie, zapis do PDF i do Excela (CSV).
- **Kod QR do przelewu** na fakturach i rachunkach płatnych przelewem (rekomendacja Związku Banków
  Polskich): nabywca skanuje go aplikacją banku, a numer konta, kwota, odbiorca i tytuł wpisują się same.
- **Zamknięcie dnia** (Historia albo menu ikony obok zegara): raport dzisiejszego utargu z podziałem
  na gotówkę, kartę i przelew, z listą dokumentów i miejscem na przeliczoną gotówkę z kasy.
- **Duplikat**: ponowny wydruk jest oznaczony „duplikat z dnia …”.
- **Data wydruku i wygenerowania** na dokumentach i zestawieniach: każdą można włączyć lub wyłączyć
  w Ustawieniach → Drukowanie.
- **Anulowanie dokumentu** z powodem: dokument zostaje w historii (przekreślony, z adnotacją
  na wydruku), nie liczy się do sum, a jego numer nie jest używany ponownie.
- „Użyj jako wzór”: nowy dokument na podstawie starego.
- **Hasło i szyfrowanie**: klucz z hasła przez Argon2id (128 MiB pamięci na próbę, zalecenie RFC 9106),
  dane szyfrowane podwójnie: AES-256-GCM, a na nim ChaCha20-Poly1305 (dwa niezależne klucze).
  Pliki ze starszych wersji przechodzą na nowe szyfrowanie przy pierwszym otwarciu hasłem. Automatyczna blokada po ustawionym czasie bezczynności,
  rosnące opóźnienie po błędnych hasłach. Zapomnianego hasła nie da się odzyskać.
- **Trzy niezależne kopie, robione cały czas**:
  1. `Dokumenty\Fakturnik\kopie`: co 10 minut, gdy dane się zmieniły, i przy zamknięciu (30 dni),
  2. `C:\ProgramData\Fakturnik\kopie`: usługa systemowa co godzinę i po starcie komputera, chronione
     przed usunięciem; zostają wszystkie z ostatnich 7 dni, potem jedna dziennie przez rok i jedna
     miesięcznie bez końca,
  3. wybrany folder: pendrive, dysk sieciowy albo OneDrive (Ustawienia → Kopie zapasowe), co 10 minut.
  Kopie są zaszyfrowane tak samo jak dane (gdy ustawiono hasło). Stan wszystkich trzech widać
  w Ustawieniach.
- **Weryfikacja urządzenia** (Ustawienia → Komputer i urządzenie): dane i ich kopie otwierają się tylko
  na tym komputerze i tym koncie Windows. Klucz szyfrujący powstaje z hasła i sekretu urządzenia
  chronionego przez Windows (DPAPI), więc skradziony plik lub kopia nie otworzą się gdzie indziej nawet
  ze znanym hasłem. Na nowym komputerze potrzebny jest **kod odzyskiwania** (pokazywany przy włączaniu,
  do zapisania lub wydrukowania).
- **Migracja na nowy komputer**: „Przenieś na inny komputer” tworzy pakiet migracji (.fkopia z osobnym
  hasłem: wszystkie dokumenty, ustawienia i wrzucone pliki). Na nowym komputerze kreator ma przycisk
  „Przenieś dane z innego komputera”.
- **Stan bezpieczeństwa komputera**: Ustawienia pokazują, czy włączony jest Secure Boot, czy program
  zainstalowano z uprawnieniami administratora (z przyciskiem, który pobiera i uruchamia instalator)
  i czy codzienna praca odbywa się na zwykłym koncie Windows (zalecane). Przy wyłączonym Secure Boot
  program raz o tym przypomina. Sam program celowo działa bez uprawnień administratora: instalator
  i usługa kopii je mają, a codzienna praca z najmniejszymi uprawnieniami jest bezpieczniejsza
  (Windows nie pozwala też na autostart programów wymagających administratora).
- **Kontrola komputera przy każdym uruchomieniu** (także przy starcie Windows, gdy program startuje w tle):
  hasło i szyfrowanie, oryginalność pliku programu (SHA-256 z wydania, sprawdzana też przez usługę
  przy starcie komputera i co godzinę), Secure Boot, instalacja z uprawnieniami administratora, praca
  usługi kopii, świeżość kopii, nienaruszony dziennik, weryfikacja urządzenia i rodzaj konta Windows.
  Wynik trafia do dziennika i do powiadomienia; szczegóły w oknie „Kontrola komputera” (Ustawienia
  albo menu ikony obok zegara). Ostrzeżenie można zignorować i przywrócić (pojedynczo lub wszystkie),
  a po sprawdzeniu naruszonego dziennika zacząć nowy (stary zostaje do wglądu).
- **Program nigdy nie podmienia się sam**: aktualizacje instaluje usługa systemowa (instalacja
  administratora) albo instalator po zgodzie administratora (okienko Windows), po sprawdzeniu SHA-256.
- **Własne powiadomienia** w rogu ekranu (także gdy okno jest schowane), w stylu programu; kliknięcie
  otwiera szczegóły (np. kontrolę komputera albo aktualizację).
- **Dziennik blokowania komputera**: blokada, odblokowanie, logowanie i wylogowanie Windows oraz
  połączenia zdalne trafiają do dziennika Fakturnika. Gdy komputer się blokuje, Fakturnik też.
  Nieudane próby odblokowania lub logowania do Windows (z dziennika zabezpieczeń, gdy program ma do
  niego dostęp) są zapisywane i zgłaszane powiadomieniem; połączenie zdalne zgłaszane od razu.
- **Bezpieczna przeglądarka** (karta „Internet”, osobny plik FakturnikPrzegladarka.exe instalowany
  instalatorem, dzięki czemu główny program jest mały i szybko startuje): zakładki KSeF, e-Urząd Skarbowy, biała lista VAT,
  CEIDG, REGON i ZUS oraz dowolny adres (np. bank). Działa w osobnym, odizolowanym procesie (strony nie
  mają dostępu do danych pacjentów), w sesji bez zapisu na dysku, tylko przez HTTPS, z odrzucaniem
  błędnych certyfikatów i zablokowaną kamerą, mikrofonem i lokalizacją. Plików wykonywalnych nie da się
  pobrać, a pobrane pliki są oznaczone jako pochodzące z internetu (sprawdza je antywirus); pobrany PDF
  jednym kliknięciem trafia do zaszyfrowanych Plików. Blokada Fakturnika zamyka przeglądarkę i kończy
  sesję. Opcjonalnie tylko zaufane strony (gov.pl, zakładki i dopisane domeny).
- **Konta asystentek**: każda loguje się własnym hasłem (bez nazwy użytkownika). Asystentka wystawia
  dokumenty, szuka w historii, drukuje i dodaje pliki; przychody i ustawienia są dla niej ukryte,
  a eksporty, anulowanie, edycja i korekty wymagają hasła właściciela. Każdy dokument zapamiętuje,
  kto go wystawił (kolumna w Historii, opcjonalnie na wydruku), a dziennik, kto co zrobił. Dane zostają
  zaszyfrowane: konto ma własny klucz, a usunięcie konta odbiera dostęp od razu.
- **Godziny pracy** (domyślnie wt 12–18, śr 10–17, czw 12–18, pt 8–14; do zmiany w Ustawieniach):
  przypomnienie przed końcem (z szybkim zamknięciem dnia), po godzinach wylogowanie asystentek
  (opcjonalnie wszystkich), a ponowne zalogowanie asystentki po godzinach tylko za zgodą właściciela.
  Ekran blokady pokazuje zegar, gabinet i najbliższe godziny pracy.
- **Zamykam gabinet** (przycisk w menu, w menu ikony obok zegara i w przypomnieniu o końcu godzin):
  podsumowanie dnia (dokumenty, gotówka, karta, przelew), opcjonalna kartka podsumowująca do druku,
  kopia zapasowa od razu, zamknięcie przeglądarki i wylogowanie.
- **Narzędzia**: stoper, minutnik (szybkie 1–15 min, powiadomienie i dźwięk po czasie), kalkulator
- **Zasłona ekranu z żabką**: po ustawionym czasie bezczynności całego komputera (domyślnie 2 min, od 5 s do godziny; do wyłączenia w Ustawieniach → Bezpieczeństwo) wszystkie monitory zasłania pełnoekranowy obraz z żabką, zegarem i datą, bez żadnych napisów. Znika po trzech naciśnięciach spacji. Nie czyści schowka i nie wylogowuje; blokada hasłem działa niezależnie. Można ją też włączyć od razu z menu ikony przy zegarze („Zasłoń ekran”).
- **Narzędzia jako kafelki**: każde narzędzie otwiera się na osobnym ekranie (powrót strzałką albo Esc).
- **Notatki GTD**: Skrzynka, Dziś, Następne działania, Czekam na, Kiedyś/może, Zrobione i swobodny Notatnik. Szybkie dodawanie w jednej linii: „Zadzwonić do laboratorium @telefon jutro !” ustawia kontekst, termin (dziś, jutro, dzień tygodnia, 15.10) i ważność. Filtr kontekstów, przenoszenie między listami, przypomnienie z zadania; zaszyfrowane razem z danymi.
- **Więcej narzędzi**: przypomnienia z godziną (np. „14:30” albo „+15” = za 15 minut; powiadomienie i dźwięk), liczenie kasy według nominałów z porównaniem do dzisiejszej gotówki z dokumentów, kalkulator dat (np. kontrola za 6 miesięcy, dni robocze do terminu), rabat i raty, generator haseł (schowek czyści się po ustawionym czasie, domyślnie 30 s, z odliczaniem; także przy blokadzie i wyłączeniu programu), a PESEL pokazuje datę urodzenia, wiek i płeć
  (tylko działania, bez wykonywania kodu), dane firmy po NIP z oficjalnej białej listy VAT (Ministerstwo Finansów) z przyciskiem
  „Wystaw fakturę dla tej firmy” (także w formularzu faktury), sprawdzanie PESEL/NIP/numeru konta,
  kwota słownie i wspólny, zaszyfrowany notatnik gabinetu.
- **Powiadomienia do ustawienia**: czas wyświetlania, dźwięk, powiadomienie startowe, blokada razem
  z komputerem.
- **Tapeta pulpitu** (Ustawienia → Tapeta pulpitu): trzy warianty w kolorach Fakturnika z nazwą
  gabinetu, rysowane w rozdzielczości ekranu; polecana „Turkus nocą”. Poprzednią tapetę można przywrócić.
- **Odporność na awarie**: dane zapisują się po każdej zmianie (atomowo), a plik jest sprawdzany przy
  każdym otwarciu. Gdy okaże się uszkodzony (np. awaria dysku lub prądu), program sam znajdzie
  najnowszą działającą kopię automatyczną i zaproponuje jej przywrócenie, a uszkodzony plik zostawi
  obok. Nieoczekiwany błąd nie zamyka programu: pojawia się komunikat, a szczegóły trafiają do
  `bledy.log` obok danych.
- **Dziennik logowań** każdej próby podania hasła i ważnych operacji (bez nazwisk i nazw plików),
  zabezpieczony łańcuchem skrótów SHA-256; skrót ostatniego wpisu jest też zapisany w zaszyfrowanej
  bazie, więc wykrywane jest również ucięcie końcówki dziennika.
- **Ochrona programu**: działający Fakturnik.exe jest zablokowany przed zmianą, a przy uruchomieniu
  program porównuje się z sumą SHA-256 opublikowaną przy swoim wydaniu i ostrzega, jeśli plik
  został podmieniony. Pełną gwarancję daje dopiero podpis cyfrowy (certyfikat Code Signing).
- **RODO**: szyfrowanie danych, minimalizacja (PESEL domyślnie nie jest drukowany na rachunku,
  podgląd PESEL maskowany), dane osobowe widoczne tylko po wyszukaniu, dziennik bez nazwisk.
  W Ustawieniach → RODO ustawiasz okres przechowywania (domyślnie 5 lat po roku wystawienia)
  i jednym przyciskiem (z hasłem) usuwasz dane osobowe ze starszych dokumentów: numery i kwoty
  zostają. W oknie Pacjenci „Dane osoby” tworzy PDF z informacją o przetwarzaniu i listą dokumentów
  pacjenta (prawo dostępu, art. 15). Eksport CSV jest zabezpieczony przed formułami Excela.
- **Ochrona pliku danych**: gdy program działa, plik jest zablokowany przed zapisem
  i usunięciem przez inne programy; po zamknięciu ma atrybut „tylko do odczytu”, a każda
  zmiana zaszyfrowanego pliku z zewnątrz zostanie wykryta. Na Windows nie da się zrobić pliku
  całkowicie nieusuwalnym dla administratora, dlatego program robi też codzienne
  **kopie automatyczne** w trzech miejscach (patrz wyżej).
- **Szyfrowana kopia zapasowa** (`.fkopia`): jeden plik z danymi i wrzuconymi plikami, zaszyfrowany
  podwójnie (AES-256-GCM i ChaCha20-Poly1305, klucz Argon2id) osobnym hasłem kopii (można ją bezpiecznie trzymać na pendrive lub w chmurze).
  Przywracanie przyjmuje `.fkopia`, `.zip` i `.db`; kopie automatyczne plików trafiają do `Dokumenty\Fakturnik\kopie\pliki`.
- **Automatyczne aktualizacje**: program sprawdza nowe wersje przy starcie i co 6 godzin. W instalacji
  z uprawnieniami administratora usługa sama pobiera nową wersję, sprawdza SHA-256 (tylko z GitHuba)
  i ją instaluje, a program uruchamia się ponownie, gdy okno jest schowane. W instalacji bez
  uprawnień administratora (lub wersji przenośnej) program tylko informuje o nowej wersji i instaluje
  ją instalatorem po zgodzie administratora.
  **Dane nie giną przy aktualizacji**: leżą osobno od programu (w `%APPDATA%`), przed instalacją
  program robi ich kopię (`przed-aktualizacja-do-…db` w katalogu kopii), a gdy nowa wersja zmienia
  układ danych, przerabia je automatycznie, zostawiając kopię oryginału. Starsza wersja programu
  odmówi otwarcia danych z nowszej, zamiast je uszkodzić.

Dane programu: `%APPDATA%\Fakturnik\Fakturnik\fakturnik.db`, dziennik obok (`dziennik.log`).

## Audyt bezpieczeństwa (wersja 1.0.24)

Poprawione:
- Rola i nazwa konta asystentki są brane z zaszyfrowanych danych, nie z pliku `konta.json`. Edycja tego pliku nie da już roli właściciela.
- Gdy dane były zaszyfrowane, plik bez szyfrowania podłożony w ich miejsce nie zostanie otwarty. Program proponuje przywrócenie ostatniej zaszyfrowanej kopii. Kopia bez szyfrowania nie zastąpi też zaszyfrowanych danych przy odtwarzaniu.
- Usługa kopii (konto SYSTEM) nie idzie za dowiązaniami ani junctionami, kopiuje tylko pliki Fakturnika i ma limit rozmiaru pliku.
- Kopie chronione każdego użytkownika może czytać tylko on sam (oraz SYSTEM i Administratorzy).
- Instalator przejmuje katalog `ProgramData\Fakturnik` na Administratorów, nawet jeśli wcześniej założył go ktoś inny. Starą wersję odinstalowuje bez uprawnień administratora.
- Przeglądarka pobiera tylko dozwolone typy plików: PDF, obrazy, XML, ZIP, dokumenty bez makr. Strony `http://` zawsze przechodzą na `https://`.
- Dziennik nie zapisuje nazw plików, które mogą zawierać nazwiska pacjentów.
- Program ignoruje zmienne środowiskowe wskazujące obce wtyczki Qt.

Znane ograniczenia (do zrobienia w przyszłości):
- Pliki programu nie mają jeszcze podpisu cyfrowego (certyfikat Authenticode). Aktualizacja sprawdza sumę SHA-256 z wydania, ale nie podpis.
- Asystentka zna klucz danych, więc po usunięciu jej konta warto zmienić hasło właściciela. Pełne unieważnienie dostępu wymaga przebudowy szyfrowania kont.
- Odinstalowanie wymaga hasła Fakturnika także z konta administratora i także po usunięciu pliku programu
  (zapasowa kopia w `ProgramData\Fakturnik\program`). Administrator może jednak ręcznie skasować pliki
  z dysku — tego żaden program nie zablokuje. Dane i kopie zostają wtedy nietknięte i zaszyfrowane.

## Uwaga o KSeF

Program drukuje dokumenty papierowe i nie wysyła ich do Krajowego Systemu e-Faktur.
Czy w danej sytuacji wystarczy rachunek, czy potrzebna jest faktura w KSeF, warto
potwierdzić z księgową.

## Wygląd

Czcionka: [Inter](https://rsms.me/inter/) (licencja SIL OFL, dołączona w `fakturnik/zasoby/czcionki`),
najbliższy darmowy odpowiednik systemowej czcionki Apple (SF Pro, której licencja nie pozwala na
użycie poza urządzeniami Apple). Ikony liniowe w stylu [Lucide](https://lucide.dev) (licencja ISC).

## Test na Macu (bez Windowsa)

Zainstaluj Pythona 3.12 z python.org, pobierz kod (Code → Download ZIP) i w Terminalu:

```
cd <rozpakowany katalog>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Na Macu działa wszystko oprócz blokady pliku i podmiany .exe przy aktualizacji (to tylko Windows).

## Dla programisty

```
pip install -r requirements.txt pytest
python -m pytest
python main.py
```

Plik `.exe` buduje GitHub Actions (`.github/workflows/build.yml`) przy każdym pushu i publikuje
wydanie `v1.0.<numer budowania>` z plikiem `Fakturnik.exe.sha256`. Zmiana tabel w bazie: dopisz
kolejny wpis w `MIGRACJE` w `fakturnik/baza.py` (nigdy nie zmieniaj istniejących).
