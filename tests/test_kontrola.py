from fakturnik import kontrola
from fakturnik.baza import Baza
from fakturnik.ochrona import Dziennik, tylko_do_odczytu


def test_ostrzezenia_ignorowanie_i_przywracanie(tmp_path):
    b = Baza(tmp_path / "d.db")
    wyniki = kontrola.kontrola(b, dziennik_ok=False, program_ok=None)
    klucze = {w.klucz for w in kontrola.do_pokazania(b, wyniki)}
    assert {"haslo", "dziennik"} <= klucze and "program" not in klucze  # „nie wiadomo” to nie ostrzeżenie
    kontrola.zapisz_zignorowane(b, {"dziennik"})
    assert "dziennik" not in {w.klucz for w in kontrola.do_pokazania(b, wyniki)}
    # problem rozwiązany: zignorowanie znika, więc ostrzeżenie wróci, gdy problem się powtórzy
    kontrola.do_pokazania(b, kontrola.kontrola(b, dziennik_ok=True, program_ok=None))
    assert "dziennik" not in kontrola.zignorowane(b)
    assert "dziennik" in {w.klucz for w in kontrola.do_pokazania(b, wyniki)}


def test_nowy_dziennik_po_naruszeniu(tmp_path):
    d = Dziennik(tmp_path / "dziennik.log")
    d.zapisz("a")
    d.zapisz("b")
    tylko_do_odczytu(d.sciezka, False)
    d.sciezka.write_text(d.sciezka.read_text().replace("\ta\t", "\tX\t"), encoding="utf-8")
    assert not d.nienaruszony()
    archiwum = d.archiwizuj()
    assert archiwum.exists() and "X" in archiwum.read_text()  # stary zostaje do wglądu
    assert d.nienaruszony() and archiwum.name in d.wpisy()[0][1]
