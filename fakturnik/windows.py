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
        ctypes.windll.kernel32.RegisterApplicationRestart("--w-tle", 0)
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
