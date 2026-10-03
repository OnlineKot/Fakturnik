import json
from datetime import date

from fakturnik.baza import ZANONIMIZOWANO, Baza, Dokument, Pozycja, bezpieczna_komorka
from fakturnik.druk import html_danych_osoby, html_dokumentu, html_zestawienia
from fakturnik.ochrona import Dziennik
from fakturnik.system import sprawdz_polecenie

DZIS = date(2026, 10, 3)


def rachunek(numer, dzien, kto="Jan Kowalski", pesel="44051401359"):
    return Dokument(numer=numer, data_wystawienia=dzien, data_uslugi=dzien, platnosc="gotówka",
                    nabywca=kto, nabywca_id=pesel, nabywca_adres="ul. Długa 1\n00-001 Warszawa",
                    pozycje=[Pozycja("Wypełnienie", 1, 250)])


def test_anonimizacja_po_okresie_przechowywania(tmp_path):
    b = Baza(tmp_path / "d.db")
    stary = b.zapisz_dokument(rachunek("1/03/2020", "2020-03-02"))
    b.zapisz_dokument(rachunek("1/05/2020", "2020-05-02", kto="Anna Nowak", pesel=""))
    b.zapisz_dokument(rachunek("1/05/2021", "2021-05-02", kto="Anna Nowak", pesel=""))
    poprawiony = b.dokument(stary.id)
    poprawiony.nabywca_adres = "ul. Krótka 2"
    b.zaktualizuj_dokument(poprawiony, "zmiana adresu")
    b.zapisz_pacjenta("Jan Kowalski", "44051401359", "ul. Krótka 2")
    b.zapisz_pacjenta("Anna Nowak")

    assert b.granica_retencji(5, DZIS) == 2020
    assert b.do_anonimizacji(5, DZIS) == 2
    assert b.anonimizuj_starsze(5, DZIS) == 2
    assert b.do_anonimizacji(5, DZIS) == 0

    d = b.dokument(stary.id)
    assert (d.nabywca, d.nabywca_id, d.nabywca_adres) == (ZANONIMIZOWANO, "", "")
    assert d.numer == "1/03/2020" and d.suma == 250  # do rozliczeń zostaje
    for _, _, wersja in b.wersje(stary.id):
        assert "Kowalski" not in json.dumps(wersja.__dict__, default=str)
    nazwy = [p.nazwa for p in b.pacjenci()]
    assert "Jan Kowalski" not in nazwy  # nie ma nowszych dokumentów
    assert "Anna Nowak" in nazwy        # ma dokument z 2021 roku
    assert ZANONIMIZOWANO not in nazwy
    b.zamknij()
    assert b"Kowalski" not in Baza(tmp_path / "d.db").db.serialize()


def test_dane_osoby_i_pesel_na_wydruku(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_dokument(rachunek("1/10/2026", "2026-10-01"))
    b.zapisz_dokument(rachunek("2/10/2026", "2026-10-02", kto="Inna Osoba"))
    dokumenty = b.dokumenty_pacjenta("Jan Kowalski")
    assert [d.numer for d in dokumenty] == ["1/10/2026"]
    u = b.ustawienia()
    html = html_danych_osoby("Jan Kowalski", "44051401359", "", dokumenty, u)
    assert "1/10/2026" in html and "2/10/2026" not in html and "UODO" in html
    assert "44051401359" not in html_dokumentu(dokumenty[0], u)  # domyślnie bez PESEL
    assert "44051401359" in html_dokumentu(dokumenty[0], dict(u, druk_pesel="1"))


def test_data_wydruku_i_wygenerowania_opcjonalne(tmp_path):
    b = Baza(tmp_path / "d.db")
    d = b.zapisz_dokument(rachunek("1/10/2026", "2026-10-01"))
    u = b.ustawienia()
    assert "Wydrukowano" not in html_dokumentu(d, u)
    assert "Wydrukowano" in html_dokumentu(d, dict(u, druk_data_wydruku="1"))
    assert "Wygenerowano" in html_zestawienia([d], u, "październik 2026")
    assert "Wygenerowano" not in html_zestawienia([d], dict(u, druk_data_wygenerowania="0"), "październik 2026")


def test_csv_nie_uruchamia_formul():
    assert bezpieczna_komorka("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert bezpieczna_komorka("+48 600") == "'+48 600"
    assert bezpieczna_komorka("Jan Kowalski") == "Jan Kowalski"


def test_polecenia_z_zewnatrz_sa_sprawdzane(tmp_path):
    plik = tmp_path / "skan.pdf"
    plik.write_bytes(b"%PDF")
    assert sprawdz_polecenie(b'{"akcja": "pokaz"}') == {"akcja": "pokaz"}
    assert sprawdz_polecenie(b'{"akcja": "usun_wszystko"}') is None
    assert sprawdz_polecenie(b"nie json") is None
    assert sprawdz_polecenie(json.dumps({"akcja": "dodaj", "pliki": [str(plik), "/nie/ma/takiego"]}).encode()) \
        == {"akcja": "dodaj", "pliki": [str(plik)]}
    assert sprawdz_polecenie(b'{"akcja": "dodaj", "pliki": "x"}') is None


def test_uciecie_dziennika_jest_wykrywane(tmp_path):
    d = Dziennik(tmp_path / "dziennik.log")
    zapamietane = []
    d.po_zapisie = zapamietane.append
    for i in range(3):
        d.zapisz(f"zdarzenie {i}")
    assert d.zawiera(zapamietane[-1]) and d.nienaruszony()
    # ktoś usuwa ostatnie wpisy: łańcuch dalej się zgadza, ale zapamiętanego wpisu już nie ma
    sciezka = tmp_path / "dziennik.log"
    sciezka.chmod(0o644)
    sciezka.write_text("".join(l + "\n" for l in sciezka.read_text().splitlines()[:1]), encoding="utf-8")
    assert d.nienaruszony() and not d.zawiera(zapamietane[-1])


def test_skrot_wpisu_trafia_do_zaszyfrowanej_bazy(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("tajnehaslo")
    b.zapamietaj_wpis_dziennika("ab" * 32)
    b.zapisz_ustawienia({"nazwa": "Gabinet"})
    b.zamknij()
    assert Baza(tmp_path / "d.db", "tajnehaslo").ustawienia()["ostatni_wpis_dziennika"] == "ab" * 32
