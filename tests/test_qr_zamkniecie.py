from datetime import date

from fakturnik.baza import Baza, Dokument, Pozycja
from fakturnik.druk import html_dokumentu, html_zamkniecia_dnia, tekst_qr_przelewu

U = {"nazwa": "Gabinet Stomatologiczny Żółć | Test", "nip": "123-456-32-18", "konto": "61 1090 1014 0000 0712 1981 2874"}


def dok(platnosc="przelew", kwota=1200.0, **kw):
    return Dokument("FV/1/10/2026", "2026-10-03", "2026-10-03", platnosc, "Firma", pozycje=[Pozycja("A", 1, kwota)],
                    rodzaj="Faktura", **kw)


def test_kod_qr_wedlug_rekomendacji_zbp():
    tekst = tekst_qr_przelewu(dok(), U)
    pola = tekst.split("|")
    assert len(pola) == 9 and len(tekst) <= 160
    assert pola[:4] == ["1234563218", "PL", "61109010140000071219812874", "120000"]
    assert pola[4] == "Gabinet Stomatologic" and len(pola[4]) <= 20  # bez polskich znaków i „|”
    assert pola[5] == "Faktura FV/1/10/2026"
    assert tekst_qr_przelewu(dok("gotówka"), U) is None
    assert tekst_qr_przelewu(dok(), dict(U, konto="")) is None
    assert tekst_qr_przelewu(dok(kwota=12000), U).split("|")[3] == ""  # powyżej 9999,99 zł kwotę wpisuje się ręcznie


def test_kod_qr_na_wydruku_mozna_wylaczyc():
    u = dict(U, adres="ul. A 1", regon="", miejsce="X", adnotacja="zw", druk_qr="1")
    assert "data:image/png;base64" in html_dokumentu(dok(), u).split("SPRZEDAWCA")[1]
    assert "Zapłać kodem QR" not in html_dokumentu(dok(), dict(u, druk_qr="0"))


def test_zamkniecie_dnia(tmp_path):
    b = Baza(tmp_path / "d.db")
    for i, (pl, kw) in enumerate([("gotówka", 250), ("karta", 400), ("gotówka", 180)], 1):
        b.zapisz_dokument(Dokument(f"{i}/10/2026", "2026-10-03", "2026-10-03", pl, f"P{i}", pozycje=[Pozycja("A", 1, kw)]))
    html = html_zamkniecia_dnia(b.dokumenty(), b.ustawienia(), date(2026, 10, 3))
    assert "sobota, 03.10.2026" in html and "430,00" in html and "400,00" in html and "Razem: 830,00" in html
