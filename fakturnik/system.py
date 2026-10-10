"""Integracja z systemem: jedna działająca kopia programu, autostart, menu prawego przycisku, skrót na pulpicie.

Wpisy w rejestrze trafiają tylko do gałęzi bieżącego użytkownika (HKCU), więc nie są potrzebne
uprawnienia administratora. Poza Windows (np. test na Macu) funkcje rejestru nic nie robią.
"""

import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAZWA_SERWERA = f"Fakturnik-{getpass.getuser()}"
ROZSZERZENIA_MENU = ("pdf", "jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp")
KLUCZ_AUTOSTARTU = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAZWA_WPISU = "Fakturnik"
# Autostart jest zawsze włączony w programie (Fakturnik pilnuje danych): przy każdym starcie program
# przywraca swój wpis, jeśli zniknął. Wyłączenia w Menedżerze zadań Windows program nie nadpisuje.
# Starszy zapisany wybór „nie uruchamiaj” jest kasowany.
KLUCZ_PREFERENCJI = r"Software\Fakturnik\Preferencje"


def na_windows() -> bool:
    return sys.platform == "win32"


def sciezka_programu() -> Path | None:
    """Ścieżka do Fakturnik.exe (tylko w wersji spakowanej; ze źródeł integracja nie ma sensu)."""
    return Path(sys.executable) if getattr(sys, "frozen", False) else None


def integracja_dostepna() -> bool:
    return na_windows() and sciezka_programu() is not None


# ---------------------------------------------------------------- jedna kopia programu

class JednaKopia(QObject):
    """Pierwsza kopia nasłuchuje; kolejne przekazują jej polecenie (pokaż okno, dodaj pliki) i kończą działanie."""

    polecenie = Signal(dict)

    def __init__(self):
        super().__init__()
        self.serwer: QLocalServer | None = None

    def wyslij_do_dzialajacej(self, wiadomosc: dict) -> bool:
        gniazdo = QLocalSocket()
        gniazdo.connectToServer(NAZWA_SERWERA)
        if not gniazdo.waitForConnected(500):
            return False
        gniazdo.write(json.dumps(wiadomosc).encode("utf-8"))
        gniazdo.flush()
        gniazdo.waitForBytesWritten(1000)
        gniazdo.disconnectFromServer()
        return True

    def nasluchuj(self) -> None:
        QLocalServer.removeServer(NAZWA_SERWERA)  # pozostałość po awarii poprzedniej kopii
        self.serwer = QLocalServer(self)
        self.serwer.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)  # tylko ten użytkownik
        self.serwer.listen(NAZWA_SERWERA)
        self.serwer.newConnection.connect(self._polaczenie)

    def zamknij(self) -> None:
        if self.serwer is not None:
            self.serwer.close()
            QLocalServer.removeServer(NAZWA_SERWERA)
            self.serwer = None

    def _polaczenie(self):
        gniazdo = self.serwer.nextPendingConnection()
        if gniazdo is None:
            return

        def odczytaj():
            surowe = bytes(gniazdo.read(64 * 1024))  # większych wiadomości nie przyjmujemy
            polecenie = sprawdz_polecenie(surowe)
            if polecenie is not None:
                self.polecenie.emit(polecenie)

        if gniazdo.bytesAvailable() or gniazdo.waitForReadyRead(1000):
            odczytaj()
        gniazdo.disconnected.connect(gniazdo.deleteLater)


