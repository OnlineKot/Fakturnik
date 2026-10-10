from datetime import date

import pytest

from fakturnik.baza import Baza, Dokument, Pozycja
from fakturnik.slownie import kwota_slownie
from fakturnik.szyfrowanie import BledneHaslo


@pytest.mark.parametrize("kwota, oczekiwane", [
    (1, "jeden złoty 00/100"),
    (2, "dwa złote 00/100"),
    (12.5, "dwanaście złotych 50/100"),
    (22, "dwadzieścia dwa złote 00/100"),
    (1000, "tysiąc złotych 00/100"),
    (1250, "tysiąc dwieście pięćdziesiąt złotych 00/100"),
    (2345.07, "dwa tysiące trzysta czterdzieści pięć złotych 07/100"),
    (15000, "piętnaście tysięcy złotych 00/100"),
])
def test_kwota_slownie(kwota, oczekiwane):
    assert kwota_slownie(kwota) == oczekiwane


def dok(numer, dzien="2026-10-02"):
    return Dokument(numer=numer, data_wystawienia=dzien, data_uslugi=dzien, platnosc="gotówka",
                    nabywca="Jan Kowalski", pozycje=[Pozycja("Leczenie kanałowe", 1, 1200)])


def test_numeracja_w_miesiacu_i_po_ponownym_otwarciu(tmp_path):
    plik = tmp_path / "dane.db"
    b = Baza(plik)
    pazdziernik = date(2026, 10, 2)
    assert b.nastepny_numer(pazdziernik) == "1/10/2026"
    b.zapisz_dokument(dok("1/10/2026"))
    assert b.nastepny_numer(pazdziernik) == "2/10/2026"
    assert b.nastepny_numer(date(2026, 11, 1)) == "1/11/2026"

    b.zamknij()
    b = Baza(plik)  # program zamknięty i otwarty ponownie
    assert b.nastepny_numer(pazdziernik) == "2/10/2026"
    b.zapisz_dokument(dok("7/10/2026"))  # numer poprawiony ręcznie
    assert b.nastepny_numer(pazdziernik) == "8/10/2026"


def test_haslo_szyfruje_plik(tmp_path):
    plik = tmp_path / "dane.db"
    b = Baza(plik)
    b.zapisz_dokument(dok("1/10/2026"))
    b.ustaw_haslo("tajne123")

    b.zamknij()
    zawartosc = plik.read_bytes()
    assert b"Kowalski" not in zawartosc and b"SQLite" not in zawartosc
    assert Baza.wymaga_hasla(plik)

    with pytest.raises(PermissionError):
        Baza(plik)
    with pytest.raises(BledneHaslo):
        Baza(plik, "zle")

    b = Baza(plik, "tajne123")
    assert [d.numer for d in b.dokumenty()] == ["1/10/2026"]
    b.zapisz_dokument(dok("2/10/2026"))  # kolejne zapisy też zaszyfrowane
    b.zamknij()
    b = Baza(plik, "tajne123")
    assert b.nastepny_numer(date(2026, 10, 1)) == "3/10/2026"

    b.ustaw_haslo(None)
    assert not Baza.wymaga_hasla(plik)
    b.zamknij()
    assert len(Baza(plik).dokumenty()) == 2


def test_eksport_i_przywracanie(tmp_path):
    b = Baza(tmp_path / "dane.db")
    b.zapisz_dokument(dok("1/10/2026"))
    b.ustaw_haslo("tajne123")
    b.kopia_zapasowa(tmp_path / "kopia.db")
    b.eksport_odszyfrowany(tmp_path / "jawny.db")
    assert (tmp_path / "jawny.db").read_bytes().startswith(b"SQLite format 3")
    assert b.eksport_csv(tmp_path / "x.csv") == 1
    assert "Jan Kowalski" in (tmp_path / "x.csv").read_text(encoding="utf-8-sig")

    b.zapisz_dokument(dok("2/10/2026"))
    with pytest.raises(BledneHaslo):
        b.przywroc(tmp_path / "kopia.db", "zle")
    b.przywroc(tmp_path / "kopia.db", "tajne123")
    assert [d.numer for d in b.dokumenty()] == ["1/10/2026"]
    assert Baza.wymaga_hasla(tmp_path / "dane.db")  # przywrócone dane nadal zaszyfrowane


def test_dziennik_wykrywa_zmiany(tmp_path):
    from fakturnik.ochrona import Dziennik, tylko_do_odczytu
    d = Dziennik(tmp_path / "dziennik.log")
    d.zapisz("udane logowanie")
    d.zapisz("nieudana próba logowania")
    d.zapisz("udane logowanie")
    assert d.nienaruszony()
    linie = d.sciezka.read_text(encoding="utf-8").splitlines()
    tylko_do_odczytu(d.sciezka, False)
    d.sciezka.write_text("\n".join([linie[0], linie[2]]) + "\n", encoding="utf-8")  # usunięta próba
    assert not d.nienaruszony()


