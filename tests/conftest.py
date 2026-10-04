"""Na Linuksie i macOS symulujemy blokadę pliku danych z Windows: druga otwarta kopia bazy
nie może zapisać pliku, który trzyma pierwsza. Dzięki temu testy łapią ten błąd lokalnie,
a nie dopiero przy budowaniu na Windows."""

import sys

import pytest

from fakturnik import ochrona

_trzymane: dict = {}


@pytest.fixture(autouse=True)
def blokada_jak_w_windows(monkeypatch):
    if sys.platform == "win32":
        yield
        return
    _trzymane.clear()
    oryginalne_zaloz, oryginalne_zwolnij = ochrona.BlokadaPliku.zaloz, ochrona.BlokadaPliku.zwolnij

    def zaloz(self):
        wlasciciel = _trzymane.get(self.sciezka)
        if wlasciciel is not None and wlasciciel is not self:
            raise PermissionError(f"plik trzyma inna kopia: {self.sciezka}")
        _trzymane[self.sciezka] = self
        oryginalne_zaloz(self)

    def zwolnij(self):
        if _trzymane.get(self.sciezka) is self:
            del _trzymane[self.sciezka]
        oryginalne_zwolnij(self)

    monkeypatch.setattr(ochrona.BlokadaPliku, "zaloz", zaloz)
    monkeypatch.setattr(ochrona.BlokadaPliku, "zwolnij", zwolnij)
    yield


@pytest.fixture(autouse=True)
def szybkie_ponowienia(monkeypatch):
    """Ponowienia pobierania aktualizacji bez czekania (w programie przerwy rosną od 5 s)."""
    from fakturnik import aktualizacje
    monkeypatch.setattr(aktualizacje, "PRZERWA_POBIERANIA", 0)
    yield
