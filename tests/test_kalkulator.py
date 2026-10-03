import pytest

from fakturnik.kalkulator import formatuj, oblicz


def test_dzialania():
    assert oblicz("900+150") == 1050
    assert oblicz("200*1,23") == pytest.approx(246)
    assert oblicz("(900+150)/2") == 525
    assert formatuj(oblicz("10/3")) == "3,33"
    assert formatuj(oblicz("1200")) == "1 200"


@pytest.mark.parametrize("zle", ['__import__("os")', "open('x')", "a+1", "1/0", "9**9**9", "[1,2]", "1e999", ""])
def test_nie_wykonuje_kodu_ani_bledow(zle):
    with pytest.raises((ValueError, SyntaxError)):
        oblicz(zle)
