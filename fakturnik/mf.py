"""Dane firmy po NIP z oficjalnego wykazu podatników VAT („biała lista”, Ministerstwo Finansów).

API: https://wl-api.mf.gov.pl/api/search/nip/{nip}?date=RRRR-MM-DD (publiczne, bez klucza, HTTPS).
Wysyłany jest tylko NIP nabywcy (dane publiczne firmy); żadne dane pacjentów nie opuszczają komputera.
"""

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

from .walidacja import nip_poprawny

ADRES = "https://wl-api.mf.gov.pl/api/search/nip/{nip}?date={data}"


class BladMF(Exception):
    pass


@dataclass
class Firma:
    nazwa: str
    nip: str
    status_vat: str
    adres: str
    regon: str = ""
    krs: str = ""
    konta: list[str] = field(default_factory=list)


def z_odpowiedzi(dane: dict) -> Firma | None:
    """Odpowiedź API → Firma; None, gdy podmiotu nie ma w wykazie."""
    if "code" in dane and "result" not in dane:
        raise BladMF(dane.get("message") or f"Błąd serwisu MF ({dane['code']}).")
    podmiot = (dane.get("result") or {}).get("subject")
    if not podmiot:
        return None
    adres = podmiot.get("workingAddress") or podmiot.get("residenceAddress") or ""
    return Firma(nazwa=(podmiot.get("name") or "").strip(), nip=podmiot.get("nip") or "",
                 status_vat=podmiot.get("statusVat") or "", adres=adres.strip(), regon=podmiot.get("regon") or "",
                 krs=podmiot.get("krs") or "", konta=list(podmiot.get("accountNumbers") or []))


def szukaj(nip: str, dzien: date | None = None, timeout: float = 12) -> Firma | None:
    nip = "".join(c for c in nip if c.isdigit())
    if not nip_poprawny(nip):
        raise BladMF("To nie jest poprawny NIP (zła cyfra kontrolna).")
    adres = ADRES.format(nip=nip, data=(dzien or date.today()).isoformat())
    zadanie = urllib.request.Request(adres, headers={"Accept": "application/json", "User-Agent": "Fakturnik"})
    try:
        with urllib.request.urlopen(zadanie, timeout=timeout) as odpowiedz:
            if urlparse(odpowiedz.geturl()).hostname != "wl-api.mf.gov.pl":
                raise BladMF("Nieoczekiwane przekierowanie serwisu MF.")
            tresc = odpowiedz.read(512 * 1024)
    except BladMF:
        raise
    except Exception as e:
        raise BladMF(f"Nie udało się połączyć z serwisem Ministerstwa Finansów ({e}).") from None
    try:
        return z_odpowiedzi(json.loads(tresc.decode("utf-8")))
    except ValueError:
        raise BladMF("Serwis Ministerstwa Finansów jest chwilowo niedostępny. Spróbuj za chwilę.") from None


def adres_dwulinijkowy(adres: str) -> str:
    """„UL. DŁUGA 1, 00-001 WARSZAWA” → „ul. Długa 1, 00-001 Warszawa” (czytelniej na fakturze)."""
    def ladnie(slowo: str) -> str:
        if slowo.upper() in ("UL.", "AL.", "PL.", "OS."):
            return slowo.lower()
        return slowo if any(c.isdigit() for c in slowo) else slowo.capitalize()
    return ", ".join(" ".join(ladnie(s) for s in czesc.split()) for czesc in adres.split(","))
