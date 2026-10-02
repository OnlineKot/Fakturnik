"""Aktualizacje programu z wydań na GitHubie.

Każde wydanie zawiera Fakturnik.exe i plik Fakturnik.exe.sha256 z jego skrótem. Pobrany plik
jest odrzucany, jeśli skrót się nie zgadza. Działający .exe nie może nadpisać sam siebie,
ale na Windows może zmienić nazwę, więc wymiana wygląda tak:
    Fakturnik.exe -> Fakturnik.old.exe,  Fakturnik.new.exe -> Fakturnik.exe
a stary plik jest usuwany przy następnym uruchomieniu.
"""

import hashlib
import json
import re
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
    return Wydanie(wersja=wersja, opis=dane.get("body") or "",
                   adres_exe=pliki[NAZWA_PLIKU]["browser_download_url"],
                   adres_sha256=pliki[NAZWA_PLIKU + ".sha256"]["browser_download_url"],
                   rozmiar=int(pliki[NAZWA_PLIKU].get("size") or 0))


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


def zainstaluj(nowy: Path, obecny: Path | None = None) -> Path:
    """Podmienia działający .exe na nowy; zwraca ścieżkę do uruchomienia."""
    obecny = obecny or Path(sys.executable)
    stary = obecny.with_name(obecny.stem + ".old" + obecny.suffix)
    stary.unlink(missing_ok=True)
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
            obecny.with_name(nazwa).unlink(missing_ok=True)
        except OSError:
            pass
