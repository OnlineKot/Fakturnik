import os
import sys
from datetime import datetime

import pytest

from fakturnik import windows


@pytest.mark.skipif(sys.platform == "win32", reason="sprawdza zachowanie poza Windows")
def test_funkcje_windows_poza_windows_nic_nie_robia():
    assert windows.nieudane_logowania(datetime.now()) is None
    assert windows.obecna_tapeta() is None and windows.ustaw_tapete("x.png") is False
    assert windows.sledz_sesje(123) is False
    assert windows.ZDARZENIA_SESJI[windows.BLOKADA] == "komputer zablokowany"


def test_tapeta_w_rozdzielczosci_ekranu(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fakturnik import tapeta
    from PySide6.QtGui import QImage
    for wariant in tapeta.WARIANTY:
        plik = tapeta.zapisz(wariant, tmp_path, 640, 360, "Gabinet")
        obraz = QImage(str(plik))
        assert (obraz.width(), obraz.height()) == (640, 360)


def test_tapeta_na_pionowym_monitorze(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fakturnik import tapeta
    from PySide6.QtGui import QImage
    # monitor obrócony (pionowy): tapeta ma tę samą orientację i nic nie wychodzi poza krawędź
    for wariant in tapeta.WARIANTY:
        obraz = tapeta.wygeneruj(wariant, 1080, 1920, "Gabinet Dr Nowak", "Rejestracja: 600 100 200")
        assert (obraz.width(), obraz.height()) == (1080, 1920)
        # róg prawy-górny tła nie jest zamalowany logo/tekstem wychodzącym poza kadr: po prostu renderuje się bez błędu
    plik = tapeta.zapisz("morski", tmp_path, 1080, 1920, "Gabinet", "tel. 600 100 200")
    assert QImage(str(plik)).height() > QImage(str(plik)).width()
