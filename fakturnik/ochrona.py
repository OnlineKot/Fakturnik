"""Ochrona pliku danych: blokada na czas pracy programu, dziennik logowań i automatyczne kopie.

Uwaga: na Windows żaden program nie zrobi pliku całkowicie nieusuwalnym dla właściciela konta
lub administratora. Dlatego ochrona ma trzy warstwy:
  * gdy program działa, plik jest otwarty bez zgody na zapis i usuwanie przez innych
    (Eksplorator pokaże "plik jest używany"),
  * gdy program jest zamknięty, plik ma atrybut "tylko do odczytu", a zaszyfrowany plik
    jest uwierzytelniony (AES-GCM), więc każda zmiana z zewnątrz zostanie wykryta,
  * automatyczne kopie trafiają do drugiego katalogu, więc usunięcie pliku nie kasuje danych.
"""

import hashlib
import os
import shutil
import stat
import sys
from datetime import date, datetime
from pathlib import Path

ILE_KOPII = 30


# ---------------------------------------------------------------- blokada pliku

class BlokadaPliku:
    """Trzyma plik otwarty tak, by inne programy mogły go tylko czytać (Windows)."""

    def __init__(self, sciezka: Path):
        self.sciezka = sciezka
        self.uchwyt = None

    def zaloz(self) -> None:
        tylko_do_odczytu(self.sciezka, True)
        if sys.platform != "win32" or self.uchwyt is not None or not self.sciezka.exists():
            return
        import ctypes
        from ctypes import wintypes
        CreateFileW = ctypes.windll.kernel32.CreateFileW
        CreateFileW.restype = wintypes.HANDLE
        GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING = 0x80000000, 0x1, 3
        uchwyt = CreateFileW(str(self.sciezka), GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None)
        if uchwyt not in (None, wintypes.HANDLE(-1).value):
            self.uchwyt = uchwyt

    def zwolnij(self) -> None:
        if self.uchwyt is not None:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(self.uchwyt)
            self.uchwyt = None
        tylko_do_odczytu(self.sciezka, False)


def tylko_do_odczytu(sciezka: Path, wlacz: bool) -> None:
    if sciezka.exists():
        os.chmod(sciezka, stat.S_IREAD if wlacz else stat.S_IREAD | stat.S_IWRITE)


# ---------------------------------------------------------------- dziennik

