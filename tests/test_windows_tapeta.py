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
    for wariant in tapeta.WARIANTY:
        plik = tapeta.zapisz(wariant, tmp_path, 640, 360, "Gabinet")
        from PySide6.QtGui import QImage
        obraz = QImage(str(plik))
        assert (obraz.width(), obraz.height()) == (640, 360)
