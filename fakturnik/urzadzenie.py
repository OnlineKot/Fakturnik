"""Weryfikacja urządzenia i stan bezpieczeństwa komputera.

Weryfikacja urządzenia: do hasła dochodzi losowy sekret urządzenia (160 bitów). Klucz szyfrujący dane
powstaje z obu, więc skopiowany plik danych (albo kopia) nie otworzy się na innym komputerze nawet
z hasłem. Sekret leży na tym komputerze zaszyfrowany przez Windows (DPAPI), czyli odczyta go tylko
to konto Windows na tym komputerze. Do przeniesienia danych na nowy komputer służy kod odzyskiwania
(ten sam sekret zapisany jako 32 znaki) albo pakiet migracji (szyfrowana kopia z osobnym hasłem).
"""

import base64
import os
import platform
import sys
from pathlib import Path

PLIK_SEKRETU = "urzadzenie.bin"
DLUGOSC_SEKRETU = 20


class BrakDPAPI(Exception):
    pass


def dostepne() -> bool:
    return sys.platform == "win32"


def nowy_sekret() -> bytes:
    return os.urandom(DLUGOSC_SEKRETU)


def kod_odzyskiwania(sekret: bytes) -> str:
    """Sekret jako 8 grup po 4 znaki (bez 0/1/8/9, które łatwo pomylić z literami)."""
    znaki = base64.b32encode(sekret).decode("ascii").rstrip("=")
    return "-".join(znaki[i:i + 4] for i in range(0, len(znaki), 4))


def sekret_z_kodu(kod: str) -> bytes | None:
    czysty = "".join(c for c in kod.upper() if c.isalnum()).replace("0", "O").replace("1", "I").replace("8", "B")
    if len(czysty) != 32:
        return None
    try:
        return base64.b32decode(czysty)
    except ValueError:
        return None


# ---------------------------------------------------------------- DPAPI (Windows)

def _blob(dane: bytes):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    bufor = ctypes.create_string_buffer(dane, len(dane))
    return DATA_BLOB(len(dane), ctypes.cast(bufor, ctypes.POINTER(ctypes.c_char))), bufor, DATA_BLOB


def _dpapi(dane: bytes, szyfruj: bool) -> bytes:
    if not dostepne():
        raise BrakDPAPI("Weryfikacja urządzenia działa na Windows.")
    import ctypes
    wejscie, _bufor, DATA_BLOB = _blob(dane)
    wyjscie = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    funkcja = crypt32.CryptProtectData if szyfruj else crypt32.CryptUnprotectData
    ok = funkcja(ctypes.byref(wejscie), "Fakturnik" if szyfruj else None, None, None, None,
                 CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(wyjscie))
    if not ok:
        raise BrakDPAPI("Windows nie odszyfrował klucza urządzenia (inne konto lub inny komputer).")
    try:
        return ctypes.string_at(wyjscie.pbData, wyjscie.cbData)
    finally:
        kernel32.LocalFree(wyjscie.pbData)


def zapisz_sekret(katalog: Path, sekret: bytes) -> None:
    plik = katalog / PLIK_SEKRETU
    tymczasowy = plik.with_suffix(".tmp")
    tymczasowy.write_bytes(_dpapi(sekret, True))
    os.replace(tymczasowy, plik)


def wczytaj_sekret(katalog: Path) -> bytes | None:
    """Sekret tego urządzenia albo None (brak, inne konto Windows, inny komputer)."""
    plik = katalog / PLIK_SEKRETU
    try:
        return _dpapi(plik.read_bytes(), False)
    except (OSError, BrakDPAPI):
        return None


def usun_sekret(katalog: Path) -> None:
    (katalog / PLIK_SEKRETU).unlink(missing_ok=True)


# ---------------------------------------------------------------- stan komputera

def nazwa_urzadzenia() -> str:
    return platform.node() or "ten komputer"


def secure_boot() -> bool | None:
    """True/False według Windows; None, gdy nie da się sprawdzić (np. stary BIOS bez UEFI albo nie Windows)."""
    if not dostepne():
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\SecureBoot\State") as k:
            wartosc, _ = winreg.QueryValueEx(k, "UEFISecureBootEnabled")
            return bool(wartosc)
    except OSError:
        return None


def konto_administratora() -> bool | None:
    if not dostepne():
        return None
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return None
