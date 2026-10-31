"""PIN właściciela działa przy potwierdzeniach (np. podgląd przychodów), ale NIE w ustawieniach."""
import types

from fakturnik import ui


class FakeBaza:
    ma_haslo = True
    sa_piny = True
    piny_zablokowane = False

    def sprawdz_haslo(self, t):
        return t == "PelneHaslo!"

    def sprawdz_pin(self, t):
        return "" if t == "2580" else ("a1" if t == "1111" else None)  # "" = właściciel, a1 = asystentka


def _okno(baza=None):
    return types.SimpleNamespace(baza=baza or FakeBaza())


def test_pin_wlasciciela_potwierdza():
    sprawdz = ui.OknoGlowne._sprawdz_wlasciciela(_okno())  # pin_ok=True (domyślnie)
    assert sprawdz("PelneHaslo!")      # pełne hasło zawsze działa
    assert sprawdz("2580")             # PIN właściciela działa
    assert not sprawdz("1111")         # PIN asystentki NIE potwierdza operacji właściciela
    assert not sprawdz("9999")         # zły PIN
    assert not sprawdz("ZleHaslo")     # złe hasło


def test_w_ustawieniach_tylko_haslo():
    sprawdz = ui.OknoGlowne._sprawdz_wlasciciela(_okno(), pin_ok=False)
    assert sprawdz("PelneHaslo!")      # tylko pełne hasło
    assert not sprawdz("2580")         # PIN właściciela w ustawieniach NIE działa


def test_pin_nie_dziala_gdy_zablokowany():
    baza = FakeBaza()
    baza.piny_zablokowane = True
    sprawdz = ui.OknoGlowne._sprawdz_wlasciciela(_okno(baza))
    assert not sprawdz("2580")         # po 10 błędach PIN nie potwierdza — potrzebne pełne hasło
    assert sprawdz("PelneHaslo!")


def test_bez_hasla_wszystko_dozwolone_tylko_na_poziomie_okna():
    baza = FakeBaza()
    baza.ma_haslo = False
    # _sprawdz_wlasciciela i tak sprawdza hasło/PIN; bramka „bez hasła” jest w potwierdz_haslem/odslon
    sprawdz = ui.OknoGlowne._sprawdz_wlasciciela(_okno(baza))
    assert sprawdz("PelneHaslo!")
