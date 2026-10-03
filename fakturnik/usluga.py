"""Usługa kopii i aktualizacji: uruchamiana przez Harmonogram zadań Windows z kontem SYSTEM.

    Fakturnik.exe --usluga

Co godzinę (i po starcie komputera) kopiuje dane Fakturnika każdego użytkownika komputera do
C:\\ProgramData\\Fakturnik\\kopie\\<użytkownik>. Ten katalog ma uprawnienia ustawione przez instalator:
zwykły użytkownik (i każdy program działający na jego koncie) może kopie czytać i przywracać,
ale nie może ich zmienić ani usunąć. Kopiowany jest plik danych w postaci z dysku (zaszyfrowany,
gdy ustawiono hasło), wrzucone pliki (też zaszyfrowane) i dziennik.

Usługa instaluje też aktualizacje programu (Program Files może zmieniać tylko administrator/SYSTEM).

Moduł nie używa Qt: działa bez okien, w tle, także zanim ktokolwiek się zaloguje.
"""

import hashlib
import os
import shutil
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

NAZWA_DANYCH = Path("AppData") / "Roaming" / "Fakturnik" / "Fakturnik"
PLIK_DANYCH = "fakturnik.db"


def katalog_uslugi() -> Path:
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Fakturnik"


def katalog_kopii_chronionych() -> Path:
    return katalog_uslugi() / "kopie"


def katalog_profili() -> Path:
    """C:\\Users (katalog nadrzędny profilu publicznego)."""
    return Path(os.environ.get("PUBLIC", r"C:\Users\Public")).parent


def profile_z_danymi(katalog: Path | None = None) -> list[tuple[str, Path]]:
    """(nazwa użytkownika, katalog danych Fakturnika) dla każdego profilu, który ma dane."""
    katalog = katalog or katalog_profili()
    wynik = []
    try:
        profile = sorted(katalog.iterdir())
    except OSError:
        return []
    for profil in profile:
        dane = profil / NAZWA_DANYCH
        try:
            if (dane / PLIK_DANYCH).is_file():
                wynik.append((profil.name, dane))
        except OSError:
            continue
    return wynik


def _skrot(sciezka: Path) -> str:
    h = hashlib.sha256()
    with open(sciezka, "rb") as f:
        while blok := f.read(1024 * 1024):
            h.update(blok)
    return h.hexdigest()


def kopia_uzytkownika(dane: Path, cel: Path, teraz: datetime | None = None) -> bool:
    """Kopia danych jednego użytkownika. Zwraca True, gdy powstała nowa kopia pliku danych
    (gdy nic się nie zmieniło od ostatniej, nowej nie robi)."""
    teraz = teraz or datetime.now()
    cel.mkdir(parents=True, exist_ok=True)
    nowa = False
    plik = dane / PLIK_DANYCH
    skrot = _skrot(plik)
    znacznik = cel / "ostatnia.sha256"
    if not znacznik.exists() or znacznik.read_text().strip() != skrot:
        docelowy = cel / f"fakturnik-{teraz:%Y-%m-%d-%H%M}.db"
        tymczasowy = docelowy.with_suffix(".tmp")
        shutil.copyfile(plik, tymczasowy)
        if _skrot(tymczasowy) != skrot:  # plik zmienił się w trakcie kopiowania: spróbujemy za godzinę
            tymczasowy.unlink(missing_ok=True)
        else:
            os.replace(tymczasowy, docelowy)
            znacznik.write_text(skrot)
            nowa = True
    pliki = dane / "pliki"
    if pliki.is_dir():
        (cel / "pliki").mkdir(exist_ok=True)
        for zrodlo in pliki.glob("*.bin"):  # wrzucone pliki nigdy się nie zmieniają, wystarczy dołożyć nowe
            docelowy = cel / "pliki" / zrodlo.name
            if not docelowy.exists():
                shutil.copyfile(zrodlo, docelowy)
    dziennik = dane / "dziennik.log"
    if dziennik.is_file():
        shutil.copyfile(dziennik, cel / "dziennik.log")
    (cel / "ostatnia-kopia.txt").write_text(f"{teraz:%Y-%m-%d %H:%M}")
    rotacja(cel, teraz)
    return nowa


