import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import fakturnik.ui as ui
import fakturnik.windows as windows


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def bez_blokady_windows(monkeypatch):
    monkeypatch.setattr(windows, "zablokuj_windows", lambda: True)
    ui.OknoHasla._wczytano = True
    ui.OknoHasla._nieudane = 0
    ui.OknoHasla._blokada_do = 0.0


def okno(app):
    return ui.OknoHasla(lambda h: h == "dobre", "Fakturnik jest zablokowany", cel="odblokowanie",
                        ekran_blokady={"gabinet": "G", "godziny": ""})


def test_wielokrotne_zle_haslo_nie_zamyka_programu(app):
    d = okno(app)
    stan = {"reject": False}
    d.rejected.connect(lambda: stan.update(reject=True))
    for _ in range(25):
        ui.OknoHasla._blokada_do = 0.0  # pomijamy przerwy między próbami
        d.pole.setText("zle")
        d.sprobuj()
    assert stan["reject"] is False  # złe hasło NIGDY nie zamyka okna ani programu


def test_esc_nie_zamyka_ekranu_blokady(app):
    d = okno(app)
    stan = {"reject": False}
    d.rejected.connect(lambda: stan.update(reject=True))
    d.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert stan["reject"] is False


def test_dobre_haslo_dziala_i_zeruje_licznik(app):
    d = okno(app)
    stan = {"accept": False}
    d.accepted.connect(lambda: stan.update(accept=True))
    d.pole.setText("zle"); d.sprobuj()
    ui.OknoHasla._blokada_do = 0.0
    d.pole.setText("dobre"); d.sprobuj()
    assert stan["accept"] is True and ui.OknoHasla._nieudane == 0


def test_blad_sprawdzania_nie_wywala_okna(app):
    def sprawdz(_):
        raise RuntimeError("awaria")
    d = ui.OknoHasla(sprawdz, "Fakturnik", cel="odblokowanie")
    stan = {"reject": False, "accept": False}
    d.rejected.connect(lambda: stan.update(reject=True))
    d.accepted.connect(lambda: stan.update(accept=True))
    d.pole.setText("cokolwiek"); d.sprobuj()
    assert not stan["reject"] and not stan["accept"]