class Dziennik:
    """Dziennik logowań i operacji na danych.

    Każdy wpis zawiera skrót SHA-256 poprzedniego wpisu (łańcuch), więc usunięcie lub zmiana
    dowolnej linii jest wykrywana. Dziennik nie zawiera danych pacjentów.
    """

    def __init__(self, sciezka: Path):
        self.sciezka = sciezka
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        self.po_zapisie = None  # wywoływane ze skrótem nowego wpisu (zapamiętanym w zaszyfrowanej bazie)

    @staticmethod
    def _skrot(poprzedni: str, tresc: str) -> str:
        return hashlib.sha256(f"{poprzedni}|{tresc}".encode("utf-8")).hexdigest()

    def _ostatni_skrot(self) -> str:
        wpisy = self.wpisy()
        return wpisy[-1][2] if wpisy else "0" * 64

    def zapisz(self, zdarzenie: str) -> None:
        tresc = f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{zdarzenie}"
        skrot = self._skrot(self._ostatni_skrot(), tresc)
        tylko_do_odczytu(self.sciezka, False)
        with open(self.sciezka, "a", encoding="utf-8") as f:
            f.write(f"{tresc}\t{skrot}\n")
        tylko_do_odczytu(self.sciezka, True)
        if self.po_zapisie:
            self.po_zapisie(skrot)

    def archiwizuj(self) -> Path | None:
        """Zamyka obecny dziennik (np. po sprawdzeniu ostrzeżenia o naruszeniu) i zaczyna nowy.
        Stary zostaje obok, tylko do odczytu, a pierwszy wpis nowego wskazuje go z jego skrótem SHA-256."""
        if not self.sciezka.exists():
            return None
        cel = self.sciezka.with_name(f"{self.sciezka.stem}-{datetime.now():%Y%m%d-%H%M%S}{self.sciezka.suffix}")
        skrot = hashlib.sha256(self.sciezka.read_bytes()).hexdigest()
        tylko_do_odczytu(self.sciezka, False)
        os.replace(self.sciezka, cel)
        tylko_do_odczytu(cel, True)
        self.zapisz(f"nowy dziennik; poprzedni zarchiwizowany: {cel.name} (SHA-256 {skrot})")
        return cel

    def zawiera(self, skrot: str) -> bool:
        """Czy wpis o tym skrócie wciąż jest w dzienniku (gdy nie ma, dziennik ucięto lub podmieniono)."""
        return any(w[2] == skrot for w in self.wpisy())

    def wpisy(self) -> list[tuple[str, str, str]]:
        """Lista (czas, zdarzenie, skrót)."""
        if not self.sciezka.exists():
            return []
        wynik = []
        for linia in self.sciezka.read_text(encoding="utf-8").splitlines():
            czesci = linia.split("\t")
            if len(czesci) == 3:
                wynik.append((czesci[0], czesci[1], czesci[2]))
        return wynik

    def nienaruszony(self) -> bool:
        poprzedni = "0" * 64
        if self.sciezka.exists():
            linie = self.sciezka.read_text(encoding="utf-8").splitlines()
            if len(linie) != len(self.wpisy()):
                return False
        for czas, zdarzenie, skrot in self.wpisy():
            if self._skrot(poprzedni, f"{czas}\t{zdarzenie}") != skrot:
                return False
            poprzedni = skrot
        return True


# ---------------------------------------------------------------- kopie automatyczne

def katalog_kopii() -> Path:
    return Path.home() / "Documents" / "Fakturnik" / "kopie"


def kopia_automatyczna(plik: Path, katalog: Path | None = None, nazwa: str | None = None) -> Path | None:
    """Kopiuje plik danych (w postaci, w jakiej leży na dysku, czyli zaszyfrowany, jeśli jest hasło).

    Bez `nazwa`: jedna kopia dziennie, zostaje ostatnie 30. Z `nazwa` (np. przed aktualizacją)
    kopia ma własną nazwę i nie jest usuwana automatycznie.
    """
    if not plik.exists():
        return None
    katalog = katalog or katalog_kopii()
    katalog.mkdir(parents=True, exist_ok=True)
    cel = katalog / (nazwa or f"fakturnik-{date.today().isoformat()}.db")
    tylko_do_odczytu(cel, False)
    shutil.copyfile(plik, cel)
    tylko_do_odczytu(cel, True)
    kopie = sorted(katalog.glob("fakturnik-*.db"))
    for stara in kopie[:-ILE_KOPII]:
        tylko_do_odczytu(stara, False)
        stara.unlink()
    return cel


def lista_kopii(katalog: Path | None = None) -> list[Path]:
    """Kopie automatyczne pliku danych, od najnowszej."""
    katalog = katalog or katalog_kopii()
    if not katalog.exists():
        return []
    return sorted((k for k in katalog.glob("*.db") if k.is_file()), key=lambda k: k.stat().st_mtime, reverse=True)


def odtworz_z_kopii(plik: Path, kopia: Path) -> Path:
    """Wstawia kopię w miejsce pliku danych; uszkodzony plik zostaje obok (nic nie jest kasowane)."""
    uszkodzony = plik.with_name(f"{plik.stem}.uszkodzony-{datetime.now():%Y%m%d-%H%M%S}{plik.suffix}")
    if plik.exists():
        tylko_do_odczytu(plik, False)
        os.replace(plik, uszkodzony)
    shutil.copyfile(kopia, plik)
    tylko_do_odczytu(plik, True)
    return uszkodzony
