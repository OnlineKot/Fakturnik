import json
from datetime import date

from fakturnik.baza import Baza, Dokument, Pozycja, dokument_z_danych, podsumuj
from fakturnik.druk import html_dokumentu


def faktura(b):
    return b.zapisz_dokument(Dokument("FV/1/10/2026", "2026-10-02", "2026-10-01", "przelew", "Firma X",
                                      "ul. B 2", "1234563218", [Pozycja("Konsultacja", 2, 150)],
                                      rodzaj="Faktura", termin_platnosci="2026-10-09"))


def korekta(f, pozycje):
    return Dokument("KOR/1/10/2026", "2026-10-03", f.data_uslugi, f.platnosc, f.nabywca, f.nabywca_adres,
                    f.nabywca_id, pozycje, rodzaj="Korekta", korekta_do=f.numer, korekta_data=f.data_wystawienia,
                    korekta_id=f.id, powod_korekty="zwrot", pozycje_przed=f.pozycje)


def test_faktura_ma_elementy_obowiazkowe(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_ustawienia({"nazwa": "Gabinet", "adres": "ul. A 1", "nip": "1234563218", "miejsce": "Kraków"})
    html = html_dokumentu(faktura(b), b.ustawienia())
    for element in ("Faktura nr FV/1/10/2026", "Data wykonania usługi", "NIP: 1234563218", "J.m.", "usł.",
                    "Cena jedn.", "Stawka VAT", "zw", "termin: 09.10.2026", "art. 43 ust. 1 pkt 19",
                    "Do zapłaty: 300,00"):
        assert element in html, element


def test_korekta_numeracja_suma_i_wydruk(tmp_path):
    b = Baza(tmp_path / "d.db")
    f = faktura(b)
    assert b.nastepny_numer(date(2026, 10, 3), "Korekta") == "KOR/1/10/2026"
    k = b.zapisz_dokument(korekta(f, [Pozycja("Konsultacja", 1, 150)]))
    assert b.nastepny_numer(date(2026, 10, 3), "Korekta") == "KOR/2/10/2026"
    assert b.nastepny_numer(date(2026, 10, 3), "Faktura") == "FV/2/10/2026"  # osobne liczniki
    k = b.dokument(k.id)
    assert (k.suma_przed, k.suma_po, k.suma) == (300, 150, -150)
    assert podsumuj(b.dokumenty()).suma == 150  # przychód po korekcie
    assert [d.numer for d in b.dokumenty(rodzaj="Korekta")] == ["KOR/1/10/2026"]
    html = html_dokumentu(k, b.ustawienia())
    for element in ("Faktura korygująca nr KOR/1/10/2026", "Dotyczy faktury nr <b>FV/1/10/2026",
                    "z dnia 02.10.2026", "Przyczyna korekty", "PRZED KOREKTĄ", "PO KOREKCIE",
                    "Do zwrotu nabywcy: 150,00"):
        assert element in html, element


def test_stare_dokumenty_bez_nowych_pol(tmp_path):
    d = dokument_z_danych(1, json.loads('{"numer": "1/10/2026", "data_wystawienia": "2026-10-01", '
                                        '"data_uslugi": "2026-10-01", "platnosc": "gotówka", "nabywca": "Jan", '
                                        '"pozycje": [{"nazwa": "A", "ilosc": 1, "cena": 10}]}'))
    assert d.pozycje[0].jm == "usł." and d.termin_platnosci == "" and not d.jest_korekta and d.suma == 10


def test_eksport_csv_z_korekta(tmp_path):
    b = Baza(tmp_path / "d.db")
    f = faktura(b)
    b.zapisz_dokument(korekta(f, []))
    b.eksport_csv(tmp_path / "x.csv")
    tekst = (tmp_path / "x.csv").read_text(encoding="utf-8-sig")
    assert ";-300,00;" in tekst and "'-300" not in tekst
