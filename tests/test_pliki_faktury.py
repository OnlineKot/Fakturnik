import os
from datetime import date

import pytest

from fakturnik.baza import Baza, Dokument, Pozycja, numer_z_wzoru


def faktura(numer, dzien="2026-10-02", rodzaj="Faktura"):
    return Dokument(numer=numer, data_wystawienia=dzien, data_uslugi=dzien, platnosc="przelew",
                    nabywca="Firma Sp. z o.o.", nabywca_id="6391234567", rodzaj=rodzaj,
                    pozycje=[Pozycja("Leczenie", 1, 900)])


def test_faktury_maja_osobna_numeracje(tmp_path):
    b = Baza(tmp_path / "d.db")
    d = date(2026, 10, 2)
    assert b.nastepny_numer(d, "Faktura") == "FV/1/10/2026"
    b.zapisz_dokument(faktura("FV/1/10/2026"))
    assert b.nastepny_numer(d, "Faktura") == "FV/2/10/2026"
    assert b.nastepny_numer(d) == "1/10/2026"  # rachunki liczone osobno
    b.zapisz_dokument(faktura("1/10/2026", rodzaj="Rachunek"))
    assert b.nastepny_numer(d) == "2/10/2026"
    assert b.nastepny_numer(d, "Faktura") == "FV/2/10/2026"
    assert [x.numer for x in b.dokumenty(rodzaj="Faktura")] == ["FV/1/10/2026"]


def test_numer_z_wzoru():
    assert numer_z_wzoru("FV/{n}/{mm}/{rrrr}", "FV/7/10/2026") == 7
    assert numer_z_wzoru("{n}/{mm}/{rrrr}", "12/03/2026") == 12
    assert numer_z_wzoru("{rrrr}/{mm}/{n}", "2026/10/5") == 5
    assert numer_z_wzoru("{n}/{mm}/{rrrr}", "3a") == 3  # numer wpisany ręcznie inaczej


def test_dokument_sprzed_faktur_jest_rachunkiem():
    assert Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan").tytul == "Rachunek"


@pytest.fixture
def skan(tmp_path):
    p = tmp_path / "faktura-prad.pdf"
    p.write_bytes(b"%PDF-1.4 tajna faktura za prad Tauron " * 50)
    return p


def test_pliki_sa_zaszyfrowane_i_wyszukiwalne(tmp_path, skan):
    b = Baza(tmp_path / "dane" / "d.db")
    p = b.dodaj_plik(skan, "2026-09-30", "Faktura kosztowa", "Tauron", "prąd wrzesień")
    assert (p.nazwa, p.typ, p.kategoria) == ("faktura-prad.pdf", "pdf", "Faktura kosztowa")
    na_dysku = list(b.katalog_plikow.glob("*.bin"))
    assert len(na_dysku) == 1 and b"Tauron" not in na_dysku[0].read_bytes()
    assert b.tresc_pliku(p.id) == skan.read_bytes()

    assert [x.id for x in b.pliki("tauron")] == [p.id]
    assert [x.id for x in b.pliki("prad")] == [p.id]  # bez polskich znaków
    assert b.pliki(rok=2026, miesiac=9) and not b.pliki(rok=2026, miesiac=10)
    assert not b.pliki(kategoria="Umowa")

    with pytest.raises(PermissionError):  # domyślnie pliki są tylko do odczytu
        b.zmien_plik(p.id, "2026-10-01", "Inne", "Tauron Sprzedaż", "")
    b.zapisz_ustawienia({"pliki_edycja": "1"})
    b.zmien_plik(p.id, "2026-10-01", "Inne", "Tauron Sprzedaż", "")
    assert b.plik(p.id).kategoria == "Inne" and b.pliki(rok=2026, miesiac=10)


def test_podmieniony_plik_jest_wykrywany(tmp_path, skan):
    from fakturnik.ochrona import tylko_do_odczytu
    b = Baza(tmp_path / "d.db")
    p = b.dodaj_plik(skan)
    plik = next(b.katalog_plikow.glob("*.bin"))
    tylko_do_odczytu(plik, False)
    dane = bytearray(plik.read_bytes())
    dane[-5] ^= 1
    plik.write_bytes(bytes(dane))
    with pytest.raises(ValueError):
        b.tresc_pliku(p.id)


def test_plik_z_haslem_i_po_zmianie_hasla(tmp_path, skan):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("tajnehaslo")
    p = b.dodaj_plik(skan)
    b.ustaw_haslo("innehaslo1")  # zmiana hasła nie wymaga przepisywania plików
    b.zamknij()
    b = Baza(tmp_path / "d.db", "innehaslo1")
    assert b.tresc_pliku(p.id) == skan.read_bytes()


def test_nieobslugiwany_plik(tmp_path):
    b = Baza(tmp_path / "d.db")
    exe = tmp_path / "wirus.exe"
    exe.write_bytes(b"MZ")
    with pytest.raises(ValueError):
        b.dodaj_plik(exe)


