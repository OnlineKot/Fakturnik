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
ITERACJE = 600_000


class BledneHaslo(Exception):
    pass


def klucz_z_hasla(haslo: str, sol: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", haslo.encode("utf-8"), sol, ITERACJE, dklen=32)


def czy_zaszyfrowane(dane: bytes) -> bool:
    return dane.startswith(MAGIC)


class Szyfr:
    """Klucz wyliczony raz z hasła; każdy zapis dostaje nowy losowy nonce."""

    def __init__(self, haslo: str, sol: bytes | None = None):
        self.sol = sol or os.urandom(16)
        self.klucz = klucz_z_hasla(haslo, self.sol)

    def zaszyfruj(self, dane: bytes) -> bytes:
        nonce = os.urandom(12)
        return MAGIC + self.sol + nonce + AESGCM(self.klucz).encrypt(nonce, dane, MAGIC)

    @classmethod
    def otworz(cls, dane: bytes, haslo: str) -> tuple[bytes, "Szyfr"]:
        """Odszyfrowuje plik; zwraca dane i szyfr gotowy do kolejnych zapisów."""
        if not czy_zaszyfrowane(dane):
            raise ValueError("Plik nie jest zaszyfrowany.")
        reszta = dane[len(MAGIC):]
        sol, nonce, szyfrogram = reszta[:16], reszta[16:28], reszta[28:]
        szyfr = cls(haslo, sol)
        try:
            return AESGCM(szyfr.klucz).decrypt(nonce, szyfrogram, MAGIC), szyfr
        except InvalidTag:
            raise BledneHaslo("Nieprawidłowe hasło.") from None
