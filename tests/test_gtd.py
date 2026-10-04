from datetime import date, datetime

from fakturnik import gtd

DZIS = date(2026, 10, 7)  # środa


def test_szybkie_dodawanie():
    z = gtd.z_linii("Zadzwonić do laboratorium @telefon jutro !", DZIS)
    assert (z.tekst, z.kontekst, z.termin, z.wazne, z.lista) == (
        "Zadzwonić do laboratorium", "telefon", "2026-10-08", True, "skrzynka")
    assert gtd.z_linii("Zamówić rękawiczki pt", DZIS).termin == "2026-10-09"
    assert gtd.z_linii("Przegląd śr", DZIS).termin == "2026-10-14"  # najbliższa środa po dziś
    assert gtd.z_linii("Faktura 3.10", DZIS).termin == "2027-10-03"  # data bez roku już minęła
    assert gtd.z_linii("Faktura 15.10.2026", DZIS).termin == "2026-10-15"
    assert gtd.z_linii("Spotkanie 31.02", DZIS).tekst == "Spotkanie 31.02"  # zła data zostaje w tekście
    assert gtd.z_linii("  @telefon ! ", DZIS) is None


def test_widoki_i_liczniki():
    zadania = [
        gtd.Zadanie("A", "nastepne", termin="2026-10-07"),
        gtd.Zadanie("B", "nastepne", termin="2026-10-06"),
        gtd.Zadanie("C", "skrzynka"),
        gtd.Zadanie("D", "kiedys", wazne=True),
        gtd.Zadanie("E", "czekam", kontekst="laboratorium"),
    ]
    assert [z.tekst for z in gtd.w_widoku(zadania, "dzis", dzis=DZIS)] == ["D", "B", "A"]
    assert zadania[1].po_terminie(DZIS) and not zadania[0].po_terminie(DZIS)
    gtd.odhacz(zadania[0])
    assert zadania[0].zrobione and zadania[0].zrobiono
    assert gtd.liczniki(zadania, DZIS) == {"dzis": 2, "skrzynka": 1, "nastepne": 1, "czekam": 1, "kiedys": 1,
                                           "zrobione": 1}
    assert [z.tekst for z in gtd.w_widoku(zadania, "czekam", "laboratorium")] == ["E"]
    assert gtd.konteksty(zadania)[0] == "laboratorium"
    gtd.odhacz(zadania[0], False)
    assert zadania[0].lista == "nastepne" and not zadania[0].zrobiono


def test_zapis_odczyt_i_czyszczenie():
    zadania = [gtd.Zadanie("Ząb", "nastepne", "gabinet", "2026-10-07", True)]
    wczytane = gtd.wczytaj(gtd.zapisz(zadania))
    assert wczytane == zadania
    assert gtd.wczytaj("zepsute") == [] and gtd.wczytaj('[{"tekst": "x", "lista": "dzis", "obce": 1}]')[0].lista == "skrzynka"
    stare = gtd.Zadanie("stare", "zrobione", zrobiono="2026-08-01T10:00")
    nowe = gtd.Zadanie("nowe", "zrobione", zrobiono="2026-10-06T10:00")
    assert gtd.wyczysc_zrobione([stare, nowe], 30, datetime(2026, 10, 7)) == [nowe]


def test_opis_terminu():
    assert gtd.opis_terminu("2026-10-07", DZIS) == "dziś"
    assert gtd.opis_terminu("2026-10-08", DZIS) == "jutro"
    assert gtd.opis_terminu("2026-10-10", DZIS) == "sob"
    assert gtd.opis_terminu("2027-01-05", DZIS) == "05.01.2027"
