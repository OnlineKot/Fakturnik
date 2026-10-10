import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def zaslona(tryb):
    from fakturnik.zaslona import Zaslona
    z = Zaslona("Gabinet", 10, tryb=tryb, sprawdz_pin=lambda p: p == "2580",
                sprawdz_haslo=lambda h: h == "Tajne Hasło!")
    z._poll_aktywny = False  # w testach podajemy klawisze przez _klawisz_windows (na Windows liczyłby je odczyt stanu)
    stan = {"zamknieta": False, "proby": False}
    z.zamknieta.connect(lambda: stan.update(zamknieta=True))
    z.za_duzo_prob.connect(lambda: stan.update(proby=True))
    return z, stan


def klawisze(app, z, lista):
    for vk, znak in lista:
        z._klawisz_windows(vk, False, znak)
        app.processEvents()
    koniec = time.monotonic() + 1.0
    while time.monotonic() < koniec:
        app.processEvents()


def test_dowolny_klawisz(app):
    z, stan = zaslona("dowolny")
    klawisze(app, z, [(0x41, "a")])
    assert z.zamykanie


def test_haslo_po_spacji(app):
    z, stan = zaslona("haslo")
    klawisze(app, z, [(0x41, c) for c in "Tajne Hasło!"] + [(0x0D, "\r")])
    assert not z.zamykanie  # bez spacji hasło nie jest przyjmowane
    klawisze(app, z, [(0x20, " ")] + [(0x41, c) for c in "Tajne Hasło!"] + [(0x0D, "\r")])
    assert z.zamykanie


def test_blokada_po_wielu_blednych_haslach(app):
    from fakturnik.zaslona import PROBY_PIN
    z, stan = zaslona("haslo")
    klawisze(app, z, ([(0x20, " "), (0x41, "x"), (0x0D, "\r")]) * PROBY_PIN)
    assert PROBY_PIN == 10 and stan["proby"] and not z.zamykanie


def test_pin_i_bez_sposobu_sprawdzenia(app):
    from fakturnik.zaslona import Zaslona
    z, stan = zaslona("pin")
    klawisze(app, z, [(0x32, ""), (0x35, ""), (0x38, ""), (0x30, ""), (0x0D, "\r")])
    assert z.zamykanie
    assert Zaslona("G", 10, tryb="haslo").tryb == "spacje"  # bez sprawdzania hasła: zawsze spacje
    assert Zaslona("G", 10, tryb="cos").tryb == "spacje"