def test_kopie_automatyczne(tmp_path):
    from fakturnik.ochrona import kopia_automatyczna
    plik = tmp_path / "dane.db"
    b = Baza(plik)
    b.zapisz_dokument(dok("1/10/2026"))
    b.zamknij()
    cel = kopia_automatyczna(plik, tmp_path / "kopie")
    assert cel.read_bytes() == plik.read_bytes()


def dok_dla(numer, dzien, nabywca, kwota, platnosc="gotówka", pesel=""):
    return Dokument(numer=numer, data_wystawienia=dzien, data_uslugi=dzien, platnosc=platnosc,
                    nabywca=nabywca, nabywca_id=pesel, pozycje=[Pozycja("Leczenie", 1, kwota)])


def baza_z_danymi(tmp_path):
    b = Baza(tmp_path / "dane.db")
    b.zapisz_dokument(dok_dla("1/09/2026", "2026-09-15", "Anna Nowak", 900, "karta"))
    b.zapisz_dokument(dok_dla("1/10/2026", "2026-10-01", "Piotr Wiśniewski", 1500, pesel="80010112345"))
    b.zapisz_dokument(dok_dla("2/10/2026", "2026-10-02", "Jan Kowalski", 1200))
    b.zapisz_dokument(dok_dla("1/10/2025", "2025-10-20", "Jan Kowalski", 200, "przelew"))
    return b


def test_szukanie_po_roku_miesiacu_i_nazwisku(tmp_path):
    b = baza_z_danymi(tmp_path)
    assert [d.numer for d in b.dokumenty(rok=2026, miesiac=10)] == ["2/10/2026", "1/10/2026"]
    assert len(b.dokumenty(rok=2026)) == 3
    assert [d.numer for d in b.dokumenty(miesiac=10)] == ["2/10/2026", "1/10/2026", "1/10/2025"]
    assert [d.numer for d in b.dokumenty("kowalski")] == ["2/10/2026", "1/10/2025"]
    assert [d.numer for d in b.dokumenty("wisniewski")] == ["1/10/2026"]  # bez polskich znaków
    assert [d.numer for d in b.dokumenty("80010112345")] == ["1/10/2026"]  # po PESEL
    assert [d.numer for d in b.dokumenty("kowalski", rok=2025)] == ["1/10/2025"]
    assert b.lata() == [2026, 2025]


def test_anulowanie_nie_psuje_numeracji_i_sum(tmp_path):
    from fakturnik.baza import podsumuj
    b = baza_z_danymi(tmp_path)
    d = b.dokumenty("Kowalski", rok=2026)[0]
    b.anuluj(d.id, "pomyłka w kwocie")
    pazdziernik = b.dokumenty(rok=2026, miesiac=10)
    assert len(pazdziernik) == 2  # anulowany zostaje w historii
    p = podsumuj(pazdziernik)
    assert (p.liczba, p.suma, p.anulowanych) == (1, 1500, 1)
    assert b.nastepny_numer(date(2026, 10, 5)) == "3/10/2026"  # numer anulowanego nie wraca
    assert b.dokument(d.id).powod_anulowania == "pomyłka w kwocie"


def test_lista_pacjentow_po_nazwisku(tmp_path):
    b = baza_z_danymi(tmp_path)
    pacjenci = b.pacjenci()
    assert [p.nazwa for p in pacjenci] == ["Jan Kowalski", "Anna Nowak", "Piotr Wiśniewski"]
    kowalski = pacjenci[0]
    assert (kowalski.dokumentow, kowalski.suma, kowalski.ostatnia_wizyta) == (2, 1400, "2026-10-02")
    assert [p.nazwa for p in b.pacjenci("now")] == ["Anna Nowak"]


def test_zestawienie_do_druku(tmp_path):
    from fakturnik import druk
    b = baza_z_danymi(tmp_path)
    html = druk.html_zestawienia(b.dokumenty(rok=2026, miesiac=10), b.ustawienia(), "Październik 2026")
    assert "Październik 2026" in html and "Jan Kowalski" in html and "2\u00a0700,00" in html


def test_nazwy_uslug_do_podpowiedzi(tmp_path):
    from fakturnik.baza import Baza, Dokument, Pozycja
    b = Baza(tmp_path / "d.db")
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan",
                               pozycje=[Pozycja("Przegląd", 1, 100), Pozycja("Czyszczenie", 1, 200)]))
    b.zapisz_dokument(Dokument("2/10/2026", "2026-10-02", "2026-10-02", "gotówka", "Ola",
                               pozycje=[Pozycja("Przegląd", 1, 100), Pozycja("Wypełnienie", 1, 300)]))
    nazwy = b.nazwy_uslug()
    assert set(nazwy) == {"Przegląd", "Czyszczenie", "Wypełnienie"}  # bez powtórek
    assert nazwy[0] == "Przegląd"  # najnowszy dokument pierwszy
