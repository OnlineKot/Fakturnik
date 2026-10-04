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
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .wersja import WERSJA

REPOZYTORIUM = "OnlineKot/Fakturnik"
ADRES_API = f"https://api.github.com/repos/{REPOZYTORIUM}/releases/latest"
# zapasowa droga bez API GitHuba (API ma limit zapytań i bywa niedostępne):
# strona najnowszego wydania przekierowuje na /releases/tag/vX, a pliki leżą pod stałymi adresami
ADRES_NAJNOWSZEGO = f"https://github.com/{REPOZYTORIUM}/releases/latest"
ADRES_POBIERANIA = f"https://github.com/{REPOZYTORIUM}/releases/download"
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


def _z_api() -> Wydanie | None:
    with _pobierz(ADRES_API) as o:
        dane = json.load(o)
    pliki = {a["name"]: a for a in dane.get("assets", [])}
    if NAZWA_PLIKU not in pliki or NAZWA_PLIKU + ".sha256" not in pliki:
        return None
    return Wydanie(wersja=dane.get("tag_name", "").lstrip("v"), opis=dane.get("body") or "",
                   adres_exe=pliki[NAZWA_PLIKU]["browser_download_url"],
                   adres_sha256=pliki[NAZWA_PLIKU + ".sha256"]["browser_download_url"],
                   rozmiar=int(pliki[NAZWA_PLIKU].get("size") or 0))


def wydanie_wersji(wersja: str, nazwa: str = NAZWA_PLIKU) -> Wydanie:
    """Wydanie o znanym numerze pod stałymi adresami GitHuba (bez API)."""
    return Wydanie(wersja=wersja, opis="", adres_exe=f"{ADRES_POBIERANIA}/v{wersja}/{nazwa}",
                   adres_sha256=f"{ADRES_POBIERANIA}/v{wersja}/{nazwa}.sha256", rozmiar=0)


def _bez_api() -> Wydanie | None:
    with _pobierz(ADRES_NAJNOWSZEGO) as o:
        koncowy = o.geturl()
    znalezione = re.search(r"/releases/tag/v?(\d+(?:\.\d+){0,2})/?$", urlparse(koncowy).path)
    if not znalezione:
        return None
    return wydanie_wersji(znalezione.group(1))


def najnowsze() -> Wydanie | None:
    """Najnowsze wydanie: najpierw przez API GitHuba, a gdy się nie uda, przez zwykłą stronę wydań."""
    bledy = []
    for sposob in (_z_api, _bez_api):
        try:
            wydanie = sposob()
        except BladAktualizacji as e:
            bledy.append(str(e))
            continue
        except Exception as e:  # noqa: BLE001 - limit API, brak sieci, zła odpowiedź
            bledy.append(str(e))
            continue
        if wydanie and wydanie.wersja:
            return wydanie
    if bledy:
        raise BladAktualizacji(f"Nie udało się połączyć z serwerem aktualizacji ({bledy[-1]}).")
    return None


def sprawdz() -> Wydanie | None:
    """Zwraca nowsze wydanie albo None, gdy program jest aktualny."""
    wydanie = najnowsze()
    if wydanie is None or not jest_nowsza(wydanie.wersja):
        return None
    return wydanie


