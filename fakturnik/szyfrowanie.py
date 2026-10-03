"""Szyfrowanie pliku z danymi hasłem.

Klucz 256-bitowy powstaje z hasła przez PBKDF2-HMAC-SHA256 (600 000 iteracji, losowa sól),
a dane są szyfrowane AES-256-GCM. GCM wykrywa też złe hasło i każdą zmianę w pliku.

Format pliku zaszyfrowanego: MAGIC | sól (16 B) | nonce (12 B) | szyfrogram z tagiem.
"""

import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"FAKTURNIK-AES1\n"
# z weryfikacją urządzenia: MAGIC2 | id sekretu urządzenia (8 B) | sól | nonce | szyfrogram
MAGIC2 = b"FAKTURNIK-AES2\n"
ITERACJE = 600_000


class BledneHaslo(Exception):
    pass


class WymaganeUrzadzenie(Exception):
    """Plik jest powiązany z urządzeniem, a tu brak jego sekretu (inny komputer/konto): potrzebny kod odzyskiwania."""


def klucz_z_hasla(haslo: str, sol: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", haslo.encode("utf-8"), sol, ITERACJE, dklen=32)


def czy_zaszyfrowane(dane: bytes) -> bool:
    return dane.startswith(MAGIC) or dane.startswith(MAGIC2)


def czy_powiazane_z_urzadzeniem(dane: bytes) -> bool:
    return dane.startswith(MAGIC2)


def _id_sekretu(sekret: bytes) -> bytes:
    return hashlib.sha256(b"fakturnik-urzadzenie-id" + sekret).digest()[:8]


class Szyfr:
    """Klucz wyliczony raz z hasła (i ewentualnie sekretu urządzenia); każdy zapis dostaje nowy nonce."""

    def __init__(self, haslo: str | None, sol: bytes | None = None, sekret: bytes | None = None,
                 _klucz_hasla: bytes | None = None):
        self.sol = sol or os.urandom(16)
        self.klucz_hasla = _klucz_hasla or klucz_z_hasla(haslo, self.sol)
        self.sekret = sekret
        if sekret:
            self.klucz = hashlib.sha256(b"fakturnik-klucz-urzadzenia" + self.klucz_hasla + sekret).digest()
        else:
            self.klucz = self.klucz_hasla

    def z_sekretem(self, sekret: bytes | None) -> "Szyfr":
        """Ten sam klucz hasła, z nowym (lub bez) sekretem urządzenia: bez ponownego pytania o hasło."""
        return Szyfr(None, self.sol, sekret, _klucz_hasla=self.klucz_hasla)

    def _naglowek(self) -> bytes:
        return MAGIC2 + _id_sekretu(self.sekret) if self.sekret else MAGIC

    def zaszyfruj(self, dane: bytes) -> bytes:
        nonce = os.urandom(12)
        naglowek = self._naglowek()
        return naglowek + self.sol + nonce + AESGCM(self.klucz).encrypt(nonce, dane, naglowek)

    @classmethod
    def otworz(cls, dane: bytes, haslo: str, sekret: bytes | None = None) -> tuple[bytes, "Szyfr"]:
        """Odszyfrowuje plik; zwraca dane i szyfr gotowy do kolejnych zapisów."""
        if dane.startswith(MAGIC2):
            id_pliku = dane[len(MAGIC2):len(MAGIC2) + 8]
            if not sekret or _id_sekretu(sekret) != id_pliku:
                raise WymaganeUrzadzenie("Dane są powiązane z innym urządzeniem.")
            naglowek, reszta = dane[:len(MAGIC2) + 8], dane[len(MAGIC2) + 8:]
        elif dane.startswith(MAGIC):
            naglowek, reszta, sekret = MAGIC, dane[len(MAGIC):], None
        else:
            raise ValueError("Plik nie jest zaszyfrowany.")
        sol, nonce, szyfrogram = reszta[:16], reszta[16:28], reszta[28:]
        szyfr = cls(haslo, sol, sekret)
        try:
            return AESGCM(szyfr.klucz).decrypt(nonce, szyfrogram, naglowek), szyfr
        except InvalidTag:
            raise BledneHaslo("Nieprawidłowe hasło.") from None


# ---------- pliki wrzucone do programu ----------
# Każdy plik jest szyfrowany losowym kluczem 256-bitowym zapisanym w bazie. Gdy baza ma hasło,
# klucz jest chroniony razem z nią, więc zmiana hasła nie wymaga przepisywania plików.

MAGIC_PLIKU = b"FAKTURNIK-PLIK1\n"


def nowy_klucz() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def zaszyfruj_plik(dane: bytes, klucz: bytes) -> bytes:
    nonce = os.urandom(12)
    return MAGIC_PLIKU + nonce + AESGCM(klucz).encrypt(nonce, dane, MAGIC_PLIKU)


def odszyfruj_plik(dane: bytes, klucz: bytes) -> bytes:
    if not dane.startswith(MAGIC_PLIKU):
        raise ValueError("Nieznany format pliku.")
    reszta = dane[len(MAGIC_PLIKU):]
    try:
        return AESGCM(klucz).decrypt(reszta[:12], reszta[12:], MAGIC_PLIKU)
    except InvalidTag:
        raise ValueError("Plik jest uszkodzony albo został zmieniony poza programem.") from None


# ---------- szyfrowana kopia zapasowa (własne hasło, może być inne niż hasło programu) ----------

MAGIC_KOPII = b"FAKTURNIK-KOPIA1\n"


def zaszyfruj_kopie(dane: bytes, haslo: str) -> bytes:
    sol, nonce = os.urandom(16), os.urandom(12)
    return MAGIC_KOPII + sol + nonce + AESGCM(klucz_z_hasla(haslo, sol)).encrypt(nonce, dane, MAGIC_KOPII)


def czy_kopia_szyfrowana(dane: bytes) -> bool:
    return dane.startswith(MAGIC_KOPII)


def odszyfruj_kopie(dane: bytes, haslo: str) -> bytes:
    reszta = dane[len(MAGIC_KOPII):]
    sol, nonce, szyfrogram = reszta[:16], reszta[16:28], reszta[28:]
    try:
        return AESGCM(klucz_z_hasla(haslo, sol)).decrypt(nonce, szyfrogram, MAGIC_KOPII)
    except InvalidTag:
        raise BledneHaslo("Nieprawidłowe hasło kopii albo uszkodzony plik.") from None
