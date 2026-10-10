import pytest

from fakturnik import konta
from fakturnik.baza import PROBY_PIN, ROLA_RESETU, Baza, blad_hasla_resetu, jest_pin


@pytest.fixture
def baza(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.ustaw_haslo("haslo-wlasciciela")
    return b


def test_pin_odblokowuje_i_ma_limit_prob(baza):
    id_kasi = baza.dodaj_konto("Kasia", "haslo-kasi-123")
    baza.ustaw_pin("", "2580")
    baza.ustaw_pin(id_kasi, "7319")
    assert baza.sprawdz_pin("2580") == "" and baza.sprawdz_pin("7319") == id_kasi
    with pytest.raises(ValueError):
        baza.ustaw_pin(id_kasi, "2580")       # każde konto ma własny PIN
    for pin in ("1111", "123", "abcd", "123456789"):
        with pytest.raises(ValueError):
            baza.ustaw_pin("", pin)
    for _ in range(PROBY_PIN):
        assert baza.sprawdz_pin("9999") is None
    assert baza.piny_zablokowane
    assert baza.sprawdz_pin("2580") is None   # po 5 błędach nawet dobry PIN nie działa
    baza.zaloguj_pelnym_haslem()
    assert baza.sprawdz_pin("2580") == ""


def test_pin_nie_jest_w_pliku_jawnie_i_znika_z_kontem(baza, tmp_path):
    id_kasi = baza.dodaj_konto("Kasia", "haslo-kasi-123")
    baza.ustaw_pin(id_kasi, "7319")
    assert b"7319" not in (tmp_path / "d.db").read_bytes()
    baza.usun_konto(id_kasi)
    assert not baza.ma_pin(id_kasi) and baza.sprawdz_pin("7319") is None


def test_haslo_resetu_otwiera_dane_i_przezywa_zmiane_hasla(baza, tmp_path):
    baza.ustaw_haslo_resetu("482913")
    assert baza.ma_haslo_resetu and baza.konta() == []  # nie jest widoczne jako konto asystentki
    baza.ustaw_haslo("inne-haslo-wlasciciela")
    baza.zamknij()
    wpis, klucz = konta.zaloguj(tmp_path, "482913")
    assert wpis["rola"] == ROLA_RESETU and wpis["argon2"] == list(konta.ARGON2_RESETU)
    b2 = Baza(tmp_path / "d.db", klucz_hasla=klucz)
    assert b2.konto(wpis["id"])["rola"] == ROLA_RESETU
    b2.ustaw_haslo("nowe-haslo-po-resecie")    # reset: nowe hasło właściciela
    b2.zamknij()
    Baza(tmp_path / "d.db", "nowe-haslo-po-resecie").zamknij()
    assert konta.zaloguj(tmp_path, "482913") is not None  # hasło do resetu dalej działa


def test_zasady_hasla_resetu(baza):
    assert blad_hasla_resetu("12345") and blad_hasla_resetu("111111") and blad_hasla_resetu("123456")
    assert blad_hasla_resetu("krotkie")
    assert blad_hasla_resetu("482913") is None and blad_hasla_resetu("dlugie-haslo") is None
    with pytest.raises(ValueError):
        baza.ustaw_haslo_resetu("haslo-wlasciciela")
    assert jest_pin("0042") and not jest_pin("１２３４")  # tylko cyfry ASCII
