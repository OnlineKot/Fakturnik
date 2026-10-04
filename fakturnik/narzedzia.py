"""Logika małych narzędzi z karty „Narzędzia” (bez Qt, żeby dało się ją testować)."""

import calendar
import json
import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .walidacja import cyfry, pesel_poprawny

# nominały w groszach (całkowite, bez błędów zaokrągleń)
NOMINALY = [50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1]


def opis_nominalu(grosze: int) -> str:
    return f"{grosze // 100} zł" if grosze >= 100 else f"{grosze} gr"


def suma_kasy(ilosci: dict[int, int]) -> float:
    """{nominał w groszach: liczba sztuk} → kwota w złotych."""
    return sum(n * max(0, int(i)) for n, i in ilosci.items() if n in NOMINALY) / 100


# ---------- PESEL ----------
@dataclass
class DanePesel:
    urodzenie: date
    plec: str  # "kobieta" / "mężczyzna"

    def wiek(self, dzis: date | None = None) -> int:
        dzis = dzis or date.today()
        return dzis.year - self.urodzenie.year - ((dzis.month, dzis.day) < (self.urodzenie.month, self.urodzenie.day))


def dane_z_peselu(tekst: str) -> DanePesel | None:
    """Data urodzenia i płeć z poprawnego numeru PESEL (stulecie zakodowane w miesiącu)."""
    c = cyfry(tekst)
    if not pesel_poprawny(c):
        return None
    rok, miesiac, dzien = int(c[0:2]), int(c[2:4]), int(c[4:6])
    stulecie = {0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800}[(miesiac // 20) * 20]
    try:
        urodzenie = date(stulecie + rok, miesiac % 20, dzien)
    except ValueError:
        return None
    return DanePesel(urodzenie, "kobieta" if int(c[9]) % 2 == 0 else "mężczyzna")


# ---------- daty ----------
def dodaj_miesiace(dzien: date, miesiace: int) -> date:
    m = dzien.month - 1 + miesiace
    rok, miesiac = dzien.year + m // 12, m % 12 + 1
    return date(rok, miesiac, min(dzien.day, calendar.monthrange(rok, miesiac)[1]))


def przesun_date(dzien: date, ile: int, jednostka: str) -> date:
    """jednostka: "dni", "tygodnie", "miesiące", "lata"."""
    if jednostka == "dni":
        return dzien + timedelta(days=ile)
    if jednostka == "tygodnie":
        return dzien + timedelta(weeks=ile)
    if jednostka == "miesiące":
        return dodaj_miesiace(dzien, ile)
    if jednostka == "lata":
        return dodaj_miesiace(dzien, 12 * ile)
    raise ValueError(jednostka)


def wielkanoc(rok: int) -> date:
    """Niedziela Wielkanocna (algorytm Meeusa/Jonesa/Butchera, kalendarz gregoriański)."""
    a, b, c = rok % 19, rok // 100, rok % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    miesiac = (h + l_ - 7 * m + 114) // 31
    dzien = (h + l_ - 7 * m + 114) % 31 + 1
    return date(rok, miesiac, dzien)


def swieta(rok: int) -> dict[date, str]:
    """Dni ustawowo wolne od pracy w Polsce (z Wigilią od 2025 r.)."""
    w = wielkanoc(rok)
    dni = {
        date(rok, 1, 1): "Nowy Rok", date(rok, 1, 6): "Trzech Króli", w: "Wielkanoc",
        w + timedelta(days=1): "Poniedziałek Wielkanocny", date(rok, 5, 1): "Święto Pracy",
        date(rok, 5, 3): "Święto Konstytucji 3 Maja", w + timedelta(days=49): "Zielone Świątki",
        w + timedelta(days=60): "Boże Ciało", date(rok, 8, 15): "Wniebowzięcie NMP",
        date(rok, 11, 1): "Wszystkich Świętych", date(rok, 11, 11): "Święto Niepodległości",
        date(rok, 12, 25): "Boże Narodzenie", date(rok, 12, 26): "Drugi dzień Bożego Narodzenia",
    }
    if rok >= 2025:
        dni[date(rok, 12, 24)] = "Wigilia"
    return dni


def swieto(dzien: date) -> str:
    return swieta(dzien.year).get(dzien, "")


def dni_robocze(od: date, do: date) -> int:
    """Dni robocze w przedziale (od, do]: od poniedziałku do piątku, bez świąt ustawowych."""
    if do < od:
        return -dni_robocze(do, od)
    wolne = {d for rok in range(od.year, do.year + 1) for d in swieta(rok)}
    return sum(1 for i in range(1, (do - od).days + 1)
               if (dz := od + timedelta(days=i)).weekday() < 5 and dz not in wolne)


# ---------- rabat i raty ----------
def rabat_i_raty(kwota: float, rabat_proc: float, raty: int) -> tuple[float, float, list[float]]:
    """(rabat w zł, kwota po rabacie, lista rat). Raty w pełnych groszach, różnica w ostatniej racie."""
    if kwota < 0 or not 0 <= rabat_proc <= 100 or raty < 1:
        raise ValueError("Niepoprawne dane.")
    po = round(kwota * (100 - rabat_proc) / 100, 2)
    grosze = round(po * 100)
    rata = grosze // raty
    lista = [rata / 100] * (raty - 1) + [(grosze - rata * (raty - 1)) / 100]
    return round(kwota - po, 2), po, lista


# ---------- hasła ----------
_LITERY = "abcdefghijkmnopqrstuvwxyz"  # bez l (myli się z 1)
_CYFRY = "23456789"                    # bez 0 i 1
_ZNAKI = "!@#$%&*?-+="


def generuj_haslo(dlugosc: int = 14, znaki: bool = True) -> str:
    """Losowe hasło (moduł secrets) z małymi i wielkimi literami, cyframi i opcjonalnie znakami,
    bez łatwych do pomylenia znaków (0/O, 1/l/I)."""
    if dlugosc < 8:
        raise ValueError("Hasło powinno mieć co najmniej 8 znaków.")
    grupy = [_LITERY, _LITERY.upper().replace("I", "").replace("O", ""), _CYFRY] + ([_ZNAKI] if znaki else [])
    wszystkie = "".join(grupy)
    haslo = [secrets.choice(g) for g in grupy] + [secrets.choice(wszystkie) for _ in range(dlugosc - len(grupy))]
    secrets.SystemRandom().shuffle(haslo)
    return "".join(haslo)


# ---------- przypomnienia ----------
def wczytaj_przypomnienia(tekst: str) -> list[dict]:
    """Ustawienie „przypomnienia” (JSON) → [{"kiedy": "RRRR-MM-DDTGG:MM", "tekst": ...}], posortowane."""
    try:
        lista = json.loads(tekst or "[]")
    except ValueError:
        return []
    wynik = []
    for p in lista if isinstance(lista, list) else []:
        try:
            datetime.fromisoformat(p["kiedy"])
            wynik.append({"kiedy": p["kiedy"], "tekst": str(p.get("tekst", ""))[:300]})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(wynik, key=lambda p: p["kiedy"])


def zapisz_przypomnienia(lista: list[dict]) -> str:
    return json.dumps(sorted(lista, key=lambda p: p["kiedy"]), ensure_ascii=False)


def kiedy_przypomniec(tekst_godziny: str, teraz: datetime) -> datetime:
    """„14:30” → dziś o 14:30 (jutro, jeśli ta godzina już minęła); „+15” → za 15 minut."""
    t = tekst_godziny.strip().replace(".", ":")
    if t.startswith("+"):
        minuty = int(t[1:])
        if not 0 < minuty <= 24 * 60:
            raise ValueError("Podaj od 1 do 1440 minut.")
        return (teraz + timedelta(minutes=minuty)).replace(second=0, microsecond=0)
    godzina = time.fromisoformat(t if len(t) > 2 else f"{int(t):02d}:00")
    kiedy = datetime.combine(teraz.date(), godzina)
    return kiedy if kiedy > teraz else kiedy + timedelta(days=1)


def do_przypomnienia(lista: list[dict], teraz: datetime) -> tuple[list[dict], list[dict]]:
    """(przypomnienia, których czas nadszedł; pozostałe)."""
    teraz_txt = teraz.isoformat(timespec="minutes")
    return [p for p in lista if p["kiedy"] <= teraz_txt], [p for p in lista if p["kiedy"] > teraz_txt]


# ---------- szybkie wyszukiwanie (Ctrl+K) ----------
_BEZ_OGONKOW = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def uproszczony(tekst: str) -> str:
    return tekst.translate(_BEZ_OGONKOW).lower().strip()


def ocena(tekst: str, zapytanie: str) -> int:
    """Jak dobrze zapytanie pasuje do tekstu (0 = wcale). Bez ogonków i wielkości liter;
    każde słowo zapytania musi wystąpić; początek tekstu i początki słów liczą się wyżej."""
    t, z = uproszczony(tekst), uproszczony(zapytanie)
    if not z:
        return 1
    slowa_t = t.split()
    wynik = 0
    for slowo in z.split():
        if t.startswith(slowo):
            wynik += 30
        elif any(s_.startswith(slowo) for s_ in slowa_t):
            wynik += 20
        elif slowo in t:
            wynik += 5
        else:
            return 0
    return wynik + max(0, 10 - len(t) // 10)
