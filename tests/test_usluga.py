from datetime import datetime, timedelta

from fakturnik import usluga
from fakturnik.baza import Baza, Dokument, Pozycja


def test_kopie_chronione_kazdego_uzytkownika(tmp_path):
    profile = tmp_path / "Users"
    dane = profile / "gabinet" / usluga.NAZWA_DANYCH
    b = Baza(dane / "fakturnik.db")
    b.zapisz_dokument(Dokument("1/10/2026", "2026-10-01", "2026-10-01", "gotówka", "Jan", pozycje=[Pozycja("A", 1, 10)]))
    skan = tmp_path / "skan.pdf"
    skan.write_bytes(b"%PDF-1.4 test")
    b.dodaj_plik(skan)
    b.zamknij()
    (profile / "inny").mkdir(parents=True)  # profil bez Fakturnika jest pomijany

    assert usluga.profile_z_danymi(profile) == [("gabinet", dane)]
    cel = tmp_path / "ProgramData" / "kopie" / "gabinet"
    t = datetime(2026, 10, 3, 12, 0)
    assert usluga.kopia_uzytkownika(dane, cel, t) is True
    assert usluga.kopia_uzytkownika(dane, cel, t + timedelta(hours=1)) is False  # bez zmian: bez nowej kopii
    assert len(list(cel.glob("fakturnik-*.db"))) == 1
    assert len(list((cel / "pliki").glob("*.bin"))) == 1
    assert (cel / "ostatnia-kopia.txt").read_text() == "2026-10-03 13:00"
    kopia = next(cel.glob("fakturnik-*.db"))
    assert [d.numer for d in Baza(kopia).dokumenty()] == ["1/10/2026"]


def test_rotacja_kopii(tmp_path):
    teraz = datetime(2026, 10, 3, 12, 0)
    for godzin in range(0, 24 * 800, 6):  # kopia co 6 godzin przez ponad 2 lata
        (tmp_path / f"fakturnik-{teraz - timedelta(hours=godzin):%Y-%m-%d-%H%M}.db").write_bytes(b"x")
    usluga.rotacja(tmp_path, teraz)
    kopie = sorted(tmp_path.glob("fakturnik-*.db"))
    ostatni_tydzien = [k for k in kopie if k.stem >= f"fakturnik-{teraz - timedelta(days=7):%Y-%m-%d-%H%M}"]
    assert len(ostatni_tydzien) == 7 * 4 + 1  # wszystkie z ostatnich 7 dni
    assert len(kopie) < 7 * 4 + 365 + 24  # starsze przerzedzone (dziennie, potem miesięcznie)
    assert (tmp_path / f"fakturnik-{teraz:%Y-%m-%d-%H%M}.db").exists()
