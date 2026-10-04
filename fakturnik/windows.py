"""Dodatki tylko dla Windows: ochrona okien przed nagrywaniem ekranu, restart po aktualizacji systemu,
grupowanie na pasku zadań i znacznik działającego programu dla instalatora.

Każda funkcja poza Windows (lub gdy funkcja systemu jest niedostępna) po prostu nic nie robi,
a błąd wywołania systemowego nigdy nie zatrzymuje programu.
"""

import sys

ID_APLIKACJI = "TeodorTeo.Fakturnik"
NAZWA_MUTEKSU = "FakturnikUruchomiony"  # ten sam w instalatorze (AppMutex): instalator poprosi o zamknięcie

WDA_NONE = 0x0
WDA_MONITOR = 0x1
WDA_EXCLUDEFROMCAPTURE = 0x11  # Windows 10 2004 i nowsze: okno znika z nagrań i zrzutów ekranu

_muteks = None


def na_windows() -> bool:
    return sys.platform == "win32"


def przygotuj_proces() -> None:
    """Wywoływane raz przy starcie programu."""
    if not na_windows():
        return
    import ctypes
    global _muteks
    try:
        # własna ikona i nazwa na pasku zadań oraz w powiadomieniach (zamiast „python”)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APLIKACJI)
    except (AttributeError, OSError):
        pass
    try:
        _muteks = ctypes.windll.kernel32.CreateMutexW(None, False, NAZWA_MUTEKSU)
    except (AttributeError, OSError):
        pass
    try:
        # po ponownym uruchomieniu komputera przez aktualizację Windows program wraca sam (w tle)
        ctypes.windll.kernel32.RegisterApplicationRestart("--w-tle --restart", 0)
    except (AttributeError, OSError):
        pass


def ochrona_przed_przechwytywaniem(okno_hwnd: int, wlacz: bool) -> bool:
    """Wyłącza (lub przywraca) widoczność okna w zrzutach i nagraniach ekranu innych programów.

    Programy robiące zrzuty ekranu (także narzędzia AI „sterujące komputerem”, nagrywarki i większość
    programów zdalnego dostępu) zobaczą w tym miejscu czarny prostokąt. Zwraca True, gdy się udało.
    """
    if not na_windows() or not okno_hwnd:
        return False
    import ctypes
    from ctypes import wintypes
    try:
        ustaw = ctypes.windll.user32.SetWindowDisplayAffinity
    except (AttributeError, OSError):
        return False
    ustaw.argtypes = [wintypes.HWND, wintypes.DWORD]
    ustaw.restype = wintypes.BOOL
    if not wlacz:
        return bool(ustaw(okno_hwnd, WDA_NONE))
    return bool(ustaw(okno_hwnd, WDA_EXCLUDEFROMCAPTURE) or ustaw(okno_hwnd, WDA_MONITOR))


# ---------------------------------------------------------------- blokowanie i odblokowanie komputera

WM_WTSSESSION_CHANGE = 0x02B1
ZDARZENIA_SESJI = {
    0x1: "podłączono konsolę", 0x2: "odłączono konsolę",
    0x3: "ZDALNE POŁĄCZENIE z komputerem", 0x4: "zakończono zdalne połączenie",
    0x5: "zalogowano do Windows", 0x6: "wylogowano z Windows",
    0x7: "komputer zablokowany", 0x8: "komputer odblokowany",
}
BLOKADA, ODBLOKOWANIE = 0x7, 0x8


def sledz_sesje(okno_hwnd: int) -> bool:
    """Prosi Windows o powiadomienia o blokowaniu, odblokowaniu, logowaniu i połączeniach zdalnych."""
    if not na_windows() or not okno_hwnd:
        return False
    import ctypes
    from ctypes import wintypes
    try:
        rejestruj = ctypes.windll.wtsapi32.WTSRegisterSessionNotification
        rejestruj.argtypes = [wintypes.HWND, wintypes.DWORD]
        return bool(rejestruj(okno_hwnd, 0))  # NOTIFY_FOR_THIS_SESSION
    except (AttributeError, OSError):
        return False


def zdarzenie_sesji(wiadomosc_wskaznik: int) -> int | None:
    """Z komunikatu okna (nativeEvent) odczytuje zdarzenie sesji Windows albo None."""
    from ctypes import wintypes
    msg = wintypes.MSG.from_address(wiadomosc_wskaznik)
    return int(msg.wParam) if msg.message == WM_WTSSESSION_CHANGE else None


def nieudane_logowania(od) -> int | None:
    """Liczba nieudanych prób zalogowania lub odblokowania Windows od chwili `od` (zdarzenie 4625
    w dzienniku zabezpieczeń). Wymaga uprawnień administratora; None, gdy nie da się sprawdzić."""
    if not na_windows():
        return None
    import subprocess
    from datetime import timezone
    od_utc = od.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    zapytanie = f"*[System[(EventID=4625) and TimeCreated[@SystemTime>='{od_utc}']]]"
    try:
        wynik = subprocess.run(["wevtutil", "qe", "Security", f"/q:{zapytanie}", "/f:xml", "/c:200"],
                               capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    if wynik.returncode != 0:
        return None  # brak uprawnień do dziennika zabezpieczeń
    return wynik.stdout.count(b"<Event ")


# ---------------------------------------------------------------- tapeta pulpitu

SPI_GETDESKWALLPAPER = 0x0073
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE_SENDCHANGE = 0x01 | 0x02


def obecna_tapeta() -> str | None:
    if not na_windows():
        return None
    import ctypes
    bufor = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(bufor), bufor, 0):
        return bufor.value or None
    return None


def ustaw_tapete(sciezka: str) -> bool:
    if not na_windows():
        return False
    import ctypes
    return bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, str(sciezka),
                                                           SPIF_UPDATEINIFILE_SENDCHANGE))


def bezczynnosc_sekund() -> float | None:
    """Ile sekund minęło od ostatniego ruchu myszy lub klawisza w całym systemie (nie tylko w programie)."""
    if not na_windows():
        return None
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000
    except Exception:  # noqa: BLE001
        return None
