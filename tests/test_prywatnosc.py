from fakturnik import prywatnosc
from fakturnik.prywatnosc import HKCU, HKLM


class FalszywyRejestr:
    def __init__(self, zablokowany=()):
        self.dane = {}
        self.zablokowany = set(zablokowany)

    def czytaj(self, galaz, klucz, nazwa):
        return self.dane.get((galaz, klucz, nazwa))

    def zapisz(self, galaz, klucz, nazwa, wartosc):
        if galaz in self.zablokowany:
            raise PermissionError("Odmowa dostępu")
        self.dane[(galaz, klucz, nazwa)] = wartosc

    def usun(self, galaz, klucz, nazwa):
        self.dane.pop((galaz, klucz, nazwa), None)


def test_wylaczenie_i_przywrocenie():
    r = FalszywyRejestr()
    assert not any(g["wylaczone"] for g in prywatnosc.stan(r).values())
    assert prywatnosc.zastosuj({HKCU}, r) == []
    stan = prywatnosc.stan(r)
    assert all(g["ustawione"] > 0 for g in stan.values()) and not stan["telemetria"]["wylaczone"]
    assert prywatnosc.zastosuj({HKLM}, r) == []
    assert all(g["wylaczone"] for g in prywatnosc.stan(r).values())
    assert r.czytaj(HKCU, r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot") == 1
    assert r.czytaj(HKLM, r"Software\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis") == 1
    prywatnosc.przywroc({HKCU, HKLM}, r)
    assert r.dane == {}


def test_bez_administratora_zglasza_bledy():
    r = FalszywyRejestr(zablokowany={HKLM})
    bledy = prywatnosc.zastosuj({HKCU, HKLM}, r)
    assert bledy and all(b.startswith("HKLM") for b in bledy)
    assert prywatnosc.stan(r)["copilot"]["brak_admin"] > 0


def test_kazda_grupa_ma_wpisy_dla_uzytkownika_i_komputera():
    for g in prywatnosc.GRUPY:
        galezie = {w.galaz for w in prywatnosc.WPISY if w.grupa == g}
        assert galezie == {HKCU, HKLM}, g
