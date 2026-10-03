from datetime import date

from fakturnik.baza import Baza, Dokument, Pozycja


def dok(numer, nabywca, kwota=900, pesel=""):
    return Dokument(numer, "2026-10-02", "2026-10-02", "gotówka", nabywca, "", pesel, [Pozycja("Leczenie", 1, kwota)])


def test_kartoteka_pamieta_pacjentow(tmp_path):
    b = Baza(tmp_path / "d.db")
    b.zapisz_dokument(dok("1/10/2026", "Jan Kowalski", pesel="44051401359"))
    b.zapisz_pacjenta("Anna Nowak", "92071512345", "ul. Długa 1")  # dodana ręcznie, bez dokumentu
    assert [p.nazwa for p in b.pacjenci()] == ["Jan Kowalski", "Anna Nowak"]
    assert b.pacjent("Anna Nowak").adres == "ul. Długa 1"
    assert b.pacjent("Jan Kowalski").identyfikator == "44051401359"

    b.zapisz_pacjenta("Anna Nowak-Kowalska", "92071512345", "ul. Krótka 2", stara_nazwa="Anna Nowak")
    assert b.pacjent("Anna Nowak") is None and b.pacjent("Anna Nowak-Kowalska").adres == "ul. Krótka 2"

    b.usun_pacjenta("Jan Kowalski")
    assert b.pacjent("Jan Kowalski") is None
    assert len(b.dokumenty()) == 1  # dokumenty zostają

    b.zamknij()
    assert [p.nazwa for p in Baza(tmp_path / "d.db").pacjenci()] == ["Anna Nowak-Kowalska"]  # pamięta po restarcie


def test_edycja_zachowuje_numer_i_historie(tmp_path):
    b = Baza(tmp_path / "d.db")
    d = b.zapisz_dokument(dok("1/10/2026", "Jan Kowalski", 900))
    d.pozycje = [Pozycja("Leczenie kanałowe 2 kanały", 1, 1200)]
    d.nabywca = "Jan Kowalski-Nowak"
    b.zaktualizuj_dokument(d, "zła kwota")
    po = b.dokument(d.id)
    assert (po.numer, po.suma, po.nabywca, po.poprawiono) == ("1/10/2026", 1200, "Jan Kowalski-Nowak",
                                                              date.today().isoformat())
    wersje = b.wersje(d.id)
    assert len(wersje) == 1 and wersje[0][1] == "zła kwota" and wersje[0][2].suma == 900
    assert b.nastepny_numer(date(2026, 10, 3)) == "2/10/2026"  # edycja nie rusza numeracji
    assert b.pacjent("Jan Kowalski-Nowak") is not None
