"""Konta asystentek: każda loguje się własnym hasłem (bez nazwy użytkownika), a dane zostają zaszyfrowane.

Plik danych szyfruje klucz z hasła właściciela. Żeby asystentka mogła go otworzyć bez znajomości tego
hasła, każde konto ma w pliku konta.json:
  * losowy klucz konta (KA), zaszyfrowany kluczem z hasła asystentki (Argon2id, AES-256-GCM;
    starsze wpisy PBKDF2-SHA256 przechodzą na Argon2id przy pierwszym logowaniu),
  * klucz danych (z hasła właściciela), zaszyfrowany kluczem konta KA.
Klucze kont są też zapisane w zaszyfrowanych danych, więc gdy właściciel zmienia hasło, program
przepisuje klucze wszystkich kont bez pytania asystentek o hasła. Usunięcie konta kasuje jego wpis
i klucz; po usunięciu zalecana jest zmiana hasła właściciela (unieważnia stare kopie pliku kont).
Wpisu nie da się podrobić ani podmienić: bez klucza danych nie powstanie poprawny wpis, a identyfikator
konta jest uwierzytelniony (AAD).
"""

import base64
import json
import os
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .szyfrowanie import ARGON2, klucz_argon2, klucz_pbkdf2

PLIK_KONT = "konta.json"
ARGON2_RESETU = (262144, 4, 4)  # klucz do resetu hasła (może być PIN-em): wolniejsze zgadywanie
ROLE = {"wlascicielka": "właściciel", "asystentka": "asystentka"}


def _b64(dane: bytes) -> str:
    return base64.b64encode(dane).decode("ascii")


def _z_b64(tekst: str) -> bytes:
    return base64.b64decode(tekst)


def wczytaj(katalog: Path) -> list[dict]:
    try:
        dane = json.loads((katalog / PLIK_KONT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [k for k in dane.get("konta", []) if isinstance(k, dict) and "id" in k]


def zapisz(katalog: Path, konta: list[dict]) -> None:
    plik = katalog / PLIK_KONT
    tymczasowy = plik.with_suffix(".tmp")
    tymczasowy.write_text(json.dumps({"wersja": 1, "konta": konta}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tymczasowy, plik)


def _klucz(wpis: dict, haslo: str) -> bytes:
    if wpis.get("kdf") == "argon2id":
        return klucz_argon2(haslo, _z_b64(wpis["sol"]), tuple(wpis["argon2"]))
    return klucz_pbkdf2(haslo, _z_b64(wpis["sol"]))


def _wpis(id_: str, nazwa: str, rola: str, haslo: str, klucz_konta: bytes, klucz_danych: bytes,
          parametry: tuple[int, int, int] | None = None) -> dict:
    parametry = tuple(parametry or ARGON2)
    sol, n1, n2 = os.urandom(16), os.urandom(12), os.urandom(12)
    k = klucz_argon2(haslo, sol, parametry)
    return {"id": id_, "nazwa": nazwa, "rola": rola, "kdf": "argon2id", "argon2": list(parametry),
            "sol": _b64(sol), "n1": _b64(n1),
            "klucz": _b64(AESGCM(k).encrypt(n1, klucz_konta, f"konto:{id_}".encode())),
            "n2": _b64(n2), "dane": _b64(AESGCM(klucz_konta).encrypt(n2, klucz_danych, f"dane:{id_}".encode()))}


def nowe_konto(nazwa: str, haslo: str, rola: str, klucz_danych: bytes,
               parametry: tuple[int, int, int] | None = None) -> tuple[dict, bytes]:
    """Zwraca (wpis do pliku kont, klucz konta do zapamiętania w zaszyfrowanych danych)."""
    id_ = uuid.uuid4().hex[:12]
    klucz_konta = os.urandom(32)
    return _wpis(id_, nazwa, rola, haslo, klucz_konta, klucz_danych, parametry), klucz_konta


def nowe_haslo(wpis: dict, haslo: str, klucz_konta: bytes, klucz_danych: bytes) -> dict:
    return _wpis(wpis["id"], wpis["nazwa"], wpis["rola"], haslo, klucz_konta, klucz_danych)


def odnow_klucz_danych(wpis: dict, klucz_konta: bytes, klucz_danych: bytes) -> dict:
    """Po zmianie hasła właściciela: nowy klucz danych dla konta (hasło asystentki bez zmian)."""
    n2 = os.urandom(12)
    return dict(wpis, n2=_b64(n2), dane=_b64(AESGCM(klucz_konta).encrypt(n2, klucz_danych,
                                                                          f"dane:{wpis['id']}".encode())))


def zaloguj(katalog: Path, haslo: str) -> tuple[dict, bytes] | None:
    """Szuka konta, do którego pasuje hasło. Zwraca (wpis, klucz danych) albo None."""
    wszystkie = wczytaj(katalog)
    for i, wpis in enumerate(wszystkie):
        try:
            k = _klucz(wpis, haslo)
            klucz_konta = AESGCM(k).decrypt(_z_b64(wpis["n1"]), _z_b64(wpis["klucz"]), f"konto:{wpis['id']}".encode())
            klucz_danych = AESGCM(klucz_konta).decrypt(_z_b64(wpis["n2"]), _z_b64(wpis["dane"]),
                                                       f"dane:{wpis['id']}".encode())
        except (InvalidTag, KeyError, ValueError, TypeError):
            continue
        if wpis.get("kdf") != "argon2id":  # starszy wpis: przejście na Argon2id (znamy już hasło)
            try:
                wszystkie[i] = _wpis(wpis["id"], wpis["nazwa"], wpis["rola"], haslo, klucz_konta, klucz_danych)
                zapisz(katalog, wszystkie)
                wpis = wszystkie[i]
            except OSError:
                pass
        return wpis, klucz_danych
    return None


def sprawdz_haslo(wpis: dict, haslo: str) -> bool:
    try:
        k = _klucz(wpis, haslo)
        AESGCM(k).decrypt(_z_b64(wpis["n1"]), _z_b64(wpis["klucz"]), f"konto:{wpis['id']}".encode())
        return True
    except (InvalidTag, KeyError, ValueError, TypeError):
        return False