def sprawdz_polecenie(surowe: bytes) -> dict | None:
    """Przyjmuje tylko znane polecenia w oczekiwanym kształcie (pliki: istniejące, maks. 50)."""
    try:
        dane = json.loads(surowe.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(dane, dict) or dane.get("akcja") not in ("pokaz", "dodaj", "w_tle"):
        return None
    if dane["akcja"] != "dodaj":
        return {"akcja": dane["akcja"]}
    pliki = dane.get("pliki")
    if not isinstance(pliki, list):
        return None
    pliki = [p for p in pliki[:50] if isinstance(p, str) and len(p) < 1024 and Path(p).is_file()]
    return {"akcja": "dodaj", "pliki": pliki} if pliki else None


def polecenie_z_argumentow(argumenty: list[str]) -> dict:
    """--dodaj plik1 plik2 … (menu prawego przycisku), --w-tle (autostart), bez argumentów: pokaż okno."""
    if "--dodaj" in argumenty:
        i = argumenty.index("--dodaj")
        return {"akcja": "dodaj", "pliki": [str(Path(p).resolve()) for p in argumenty[i + 1:] if Path(p).is_file()]}
    if "--w-tle" in argumenty:  # --straznik: ponowne uruchomienie przez strażnika (bez wyskakującego okna)
        return {"akcja": "w_tle", "straznik": "--straznik" in argumenty}
    return {"akcja": "pokaz"}


# ---------------------------------------------------------------- rejestr Windows

def _rejestr():
    import winreg
    return winreg


def _usun_wartosc(galaz, klucz: str, nazwa: str) -> None:
    winreg = _rejestr()
    try:
        with winreg.OpenKey(galaz, klucz, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, nazwa)
    except OSError:
        pass


KLUCZ_ZATWIERDZONYCH = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def autostart_zablokowany() -> bool | None:
    """Czy ktoś wyłączył Fakturnik w Menedżerze zadań → Uruchamianie (None = nie da się sprawdzić).
    Windows zapisuje to w StartupApproved: pierwszy bajt nieparzysty (np. 03) = wyłączone."""
    if not integracja_dostepna():
        return None
    winreg = _rejestr()
    for galaz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(galaz, KLUCZ_ZATWIERDZONYCH) as k:
                dane = winreg.QueryValueEx(k, NAZWA_WPISU)[0]
        except OSError:
            continue
        if isinstance(dane, bytes) and dane and dane[0] & 1:
            if galaz == winreg.HKEY_CURRENT_USER or not _wpis_uzytkownika_dziala():
                return True
    return not autostart_wlaczony()


def _wpis_uzytkownika_dziala() -> bool:
    """Wpis w HKCU\Run istnieje i nie jest wyłączony (wtedy wyłączony wpis instalatora nie przeszkadza)."""
    winreg = _rejestr()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KLUCZ_AUTOSTARTU) as k:
            winreg.QueryValueEx(k, NAZWA_WPISU)
    except OSError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KLUCZ_ZATWIERDZONYCH) as k:
            dane = winreg.QueryValueEx(k, NAZWA_WPISU)[0]
        return not (isinstance(dane, bytes) and dane and dane[0] & 1)
    except OSError:
        return True


def wlacz_autostart_ponownie() -> bool:
    """Na kliknięcie użytkownika: cofnięcie wyłączenia z Menedżera zadań dla tego konta i wpis autostartu."""
    if not integracja_dostepna():
        return False
    winreg = _rejestr()
    _usun_wartosc(winreg.HKEY_CURRENT_USER, KLUCZ_ZATWIERDZONYCH, NAZWA_WPISU)
    ustaw_autostart(True)
    return autostart_zablokowany() is False


def zapewnij_autostart() -> None:
    """Przy każdym starcie: wpis autostartu programu jest na miejscu."""
    if not integracja_dostepna():
        return
    winreg = _rejestr()
    _usun_wartosc(winreg.HKEY_CURRENT_USER, KLUCZ_PREFERENCJI, "autostart_wylaczony")
    if not autostart_wlaczony():
        ustaw_autostart(True)


def start_z_windows(argumenty: list[str]) -> bool:
    """Uruchomienie przez wpis autostartu (a nie restart po aktualizacji lub po awarii)."""
    return "--w-tle" in argumenty and "--po-aktualizacji" not in argumenty and "--restart" not in argumenty


