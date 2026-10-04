import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fakturnik import druk
from fakturnik.baza import DOMYSLNE_USTAWIENIA, KATEGORIA_WYSTAWIONE, Baza, Dokument, Pozycja


def rachunek(numer="1/10/2026"):
    return Dokument(numer, "2026-10-02", "2026-10-02", "gotówka", "Jan Kowalski", nabywca_id="44051401458",
                    pozycje=[Pozycja("Leczenie", 1, 300)])


def test_pdf_kazdej_wersji_dokumentu_raz(tmp_path):
    b = Baza(tmp_path / "d.db")
    dok = b.zapisz_dokument(rachunek())
    assert [d.numer for d in b.dokumenty_bez_pdf()] == ["1/10/2026"]
    plik = b.dodaj_pdf_dokumentu(dok, b"%PDF-1.4 wystawiony")
    assert plik.kategoria == KATEGORIA_WYSTAWIONE and plik.osoba == "Jan Kowalski"
    assert plik.nazwa == "Rachunek 1-10-2026.pdf" and plik.data == "2026-10-02"
    assert b.tresc_pliku(plik.id) == b"%PDF-1.4 wystawiony"
    assert b.dodaj_pdf_dokumentu(b.dokument(dok.id), b"%PDF-1.4 drugi raz") is None  # bez duplikatów
    assert b.dokumenty_bez_pdf() == []

    b.zaktualizuj_dokument(b.dokument(dok.id), "literówka")
    assert len(b.dokumenty_bez_pdf()) == 1  # poprawiony dokument potrzebuje nowego PDF-u
    poprawiony = b.dodaj_pdf_dokumentu(b.dokument(dok.id), b"%PDF-1.4 poprawiony")
    assert "poprawiony" in poprawiony.nazwa
    anulowany = b.dodaj_pdf_dokumentu(b.anuluj(dok.id, "pomyłka"), b"%PDF-1.4 anulowany")
    assert "anulowany" in anulowany.nazwa
    assert len(b.pliki(kategoria=KATEGORIA_WYSTAWIONE)) == 3  # stare wersje zostają w archiwum


def test_powiazania_przetrwaja_ponowne_otwarcie(tmp_path):
    b = Baza(tmp_path / "d.db")
    dok = b.zapisz_dokument(rachunek())
    b.dodaj_pdf_dokumentu(dok, b"%PDF-1.4 x")
    b.zamknij()
    b2 = Baza(tmp_path / "d.db")
    assert b2.dokumenty_bez_pdf() == []


def test_anonimizacja_usuwa_pdf_z_danymi_osobowymi(tmp_path):
    b = Baza(tmp_path / "d.db")
    stary = Dokument("1/01/2015", "2015-01-10", "2015-01-10", "gotówka", "Jan Kowalski",
                     pozycje=[Pozycja("A", 1, 10)])
    dok = b.zapisz_dokument(stary)
    b.dodaj_pdf_dokumentu(dok, b"%PDF-1.4 Jan Kowalski")
    assert b.anonimizuj_starsze(5, dzis=date(2026, 10, 2)) == 1
    assert b.pliki(kategoria=KATEGORIA_WYSTAWIONE) == []
    assert len(b.dokumenty_bez_pdf()) == 1  # można dodać PDF już bez danych osobowych


def test_prawdziwy_pdf_dokumentu(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    pdf = druk.pdf_dokumentu(rachunek(), dict(DOMYSLNE_USTAWIENIA))
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    b = Baza(tmp_path / "d.db")
    dok = b.zapisz_dokument(rachunek())
    p = b.dodaj_pdf_dokumentu(dok, pdf)
    assert b.tresc_pliku(p.id) == pdf
