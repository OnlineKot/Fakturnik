"""Szyfrowanie danych hasłem.

Wersja 3 (obecna):
  * klucz z hasła: Argon2id (128 MiB pamięci, 3 przebiegi, 4 wątki, losowa sól 16 B) — zwycięzca
    Password Hashing Competition i zalecenie RFC 9106. Wymaga dużo pamięci na każdą próbę, więc
    zgadywanie hasła kartami graficznymi i specjalnym sprzętem jest bardzo kosztowne;
  * z klucza hasła (i sekretu urządzenia) HKDF-SHA256 wyprowadza dwa niezależne klucze 256-bitowe;
  * dane są szyfrowane kaskadowo: najpierw AES-256-GCM, potem ChaCha20-Poly1305. Dwa różne szyfry
    z różnymi kluczami: nawet gdyby kiedyś złamano jeden z nich, dane chroni drugi. Oba wykrywają
    złe hasło i każdą zmianę w pliku (uwierzytelnianie, nagłówek z parametrami jako AAD).

Format v3: MAGIC3 | flaga urządzenia (1 B) | [id sekretu urządzenia 8 B] | pamięć KiB (4 B) | przebiegi (1 B) |
           wątki (1 B) | sól (16 B) | nonce AES (12 B) | nonce ChaCha (12 B) | szyfrogram
Starsze formaty (v1/v2: PBKDF2-SHA256 600 000 iteracji + AES-256-GCM) są nadal odczytywane, a plik
przechodzi na v3 przy pierwszym otwarciu hasłem.
"""

import hashlib
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"FAKTURNIK-AES1\n"
# z weryfikacją urządzenia: MAGIC2 | id sekretu urządzenia (8 B) | sól | nonce | szyfrogram
MAGIC2 = b"FAKTURNIK-AES2\n"
MAGIC3 = b"FAKTURNIK-AES3\n"
ITERACJE = 600_000  # PBKDF2, tylko do odczytu starszych plików
ARGON2 = (131072, 3, 4)  # pamięć w KiB (128 MiB), przebiegi, wątki
MIN_ARGON2 = (19456, 2, 1)  # minimum OWASP: nie przyjmujemy słabszych parametrów z pliku


class BledneHaslo(Exception):
    pass


class WymaganeUrzadzenie(Exception):
    """Plik jest powiązany z urządzeniem, a tu brak jego sekretu (inny komputer/konto): potrzebny kod odzyskiwania."""


