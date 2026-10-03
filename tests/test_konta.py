import pytest

from fakturnik import konta
from fakturnik.baza import Baza, Dokument, Pozycja
from fakturnik.szyfrowanie import BledneHaslo


def baza_z_kontem(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("haslo-wlascicielki")
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan", pozycje=[Pozycja("A", 1, 10)],
                               wystawil="Właścicielka"))
    id_ = b.dodaj_konto("Kasia", "haslo-kasi-123")
    return b, id_


def test_asystentka_otwiera_dane_wlasnym_haslem(tmp_path):
    b, id_ = baza_z_kontem(tmp_path)
    b.zamknij()
    wpis, klucz = konta.zaloguj(tmp_path, "haslo-kasi-123")
    assert wpis["nazwa"] == "Kasia" and wpis["rola"] == "asystentka"
    b2 = Baza(tmp_path / "d.db", klucz_hasla=klucz)
    assert b2.konto_aktywne(id_) and [d.wystawil for d in b2.dokumenty()] == ["Właścicielka"]
    assert konta.zaloguj(tmp_path, "zle-haslo") is None
    with pytest.raises(BledneHaslo):
        Baza(tmp_path / "d.db", "haslo-kasi-123")  # hasło asystentki nie jest hasłem danych
    assert b"Kasia" not in (tmp_path / "d.db").read_bytes()


def test_zmiana_hasla_wlascicielki_nie_psuje_kont(tmp_path):
    b, id_ = baza_z_kontem(tmp_path)
    b.ustaw_haslo("nowe-haslo-wlascicielki")
    b.zamknij()
    _, klucz = konta.zaloguj(tmp_path, "haslo-kasi-123")
    assert Baza(tmp_path / "d.db", klucz_hasla=klucz).konto_aktywne(id_)


def test_usuniete_konto_i_zmiana_hasla_konta(tmp_path):
    b, id_ = baza_z_kontem(tmp_path)
    id2 = b.dodaj_konto("Ola", "haslo-oli-1234")
    with pytest.raises(ValueError):
        b.dodaj_konto("Ania", "haslo-oli-1234")  # każde konto musi mieć własne hasło
    b.ustaw_haslo_konta(id2, "nowe-haslo-oli")
    assert konta.zaloguj(tmp_path, "haslo-oli-1234") is None
    assert konta.zaloguj(tmp_path, "nowe-haslo-oli")[0]["id"] == id2
    b.usun_konto(id_)
    assert konta.zaloguj(tmp_path, "haslo-kasi-123") is None and not b.konto_aktywne(id_)
    assert [k["nazwa"] for k in b.konta()] == ["Ola"]


def test_bez_hasla_nie_ma_kont(tmp_path):
    b, _ = baza_z_kontem(tmp_path)
    b.ustaw_haslo(None)
    assert b.konta() == [] and konta.wczytaj(tmp_path) == []
    with pytest.raises(PermissionError):
        b.dodaj_konto("Kasia", "haslo-kasi-123")
