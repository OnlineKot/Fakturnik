import pytest

from fakturnik import urzadzenie
from fakturnik.baza import Baza, Dokument, Pozycja
from fakturnik.szyfrowanie import BledneHaslo, WymaganeUrzadzenie


def dok():
    return Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan", pozycje=[Pozycja("A", 1, 10)])


def test_kod_odzyskiwania_w_obie_strony():
    s = urzadzenie.nowy_sekret()
    kod = urzadzenie.kod_odzyskiwania(s)
    assert len(kod) == 39 and kod.count("-") == 7
    assert urzadzenie.sekret_z_kodu(kod) == s
    assert urzadzenie.sekret_z_kodu(kod.lower().replace("-", " ")) == s  # wielkość liter i odstępy bez znaczenia
    assert urzadzenie.sekret_z_kodu("ABCD") is None


def test_dane_powiazane_z_urzadzeniem(tmp_path):
    plik = tmp_path / "d.db"
    b = Baza(plik)
    b.ustaw_haslo("tajnehaslo")
    b.zapisz_dokument(dok())
    s = urzadzenie.nowy_sekret()
    b.powiaz_z_urzadzeniem(s)
    assert b.weryfikacja_urzadzenia and Baza.powiazany_z_urzadzeniem(plik)
    b.ustaw_haslo("nowehaslo1")  # zmiana hasła nie zdejmuje powiązania
    assert b.weryfikacja_urzadzenia and b.sprawdz_haslo("nowehaslo1")
    b.zamknij()

    with pytest.raises(WymaganeUrzadzenie):
        Baza(plik, "nowehaslo1")  # inny komputer: samo hasło nie wystarczy
    with pytest.raises(WymaganeUrzadzenie):
        Baza(plik, "nowehaslo1", urzadzenie.nowy_sekret())  # zły kod
    with pytest.raises(BledneHaslo):
        Baza(plik, "zlehaslo", s)
    assert not Baza.da_sie_otworzyc(plik, "nowehaslo1") and Baza.da_sie_otworzyc(plik, "nowehaslo1", s)

    b = Baza(plik, "nowehaslo1", urzadzenie.sekret_z_kodu(urzadzenie.kod_odzyskiwania(s)))
    assert [d.numer for d in b.dokumenty()] == ["1/10/2026"]
    b.powiaz_z_urzadzeniem(None)  # wyłączenie
    b.zamknij()
    assert [d.numer for d in Baza(plik, "nowehaslo1").dokumenty()] == ["1/10/2026"]


def test_pakiet_migracji_nie_zalezy_od_urzadzenia(tmp_path):
    b = Baza(tmp_path / "a" / "d.db")
    b.ustaw_haslo("tajnehaslo")
    b.zapisz_dokument(dok())
    b.powiaz_z_urzadzeniem(urzadzenie.nowy_sekret())
    b.kopia_zaszyfrowana(tmp_path / "migracja.fkopia", "haslo-pakietu")
    b.zamknij()
    nowy = Baza(tmp_path / "b" / "d.db")  # nowy komputer
    nowy.przywroc(tmp_path / "migracja.fkopia", "haslo-pakietu")
    assert [d.numer for d in nowy.dokumenty()] == ["1/10/2026"]


def test_weryfikacja_wymaga_hasla(tmp_path):
    b = Baza(tmp_path / "d.db")
    with pytest.raises(PermissionError):
        b.powiaz_z_urzadzeniem(urzadzenie.nowy_sekret())
