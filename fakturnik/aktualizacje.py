"""Aktualizacje programu z wydań na GitHubie.

Każde wydanie zawiera Fakturnik.exe i plik Fakturnik.exe.sha256 z jego skrótem. Pobrany plik
jest odrzucany, jeśli skrót się nie zgadza. Działający .exe nie może nadpisać sam siebie,
ale na Windows może zmienić nazwę, więc wymiana wygląda tak:
    Fakturnik.exe -> Fakturnik.old.exe,  Fakturnik.new.exe -> Fakturnik.exe
a stary plik jest usuwany przy następnym uruchomieniu.
"""

import hashlib
import json
import os
import re
import stat
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .wersja import WERSJA

REPOZYTORIUM = "OnlineKot/Fakturnik"
ADRES_API = f"https://api.github.com/repos/{REPOZYTORIUM}/releases/latest"
NAZWA_PLIKU = "Fakturnik.exe"
ZAUFANE_HOSTY = {"github.com", "api.github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com"}


class BladAktualizacji(Exception):
    pass


@dataclass
class Wydanie:
    wersja: str
    opis: str
    adres_exe: str
    adres_sha256: str
    rozmiar: int
    przegladarka: "Wydanie | None" = None  # FakturnikPrzegladarka.exe z tego samego wydania (jeśli jest)


