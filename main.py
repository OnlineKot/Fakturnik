import os
import subprocess
import sys


def _uruchom_od_nowa() -> None:
    """Start po aktualizacji ze starej wersji (do 1.0.12): stara wersja przekazywała nowej swoje
    zmienne PyInstallera, więc nowa szukała bibliotek w usuniętym już folderze tymczasowym starej.
    Wtedy uruchamiamy się jeszcze raz w czystym środowisku (tylko raz, żeby nie zapętlić)."""
    srodowisko = {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}
    srodowisko["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    srodowisko["FAKTURNIK_PONOWNY_START"] = "1"
    flagi = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, *sys.argv[1:]], env=srodowisko, creationflags=flagi, close_fds=True)


if __name__ == "__main__":
    try:
        from fakturnik.ui import uruchom
    except ImportError:
        if not getattr(sys, "frozen", False) or os.environ.get("FAKTURNIK_PONOWNY_START"):
            raise
        _uruchom_od_nowa()
        sys.exit(0)
    os.environ.pop("FAKTURNIK_PONOWNY_START", None)  # kolejne aktualizacje znów mogą skorzystać z tej ochrony
    sys.exit(uruchom())
