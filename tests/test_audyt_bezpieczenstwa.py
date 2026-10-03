import json
import shutil

import pytest

from fakturnik import konta, usluga
from fakturnik.baza import Baza, Dokument, Pozycja


def test_rola_konta_z_zaszyfrowanych_danych_nie_z_pliku_kont(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("haslo-wlasciciela")
    id_ = b.dodaj_konto("Kasia", "haslo-kasi-123")
    plik = tmp_path / konta.PLIK_KONT
    dane = json.loads(plik.read_text(encoding="utf-8"))
    dane["konta"][0]["rola"] = "wlascicielka"  # próba nadania sobie roli właściciela
    dane["konta"][0]["nazwa"] = "Właściciel"
    plik.write_text(json.dumps(dane), encoding="utf-8")
    wpis, _ = konta.zaloguj(tmp_path, "haslo-kasi-123")
    assert wpis["rola"] == "wlascicielka"  # plik da się zmienić...
    assert b.konto(id_) == {"id": id_, "nazwa": "Kasia", "rola": "asystentka"}  # ...ale program mu nie wierzy
    assert b.konto("nie-ma") is None


def test_kopia_bez_szyfrowania_nie_zastapi_zaszyfrowanych_danych(tmp_path):
    jawna = Baza(tmp_path / "jawna.db")
    jawna.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "X", pozycje=[Pozycja("A", 1, 1)]))
    jawna.zamknij()
    assert Baza.da_sie_otworzyc(tmp_path / "jawna.db", None)
    assert not Baza.da_sie_otworzyc(tmp_path / "jawna.db", "dowolne-haslo")


@pytest.mark.skipif(not hasattr(__import__("os"), "symlink"), reason="brak dowiązań")
def test_usluga_nie_idzie_za_dowiazaniami(tmp_path):
    profil = tmp_path / "Users" / "gabinet"
    dane = profil / usluga.NAZWA_DANYCH
    Baza(dane / "fakturnik.db").zamknij()
    usluga.sprawdz_sciezke(dane, profil)  # zwykłe katalogi: w porządku

    tajne = tmp_path / "tajne"
    tajne.mkdir()
    (tajne / ("a" * 32 + ".bin")).write_bytes(b"cudze")
    (dane / "pliki").mkdir(exist_ok=True)
    shutil.rmtree(dane / "pliki")
    (dane / "pliki").symlink_to(tajne, target_is_directory=True)
    cel = tmp_path / "kopie" / "gabinet"
    usluga.kopia_uzytkownika(dane, cel)
    assert not (cel / "pliki" / ("a" * 32 + ".bin")).exists()  # nie skopiowano przez dowiązanie

    dowiazany = tmp_path / "Users" / "zly"
    dowiazany.symlink_to(profil, target_is_directory=True)
    with pytest.raises(usluga.Dowiazanie):
        usluga.sprawdz_sciezke(dowiazany / usluga.NAZWA_DANYCH, dowiazany)
