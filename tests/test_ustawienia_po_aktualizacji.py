from fakturnik import baza as modul_bazy
from fakturnik.baza import Baza
from fakturnik.system import start_z_windows


def test_ustawienia_nie_zmieniaja_sie_po_aktualizacji(tmp_path, monkeypatch):
    b = Baza(tmp_path / "d.db")
    b.zapisz_ustawienia({"zaslona_sekund": "120"})  # zmienione przez użytkownika
    przed = b.ustawienia()
    b.zamknij()
    # nowa wersja zmienia wartości domyślne i dodaje nowe ustawienie
    nowe = dict(modul_bazy.DOMYSLNE_USTAWIENIA, zaslona_sekund="45", schowek_sekund="10", nowa_funkcja="1")
    monkeypatch.setattr(modul_bazy, "DOMYSLNE_USTAWIENIA", nowe)
    po = Baza(tmp_path / "d.db").ustawienia()
    assert po["zaslona_sekund"] == "120"
    assert po["schowek_sekund"] == przed["schowek_sekund"]  # nigdy niezapisana wartość też zostaje
    assert po["nowa_funkcja"] == "1"  # nowe ustawienie dostaje wartość domyślną
    assert {k: po[k] for k in przed} == przed


def test_start_z_windows_a_restart():
    assert start_z_windows(["--w-tle"])
    assert not start_z_windows(["--po-aktualizacji", "123", "--w-tle"])
    assert not start_z_windows(["--w-tle", "--restart"])
    assert not start_z_windows([])
