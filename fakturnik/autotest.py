"""Autotest programu (Fakturnik.exe --autotest <plik wyniku>), uruchamiany przez usługę aktualizacji.

Nowa wersja jest najpierw uruchamiana w tym trybie, zanim zastąpi działającą: musi wczytać wszystkie
swoje moduły (także interfejs i biblioteki Qt), zaszyfrować i odszyfrować dane, otworzyć bazę
w folderze tymczasowym i narysować okno w pamięci. Dopiero „AUTOTEST OK <wersja>” w pliku wyniku
pozwala ją zainstalować; inaczej zostaje poprzednia, działająca wersja. Nie dotyka danych gabinetu.
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path

MODULY = ["aktualizacje", "autotest", "baza", "druk", "godziny", "gtd", "kalkulator", "konta", "kontrola", "mf",
          "narzedzia", "ochrona", "skaner", "slownie", "system", "szyfrowanie", "tapeta", "urzadzenie", "usluga",
          "walidacja", "windows", "zaslona", "ui"]


def uruchom(plik_wyniku: str) -> int:
    from .wersja import WERSJA
    wynik = Path(plik_wyniku)
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import importlib
        for m in MODULY:
            importlib.import_module(f"fakturnik.{m}")
        from .szyfrowanie import Szyfr
        szyfr = Szyfr("autotest-haslo")
        dane, _ = Szyfr.otworz(szyfr.zaszyfruj(b"fakturnik"), "autotest-haslo")
        assert dane == b"fakturnik"
        from .baza import DOMYSLNE_USTAWIENIA, Baza, Dokument, Pozycja
        with tempfile.TemporaryDirectory() as katalog:
            b = Baza(Path(katalog) / "autotest.db")
            b.zapisz_dokument(Dokument("1/01/2026", "2026-01-01", "2026-01-01", "gotówka", "Test",
                                       pozycje=[Pozycja("A", 1, 1)]))
            assert len(b.dokumenty()) == 1
            b.zamknij()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from . import druk
        proba = Dokument("1/01/2026", "2026-01-01", "2026-01-01", "gotówka", "Test", pozycje=[Pozycja("A", 1, 1)])
        druk.html_dokumentu(proba, dict(DOMYSLNE_USTAWIENIA), False, False)
        druk.pdf_dokumentu(proba, dict(DOMYSLNE_USTAWIENIA))  # PDF-y wystawionych dokumentów do Plików
        del app
        wynik.write_text(f"AUTOTEST OK {WERSJA}\n", encoding="utf-8")
        return 0
    except BaseException:  # noqa: BLE001 - każdy błąd = wersja nie nadaje się do instalacji
        try:
            wynik.write_text("AUTOTEST BLAD\n" + traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(uruchom(sys.argv[1] if len(sys.argv) > 1 else "autotest.txt"))
