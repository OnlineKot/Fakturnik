"""Notatki w stylu GTD (Getting Things Done): wszystko trafia najpierw do Skrzynki, potem do list.

Szybkie wpisywanie w jednej linii:
  „Zadzwonić do laboratorium @telefon jutro !”  →  kontekst „telefon”, termin jutro, ważne.
Terminy: „dziś”, „jutro”, „pojutrze”, dzień tygodnia („pt”, „piątek”) albo data „15.10” / „15.10.2026”.
Dane są w zaszyfrowanych ustawieniach (klucz „gtd”), wspólne dla wszystkich kont.
"""

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

LISTY = [
    ("dzis", "Dziś"),
    ("skrzynka", "Skrzynka"),
    ("nastepne", "Następne działania"),
    ("czekam", "Czekam na"),
    ("kiedys", "Kiedyś / może"),
    ("zrobione", "Zrobione"),
]
NAZWY_LIST = dict(LISTY)
PRZENOSZENIE = ["skrzynka", "nastepne", "czekam", "kiedys"]  # listy, do których przenosi się zadanie
KONTEKSTY = ["telefon", "gabinet", "komputer", "sprawy", "laboratorium"]

_DNI = {"pon": 0, "poniedziałek": 0, "wt": 1, "wtorek": 1, "śr": 2, "sr": 2, "środa": 2, "sroda": 2,
        "czw": 3, "czwartek": 3, "pt": 4, "piątek": 4, "piatek": 4, "sob": 5, "sobota": 5,
        "nd": 6, "niedz": 6, "niedziela": 6}


@dataclass
class Zadanie:
    tekst: str
    lista: str = "skrzynka"
    kontekst: str = ""
    termin: str = ""           # RRRR-MM-DD albo ""
    wazne: bool = False
    utworzono: str = field(default_factory=lambda: datetime.now().isoformat(timespec="minutes"))
    zrobiono: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def zrobione(self) -> bool:
        return self.lista == "zrobione"

    def po_terminie(self, dzis: date | None = None) -> bool:
        return bool(self.termin) and not self.zrobione and self.termin < (dzis or date.today()).isoformat()


def termin_z_slowa(slowo: str, dzis: date) -> date | None:
    s = slowo.lower().strip(".,")
    if s in ("dziś", "dzis", "dzisiaj"):
        return dzis
    if s == "jutro":
        return dzis + timedelta(days=1)
    if s == "pojutrze":
        return dzis + timedelta(days=2)
    if s in _DNI:
        return dzis + timedelta(days=(_DNI[s] - dzis.weekday() - 1) % 7 + 1)  # najbliższy taki dzień po dziś
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", s)
    if m:
        d, mies, rok = int(m[1]), int(m[2]), int(m[3]) if m[3] else dzis.year
        try:
            wynik = date(rok, mies, d)
        except ValueError:
            return None
        if not m[3] and wynik < dzis:
            try:
                wynik = date(rok + 1, mies, d)
            except ValueError:
                return None
        return wynik
    return None


def z_linii(linia: str, dzis: date | None = None, lista: str = "skrzynka") -> Zadanie | None:
    """Szybkie dodanie: tekst z @kontekstem, terminem i „!” (ważne)."""
    dzis = dzis or date.today()
    kontekst, termin, wazne, slowa = "", "", False, []
    for slowo in linia.split():
        if slowo.startswith("@") and len(slowo) > 1:
            kontekst = slowo[1:].lower().strip(".,")
        elif slowo in ("!", "!!"):
            wazne = True
        elif (d := termin_z_slowa(slowo, dzis)) is not None and not termin:
            termin = d.isoformat()
        else:
            slowa.append(slowo)
    tekst = " ".join(slowa).strip()
    if not tekst:
        return None
    return Zadanie(tekst[:500], lista if lista in PRZENOSZENIE else "skrzynka", kontekst[:40], termin, wazne)


def wczytaj(tekst: str) -> list[Zadanie]:
    try:
        surowe = json.loads(tekst or "[]")
    except ValueError:
        return []
    wynik = []
    znane = set(Zadanie.__dataclass_fields__)
    for z in surowe if isinstance(surowe, list) else []:
        if isinstance(z, dict) and isinstance(z.get("tekst"), str):
            try:
                zad = Zadanie(**{k: v for k, v in z.items() if k in znane})
            except TypeError:
                continue
            if zad.lista not in NAZWY_LIST or zad.lista == "dzis":
                zad.lista = "skrzynka"
            wynik.append(zad)
    return wynik


def zapisz(zadania: list[Zadanie]) -> str:
    return json.dumps([asdict(z) for z in zadania], ensure_ascii=False)


def w_widoku(zadania: list[Zadanie], widok: str, kontekst: str = "", dzis: date | None = None) -> list[Zadanie]:
    """Zadania listy (albo widoku „Dziś”: z terminem do dziś i ważne), posortowane:
    po terminie i ważne najpierw, potem po terminie, potem od najnowszych."""
    dzis_txt = (dzis or date.today()).isoformat()
    if widok == "dzis":
        wynik = [z for z in zadania if not z.zrobione and ((z.termin and z.termin <= dzis_txt) or z.wazne)]
    else:
        wynik = [z for z in zadania if z.lista == widok]
    if kontekst:
        wynik = [z for z in wynik if z.kontekst == kontekst]
    if widok == "zrobione":
        return sorted(wynik, key=lambda z: z.zrobiono, reverse=True)
    return sorted(wynik, key=lambda z: (not z.wazne, z.termin or "9999", z.utworzono))


def liczniki(zadania: list[Zadanie], dzis: date | None = None) -> dict[str, int]:
    return {k: len(w_widoku(zadania, k, dzis=dzis)) for k, _ in LISTY}


def konteksty(zadania: list[Zadanie]) -> list[str]:
    uzyte = {z.kontekst for z in zadania if z.kontekst and not z.zrobione}
    return sorted(uzyte | set(KONTEKSTY), key=lambda k: (k not in uzyte, k))


def odhacz(zadanie: Zadanie, zrobione: bool = True) -> None:
    if zrobione:
        zadanie.zrobiono = datetime.now().isoformat(timespec="minutes")
        zadanie.lista = "zrobione"
    else:
        zadanie.zrobiono = ""
        zadanie.lista = "nastepne"


def wyczysc_zrobione(zadania: list[Zadanie], starsze_niz_dni: int = 30, teraz: datetime | None = None) -> list[Zadanie]:
    granica = ((teraz or datetime.now()) - timedelta(days=starsze_niz_dni)).isoformat(timespec="minutes")
    return [z for z in zadania if not (z.zrobione and z.zrobiono and z.zrobiono < granica)]


def opis_terminu(termin: str, dzis: date | None = None) -> str:
    if not termin:
        return ""
    dzis = dzis or date.today()
    d = date.fromisoformat(termin)
    roznica = (d - dzis).days
    if roznica == 0:
        return "dziś"
    if roznica == 1:
        return "jutro"
    if roznica == -1:
        return "wczoraj"
    if 1 < roznica < 7:
        return ["pon", "wt", "śr", "czw", "pt", "sob", "nd"][d.weekday()]
    return f"{d:%d.%m}" if d.year == dzis.year else f"{d:%d.%m.%Y}"