def numer_wersji(tekst: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", tekst)[:3]) or (0,)


def jest_nowsza(zdalna: str, lokalna: str = WERSJA) -> bool:
    return numer_wersji(zdalna) > numer_wersji(lokalna)


def czy_spakowany() -> bool:
    """True, gdy program działa jako .exe (PyInstaller), a nie ze źródeł."""
    return bool(getattr(sys, "frozen", False))


def _pobierz(adres: str, timeout: float = 10):
    if urlparse(adres).scheme != "https" or urlparse(adres).hostname not in ZAUFANE_HOSTY:
        raise BladAktualizacji(f"Niedozwolony adres: {adres}")
    zadanie = urllib.request.Request(adres, headers={"User-Agent": f"Fakturnik/{WERSJA}",
                                                     "Accept": "application/octet-stream, application/json"})
    odpowiedz = urllib.request.urlopen(zadanie, timeout=timeout)
    koncowy = urlparse(odpowiedz.geturl()).hostname
    if koncowy not in ZAUFANE_HOSTY:  # przekierowanie poza GitHub
        raise BladAktualizacji(f"Niedozwolone przekierowanie: {koncowy}")
    return odpowiedz


def sprawdz() -> Wydanie | None:
    """Zwraca nowsze wydanie albo None, gdy program jest aktualny."""
    try:
        with _pobierz(ADRES_API) as o:
            dane = json.load(o)
    except BladAktualizacji:
        raise
    except Exception as e:
        raise BladAktualizacji(f"Nie udało się połączyć z serwerem aktualizacji ({e}).") from None
    pliki = {a["name"]: a for a in dane.get("assets", [])}
    if NAZWA_PLIKU not in pliki or NAZWA_PLIKU + ".sha256" not in pliki:
        return None
    wersja = dane.get("tag_name", "").lstrip("v")
    if not jest_nowsza(wersja):
        return None
    przegladarka = None
    if "FakturnikPrzegladarka.exe" in pliki and "FakturnikPrzegladarka.exe.sha256" in pliki:
        przegladarka = Wydanie(wersja=wersja, opis="",
                               adres_exe=pliki["FakturnikPrzegladarka.exe"]["browser_download_url"],
                               adres_sha256=pliki["FakturnikPrzegladarka.exe.sha256"]["browser_download_url"],
                               rozmiar=int(pliki["FakturnikPrzegladarka.exe"].get("size") or 0))
    return Wydanie(wersja=wersja, opis=dane.get("body") or "",
                   adres_exe=pliki[NAZWA_PLIKU]["browser_download_url"],
                   adres_sha256=pliki[NAZWA_PLIKU + ".sha256"]["browser_download_url"],
                   rozmiar=int(pliki[NAZWA_PLIKU].get("size") or 0), przegladarka=przegladarka)


def pobierz(wydanie: Wydanie, cel: Path, postep=lambda procent: None) -> Path:
    """Pobiera nowy .exe do `cel` i sprawdza jego SHA-256. Przy niezgodności plik jest usuwany."""
    with _pobierz(wydanie.adres_sha256) as o:
        oczekiwany = o.read().decode("ascii", "replace").split()[0].strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", oczekiwany):
        raise BladAktualizacji("Nieprawidłowy plik sumy kontrolnej.")
    skrot = hashlib.sha256()
    pobrano = 0
    try:
        with _pobierz(wydanie.adres_exe, timeout=30) as o, open(cel, "wb") as f:
            while blok := o.read(256 * 1024):
                f.write(blok)
                skrot.update(blok)
                pobrano += len(blok)
                if wydanie.rozmiar:
                    postep(min(100, pobrano * 100 // wydanie.rozmiar))
        if skrot.hexdigest() != oczekiwany:
            raise BladAktualizacji("Suma kontrolna SHA-256 pobranego pliku się nie zgadza. Aktualizacja przerwana.")
    except BaseException:
        cel.unlink(missing_ok=True)
        raise
    return cel


def skrot_pliku(sciezka: Path) -> str:
    skrot = hashlib.sha256()
    with open(sciezka, "rb") as f:
        while blok := f.read(1024 * 1024):
            skrot.update(blok)
    return skrot.hexdigest()


def sprawdz_wlasny_plik(obecny: Path | None = None, wersja: str = WERSJA) -> bool | None:
    """Porównuje działający Fakturnik.exe z sumą SHA-256 opublikowaną przy jego wydaniu.

    True = plik jest oryginalny, False = ktoś go zmienił, None = nie da się sprawdzić
    (wersja ze źródeł, brak internetu albo wydania).
    """
    if obecny is None:
        if not czy_spakowany():
            return None
        obecny = Path(sys.executable)
    try:
        with _pobierz(f"https://api.github.com/repos/{REPOZYTORIUM}/releases/tags/v{wersja}") as o:
            dane = json.load(o)
        pliki = {a["name"]: a for a in dane.get("assets", [])}
        if NAZWA_PLIKU + ".sha256" not in pliki:
            return None
        with _pobierz(pliki[NAZWA_PLIKU + ".sha256"]["browser_download_url"]) as o:
            oczekiwany = o.read().decode("ascii", "replace").split()[0].strip().lower()
    except Exception:
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", oczekiwany):
        return None
    return skrot_pliku(obecny) == oczekiwany


# ---------------------------------------------------------------- instalacja w Program Files

def mozna_zapisac_obok(exe: Path | None = None) -> bool:
    """Czy program może sam podmienić swój plik. Nie, gdy zainstalowano go w Program Files
    (tam zmiany robi tylko administrator, a aktualizacje instaluje usługa Fakturnika)."""
    katalog = (exe or Path(sys.executable)).parent
    proba = katalog / f".fakturnik-proba-{os.getpid()}"
    try:
        proba.write_bytes(b"")
        proba.unlink()
        return True
    except OSError:
        return False


_stan_pliku: tuple[int, int] | None = None


def zapamietaj_plik_programu() -> None:
    global _stan_pliku
    try:
        st = Path(sys.executable).stat()
        _stan_pliku = (st.st_size, st.st_mtime_ns)
    except OSError:
        _stan_pliku = None


def plik_programu_zmieniony() -> bool:
    """True, gdy usługa podmieniła plik programu na nową wersję, odkąd program działa."""
    if not czy_spakowany() or _stan_pliku is None:
        return False
    try:
        st = Path(sys.executable).stat()
    except OSError:
        return False
    return (st.st_size, st.st_mtime_ns) != _stan_pliku


# ---------------------------------------------------------------- blokada działającego programu

_blokada_programu = None


def zablokuj_program() -> None:
    """Gdy program działa, jego .exe jest otwarty bez zgody na zapis, zmianę nazwy i usunięcie (Windows).

    Nie dotyczy instalacji w Program Files: tam plik chronią uprawnienia Windows, a blokada
    uniemożliwiłaby usłudze zainstalowanie aktualizacji."""
    global _blokada_programu
    if not czy_spakowany() or _blokada_programu is not None or not mozna_zapisac_obok():
        return
    from .ochrona import BlokadaPliku
    _blokada_programu = BlokadaPliku(Path(sys.executable))
    _blokada_programu.zaloz()


def odblokuj_program() -> None:
    global _blokada_programu
    if _blokada_programu is not None:
        _blokada_programu.zwolnij()
        _blokada_programu = None


def _usun(sciezka: Path) -> None:
    if sciezka.exists():
        os.chmod(sciezka, stat.S_IREAD | stat.S_IWRITE)  # zdejmij „tylko do odczytu”
        sciezka.unlink()


def pobierz_instalator(cel: Path, postep=lambda procent: None) -> Path:
    """Najnowszy FakturnikSetup.exe z GitHuba, sprawdzony sumą SHA-256 (do instalacji z uprawnieniami admina)."""
    try:
        with _pobierz(ADRES_API) as o:
            dane = json.load(o)
    except BladAktualizacji:
        raise
    except Exception as e:
        raise BladAktualizacji(f"Nie udało się połączyć z GitHubem ({e}).") from None
    pliki = {a["name"]: a for a in dane.get("assets", [])}
    if "FakturnikSetup.exe" not in pliki or "FakturnikSetup.exe.sha256" not in pliki:
        raise BladAktualizacji("W najnowszym wydaniu nie ma instalatora.")
    wydanie = Wydanie(wersja=dane.get("tag_name", "").lstrip("v"), opis="",
                      adres_exe=pliki["FakturnikSetup.exe"]["browser_download_url"],
                      adres_sha256=pliki["FakturnikSetup.exe.sha256"]["browser_download_url"],
                      rozmiar=int(pliki["FakturnikSetup.exe"].get("size") or 0))
    return pobierz(wydanie, cel, postep)


def zainstaluj(nowy: Path, obecny: Path | None = None) -> Path:
    """Podmienia działający .exe na nowy; zwraca ścieżkę do uruchomienia."""
    obecny = obecny or Path(sys.executable)
    odblokuj_program()  # inaczej Windows nie pozwoli zmienić nazwy
    if not obecny.exists():  # np. przeglądarka, której jeszcze nie było
        nowy.rename(obecny)
        return obecny
    stary = obecny.with_name(obecny.stem + ".old" + obecny.suffix)
    _usun(stary)
    obecny.rename(stary)
    try:
        nowy.rename(obecny)
    except OSError:
        stary.rename(obecny)  # przywróć poprzednią wersję
        raise
    return obecny


def posprzataj(obecny: Path | None = None) -> None:
    """Usuwa plik poprzedniej wersji pozostawiony po aktualizacji."""
    if not czy_spakowany() and obecny is None:
        return
    obecny = obecny or Path(sys.executable)
    for nazwa in (obecny.stem + ".old" + obecny.suffix, obecny.stem + ".new" + obecny.suffix):
        try:
            _usun(obecny.with_name(nazwa))
        except OSError:
            pass


def uruchom_nowa_wersje(exe: Path, argumenty: list[str] | None = None) -> None:
    """Uruchamia zaktualizowany program; ten poczeka, aż bieżący proces się zakończy.

    Nowy proces dostaje czyste środowisko: bez zmiennych PyInstallera, które wskazywałyby mu folder
    tymczasowy starej wersji (stara wersja usuwa go przy zamykaniu, co kończyło się błędem krytycznym).
    Program startuje bezpośrednio (bez cmd i ping), co nie budzi podejrzeń antywirusa.
    """
    import subprocess
    srodowisko = {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}
    srodowisko["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    polecenie = [str(exe), "--po-aktualizacji", str(os.getpid()), *(argumenty or [])]
    if sys.platform == "win32":
        flagi = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(polecenie, env=srodowisko, creationflags=flagi, close_fds=True)
    else:
        subprocess.Popen(polecenie, env=srodowisko, start_new_session=True, close_fds=True)


def czekaj_na_poprzednia(argumenty: list[str], limit_s: float = 30) -> list[str]:
    """Po aktualizacji: czeka, aż stara wersja się zamknie (zwolni dane), i zwraca argumenty bez znacznika."""
    if "--po-aktualizacji" not in argumenty:
        return argumenty
    i = argumenty.index("--po-aktualizacji")
    reszta = argumenty[:i] + argumenty[i + 2:]
    try:
        pid = int(argumenty[i + 1])
    except (IndexError, ValueError):
        return reszta
    if sys.platform == "win32":
        import ctypes
        SYNCHRONIZE = 0x00100000
        uchwyt = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if uchwyt:
            ctypes.windll.kernel32.WaitForSingleObject(uchwyt, int(limit_s * 1000))
            ctypes.windll.kernel32.CloseHandle(uchwyt)
    else:
        import time
        koniec = time.monotonic() + limit_s
        while time.monotonic() < koniec:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.2)
    return reszta