def test_usuwanie_pliku(tmp_path, skan):
    b = Baza(tmp_path / "d.db")
    p = b.dodaj_plik(skan)
    with pytest.raises(PermissionError):
        b.usun_plik(p.id)
    b.zapisz_ustawienia({"pliki_edycja": "1"})
    b.usun_plik(p.id)
    assert not b.pliki() and not list(b.katalog_plikow.glob("*.bin"))


def test_zmieniony_plik_na_dysku_przywracany_z_kopii(tmp_path, skan):
    import shutil
    b = Baza(tmp_path / "d.db")
    p = b.dodaj_plik(skan)
    kopie = tmp_path / "kopie"
    b.kopia_plikow(kopie)
    na_dysku = next(b.katalog_plikow.glob("*.bin"))
    oryginal = na_dysku.read_bytes()
    os.chmod(na_dysku, 0o600)
    na_dysku.write_bytes(oryginal[:-5] + b"XXXXX")  # podmiana zawartości poza programem
    problemy = b.sprawdz_integralnosc(kopie)
    assert any("zmieniony" in x for x in problemy)
    assert na_dysku.read_bytes() == oryginal and b.tresc_pliku(p.id) == skan.read_bytes()
    assert b.sprawdz_integralnosc(kopie) == []


def test_pelna_kopia_zip_z_plikami(tmp_path, skan):
    b = Baza(tmp_path / "a" / "d.db")
    b.ustaw_haslo("tajnehaslo")
    b.zapisz_dokument(faktura("FV/1/10/2026"))
    p = b.dodaj_plik(skan, osoba="Tauron")
    b.kopia_zapasowa(tmp_path / "kopia.zip")
    b.zamknij()

    # nowy komputer: pusta baza, przywrócenie z kopii .zip
    nowa = Baza(tmp_path / "b" / "d.db")
    nowa.przywroc(tmp_path / "kopia.zip", "tajnehaslo")
    assert [d.numer for d in nowa.dokumenty()] == ["FV/1/10/2026"]
    assert nowa.tresc_pliku(p.id) == skan.read_bytes()


def test_kopia_plikow_doklada_tylko_nowe(tmp_path, skan):
    b = Baza(tmp_path / "d.db")
    b.dodaj_plik(skan)
    assert b.kopia_plikow(tmp_path / "kopie") == 1
    assert b.kopia_plikow(tmp_path / "kopie") == 0


def test_straznik_odtwarza_zmieniony_plik_danych_i_brakujace_pliki(tmp_path, skan):
    from fakturnik.ochrona import tylko_do_odczytu
    b = Baza(tmp_path / "dane" / "d.db")
    b.zapisz_dokument(faktura("FV/1/10/2026"))
    p = b.dodaj_plik(skan)
    b.kopia_plikow(tmp_path / "kopie")
    assert b.sprawdz_integralnosc(tmp_path / "kopie") == []

    # ktoś podmienia plik danych z zewnątrz (na Windows działający program blokuje plik,
    # więc symulujemy chwilę bez blokady, np. gdy plik był podmieniony, zanim program go zablokował)
    b.blokada.zwolnij()
    tylko_do_odczytu(b.sciezka, False)
    b.sciezka.write_bytes(b"SQLite format 3\0 podrobka")
    problemy = b.sprawdz_integralnosc(tmp_path / "kopie")
    assert len(problemy) == 1 and "zmieniony" in problemy[0]
    b.zamknij()
    b = Baza(b.sciezka)  # ponowne otwarcie: dane wróciły
    assert [d.numer for d in b.dokumenty()] == ["FV/1/10/2026"]

    # ktoś usuwa wrzucony plik
    b.blokada.zwolnij()
    plik = next(b.katalog_plikow.glob("*.bin"))
    tylko_do_odczytu(plik, False)
    plik.unlink()
    problemy = b.sprawdz_integralnosc(tmp_path / "kopie")
    assert "Przywrócono go z kopii" in problemy[0]
    assert b.tresc_pliku(p.id) == skan.read_bytes()


def test_szyfrowana_kopia_wlasnym_haslem(tmp_path, skan):
    from fakturnik.szyfrowanie import BledneHaslo
    b = Baza(tmp_path / "a" / "d.db")
    b.ustaw_haslo("haslo-programu")
    b.zapisz_dokument(faktura("FV/1/10/2026"))
    p = b.dodaj_plik(skan, osoba="Tauron")
    b.kopia_zaszyfrowana(tmp_path / "kopia.fkopia", "inne-haslo-kopii")
    b.zamknij()
    surowe = (tmp_path / "kopia.fkopia").read_bytes()
    assert b"Firma" not in surowe and b"SQLite" not in surowe and Baza.czy_kopia_szyfrowana(tmp_path / "kopia.fkopia")

    nowa = Baza(tmp_path / "b" / "d.db")
    with pytest.raises(BledneHaslo):
        nowa.przywroc(tmp_path / "kopia.fkopia", "haslo-programu")  # potrzebne hasło kopii, nie programu
    nowa.przywroc(tmp_path / "kopia.fkopia", "inne-haslo-kopii")
    assert [d.numer for d in nowa.dokumenty()] == ["FV/1/10/2026"]
    assert nowa.tresc_pliku(p.id) == skan.read_bytes()
