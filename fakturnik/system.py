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

    def _polaczenie(self):
        gniazdo = self.serwer.nextPendingConnection()
        if gniazdo is None:
            return

        def odczytaj():
            try:
                dane = json.loads(bytes(gniazdo.readAll()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return
            if isinstance(dane, dict):
                self.polecenie.emit(dane)

        if gniazdo.bytesAvailable() or gniazdo.waitForReadyRead(1000):
            odczytaj()
        gniazdo.disconnected.connect(gniazdo.deleteLater)


def polecenie_z_argumentow(argumenty: list[str]) -> dict:
    """--dodaj plik1 plik2 … (menu prawego przycisku), --w-tle (autostart), bez argumentów: pokaż okno."""
    if "--dodaj" in argumenty:
        i = argumenty.index("--dodaj")
        return {"akcja": "dodaj", "pliki": [str(Path(p).resolve()) for p in argumenty[i + 1:] if Path(p).is_file()]}
    if "--w-tle" in argumenty:
        return {"akcja": "w_tle"}
    return {"akcja": "pokaz"}


# ---------------------------------------------------------------- rejestr Windows

def _rejestr():
    import winreg
    return winreg


def autostart_wlaczony() -> bool:
    if not integracja_dostepna():
        return False
    winreg = _rejestr()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KLUCZ_AUTOSTARTU) as k:
            wartosc, _ = winreg.QueryValueEx(k, NAZWA_WPISU)
            return str(sciezka_programu()) in wartosc
    except OSError:
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


def utworz_skrot_na_pulpicie() -> bool:
    if not integracja_dostepna():
        return False
    exe = str(sciezka_programu()).replace("'", "''")
    cel = str(sciezka_skrotu()).replace("'", "''")
    skrypt = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{cel}');"
              f"$s.TargetPath='{exe}';$s.WorkingDirectory='{str(Path(exe).parent)}';"
              f"$s.IconLocation='{exe},0';$s.Description='Fakturnik';$s.Save()")
    wynik = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", skrypt],
                           capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return wynik.returncode == 0