def _pobierz_raz(wydanie: Wydanie, cel: Path, postep) -> Path:
    with _pobierz(wydanie.adres_sha256) as o:
        oczekiwany = o.read().decode("ascii", "replace").split()[0].strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", oczekiwany):
        raise BladAktualizacji("Nieprawidłowy plik sumy kontrolnej.")
    skrot = hashlib.sha256()
    pobrano = 0
    try:
        with _pobierz(wydanie.adres_exe, timeout=60) as o, open(cel, "wb") as f:
            naglowki = getattr(o, "headers", None)
            rozmiar = wydanie.rozmiar or int((naglowki.get("Content-Length") if naglowki else 0) or 0)
            while blok := o.read(256 * 1024):
                f.write(blok)
                skrot.update(blok)
                pobrano += len(blok)
                if rozmiar:
                    postep(min(100, pobrano * 100 // rozmiar))
            f.flush()
            os.fsync(f.fileno())
        if skrot.hexdigest() != oczekiwany:
            raise BladAktualizacji("Suma kontrolna SHA-256 pobranego pliku się nie zgadza. Aktualizacja przerwana.")
    except BaseException:
        cel.unlink(missing_ok=True)
        raise
    return cel


PROBY_POBIERANIA = 4
PRZERWA_POBIERANIA = 5.0  # sekundy przed pierwszym ponowieniem, potem dwa razy dłużej


def zalegla(wersja: str, zapis: str, teraz, godzin: float = 3, przerwa_h: float = 2.5) -> tuple[str, bool]:
    """Strażnik usługi: czy dostępna wersja czeka już za długo na instalację przez usługę.

    Liczy się tylko czas, gdy komputer działał: przerwa między sprawdzeniami dłuższa niż `przerwa_h`
    (komputer wyłączony albo uśpiony) nie jest doliczana, bo wtedy usługa nie mogła nic zrobić.
    `zapis` to "wersja|sekundy oczekiwania|ostatni pomiar"; zwraca (nowy zapis, czy zaległa).
    """
    from datetime import datetime
    czesci = (zapis or "").split("|")
    czekano = 0.0
    if len(czesci) == 3 and czesci[0] == wersja:
        try:
            czekano = float(czesci[1])
            odstep = (teraz - datetime.fromisoformat(czesci[2])).total_seconds()
            if 0 < odstep <= przerwa_h * 3600:
                czekano += odstep
        except ValueError:
            czekano = 0.0
    nowy = f"{wersja}|{int(czekano)}|{teraz.isoformat(timespec='seconds')}"
    return nowy, czekano >= godzin * 3600


def pobierz(wydanie: Wydanie, cel: Path, postep=lambda procent: None, proby: int | None = None,
            przerwa: float | None = None) -> Path:
    """Pobiera nowy .exe do `cel` i sprawdza jego SHA-256. Przy niezgodności plik jest usuwany.

    Zerwane połączenie albo uszkodzony plik nie kończą aktualizacji: pobieranie jest ponawiane
    (z coraz dłuższą przerwą), także drugą drogą (stałe adresy bez API), gdy pierwsza zawodzi.
    """
    proby = PROBY_POBIERANIA if proby is None else proby
    przerwa = PRZERWA_POBIERANIA if przerwa is None else przerwa
    nazwa = urlparse(wydanie.adres_sha256).path.rsplit("/", 1)[-1].removesuffix(".sha256")
    zapasowe = wydanie_wersji(wydanie.wersja, nazwa) if wydanie.wersja and nazwa else None
    if zapasowe and zapasowe.adres_exe == wydanie.adres_exe:
        zapasowe = None
    ostatni: Exception | None = None
    for proba in range(max(1, proby)):
        zrodlo = zapasowe if (proba % 2 and zapasowe) else wydanie
        try:
            return _pobierz_raz(zrodlo, cel, postep)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BladAktualizacji as e:
            if "Niedozwolon" in str(e):  # adres spoza GitHuba: nie ponawiamy
                raise
            ostatni = e
        except Exception as e:  # noqa: BLE001 - sieć, dysk
            ostatni = e
        if proba + 1 < proby:
            time.sleep(przerwa * (2 ** proba))
    if isinstance(ostatni, BladAktualizacji):
        raise ostatni
    raise BladAktualizacji(f"Nie udało się pobrać aktualizacji ({ostatni}).")


def skrot_pliku(sciezka: Path) -> str:
    skrot = hashlib.sha256()
    with open(sciezka, "rb") as f:
        while blok := f.read(1024 * 1024):
            skrot.update(blok)
    return skrot.hexdigest()


def _skrot_z_adresu(adres_sha: str) -> str | None:
    with _pobierz(adres_sha) as o:
        oczekiwany = o.read().decode("ascii", "replace").split()[0].strip().lower()
    return oczekiwany if re.fullmatch(r"[0-9a-f]{64}", oczekiwany) else None


def sprawdz_wlasny_plik(obecny: Path | None = None, wersja: str = WERSJA) -> bool | None:
    """Porównuje plik Fakturnik.exe z sumami SHA-256 opublikowanymi w wydaniach.

    True = plik jest oryginalny, False = ktoś go zmienił, None = nie da się sprawdzić
    (wersja ze źródeł, brak internetu albo wydania, plik właśnie podmieniony przez aktualizację).
    Plik może już być nowszą wersją zainstalowaną przez usługę, gdy program jeszcze działa,
    dlatego zgodność z najnowszym wydaniem też oznacza oryginał.
    """
    if obecny is None:
        if not czy_spakowany() or plik_programu_zmieniony():
            return None
        obecny = Path(sys.executable)
    try:
        skrot = skrot_pliku(obecny)
    except OSError:
        return None
    adresy = [wydanie_wersji(wersja).adres_sha256]
    try:
        if (ostatnie := najnowsze()) is not None:
            adresy.append(ostatnie.adres_sha256)
    except Exception:  # noqa: BLE001
        pass
    znane = set()
    for adres in adresy:
        try:
            if (oczekiwany := _skrot_z_adresu(adres)):
                znane.add(oczekiwany)
        except Exception:  # noqa: BLE001 - np. brak wydania o tym numerze
            continue
    if not znane:
        return None
    return skrot in znane


# ---------------------------------------------------------------- instalacja w Program Files

def zainstalowany(exe: Path | None = None) -> bool:
    """Program działa z instalacji w Program Files (także gdy uruchomiono go jako administrator,
    a wtedy folder byłby zapisywalny i sam test zapisu by się pomylił)."""
    exe = (exe or Path(sys.executable)).resolve()
    for zmienna in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        katalog = os.environ.get(zmienna)
        if katalog:
            try:
                exe.relative_to(Path(katalog).resolve())
                return True
            except ValueError:
                continue
    return not mozna_zapisac_obok(exe)


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
    if not czy_spakowany() or _blokada_programu is not None or zainstalowany():
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
    wydanie = najnowsze()
    if wydanie is None:
        raise BladAktualizacji("Nie znaleziono wydania z instalatorem.")
    return pobierz(wydanie_wersji(wydanie.wersja, "FakturnikSetup.exe"), cel, postep)


def zainstaluj(nowy: Path, obecny: Path | None = None) -> Path:
    """Podmienia działający .exe na nowy; zwraca ścieżkę do uruchomienia."""
    obecny = obecny or Path(sys.executable)
    odblokuj_program()  # inaczej Windows nie pozwoli zmienić nazwy
    if not obecny.exists():  # pierwsza instalacja pliku
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
