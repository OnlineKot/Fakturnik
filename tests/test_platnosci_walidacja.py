from datetime import date

from fakturnik.baza import Baza, Dokument, Pozycja, podsumuj
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


def przelew(numer, kwota, termin, nieoplacony=True):
    return Dokument(numer=numer, data_wystawienia="2026-10-01", data_uslugi="2026-10-01", platnosc="przelew",
                    nabywca="Firma", pozycje=[Pozycja("Leczenie", 1, kwota)], rodzaj="Faktura",
                    nieoplacony=nieoplacony, termin_platnosci=termin)


def test_nieoplacone_i_po_terminie(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_dokument(przelew("FV/1/10/2026", 900, "2026-10-05"))
    b.zapisz_dokument(przelew("FV/2/10/2026", 1200, "2099-01-01"))
    b.zapisz_dokument(przelew("FV/3/10/2026", 500, "", nieoplacony=False))
    czekajace = b.nieoplacone()
    assert [d.numer for d in czekajace] == ["FV/1/10/2026", "FV/2/10/2026"]  # od najstarszego terminu
    assert czekajace[0].po_terminie(date(2026, 10, 6)) and not czekajace[1].po_terminie(date(2026, 10, 6))
    p = podsumuj(b.dokumenty())
    assert (p.nieoplaconych, p.do_zaplaty) == (2, 2100)
    assert [d.numer for d in b.dokumenty(rodzaj="nieoplacone")] == ["FV/2/10/2026", "FV/1/10/2026"]

    b.oznacz_oplacony(czekajace[0].id, "2026-10-07")
    d = b.dokument(czekajace[0].id)
    assert not d.nieoplacony and d.oplacono == "2026-10-07"
    assert len(b.nieoplacone()) == 1

    b.anuluj(czekajace[1].id)
    assert b.nieoplacone() == []  # anulowany nie czeka na zapłatę


def test_starsze_dokumenty_sa_oplacone(tmp_path):
    # dokument zapisany przez wersję bez płatności nie ma pól nieoplacony/termin
    d = Dokument("1/10/2026", "2026-10-01", "2026-10-01", "przelew", "Jan")
    assert not d.czeka_na_zaplate and not d.po_terminie()


def test_wydruk_terminu_platnosci(tmp_path):
    from fakturnik import druk
    b = Baza(tmp_path / "d.db")
    b.zapisz_ustawienia({"konto": "61109010140000071219812874"})
    html = druk.html_dokumentu(przelew("FV/1/10/2026", 900, "2026-10-15"), b.ustawienia())
    assert "Termin płatności: 15.10.2026" in html and "61 1090 1014" in html and "zapłacono" not in html
    html = druk.html_dokumentu(przelew("FV/1/10/2026", 900, "", nieoplacony=False), b.ustawienia())
    assert "(zapłacono)" in html
