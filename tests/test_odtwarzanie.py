import pytest

from fakturnik.baza import Baza, Dokument, Pozycja
from fakturnik.ochrona import kopia_automatyczna, lista_kopii, odtworz_z_kopii, tylko_do_odczytu


def test_uszkodzony_plik_odtwarzany_z_kopii(tmp_path):
    plik, kopie = tmp_path / "dane" / "d.db", tmp_path / "kopie"
    b = Baza(plik)
    b.ustaw_haslo("tajnehaslo")
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan", pozycje=[Pozycja("A", 1, 10)]))
    b.zamknij()
    kopia_automatyczna(plik, kopie)
    assert lista_kopii(kopie) and Baza.da_sie_otworzyc(lista_kopii(kopie)[0], "tajnehaslo")
    assert not Baza.da_sie_otworzyc(lista_kopii(kopie)[0], "zlehaslo")

    tylko_do_odczytu(plik, False)
    dane = bytearray(plik.read_bytes())
    dane[200] ^= 0xFF  # uszkodzenie (np. awaria dysku)
    plik.write_bytes(bytes(dane))
    assert not Baza.da_sie_otworzyc(plik, "tajnehaslo")

    uszkodzony = odtworz_z_kopii(plik, lista_kopii(kopie)[0])
    assert uszkodzony.exists()  # nic nie jest kasowane
    assert [d.numer for d in Baza(plik, "tajnehaslo").dokumenty()] == ["1/10/2026"]


def test_uszkodzona_baza_bez_hasla_jest_wykrywana(tmp_path):
    plik = tmp_path / "d.db"
    b = Baza(plik)
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan", pozycje=[Pozycja("A", 1, 10)]))
    b.zamknij()
    tylko_do_odczytu(plik, False)
    dane = bytearray(plik.read_bytes())
    for i in range(120, len(dane), 7):
        dane[i] ^= 0x5A
    plik.write_bytes(bytes(dane))
    with pytest.raises(ValueError):
        Baza(plik)
