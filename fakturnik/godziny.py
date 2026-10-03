"""Godziny pracy gabinetu: kiedy asystentki mogą pracować w programie, przypomnienie przed końcem
i wylogowanie po godzinach. Właścicielka może zalogować się zawsze i udzielić zgody na pracę po godzinach."""

import json
from datetime import date, datetime, time, timedelta

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
DNI_KROTKO = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]
DOMYSLNE = {"1": "12:00-18:00", "2": "10:00-17:00", "3": "12:00-18:00", "4": "08:00-14:00"}


def wczytaj(tekst: str) -> dict[int, tuple[time, time]]:
    """Ustawienie „godziny_pracy” (JSON {dzień tygodnia 0=pon: "GG:MM-GG:MM"}) → {dzień: (od, do)}."""
    try:
        surowe = json.loads(tekst) if tekst else DOMYSLNE
    except ValueError:
        surowe = DOMYSLNE
    wynik = {}
    for dzien, przedzial in surowe.items():
        try:
            od, do = (time.fromisoformat(x.strip()) for x in przedzial.split("-"))
            if od < do:
                wynik[int(dzien)] = (od, do)
        except (ValueError, AttributeError):
            continue
    return wynik


def zapisz(godziny: dict[int, tuple[time, time]]) -> str:
    return json.dumps({str(d): f"{od:%H:%M}-{do:%H:%M}" for d, (od, do) in sorted(godziny.items())})


def w_godzinach(godziny: dict, teraz: datetime) -> bool:
    przedzial = godziny.get(teraz.weekday())
    return bool(przedzial) and przedzial[0] <= teraz.time() < przedzial[1]


def koniec_dzis(godziny: dict, teraz: datetime) -> datetime | None:
    przedzial = godziny.get(teraz.weekday())
    return datetime.combine(teraz.date(), przedzial[1]) if przedzial else None


def nastepne(godziny: dict, teraz: datetime) -> tuple[datetime, datetime] | None:
    """Najbliższe godziny pracy (trwające albo przyszłe) w ciągu tygodnia."""
    for przesuniecie in range(8):
        dzien = teraz.date() + timedelta(days=przesuniecie)
        przedzial = godziny.get(dzien.weekday())
        if przedzial:
            od, do = datetime.combine(dzien, przedzial[0]), datetime.combine(dzien, przedzial[1])
            if do > teraz:
                return od, do
    return None


def opis_tygodnia(godziny: dict) -> str:
    return ", ".join(f"{DNI_KROTKO[d]} {od:%H:%M}–{do:%H:%M}" for d, (od, do) in sorted(godziny.items())) or "brak"


def opis_stanu(godziny: dict, teraz: datetime) -> str:
    if w_godzinach(godziny, teraz):
        return f"Godziny pracy do {koniec_dzis(godziny, teraz):%H:%M}"
    nast = nastepne(godziny, teraz)
    if not nast:
        return "Po godzinach pracy"
    od, do = nast
    kiedy = "dziś" if od.date() == teraz.date() else ("jutro" if od.date() == teraz.date() + timedelta(days=1)
                                                       else DNI[od.weekday()])
    return f"Po godzinach · następne: {kiedy} {od:%H:%M}–{do:%H:%M}"


def dzis(teraz: datetime | None = None) -> date:
    return (teraz or datetime.now()).date()


# zgoda właścicielki na pracę asystentek po godzinach (do końca bieżącego dnia)
zgoda_do: datetime | None = None


def zgoda_aktywna(teraz: datetime | None = None) -> bool:
    teraz = teraz or datetime.now()
    return zgoda_do is not None and teraz < zgoda_do


def udziel_zgody(teraz: datetime | None = None) -> datetime:
    global zgoda_do
    teraz = teraz or datetime.now()
    zgoda_do = datetime.combine(teraz.date(), time(23, 59, 59))
    return zgoda_do


def odmowa(ustawienia: dict, rola: str, teraz: datetime | None = None) -> str | None:
    """Powód odmowy logowania (asystentka poza godzinami pracy bez zgody) albo None."""
    if rola == "wlascicielka":
        return None
    teraz = teraz or datetime.now()
    godz = wczytaj(ustawienia.get("godziny_pracy", ""))
    if w_godzinach(godz, teraz) or zgoda_aktywna(teraz):
        return None
    return (f"Poza godzinami pracy ({opis_tygodnia(godz)}). Pracę po godzinach może zatwierdzić "
            "właścicielka przyciskiem „Zgoda właścicielki”.")