def autostart_wlaczony() -> bool:
    if not integracja_dostepna():
        return False
    winreg = _rejestr()
    for galaz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):  # HKLM: wpis z instalatora (wszystkie konta)
        try:
            with winreg.OpenKey(galaz, KLUCZ_AUTOSTARTU) as k:
                wartosc, _ = winreg.QueryValueEx(k, NAZWA_WPISU)
                if str(sciezka_programu()).lower() in wartosc.lower():
                    return True
        except OSError:
            continue
    return False


def ustaw_autostart(wlacz: bool) -> bool:
    if not integracja_dostepna():
        return False
    winreg = _rejestr()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KLUCZ_AUTOSTARTU) as k:
        if wlacz:
            winreg.SetValueEx(k, NAZWA_WPISU, 0, winreg.REG_SZ, f'"{sciezka_programu()}" --w-tle')
        else:
            try:
                winreg.DeleteValue(k, NAZWA_WPISU)
            except OSError:
                pass
    return True


def _klucz_menu(rozszerzenie: str) -> str:
    return rf"Software\Classes\SystemFileAssociations\.{rozszerzenie}\shell\Fakturnik"


def menu_kontekstowe_wlaczone() -> bool:
    if not integracja_dostepna():
        return False
    winreg = _rejestr()
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, _klucz_menu("pdf")).Close()
        return True
    except OSError:
        return False


def ustaw_menu_kontekstowe(wlacz: bool) -> bool:
    """Pozycja „Dodaj do Fakturnika” w menu prawego przycisku dla PDF-ów i zdjęć."""
    if not integracja_dostepna():
        return False
    winreg = _rejestr()
    exe = str(sciezka_programu())
    for roz in ROZSZERZENIA_MENU:
        klucz = _klucz_menu(roz)
        if wlacz:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, klucz) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Dodaj do Fakturnika")
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, f'"{exe}",0')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, klucz + r"\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe}" --dodaj "%1"')
        else:
            for podklucz in (klucz + r"\command", klucz):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, podklucz)
                except OSError:
                    pass
    return True


def sciezka_skrotu() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "Fakturnik.lnk"


def sciezka_skrotu_menu_start() -> Path:
    """Skrót tworzony przez instalator (Menu Start bieżącego użytkownika)."""
    return (Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu"
            / "Programs" / "Fakturnik.lnk")


def utworz_skrot_na_pulpicie() -> bool:
    if not integracja_dostepna():
        return False
    if sciezka_skrotu().exists():
        return True
    menu_start = sciezka_skrotu_menu_start()
    if menu_start.exists():  # wersja z instalatora: wystarczy skopiować gotowy skrót (bez PowerShella)
        import shutil
        shutil.copyfile(menu_start, sciezka_skrotu())
        return True
    exe = str(sciezka_programu()).replace("'", "''")
    cel = str(sciezka_skrotu()).replace("'", "''")
    skrypt = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{cel}');"
              f"$s.TargetPath='{exe}';$s.WorkingDirectory='{str(Path(exe).parent)}';"
              f"$s.IconLocation='{exe},0';$s.Description='Fakturnik';$s.Save()")
    wynik = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", skrypt],
                           capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return wynik.returncode == 0


def popros_usluge_o_aktualizacje() -> bool:
    """Prosi usługę (zadanie Harmonogramu) o natychmiastowe sprawdzenie i pobranie aktualizacji w tle.
    Najlepszy wysiłek: gdy zwykłe konto nie może uruchomić zadania SYSTEM, usługa i tak zrobi to w swoim cyklu."""
    if not na_windows():
        return False
    import subprocess
    schtasks = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "schtasks.exe")
    for nazwa in (r"Fakturnik\Kopie co godzine", r"Fakturnik\Kopie po zalogowaniu"):
        try:
            if subprocess.run([schtasks, "/Run", "/TN", nazwa], capture_output=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=20).returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False
