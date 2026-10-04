import hashlib
import io
import sqlite3
from datetime import date

import pytest

from fakturnik import aktualizacje
from fakturnik.aktualizacje import BladAktualizacji, Wydanie
from fakturnik.baza import WERSJA_DANYCH, Baza, NowszaBaza
from fakturnik.szyfrowanie import Szyfr


def plik_starej_wersji(sciezka, haslo=None):
    """Plik danych w postaci zapisywanej przez pierwszą wersję programu (bez numeru wersji danych)."""
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE ustawienia (klucz TEXT PRIMARY KEY, wartosc TEXT);
        CREATE TABLE liczniki (miesiac TEXT PRIMARY KEY, ostatni INTEGER);
        CREATE TABLE dokumenty (id INTEGER PRIMARY KEY AUTOINCREMENT, numer TEXT NOT NULL,
            data_wystawienia TEXT NOT NULL, dane TEXT NOT NULL, utworzono TEXT DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO ustawienia VALUES ('nip', '639-000-00-00');
        INSERT INTO liczniki VALUES ('2026-10', 5);
        INSERT INTO dokumenty (numer, data_wystawienia, dane) VALUES ('5/10/2026', '2026-10-02',
            '{"numer": "5/10/2026", "data_wystawienia": "2026-10-02", "data_uslugi": "2026-10-02",
              "platnosc": "gotówka", "nabywca": "Jan Kowalski", "nabywca_adres": "", "nabywca_id": "",
              "pozycje": [{"nazwa": "Konsultacja", "ilosc": 1, "cena": 200}]}');
    """)
    db.commit()
    dane = db.serialize()
    sciezka.write_bytes(Szyfr(haslo).zaszyfruj(dane) if haslo else dane)


@pytest.mark.parametrize("haslo", [None, "tajnehaslo"])
def test_dane_przezywaja_aktualizacje(tmp_path, haslo):
    plik = tmp_path / "fakturnik.db"
    plik_starej_wersji(plik, haslo)

    b = Baza(plik, haslo)
    assert [d.nabywca for d in b.dokumenty()] == ["Jan Kowalski"]
    assert b.ustawienia()["nip"] == "639-000-00-00"
    assert b.nastepny_numer(date(2026, 10, 9)) == "6/10/2026"
    assert b.ma_haslo == bool(haslo)
    # przed przerobieniem danych została kopia oryginalnego pliku
    assert (tmp_path / "fakturnik-przed-migracja-v0.db").exists()
    b.zamknij()

    b = Baza(plik, haslo)  # kolejne uruchomienie: bez ponownej migracji i bez utraty danych
    assert len(b.dokumenty()) == 1


def test_starsza_wersja_nie_psuje_nowszych_danych(tmp_path):
    plik = tmp_path / "fakturnik.db"
    b = Baza(plik)
    b.db.execute(f"PRAGMA user_version = {WERSJA_DANYCH + 1}")
    b._utrwal()
    b.zamknij()
    przed = plik.read_bytes()
    with pytest.raises(NowszaBaza):
        Baza(plik)
    assert plik.read_bytes() == przed


def test_porownanie_wersji():
    assert aktualizacje.jest_nowsza("1.0.12", "1.0.9")
    assert not aktualizacje.jest_nowsza("1.0.9", "1.0.12")
    assert not aktualizacje.jest_nowsza("1.0.9", "1.0.9")
    assert aktualizacje.jest_nowsza("v1.1.0", "1.0.99")


def test_podmiana_exe_i_sprzatanie(tmp_path):
    obecny = tmp_path / "Fakturnik.exe"
    obecny.write_bytes(b"stara")
    nowy = tmp_path / "Fakturnik.new.exe"
    nowy.write_bytes(b"nowa")
    aktualizacje.zainstaluj(nowy, obecny)
    assert obecny.read_bytes() == b"nowa"
    assert (tmp_path / "Fakturnik.old.exe").read_bytes() == b"stara"
    aktualizacje.posprzataj(obecny)
    assert not (tmp_path / "Fakturnik.old.exe").exists()


class Odpowiedz(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def podstaw_serwer(monkeypatch, exe: bytes, suma: str):
    pliki = {"https://github.com/x/Fakturnik.exe": exe, "https://github.com/x/Fakturnik.exe.sha256": suma.encode()}
    monkeypatch.setattr(aktualizacje, "_pobierz", lambda adres, timeout=10: Odpowiedz(pliki[adres]))
    return Wydanie("9.9.9", "", "https://github.com/x/Fakturnik.exe", "https://github.com/x/Fakturnik.exe.sha256",
                   len(exe))


def test_pobieranie_sprawdza_sha256(tmp_path, monkeypatch):
    exe = b"nowy program" * 1000
    wydanie = podstaw_serwer(monkeypatch, exe, hashlib.sha256(exe).hexdigest() + "  Fakturnik.exe\n")
    cel = aktualizacje.pobierz(wydanie, tmp_path / "Fakturnik.new.exe")
    assert cel.read_bytes() == exe


def test_podmieniony_plik_jest_odrzucany(tmp_path, monkeypatch):
    wydanie = podstaw_serwer(monkeypatch, b"zlosliwy", hashlib.sha256(b"oryginal").hexdigest())
    with pytest.raises(BladAktualizacji):
        aktualizacje.pobierz(wydanie, tmp_path / "Fakturnik.new.exe")
    assert not (tmp_path / "Fakturnik.new.exe").exists()


def test_tylko_zaufane_adresy():
    with pytest.raises(BladAktualizacji):
        aktualizacje._pobierz("https://zly-serwer.example/Fakturnik.exe")
    with pytest.raises(BladAktualizacji):
        aktualizacje._pobierz("http://github.com/Fakturnik.exe")


def test_sprawdzenie_wlasnego_pliku(tmp_path, monkeypatch):
    exe = tmp_path / "Fakturnik.exe"
    exe.write_bytes(b"MZ oryginalny program")
    skrot = hashlib.sha256(exe.read_bytes()).hexdigest()

    def falszywe_pobieranie(adres, timeout=10):
        if adres.endswith("/releases/tags/v1.0.5"):
            return io.BytesIO(b'{"assets": [{"name": "Fakturnik.exe.sha256", '
                              b'"browser_download_url": "https://github.com/x/Fakturnik.exe.sha256"}]}')
        return io.BytesIO(skrot.encode())

    monkeypatch.setattr(aktualizacje, "_pobierz", falszywe_pobieranie)
    assert aktualizacje.sprawdz_wlasny_plik(exe, "1.0.5") is True
    exe.write_bytes(b"MZ podmieniony program")
    assert aktualizacje.sprawdz_wlasny_plik(exe, "1.0.5") is False
    assert aktualizacje.sprawdz_wlasny_plik(exe, "9.9.9") is None  # brak wydania / internetu


def test_instalacja_usuwa_stara_wersje_tylko_do_odczytu(tmp_path):
    from fakturnik.ochrona import tylko_do_odczytu
    obecny, nowy = tmp_path / "Fakturnik.exe", tmp_path / "Fakturnik.new.exe"
    obecny.write_bytes(b"v1")
    nowy.write_bytes(b"v2")
    stary = tmp_path / "Fakturnik.old.exe"
    stary.write_bytes(b"v0")
    tylko_do_odczytu(stary, True)
    aktualizacje.zainstaluj(nowy, obecny)
    assert obecny.read_bytes() == b"v2" and stary.read_bytes() == b"v1"
    tylko_do_odczytu(stary, True)
    aktualizacje.posprzataj(obecny)
    assert not stary.exists()


def test_nowa_wersja_czeka_na_zamkniecie_starej():
    import subprocess
    import sys
    import time
    import threading
    stara = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"])
    threading.Thread(target=stara.wait, daemon=True).start()  # jak system: zakończony proces znika
    start = time.monotonic()
    assert aktualizacje.czekaj_na_poprzednia(["--po-aktualizacji", str(stara.pid), "--w-tle"], limit_s=10) \
        == ["--w-tle"]
    assert stara.poll() is not None and time.monotonic() - start < 10
    assert aktualizacje.czekaj_na_poprzednia(["--dodaj", "a.pdf"]) == ["--dodaj", "a.pdf"]
    assert aktualizacje.czekaj_na_poprzednia(["--po-aktualizacji", "x"]) == []


def test_zainstalowany_w_program_files(tmp_path, monkeypatch):
    pf = tmp_path / "Program Files"
    (pf / "Fakturnik").mkdir(parents=True)
    monkeypatch.setenv("ProgramFiles", str(pf))
    assert aktualizacje.zainstalowany(pf / "Fakturnik" / "Fakturnik.exe")  # nawet gdy folder jest zapisywalny
    (tmp_path / "Pobrane").mkdir()
    assert not aktualizacje.zainstalowany(tmp_path / "Pobrane" / "Fakturnik.exe")