def rotacja(cel: Path, teraz: datetime | None = None) -> list[Path]:
    """Ile kopii zostaje: wszystkie z ostatnich 7 dni, potem jedna dziennie przez rok, a starsze
    po jednej na miesiąc (bez końca). Najnowsza kopia nigdy nie jest usuwana. Zwraca usunięte."""
    teraz = teraz or datetime.now()
    kopie = []
    for k in cel.glob("fakturnik-*.db"):
        try:
            kopie.append((datetime.strptime(k.stem[len("fakturnik-"):], "%Y-%m-%d-%H%M"), k))
        except ValueError:
            continue
    kopie.sort(reverse=True)
    zostaja, usuniete = set(), []
    for i, (kiedy, k) in enumerate(kopie):
        wiek = teraz - kiedy
        if i == 0 or wiek <= timedelta(days=7):
            klucz = k.name
        elif wiek <= timedelta(days=365):
            klucz = f"dzien-{kiedy:%Y-%m-%d}"
        else:
            klucz = f"miesiac-{kiedy:%Y-%m}"
        if klucz in zostaja:
            k.unlink()
            usuniete.append(k)
        else:
            zostaja.add(klucz)
    return usuniete


def ostatnia_kopia_chroniona(uzytkownik: str | None = None) -> str | None:
    """Czas ostatniej kopii usługi dla użytkownika (do pokazania w Ustawieniach) albo None."""
    uzytkownik = uzytkownik or os.environ.get("USERNAME") or os.environ.get("USER") or ""
    plik = katalog_kopii_chronionych() / uzytkownik / "ostatnia-kopia.txt"
    try:
        return plik.read_text().strip() or None
    except OSError:
        return None


def _zapisz_log(tekst: str) -> None:
    log = katalog_uslugi() / "usluga.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.exists() and log.stat().st_size > 512 * 1024:
            os.replace(log, log.with_suffix(".old.log"))
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {tekst}\n")
    except OSError:
        pass


def aktualizuj_program() -> str:
    """Instaluje nowszą wersję z GitHuba (sprawdzoną SHA-256). Działający u użytkownika program
    zauważy nowy plik i uruchomi się ponownie, gdy okno będzie schowane."""
    from . import aktualizacje
    if not aktualizacje.czy_spakowany():
        return "pominięto (wersja ze źródeł)"
    exe = Path(sys.executable)
    aktualizacje.posprzataj(exe)
    wydanie = aktualizacje.sprawdz()
    if not wydanie:
        return "program aktualny"
    nowy = aktualizacje.pobierz(wydanie, exe.with_name("Fakturnik.new.exe"))
    aktualizacje.zainstaluj(nowy, exe)
    return f"zainstalowano wersję {wydanie.wersja}"


def uruchom_usluge() -> int:
    profile = profile_z_danymi()
    for uzytkownik, dane in profile:
        try:
            nowa = kopia_uzytkownika(dane, katalog_kopii_chronionych() / uzytkownik)
            _zapisz_log(f"kopia {uzytkownik}: {'nowa' if nowa else 'bez zmian'}")
        except Exception:  # noqa: BLE001 - błąd jednego profilu nie zatrzymuje pozostałych
            _zapisz_log(f"kopia {uzytkownik}: BŁĄD\n{traceback.format_exc()}")
    if not profile:
        _zapisz_log("brak danych Fakturnika w profilach użytkowników")
    try:
        _zapisz_log("aktualizacja: " + aktualizuj_program())
    except Exception as e:  # noqa: BLE001 - brak internetu itp.; spróbujemy za godzinę
        _zapisz_log(f"aktualizacja: nie udało się ({e})")
    return 0
