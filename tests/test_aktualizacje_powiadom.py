from pathlib import Path

from fakturnik import usluga
from fakturnik.usluga import NAZWA_DANYCH, PLIK_DANYCH, ZNACZNIK_BEZ_AUTO


def _profil(katalog: Path, nazwa: str) -> Path:
    dane = katalog / nazwa / NAZWA_DANYCH
    dane.mkdir(parents=True)
    (dane / PLIK_DANYCH).write_bytes(b"x")
    return dane


def test_znacznik_wylacza_auto_aktualizacje(tmp_path, monkeypatch):
    monkeypatch.setattr(usluga, "katalog_profili", lambda: tmp_path)
    dane = _profil(tmp_path, "Ania")
    _profil(tmp_path, "Basia")
    assert usluga.auto_aktualizacje_wylaczone() is False
    (dane / ZNACZNIK_BEZ_AUTO).write_text("1")
    assert usluga.auto_aktualizacje_wylaczone() is True


def test_aktualizuj_program_pomija_przy_znaczniku(tmp_path, monkeypatch):
    monkeypatch.setattr(usluga, "katalog_profili", lambda: tmp_path)
    dane = _profil(tmp_path, "Ania")
    (dane / ZNACZNIK_BEZ_AUTO).write_text("1")
    from fakturnik import aktualizacje
    monkeypatch.setattr(aktualizacje, "czy_spakowany", lambda: True)
    assert "tylko powiadamiaj" in usluga.aktualizuj_program()
