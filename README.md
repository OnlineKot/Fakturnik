# Fakturnik

Prosty program dla Windows do wystawiania i drukowania rachunków (lub faktur) dla gabinetu
zwolnionego z VAT (usługi medyczne, art. 43 ust. 1 pkt 19 ustawy o VAT).

## Pobranie

Gotowy plik **Fakturnik.exe** jest w zakładce *Releases* (najnowsze wydanie):
https://github.com/OnlineKot/Fakturnik/releases/latest/download/Fakturnik.exe
Python i inne programy są spakowane do środka pliku, więc nic nie trzeba instalować.
Przy pierwszym uruchomieniu Windows SmartScreen może pokazać ostrzeżenie (program nie jest
podpisany certyfikatem): „Więcej informacji” → „Uruchom mimo to”.

## Co potrafi

- **Drukowanie od razu** (F5 lub Ctrl+P) na wybranej drukarce, bez okna drukowania
  (okno można włączyć w Ustawieniach), opcjonalnie oryginał i kopia; zapis do PDF.
- **Numeracja** `nr/miesiąc/rok` (np. `3/10/2026`): program pamięta kolejny numer
  w każdym miesiącu; numer można poprawić ręcznie.
- **Ostatni pacjenci** jako przyciski oraz podpowiedzi przy wpisywaniu nazwiska.
- **Szybkie usługi**: przyciski z nazwą i ceną.
- **Historia**: wyszukiwanie, ponowny wydruk, „użyj jako wzór”, eksport do CSV (Excel).
- **Hasło i szyfrowanie**: klucz 256-bitowy z hasła (PBKDF2-HMAC-SHA256, 600 000 iteracji),
  dane szyfrowane AES-256-GCM. Automatyczna blokada po 10 minutach bezczynności,
  rosnące opóźnienie po błędnych hasłach. Zapomnianego hasła nie da się odzyskać.
- **Dziennik logowań** każdej próby podania hasła i ważnych operacji, zabezpieczony
  łańcuchem skrótów SHA-256 (wykrywa usunięcie lub zmianę wpisu).
- **Ochrona pliku danych**: gdy program działa, plik jest zablokowany przed zapisem
  i usunięciem przez inne programy; po zamknięciu ma atrybut „tylko do odczytu”, a każda
  zmiana zaszyfrowanego pliku z zewnątrz zostanie wykryta. Na Windows nie da się zrobić pliku
  całkowicie nieusuwalnym dla administratora, dlatego program robi też codzienne
  **kopie automatyczne** (ostatnie 30) w `Dokumenty\Fakturnik\kopie`.
- **Kopia zapasowa / przywracanie / eksport odszyfrowany** w Ustawieniach.
- **Aktualizacje**: program sprawdza przy uruchomieniu, czy jest nowsza wersja, i instaluje ją
  jednym kliknięciem. Pobrany plik jest sprawdzany sumą SHA-256 i pobierany tylko z GitHuba.
  **Dane nie giną przy aktualizacji**: leżą osobno od programu (w `%APPDATA%`), przed instalacją
  program robi ich kopię (`przed-aktualizacja-do-…db` w katalogu kopii), a gdy nowa wersja zmienia
  układ danych, przerabia je automatycznie, zostawiając kopię oryginału. Starsza wersja programu
  odmówi otwarcia danych z nowszej, zamiast je uszkodzić.

Dane programu: `%APPDATA%\Fakturnik\Fakturnik\fakturnik.db`, dziennik obok (`dziennik.log`).

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
