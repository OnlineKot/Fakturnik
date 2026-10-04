from datetime import date, datetime

import pytest

from fakturnik import narzedzia as n


def test_suma_kasy():
    assert n.suma_kasy({20000: 2, 5000: 1, 500: 3, 50: 1, 1: 7}) == 465.57
    assert n.suma_kasy({10000: -3}) == 0


def test_pesel():
    d = n.dane_z_peselu("44051401458")
    assert d.urodzenie == date(1944, 5, 14) and d.plec == "mężczyzna"
    assert d.wiek(date(2026, 5, 13)) == 81 and d.wiek(date(2026, 5, 14)) == 82
    d2 = n.dane_z_peselu("02270803624")
    assert d2.urodzenie == date(2002, 7, 8) and d2.plec == "kobieta"
    assert n.dane_z_peselu("44051401459") is None


def test_daty():
    assert n.przesun_date(date(2026, 8, 31), 6, "miesiące") == date(2027, 2, 28)
    assert n.przesun_date(date(2024, 2, 29), 1, "lata") == date(2025, 2, 28)
    assert n.przesun_date(date(2026, 10, 1), 2, "tygodnie") == date(2026, 10, 15)
    assert n.dni_robocze(date(2026, 10, 2), date(2026, 10, 9)) == 5  # pt → pt
    assert n.dni_robocze(date(2026, 11, 6), date(2026, 11, 13)) == 4  # 11 listopada wolne


def test_swieta():
    assert n.wielkanoc(2026) == date(2026, 4, 5) and n.wielkanoc(2027) == date(2027, 3, 28)
    s26 = n.swieta(2026)
    assert s26[date(2026, 6, 4)] == "Boże Ciało" and s26[date(2026, 5, 24)] == "Zielone Świątki"
    assert date(2026, 12, 24) in s26 and date(2024, 12, 24) not in n.swieta(2024)
    assert n.swieto(date(2026, 11, 11)) == "Święto Niepodległości" and n.swieto(date(2026, 11, 12)) == ""


def test_szybkie_wyszukiwanie():
    assert n.ocena("Kalkulator dat", "kalk") > n.ocena("Kalkulator dat", "dat") > 0
    assert n.ocena("Zamknięcie dnia", "zamkniecie") > 0  # bez ogonków
    assert n.ocena("Jan Kowalski", "kow jan") > 0
    assert n.ocena("Jan Kowalski", "nowak") == 0


def test_rabat_i_raty():
    rabat, po, raty = n.rabat_i_raty(1000, 10, 3)
    assert rabat == 100 and po == 900 and raty == [300, 300, 300]
    _, po, raty = n.rabat_i_raty(100, 0, 3)
    assert raty == [33.33, 33.33, 33.34] and round(sum(raty), 2) == po
    with pytest.raises(ValueError):
        n.rabat_i_raty(100, 120, 1)


def test_haslo():
    h = n.generuj_haslo(16)
    assert len(h) == 16 and any(c.isdigit() for c in h) and any(c.isupper() for c in h)
    assert not set(h) & set("0O1lI")
    assert n.generuj_haslo() != n.generuj_haslo()
    with pytest.raises(ValueError):
        n.generuj_haslo(5)


def test_przypomnienia():
    teraz = datetime(2026, 10, 4, 15, 0)
    assert n.kiedy_przypomniec("16:30", teraz) == datetime(2026, 10, 4, 16, 30)
    assert n.kiedy_przypomniec("9", teraz) == datetime(2026, 10, 5, 9, 0)
    assert n.kiedy_przypomniec("+15", teraz) == datetime(2026, 10, 4, 15, 15)
    lista = n.wczytaj_przypomnienia(n.zapisz_przypomnienia([
        {"kiedy": "2026-10-04T16:30", "tekst": "B"}, {"kiedy": "2026-10-04T14:00", "tekst": "A"}]) )
    assert [p["tekst"] for p in lista] == ["A", "B"]
    teraz_, reszta = n.do_przypomnienia(lista, teraz)
    assert [p["tekst"] for p in teraz_] == ["A"] and [p["tekst"] for p in reszta] == ["B"]
    assert n.wczytaj_przypomnienia("zepsute") == []
