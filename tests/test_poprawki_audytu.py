from datetime import date

import pytest

from fakturnik.baza import Baza, Dokument, Pozycja


def test_liczby_wpisywane_po_polsku():
    from fakturnik.ui import ilosc_z_tekstu, liczba, liczba_lub_none
    assert liczba("1 200,50") == 1200.5
    assert liczba("1.200,00") == 1200.0
    assert liczba("150 zł") == 150.0
    assert liczba("900.00") == 900.0
    assert liczba_lub_none("nan") is None and liczba_lub_none("1e400") is None and liczba_lub_none("abc") is None
    assert ilosc_z_tekstu("") == 1.0 and ilosc_z_tekstu("0") == 0.0 and ilosc_z_tekstu("x") is None


def test_wyszukiwanie_bez_hasla_nie_pokazuje_wszystkiego():
    from fakturnik.ui import zapytanie_dozwolone
    for zle in ("20", "2026", "01", "/10/2026", "ab", "FV"):
        assert not zapytanie_dozwolone(zle), zle
    for dobre in ("Kow", "Nowak", "44051401359", "3/10/2026", "FV/3/10/2026"):
        assert zapytanie_dozwolone(dobre), dobre


def test_numeracja_roczna_i_ciagla(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_ustawienia({"format_numeru": "{n}/{rrrr}"})
    b.zapisz_dokument(Dokument("1/2026", "2026-01-15", "2026-01-15", "gotówka", "A", pozycje=[Pozycja("x", 1, 1)]))
    assert b.nastepny_numer(date(2026, 2, 1)) == "2/2026"  # nie zaczyna od 1 w lutym
    assert b.nastepny_numer(date(2027, 1, 1)) == "1/2027"
    b.zapisz_ustawienia({"format_numeru": "R{n}"})
    b.zapisz_dokument(Dokument("R1", "2026-01-15", "2026-01-15", "gotówka", "A", pozycje=[Pozycja("x", 1, 1)]))
    assert b.nastepny_numer(date(2027, 5, 1)) == "R2"
    # domyślny format z miesiącem dalej liczy od nowa co miesiąc
    b.zapisz_ustawienia({"format_numeru": "{n}/{mm}/{rrrr}"})
    assert b.nastepny_numer(date(2026, 3, 1)) == "1/03/2026"


def test_kartoteka_pacjentow_bez_nadpisywania(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_pacjenta("B", "44051401359", "ul. B", nowy=True)
    b.zapisz_pacjenta("C", nowy=True)
    with pytest.raises(ValueError):
        b.zapisz_pacjenta("B", stara_nazwa="C")  # zmiana nazwy na istniejącą
    with pytest.raises(ValueError):
        b.zapisz_pacjenta("B", nowy=True)
    assert b.pacjent("B").identyfikator == "44051401359"
    b.usun_pacjenta("C")
    assert b.pacjent("C") is None
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "C", pozycje=[Pozycja("x", 1, 5)]))
    assert b.pacjent("C").dokumentow == 1  # po nowym dokumencie pacjent wraca z dokumentami
