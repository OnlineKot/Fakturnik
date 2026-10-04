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
import stat
import subprocess
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

NAZWA_DANYCH = Path("AppData") / "Roaming" / "Fakturnik" / "Fakturnik"
PLIK_DANYCH = "fakturnik.db"
MAKS_ROZMIAR = 1024 * 1024 * 1024  # 1 GB na plik: usługa (SYSTEM) nie zapcha dysku cudzym plikiem


class Dowiazanie(Exception):
    """Ścieżka prowadzi przez dowiązanie (symlink/junction): usługa SYSTEM nie pójdzie za nim."""


def _dowiazanie(sciezka: Path) -> bool:
    try:
        st = os.lstat(sciezka)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)  # REPARSE_POINT


def sprawdz_sciezke(sciezka: Path, korzen: Path) -> Path:
    """Żaden element ścieżki od katalogu korzen (włącznie z nim) nie może być dowiązaniem.
    Inaczej użytkownik mógłby podstawić junction i kazać usłudze z konta SYSTEM czytać lub
    zapisywać cudze pliki."""
    sciezka, korzen = Path(sciezka), Path(korzen)
    czesci = [korzen, *[korzen.joinpath(*sciezka.relative_to(korzen).parts[:i + 1])
                        for i in range(len(sciezka.relative_to(korzen).parts))]]
    for c in czesci:
        if _dowiazanie(c):
            raise Dowiazanie(str(c))
    return sciezka


def _kopiuj(zrodlo: Path, cel: Path) -> None:
    if _dowiazanie(zrodlo) or not zrodlo.is_file():
        raise Dowiazanie(str(zrodlo))
    if zrodlo.stat().st_size > MAKS_ROZMIAR:
        raise ValueError(f"plik za duży: {zrodlo.name}")
    if _dowiazanie(cel):
        cel.unlink()
    shutil.copyfile(zrodlo, cel, follow_symlinks=False)


def sid_profilu(profil: Path) -> str | None:
    """SID konta Windows, do którego należy katalog profilu (z rejestru ProfileList)."""
    if sys.platform != "win32":
        return None
    import winreg
    klucz = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, klucz) as lista:
            for i in range(winreg.QueryInfoKey(lista)[0]):
                sid = winreg.EnumKey(lista, i)
                try:
                    with winreg.OpenKey(lista, sid) as k:
                        sciezka = os.path.expandvars(winreg.QueryValueEx(k, "ProfileImagePath")[0])
                except OSError:
                    continue
                if os.path.normcase(os.path.normpath(sciezka)) == os.path.normcase(os.path.normpath(str(profil))):
                    return sid
    except OSError:
        pass
    return None


