import sys
from pathlib import Path

import pytest

from fakturnik import aktualizacje, usluga

STARY = b"MZ" + b"stara wersja" + b"\0" * (2 * 1024 * 1024)
NOWY = b"MZ" + b"nowa wersja" + b"\0" * (2 * 1024 * 1024)


@pytest.fixture
def srodowisko(tmp_path, monkeypatch):
    program = tmp_path / "Program Files" / "Fakturnik"
    program.mkdir(parents=True)
    exe = program / "Fakturnik.exe"
    exe.write_bytes(STARY)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(aktualizacje, "czy_spakowany", lambda: True)
    monkeypatch.setattr(usluga, "katalog_uslugi", lambda: tmp_path / "ProgramData")
    monkeypatch.setattr(aktualizacje, "sprawdz", lambda: aktualizacje.Wydanie("1.0.99", "", "https://github.com/a",
                                                                              "https://github.com/b", len(NOWY)))

    def pobierz(wydanie, cel, postep=None):
        Path(cel).write_bytes(NOWY)
        return Path(cel)
    monkeypatch.setattr(aktualizacje, "pobierz", pobierz)
    return exe


def test_udana_aktualizacja(srodowisko, monkeypatch):
    testy = []
    monkeypatch.setattr(usluga, "autotest_programu", lambda exe, wersja="": (testy.append(exe.name) or (True, "OK")))
    assert "zainstalowano wersję 1.0.99" in usluga.aktualizuj_program()
    assert srodowisko.read_bytes() == NOWY
    assert testy == ["Fakturnik-1.0.99.exe", "Fakturnik.exe"]  # autotest przed i po instalacji


def test_wadliwa_wersja_nie_jest_instalowana_i_pomijana_przez_dobe(srodowisko, monkeypatch):
    monkeypatch.setattr(usluga, "autotest_programu", lambda exe, wersja="": (False, "ImportError: brak modułu"))
    wynik = usluga.aktualizuj_program()
    assert "odrzucono wersję 1.0.99" in wynik and srodowisko.read_bytes() == STARY
    assert "pominięto wersję 1.0.99" in usluga.aktualizuj_program()


def test_wycofanie_gdy_zainstalowana_wersja_nie_dziala(srodowisko, monkeypatch):
    monkeypatch.setattr(usluga, "autotest_programu",
                        lambda exe, wersja="": (True, "OK") if exe.name.startswith("Fakturnik-") else (False, "awaria"))
    assert "wycofano wersję 1.0.99" in usluga.aktualizuj_program()
    assert srodowisko.read_bytes() == STARY  # wróciła poprzednia, działająca wersja


def test_pobrany_plik_ktory_nie_jest_programem(srodowisko, monkeypatch):
    monkeypatch.setattr(aktualizacje, "pobierz", lambda w, cel, postep=None: Path(cel).write_bytes(b"<html>") or cel)
    monkeypatch.setattr(usluga, "autotest_programu", lambda exe, wersja="": (True, "OK"))
    assert "nie jest programem" in usluga.aktualizuj_program() and srodowisko.read_bytes() == STARY


def test_jedna_aktualizacja_naraz(srodowisko, monkeypatch, tmp_path):
    with usluga._Blokada(tmp_path / "ProgramData" / "aktualizacja.lock") as moja:
        assert moja
        assert "inna aktualizacja w toku" in usluga.aktualizuj_program()


def test_autotest_zrodel(tmp_path):
    """Autotest uruchomiony naprawdę (wersja ze źródeł)."""
    from fakturnik import autotest
    wynik = tmp_path / "wynik.txt"
    assert autotest.uruchom(str(wynik)) == 0 and wynik.read_text().startswith("AUTOTEST OK")