def klucz_pbkdf2(haslo: str, sol: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", haslo.encode("utf-8"), sol, ITERACJE, dklen=32)


def klucz_argon2(haslo: str, sol: bytes, parametry: tuple[int, int, int] = ARGON2) -> bytes:
    pamiec, przebiegi, watki = parametry
    if pamiec < MIN_ARGON2[0] or przebiegi < MIN_ARGON2[1] or watki < 1 or pamiec > 4 * 1024 * 1024 or watki > 64:
        raise ValueError("Niedozwolone parametry Argon2.")
    return Argon2id(salt=sol, length=32, iterations=przebiegi, lanes=watki, memory_cost=pamiec).derive(
        haslo.encode("utf-8"))


def klucz_z_hasla(haslo: str, sol: bytes) -> bytes:
    """Zgodność wstecz (PBKDF2)."""
    return klucz_pbkdf2(haslo, sol)


def czy_zaszyfrowane(dane: bytes) -> bool:
    return dane.startswith((MAGIC, MAGIC2, MAGIC3))


def czy_powiazane_z_urzadzeniem(dane: bytes) -> bool:
    return dane.startswith(MAGIC2) or (dane.startswith(MAGIC3) and dane[len(MAGIC3):len(MAGIC3) + 1] == b"\x01")


def _id_sekretu(sekret: bytes) -> bytes:
    return hashlib.sha256(b"fakturnik-urzadzenie-id" + sekret).digest()[:8]


def _dwa_klucze(klucz_hasla: bytes, sekret: bytes | None, sol: bytes) -> tuple[bytes, bytes]:
    k = HKDF(algorithm=hashes.SHA256(), length=64, salt=sol,
             info=b"fakturnik-v3-dane" + (b"-urzadzenie" if sekret else b"")).derive(klucz_hasla + (sekret or b""))
    return k[:32], k[32:]


class Szyfr:
    """Klucz wyliczony raz z hasła (i ewentualnie sekretu urządzenia); każdy zapis dostaje nowe nonce.

    wersja 3: Argon2id + AES-256-GCM i ChaCha20-Poly1305; wersja 1: starszy plik (PBKDF2 + AES-256-GCM).
    """

    def __init__(self, haslo: str | None, sol: bytes | None = None, sekret: bytes | None = None,
                 _klucz_hasla: bytes | None = None, wersja: int = 3, parametry: tuple[int, int, int] = ARGON2):
        self.sol = sol or os.urandom(16)
        self.wersja = wersja
        self.parametry = parametry
        self.klucz_hasla = _klucz_hasla or self.klucz_dla(haslo)
        self.sekret = sekret
        if wersja >= 3:
            self.klucz_aes, self.klucz_chacha = _dwa_klucze(self.klucz_hasla, sekret, self.sol)
            self.klucz = self.klucz_aes
        elif sekret:
            self.klucz = hashlib.sha256(b"fakturnik-klucz-urzadzenia" + self.klucz_hasla + sekret).digest()
        else:
            self.klucz = self.klucz_hasla

    def klucz_dla(self, haslo: str) -> bytes:
        """Klucz hasła wyliczony tą samą metodą i solą (do sprawdzania hasła przy odblokowaniu)."""
        return klucz_argon2(haslo, self.sol, self.parametry) if self.wersja >= 3 else klucz_pbkdf2(haslo, self.sol)

    def z_sekretem(self, sekret: bytes | None) -> "Szyfr":
        """Ten sam klucz hasła, z nowym (lub bez) sekretem urządzenia: bez ponownego pytania o hasło."""
        return Szyfr(None, self.sol, sekret, _klucz_hasla=self.klucz_hasla, wersja=self.wersja,
                     parametry=self.parametry)

    def _naglowek(self) -> bytes:
        if self.wersja >= 3:
            urz = b"\x01" + _id_sekretu(self.sekret) if self.sekret else b"\x00"
            return MAGIC3 + urz + struct.pack(">IBB", *self.parametry) + self.sol
        return MAGIC2 + _id_sekretu(self.sekret) if self.sekret else MAGIC

    def zaszyfruj(self, dane: bytes) -> bytes:
        naglowek = self._naglowek()
        if self.wersja >= 3:
            n1, n2 = os.urandom(12), os.urandom(12)
            wewnatrz = AESGCM(self.klucz_aes).encrypt(n1, dane, naglowek)
            return naglowek + n1 + n2 + ChaCha20Poly1305(self.klucz_chacha).encrypt(n2, wewnatrz, naglowek)
        nonce = os.urandom(12)
        return naglowek + self.sol + nonce + AESGCM(self.klucz).encrypt(nonce, dane, naglowek)

    @classmethod
    def otworz(cls, dane: bytes, haslo: str | None, sekret: bytes | None = None,
               klucz_hasla: bytes | None = None) -> tuple[bytes, "Szyfr"]:
        """Odszyfrowuje plik; zwraca dane i szyfr gotowy do kolejnych zapisów."""
        if dane.startswith(MAGIC3):
            poz = len(MAGIC3)
            flaga = dane[poz:poz + 1]
            poz += 1
            if flaga == b"\x01":
                if not sekret or _id_sekretu(sekret) != dane[poz:poz + 8]:
                    raise WymaganeUrzadzenie("Dane są powiązane z innym urządzeniem.")
                poz += 8
            elif flaga == b"\x00":
                sekret = None
            else:
                raise ValueError("Uszkodzony nagłówek pliku.")
            parametry = struct.unpack(">IBB", dane[poz:poz + 6])
            sol = dane[poz + 6:poz + 22]
            naglowek = dane[:poz + 22]
            n1, n2, szyfrogram = dane[poz + 22:poz + 34], dane[poz + 34:poz + 46], dane[poz + 46:]
            szyfr = cls(haslo, sol, sekret, _klucz_hasla=klucz_hasla, wersja=3, parametry=parametry)
            try:
                wewnatrz = ChaCha20Poly1305(szyfr.klucz_chacha).decrypt(n2, szyfrogram, naglowek)
                return AESGCM(szyfr.klucz_aes).decrypt(n1, wewnatrz, naglowek), szyfr
            except InvalidTag:
                raise BledneHaslo("Nieprawidłowe hasło.") from None
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
        szyfr = cls(haslo, sol, sekret, _klucz_hasla=klucz_hasla, wersja=1)  # klucz_hasla: konto asystentki
        try:
            return AESGCM(szyfr.klucz).decrypt(nonce, szyfrogram, naglowek), szyfr
        except InvalidTag:
            raise BledneHaslo("Nieprawidłowe hasło.") from None


# ---------- weryfikator hasła (dla deinstalatora) ----------
# Deinstalator może działać na koncie administratora, które nie ma sekretu urządzenia (DPAPI) użytkownika,
# więc nie odszyfruje danych. Sprawdza hasło weryfikatorem: HMAC z klucza Argon2id hasła (bez danych pacjentów).

def weryfikator(szyfr: "Szyfr") -> dict:
    import base64
    import hmac as _hmac
    return {"wersja": 1, "kdf": "argon2id", "argon2": list(szyfr.parametry),
            "sol": base64.b64encode(szyfr.sol).decode(),
            "skrot": base64.b64encode(_hmac.digest(szyfr.klucz_hasla, b"fakturnik-weryfikator", "sha256")).decode()}


def sprawdz_weryfikator(dane: dict, haslo: str) -> bool:
    import base64
    import hmac as _hmac
    try:
        if dane.get("kdf") != "argon2id":
            return False
        klucz = klucz_argon2(haslo, base64.b64decode(dane["sol"]), tuple(dane["argon2"]))
        return _hmac.compare_digest(_hmac.digest(klucz, b"fakturnik-weryfikator", "sha256"),
                                    base64.b64decode(dane["skrot"]))
    except (KeyError, TypeError, ValueError):
        return False


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

MAGIC_KOPII = b"FAKTURNIK-KOPIA1\n"   # PBKDF2 + AES-256-GCM (tylko odczyt)
MAGIC_KOPII2 = b"FAKTURNIK-KOPIA2\n"  # Argon2id + AES-256-GCM i ChaCha20-Poly1305


def zaszyfruj_kopie(dane: bytes, haslo: str) -> bytes:
    sol = os.urandom(16)
    naglowek = MAGIC_KOPII2 + struct.pack(">IBB", *ARGON2) + sol
    k_aes, k_chacha = _dwa_klucze(klucz_argon2(haslo, sol), None, sol)
    n1, n2 = os.urandom(12), os.urandom(12)
    return naglowek + n1 + n2 + ChaCha20Poly1305(k_chacha).encrypt(n2, AESGCM(k_aes).encrypt(n1, dane, naglowek),
                                                                   naglowek)


def czy_kopia_szyfrowana(dane: bytes) -> bool:
    return dane.startswith((MAGIC_KOPII, MAGIC_KOPII2))


def odszyfruj_kopie(dane: bytes, haslo: str) -> bytes:
    try:
        if dane.startswith(MAGIC_KOPII2):
            poz = len(MAGIC_KOPII2)
            parametry = struct.unpack(">IBB", dane[poz:poz + 6])
            sol, naglowek = dane[poz + 6:poz + 22], dane[:poz + 22]
            n1, n2, szyfrogram = dane[poz + 22:poz + 34], dane[poz + 34:poz + 46], dane[poz + 46:]
            k_aes, k_chacha = _dwa_klucze(klucz_argon2(haslo, sol, parametry), None, sol)
            return AESGCM(k_aes).decrypt(n1, ChaCha20Poly1305(k_chacha).decrypt(n2, szyfrogram, naglowek), naglowek)
        reszta = dane[len(MAGIC_KOPII):]
        sol, nonce, szyfrogram = reszta[:16], reszta[16:28], reszta[28:]
        return AESGCM(klucz_pbkdf2(haslo, sol)).decrypt(nonce, szyfrogram, MAGIC_KOPII)
    except (InvalidTag, struct.error):
        raise BledneHaslo("Nieprawidłowe hasło kopii albo uszkodzony plik.") from None
