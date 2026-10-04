from fakturnik.zaslona import ODSTEP, PAUZA, LicznikSpacji


def seria(licznik, czasy, spacja=True):
    for t in czasy:
        licznik.nacisniecie(spacja, t)


def test_dokladnie_piec_spacji_odblokowuje():
    l = LicznikSpacji()
    seria(l, [10.0, 10.3, 10.6])
    assert not l.odblokowac(10.6 + PAUZA + 0.01)  # trzy to za mało
    seria(l, [10.9, 11.2])
    assert not l.odblokowac(11.3)            # jeszcze trwa pauza: może przyjść szósta
    assert l.odblokowac(11.2 + PAUZA + 0.01)


def test_szesc_i_wiecej_spacji_nie_odblokowuje():
    l = LicznikSpacji()
    seria(l, [10.0, 10.2, 10.4, 10.5, 10.6, 10.7])
    assert not l.odblokowac(12.0)
    l = LicznikSpacji()
    seria(l, [10.0 + i * 0.1 for i in range(8)])
    assert not l.odblokowac(15.0)


def test_inny_klawisz_i_przytrzymanie_kasuja_serie_bez_kary():
    l = LicznikSpacji()
    seria(l, [10.0, 10.2])
    l.nacisniecie(False, 10.3)               # inny klawisz psuje serię
    seria(l, [10.4, 10.6, 10.8])
    assert not l.odblokowac(12.0)
    l = LicznikSpacji()
    l.nacisniecie(True, 20.0)
    l.nacisniecie(True, 20.1, powtorzenie=True)  # przytrzymana spacja
    assert not l.odblokowac(25.0)
    seria(l, [20.3, 20.5, 20.7, 20.9, 21.1])  # od razu można spróbować ponownie
    assert l.odblokowac(21.1 + PAUZA + 0.01)


def test_wolne_stukanie_dziala():
    l = LicznikSpacji()
    t = [10.0 + i * 1.2 for i in range(5)]   # spacja co 1,2 s
    seria(l, t)
    assert l.odblokowac(t[-1] + PAUZA + 0.01)


def test_wczesniejsza_przypadkowa_spacja_nie_przeszkadza():
    l = LicznikSpacji()
    l.nacisniecie(True, 5.0)                 # np. ktoś stuknął spację, żeby obudzić ekran
    t = 5.0 + ODSTEP + 0.5
    seria(l, [t, t + 0.3, t + 0.6, t + 0.9, t + 1.2])
    assert l.odblokowac(t + 1.2 + PAUZA + 0.01)


def test_zbyt_dlugie_przerwy_zaczynaja_od_nowa():
    l = LicznikSpacji()
    seria(l, [10.0, 12.0, 14.0, 16.0, 18.0])  # co 2 s: każda spacja to nowa seria
    assert not l.odblokowac(19.0)


def test_odbijanie_od_krawedzi():
    from fakturnik.zaslona import odbicie
    pozycje = [odbicie(d, 500) for d in range(0, 5000, 13)]
    assert all(0 <= x <= 500 for x in pozycje)
    assert odbicie(250, 500) == 250 and odbicie(750, 500) == 250  # odbija się i wraca
    assert odbicie(123, 0) == 0


def test_gaszenie_ekranu():
    from fakturnik.zaslona import GASNIECIE, jasnosc_po_czasie
    assert jasnosc_po_czasie(10, 600) == 1.0
    assert 0 < jasnosc_po_czasie(600 + GASNIECIE / 2, 600) < 1
    assert jasnosc_po_czasie(600 + GASNIECIE, 600) == 0
    assert jasnosc_po_czasie(99999, 0) == 1.0  # 0 = nigdy nie gaśnie
