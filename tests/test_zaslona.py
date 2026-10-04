from fakturnik.zaslona import KARA, PAUZA, LicznikSpacji


def seria(licznik, czasy, spacja=True):
    for t in czasy:
        licznik.nacisniecie(spacja, t)


def test_dokladnie_trzy_spacje_odblokowuja():
    l = LicznikSpacji()
    seria(l, [10.0, 10.3, 10.6])
    assert not l.odblokowac(10.7)            # jeszcze trwa pauza: może przyjść czwarta
    assert l.odblokowac(10.6 + PAUZA + 0.01)


def test_cztery_i_wiecej_spacji_nie_odblokowuja():
    l = LicznikSpacji()
    seria(l, [10.0, 10.2, 10.4, 10.5])
    assert not l.odblokowac(12.0)
    seria(l, [10.0 + i * 0.1 for i in range(8)])
    assert not l.odblokowac(15.0)


def test_inny_klawisz_przytrzymanie_i_kara():
    l = LicznikSpacji()
    seria(l, [10.0, 10.2])
    l.nacisniecie(False, 10.3)               # inny klawisz psuje serię
    l.nacisniecie(True, 10.4)
    assert not l.odblokowac(11.5)
    l = LicznikSpacji()
    l.nacisniecie(True, 20.0)
    l.nacisniecie(True, 20.1, powtorzenie=True)  # przytrzymana spacja
    assert not l.odblokowac(25.0)
    # po karze można spróbować od nowa
    t = 20.1 + KARA + 0.1
    seria(l, [t, t + 0.2, t + 0.4])
    assert l.odblokowac(t + 0.4 + PAUZA + 0.01)


def test_spacje_zbyt_rozciagniete_w_czasie():
    l = LicznikSpacji()
    seria(l, [10.0, 11.5, 13.0])             # więcej niż 2 s na trzy spacje
    assert not l.odblokowac(14.0)


def test_wedrowka_obrazu_nie_wychodzi_poza_zapas():
    from fakturnik.zaslona import przesuniecie
    for t in range(0, 3600, 7):
        dx, dy = przesuniecie(t, 300, 120)
        assert abs(dx) <= 300 and abs(dy) <= 120
    pozycje = {tuple(round(v) for v in przesuniecie(t, 300, 120)) for t in range(0, 600, 30)}
    assert len(pozycje) > 10  # obraz faktycznie się przesuwa


def test_gaszenie_ekranu():
    from fakturnik.zaslona import GASNIECIE, jasnosc_po_czasie
    assert jasnosc_po_czasie(10, 600) == 1.0
    assert 0 < jasnosc_po_czasie(600 + GASNIECIE / 2, 600) < 1
    assert jasnosc_po_czasie(600 + GASNIECIE, 600) == 0
    assert jasnosc_po_czasie(99999, 0) == 1.0  # 0 = nigdy nie gaśnie
