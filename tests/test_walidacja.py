from fakturnik.baza import Baza, Dokument, Pozycja, dokument_z_danych
from fakturnik.walidacja import (
    formatuj_konto, konto_poprawne, nip_poprawny, opis_identyfikatora, pesel_poprawny,
)


def test_pesel_nip_konto():
    assert pesel_poprawny("44051401359") and not pesel_poprawny("44051401358")
    assert nip_poprawny("526-025-02-74") and not nip_poprawny("5260250275")
    assert konto_poprawne("PL61 1090 1014 0000 0712 1981 2874")
    assert not konto_poprawne("61 1090 1014 0000 0712 1981 2875")
    assert formatuj_konto("61109010140000071219812874") == "61 1090 1014 0000 0712 1981 2874"
    assert opis_identyfikatora("44051401359") == ("PESEL poprawny", True)
    assert opis_identyfikatora("5260250275")[1] is False
    assert opis_identyfikatora("123")[1] is False
    assert opis_identyfikatora("") is None


def test_nieznane_pola_z_innej_wersji_sa_pomijane():
    d = dokument_z_danych(7, {"numer": "FV/1/10/2026", "data_wystawienia": "2026-10-01", "data_uslugi": "2026-10-01",
                              "platnosc": "przelew", "nabywca": "Firma", "termin_platnosci": "2026-10-15",
                              "nieoplacony": True, "pozycje": [{"nazwa": "x", "ilosc": 1, "cena": 5, "rabat": 0}]})
    assert d.id == 7 and d.suma == 5


def test_wydruk_numeru_konta(tmp_path):
    from fakturnik import druk
    b = Baza(tmp_path / "d.db")
    b.zapisz_ustawienia({"konto": "61109010140000071219812874"})
    d = Dokument("FV/1/10/2026", "2026-10-01", "2026-10-01", "przelew", "Firma", pozycje=[Pozycja("x", 1, 900)])
    assert "61 1090 1014" in druk.html_dokumentu(d, b.ustawienia())


def test_polecenia_z_wiersza_polecen(tmp_path):
    from fakturnik.system import polecenie_z_argumentow
    plik = tmp_path / "faktura.pdf"
    plik.write_bytes(b"%PDF")
    assert polecenie_z_argumentow([]) == {"akcja": "pokaz"}
    assert polecenie_z_argumentow(["--w-tle"]) == {"akcja": "w_tle"}
    p = polecenie_z_argumentow(["--dodaj", str(plik), str(tmp_path / "nie-ma.pdf")])
    assert p["akcja"] == "dodaj" and p["pliki"] == [str(plik.resolve())]


def test_sila_hasla():
    from fakturnik.kreator import sila_hasla
    assert sila_hasla("krotkie")[0].startswith("Za krótkie")
    assert sila_hasla("abcdefgh")[0].startswith("Słabe")
    assert sila_hasla("Tajne-Haslo-2026")[0] == "Silne"