def zabezpiecz_katalog(cel: Path, sid: str | None) -> None:
    """Kopie użytkownika czyta tylko on sam (i SYSTEM/Administratorzy), nie inni użytkownicy komputera."""
    if sys.platform != "win32" or not sid:
        return
    subprocess.run(["icacls", str(cel), "/inheritance:r", "/grant:r", "*S-1-5-18:(OI)(CI)F",
                    "*S-1-5-32-544:(OI)(CI)F", f"*{sid}:(OI)(CI)RX"],
                   capture_output=True, timeout=60, creationflags=0x08000000, check=False)


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
    if _dowiazanie(cel.parent) or _dowiazanie(cel):
        raise Dowiazanie(str(cel))
    cel.mkdir(parents=True, exist_ok=True)
    nowa = False
    plik = dane / PLIK_DANYCH
    if _dowiazanie(plik) or plik.stat().st_size > MAKS_ROZMIAR:
        raise Dowiazanie(str(plik))
    skrot = _skrot(plik)
    znacznik = cel / "ostatnia.sha256"
    if not znacznik.exists() or znacznik.read_text().strip() != skrot:
        docelowy = cel / f"fakturnik-{teraz:%Y-%m-%d-%H%M}.db"
        tymczasowy = docelowy.with_suffix(".tmp")
        _kopiuj(plik, tymczasowy)
        if _skrot(tymczasowy) != skrot:  # plik zmienił się w trakcie kopiowania: spróbujemy za godzinę
            tymczasowy.unlink(missing_ok=True)
        else:
            os.replace(tymczasowy, docelowy)
            znacznik.write_text(skrot)
            nowa = True
    pliki = dane / "pliki"
    if pliki.is_dir() and not _dowiazanie(pliki):
        if _dowiazanie(cel / "pliki"):
            raise Dowiazanie(str(cel / "pliki"))
        (cel / "pliki").mkdir(exist_ok=True)
        for zrodlo in pliki.glob("*.bin"):  # wrzucone pliki nigdy się nie zmieniają, wystarczy dołożyć nowe
            if len(zrodlo.stem) != 32 or any(c not in "0123456789abcdef" for c in zrodlo.stem):
                continue  # tylko pliki zapisane przez Fakturnik
            docelowy = cel / "pliki" / zrodlo.name
            if not docelowy.exists() and not _dowiazanie(zrodlo):
                _kopiuj(zrodlo, docelowy)
    dziennik = dane / "dziennik.log"
    if dziennik.is_file() and not _dowiazanie(dziennik):
        _kopiuj(dziennik, cel / "dziennik.log")
    weryfikator = dane / "weryfikator.json"  # żeby deinstalator sprawdził hasło także po usunięciu danych z profilu
    if weryfikator.is_file() and not _dowiazanie(weryfikator) and weryfikator.stat().st_size < 4096:
        _kopiuj(weryfikator, cel / "weryfikator.json")
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


STAN_AKTUALIZACJI = "aktualizacja.json"
PRZERWA_PO_BLEDZIE = timedelta(hours=24)  # wersji, która nie przeszła autotestu, nie próbujemy przez dobę


def _stan_aktualizacji() -> dict:
    import json
    try:
        dane = json.loads((katalog_uslugi() / STAN_AKTUALIZACJI).read_text(encoding="utf-8"))
        return dane if isinstance(dane, dict) else {}
    except (OSError, ValueError):
        return {}


def _zapisz_stan_aktualizacji(stan: dict) -> None:
    import json
    plik = katalog_uslugi() / STAN_AKTUALIZACJI
    try:
        plik.parent.mkdir(parents=True, exist_ok=True)
        tymczasowy = plik.with_suffix(".tmp")
        tymczasowy.write_text(json.dumps(stan, ensure_ascii=False), encoding="utf-8")
        os.replace(tymczasowy, plik)
    except OSError:
        pass


def _oznacz_zla(wersja: str, powod: str) -> None:
    stan = _stan_aktualizacji()
    stan.setdefault("zle", {})[wersja] = {"kiedy": datetime.now().isoformat(timespec="seconds"), "powod": powod[:300]}
    _zapisz_stan_aktualizacji(stan)


def _niedawno_zla(wersja: str, teraz: datetime | None = None) -> bool:
    wpis = _stan_aktualizacji().get("zle", {}).get(wersja)
    if not wpis:
        return False
    try:
        return (teraz or datetime.now()) - datetime.fromisoformat(wpis["kiedy"]) < PRZERWA_PO_BLEDZIE
    except (KeyError, ValueError):
        return False


