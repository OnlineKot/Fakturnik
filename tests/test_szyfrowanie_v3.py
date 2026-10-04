import json

import pytest

from fakturnik import konta
from fakturnik.baza import Baza, Dokument, Pozycja
from fakturnik.szyfrowanie import (
    MAGIC, MAGIC3, MAGIC_KOPII, BledneHaslo, Szyfr, WymaganeUrzadzenie, czy_powiazane_z_urzadzeniem, klucz_pbkdf2,
    odszyfruj_kopie, zaszyfruj_kopie,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os


def test_nowy_plik_argon2id_i_podwojne_szyfrowanie(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan Kowalski",
                               pozycje=[Pozycja("A", 1, 10)]))
    b.ustaw_haslo("tajne-haslo-123")
    b.zamknij()
    dane = (tmp_path / "d.db").read_bytes()
    assert dane.startswith(MAGIC3) and b"Kowalski" not in dane
    with pytest.raises(BledneHaslo):
        Baza(tmp_path / "d.db", "zle")
    b2 = Baza(tmp_path / "d.db", "tajne-haslo-123")
    assert b2.sprawdz_haslo("tajne-haslo-123") and not b2.sprawdz_haslo("zle")
    assert [d.nabywca for d in b2.dokumenty()] == ["Jan Kowalski"]


def test_zmiana_bajtu_wykryta():
    s = Szyfr("haslo-1234")
    zaszyfrowane = bytearray(s.zaszyfruj(b"dane pacjentow"))
    for poz in (len(MAGIC3) + 2, len(zaszyfrowane) // 2, len(zaszyfrowane) - 1):  # parametry, treść, tag
        zmienione = bytearray(zaszyfrowane)
        zmienione[poz] ^= 1
        with pytest.raises((BledneHaslo, ValueError)):
            Szyfr.otworz(bytes(zmienione), "haslo-1234")


def test_slabe_parametry_z_pliku_odrzucone():
    dane = bytearray(Szyfr("haslo-1234").zaszyfruj(b"x"))
    poz = len(MAGIC3) + 1
    dane[poz:poz + 4] = (8).to_bytes(4, "big")  # podstawione 8 KiB pamięci
    with pytest.raises(ValueError):
        Szyfr.otworz(bytes(dane), "haslo-1234")


def test_urzadzenie_v3():
    sekret = os.urandom(32)
    dane = Szyfr("haslo-1234", sekret=sekret).zaszyfruj(b"abc")
    assert czy_powiazane_z_urzadzeniem(dane)
    with pytest.raises(WymaganeUrzadzenie):
        Szyfr.otworz(dane, "haslo-1234")
    assert Szyfr.otworz(dane, "haslo-1234", sekret)[0] == b"abc"


def test_stary_plik_przechodzi_na_v3(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan", pozycje=[Pozycja("A", 1, 1)]))
    b.szyfr = Szyfr("stare-haslo", wersja=1)  # plik zapisany jak przez starszą wersję programu
    b._utrwal()
    b.zamknij()
    assert (tmp_path / "d.db").read_bytes().startswith(MAGIC)
    b2 = Baza(tmp_path / "d.db", "stare-haslo")
    assert b2.szyfr.wersja == 3
    b2.zamknij()
    assert (tmp_path / "d.db").read_bytes().startswith(MAGIC3)
    assert [d.numer for d in Baza(tmp_path / "d.db", "stare-haslo").dokumenty()] == ["1/10/2026"]


def test_kopie_v2_i_stare():
    assert odszyfruj_kopie(zaszyfruj_kopie(b"kopia", "h-kopii-1"), "h-kopii-1") == b"kopia"
    with pytest.raises(BledneHaslo):
        odszyfruj_kopie(zaszyfruj_kopie(b"kopia", "h-kopii-1"), "zle")
    sol, nonce = os.urandom(16), os.urandom(12)
    stara = MAGIC_KOPII + sol + nonce + AESGCM(klucz_pbkdf2("h", sol)).encrypt(nonce, b"stara", MAGIC_KOPII)
    assert odszyfruj_kopie(stara, "h") == b"stara"


def test_stare_konto_przechodzi_na_argon2(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("haslo-wlasciciela")
    b.dodaj_konto("Kasia", "haslo-kasi-123")
    plik = tmp_path / konta.PLIK_KONT
    dane = json.loads(plik.read_text(encoding="utf-8"))
    wpis = dane["konta"][0]
    assert wpis["kdf"] == "argon2id"
    # symulacja wpisu ze starszej wersji (PBKDF2)
    wpis_k = konta._klucz(wpis, "haslo-kasi-123")
    klucz_konta = AESGCM(wpis_k).decrypt(konta._z_b64(wpis["n1"]), konta._z_b64(wpis["klucz"]),
                                         f"konto:{wpis['id']}".encode())
    sol, n1 = os.urandom(16), os.urandom(12)
    stary = dict(wpis, sol=konta._b64(sol), n1=konta._b64(n1),
                 klucz=konta._b64(AESGCM(klucz_pbkdf2("haslo-kasi-123", sol)).encrypt(
                     n1, klucz_konta, f"konto:{wpis['id']}".encode())))
    del stary["kdf"], stary["argon2"]
    konta.zapisz(tmp_path, [stary])
    wynik = konta.zaloguj(tmp_path, "haslo-kasi-123")
    assert wynik and wynik[1] == b.szyfr.klucz_hasla
    assert konta.wczytaj(tmp_path)[0]["kdf"] == "argon2id"
    assert konta.zaloguj(tmp_path, "haslo-kasi-123")[1] == b.szyfr.klucz_hasla


def test_weryfikator_hasla_dla_deinstalatora(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("haslo-wlasciciela")
    b.powiaz_z_urzadzeniem(os.urandom(32))  # konto administratora nie ma sekretu urządzenia
    b.zamknij()
    assert not Baza.da_sie_otworzyc(tmp_path / "d.db", "haslo-wlasciciela")
    assert Baza.haslo_pasuje(tmp_path, "haslo-wlasciciela")
    assert not Baza.haslo_pasuje(tmp_path, "zle-haslo")
    assert b"haslo" not in (tmp_path / "weryfikator.json").read_bytes()
    b2 = Baza(tmp_path / "d2.db")
    b2.ustaw_haslo("x-haslo-123")
    b2.ustaw_haslo(None)
    assert not (tmp_path / "weryfikator.json").exists()  # usunięcie hasła usuwa weryfikator