class _Blokada:
    """Tylko jedna aktualizacja naraz (np. zadanie godzinowe i zadanie po starcie komputera)."""

    def __init__(self, plik: Path, przeterminowana: timedelta = timedelta(hours=1)):
        self.plik, self.przeterminowana, self.moja = plik, przeterminowana, False

    def __enter__(self):
        self.plik.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.plik.exists() and datetime.now() - datetime.fromtimestamp(self.plik.stat().st_mtime) \
                    > self.przeterminowana:
                self.plik.unlink()  # po awarii zasilania blokada mogła zostać
            fd = os.open(self.plik, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self.moja = True
        except OSError:
            self.moja = False
        return self.moja

    def __exit__(self, *_):
        if self.moja:
            try:
                self.plik.unlink()
            except OSError:
                pass


def autotest_programu(exe: Path, wersja: str = "", limit_s: int = 180) -> tuple[bool, str]:
    """Uruchamia program z --autotest (czyste środowisko, bez okien) i czyta wynik z pliku."""
    import tempfile
    with tempfile.TemporaryDirectory() as katalog:
        wynik = Path(katalog) / "autotest.txt"
        srodowisko = {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}
        srodowisko.update({"PYINSTALLER_RESET_ENVIRONMENT": "1", "QT_QPA_PLATFORM": "offscreen"})
        try:
            kod = subprocess.run([str(exe), "--autotest", str(wynik)], env=srodowisko, capture_output=True,
                                 timeout=limit_s, creationflags=0x08000000 if sys.platform == "win32" else 0).returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"nie uruchomił się ({e})"
        try:
            tresc = wynik.read_text(encoding="utf-8", errors="replace")
        except OSError:
            tresc = ""
    ok = kod == 0 and tresc.startswith("AUTOTEST OK") and (not wersja or f"AUTOTEST OK {wersja}" in tresc)
    return ok, "OK" if ok else (tresc.strip().splitlines()[-1] if tresc.strip() else f"kod wyjścia {kod}")


def _wyglada_na_program(plik: Path) -> bool:
    try:
        with open(plik, "rb") as f:
            return f.read(2) == b"MZ" and plik.stat().st_size > 1024 * 1024
    except OSError:
        return False


def aktualizuj_program() -> str:
    """Pancerna aktualizacja: pobranie (SHA-256) → autotest pobranej wersji → podmiana → autotest
    zainstalowanej; przy jakimkolwiek błędzie zostaje (albo wraca) poprzednia, działająca wersja,
    a wadliwa wersja jest pomijana przez dobę. Działający u użytkownika program zauważy nowy plik
    i uruchomi się ponownie, gdy okno będzie schowane."""
    from . import aktualizacje
    if not aktualizacje.czy_spakowany():
        return "pominięto (wersja ze źródeł)"
    exe = Path(sys.executable)
    with _Blokada(katalog_uslugi() / "aktualizacja.lock") as moja:
        if not moja:
            return "pominięto (inna aktualizacja w toku)"
        aktualizacje.posprzataj(exe)
        try:  # przeglądarka nie jest już częścią programu: plik ze starszej wersji jest usuwany
            exe.with_name("FakturnikPrzegladarka.exe").unlink(missing_ok=True)
        except OSError:
            pass
        wydanie = aktualizacje.sprawdz()
        if not wydanie:
            return "program aktualny"
        if _niedawno_zla(wydanie.wersja):
            return f"pominięto wersję {wydanie.wersja} (nie przeszła autotestu, następna próba za dobę)"
        try:
            wolne = shutil.disk_usage(exe.parent).free
        except OSError:
            wolne = 0
        if wydanie.rozmiar and wolne and wolne < 3 * wydanie.rozmiar:
            return "pominięto (za mało miejsca na dysku)"
        katalog = katalog_uslugi() / "aktualizacja"
        katalog.mkdir(parents=True, exist_ok=True)
        pobrany = katalog / f"Fakturnik-{wydanie.wersja}.exe"
        try:
            aktualizacje.pobierz(wydanie, pobrany)  # SHA-256 z wydania; przy niezgodności plik jest usuwany
            if not _wyglada_na_program(pobrany):
                _oznacz_zla(wydanie.wersja, "pobrany plik nie jest programem")
                return f"odrzucono wersję {wydanie.wersja} (pobrany plik nie jest programem)"
            ok, opis = autotest_programu(pobrany, wydanie.wersja)
            if not ok:
                _oznacz_zla(wydanie.wersja, f"autotest przed instalacją: {opis}")
                return f"odrzucono wersję {wydanie.wersja}: autotest nie przeszedł ({opis}); zostaje obecna"
            nowy = exe.with_name("Fakturnik.new.exe")
            shutil.copyfile(pobrany, nowy)
            if _skrot(nowy) != _skrot(pobrany):
                nowy.unlink(missing_ok=True)
                return "przerwano (kopia pliku uszkodzona przy zapisie)"
            aktualizacje.zainstaluj(nowy, exe)
            ok, opis = autotest_programu(exe, wydanie.wersja)
            if not ok:
                stary = exe.with_name("Fakturnik.old.exe")
                if stary.exists():
                    zly = exe.with_name("Fakturnik.zly.exe")
                    try:
                        zly.unlink(missing_ok=True)
                    except OSError:
                        pass
                    os.replace(exe, zly)
                    os.replace(stary, exe)
                _oznacz_zla(wydanie.wersja, f"autotest po instalacji: {opis}")
                return f"wycofano wersję {wydanie.wersja} ({opis}); przywrócono poprzednią"
        finally:
            try:
                pobrany.unlink(missing_ok=True)
            except OSError:
                pass
        stan = _stan_aktualizacji()
        stan["ostatnia"] = {"wersja": wydanie.wersja, "kiedy": datetime.now().isoformat(timespec="seconds")}
        _zapisz_stan_aktualizacji(stan)
        return f"zainstalowano wersję {wydanie.wersja} (autotest OK)"


def kopia_programu() -> str:
    """Zapasowa kopia Fakturnik.exe w ProgramData (tylko administratorzy/SYSTEM mogą ją zmienić).
    Deinstalator używa jej do pytania o hasło, gdy ktoś usunie albo podmieni plik w Program Files."""
    from . import aktualizacje
    if not aktualizacje.czy_spakowany():
        return "pominięto (wersja ze źródeł)"
    exe = Path(sys.executable)
    cel = katalog_uslugi() / "program" / "Fakturnik.exe"
    if _dowiazanie(cel.parent) or _dowiazanie(cel):
        raise Dowiazanie(str(cel))
    if aktualizacje.sprawdz_wlasny_plik() is False:
        return "nie odświeżono (plik programu różni się od wydania)"
    if cel.is_file() and _skrot(cel) == _skrot(exe):
        return "aktualna"
    cel.parent.mkdir(parents=True, exist_ok=True)
    tymczasowy = cel.with_suffix(".tmp")
    shutil.copyfile(exe, tymczasowy)
    os.replace(tymczasowy, cel)
    return "odświeżona"


def zapisz_stan_programu() -> str:
    """Przy starcie komputera i co godzinę: czy plik programu jest identyczny z opublikowanym wydaniem."""
    from . import aktualizacje
    wynik = aktualizacje.sprawdz_wlasny_plik()
    stan = {True: "oryginalny", False: "ZMIENIONY", None: "nieznany"}[wynik]
    plik = katalog_uslugi() / "program.txt"
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(f"{stan} {datetime.now():%Y-%m-%d %H:%M}")
    return stan


def stan_programu() -> bool | None:
    """Ostatni wynik sprawdzenia programu przez usługę (do kontroli komputera w programie)."""
    try:
        stan = (katalog_uslugi() / "program.txt").read_text().split()[0]
    except (OSError, IndexError):
        return None
    return {"oryginalny": True, "ZMIENIONY": False}.get(stan)


# Komputer nie musi działać cały czas: usługa rusza też po zalogowaniu (po „zamknięciu” z szybkim
# uruchamianiem Windows nie ma prawdziwego startu systemu) i po wybudzeniu ze snu, a nie tylko co godzinę.
WYBUDZENIE = "*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]"


def zadania_uslugi(exe: Path) -> dict[str, list[str]]:
    polecenie = f'"{exe}" --usluga'
    wspolne = ["/RU", "SYSTEM", "/RL", "HIGHEST", "/TR", polecenie]
    return {
        "Fakturnik\\Kopie co godzine": ["/SC", "HOURLY"] + wspolne,
        "Fakturnik\\Kopie po starcie": ["/SC", "ONSTART", "/DELAY", "0005:00"] + wspolne,
        "Fakturnik\\Kopie po zalogowaniu": ["/SC", "ONLOGON", "/DELAY", "0002:00"] + wspolne,
        "Fakturnik\\Kopie po wybudzeniu": ["/SC", "ONEVENT", "/EC", "System", "/MO", WYBUDZENIE,
                                             "/DELAY", "0002:00"] + wspolne,
    }


def zapewnij_zadania() -> str:
    """Dopisuje brakujące zadania usługi (starsze instalacje miały tylko „co godzinę” i „po starcie”)."""
    from . import aktualizacje
    if sys.platform != "win32" or not aktualizacje.czy_spakowany() or not aktualizacje.zainstalowany():
        return "pominięto"
    schtasks = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "schtasks.exe"
    bez_okna = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    dodane = []
    for nazwa, argumenty in zadania_uslugi(Path(sys.executable)).items():
        if subprocess.run([str(schtasks), "/Query", "/TN", nazwa], capture_output=True,
                          creationflags=bez_okna, timeout=30).returncode == 0:
            continue
        wynik = subprocess.run([str(schtasks), "/Create", "/F", "/TN", nazwa] + argumenty, capture_output=True,
                               creationflags=bez_okna, timeout=30)
        dodane.append(nazwa.split("\\")[-1] + ("" if wynik.returncode == 0 else " (błąd)"))
    return "dodano: " + ", ".join(dodane) if dodane else "komplet"


def uruchom_usluge() -> int:
    # kilka zadań może ruszyć naraz (np. start komputera i zalogowanie): pracuje tylko jedno
    with _Blokada(katalog_uslugi() / "usluga.lock") as moja:
        if not moja:
            _zapisz_log("pominięto (usługa już działa)")
            return 0
        return _uruchom_usluge()


def _uruchom_usluge() -> int:
    try:
        _zapisz_log("zadania usługi: " + zapewnij_zadania())
    except Exception as e:  # noqa: BLE001
        _zapisz_log(f"zadania usługi: nie sprawdzono ({e})")
    profile = profile_z_danymi()
    for uzytkownik, dane in profile:
        try:
            profil = katalog_profili() / uzytkownik
            sprawdz_sciezke(dane, profil)
            cel = katalog_kopii_chronionych() / uzytkownik
            nowa = kopia_uzytkownika(dane, cel)
            zabezpiecz_katalog(cel, sid_profilu(profil))
            _zapisz_log(f"kopia {uzytkownik}: {'nowa' if nowa else 'bez zmian'}")
        except Exception:  # noqa: BLE001 - błąd jednego profilu nie zatrzymuje pozostałych
            _zapisz_log(f"kopia {uzytkownik}: BŁĄD\n{traceback.format_exc()}")
    if not profile:
        _zapisz_log("brak danych Fakturnika w profilach użytkowników")
    try:
        _zapisz_log("plik programu: " + zapisz_stan_programu())
    except Exception as e:  # noqa: BLE001
        _zapisz_log(f"plik programu: nie sprawdzono ({e})")
    try:
        _zapisz_log("kopia programu: " + kopia_programu())
    except Exception as e:  # noqa: BLE001
        _zapisz_log(f"kopia programu: nie udało się ({e})")
    try:
        _zapisz_log("aktualizacja: " + aktualizuj_program())
    except Exception as e:  # noqa: BLE001 - brak internetu itp.; spróbujemy za godzinę
        _zapisz_log(f"aktualizacja: nie udało się ({e})")
    return 0
