"""Sprawdzanie numerów PESEL, NIP i rachunku bankowego (sumy kontrolne), żeby literówka nie trafiła na dokument."""


def cyfry(tekst: str) -> str:
    return "".join(c for c in tekst if c.isdigit())


def pesel_poprawny(tekst: str) -> bool:
    c = cyfry(tekst)
    if len(c) != 11:
        return False
    wagi = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    suma = sum(int(c[i]) * wagi[i] for i in range(10))
    return (10 - suma % 10) % 10 == int(c[10])


def nip_poprawny(tekst: str) -> bool:
    c = cyfry(tekst)
    if len(c) != 10:
        return False
    wagi = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    kontrolna = sum(int(c[i]) * wagi[i] for i in range(9)) % 11
    return kontrolna != 10 and kontrolna == int(c[9])


def konto_poprawne(tekst: str) -> bool:
    """Polski numer rachunku (NRB, 26 cyfr, z "PL" lub bez) sprawdzony algorytmem IBAN (mod 97)."""
    c = cyfry(tekst)
    if len(c) != 26:
        return False
    # IBAN: 2 cyfry kontrolne + 24 cyfry; "PL" = 25 21; przeniesienie na koniec i reszta z dzielenia przez 97
    return int(c[2:] + "2521" + c[:2]) % 97 == 1


def formatuj_konto(tekst: str) -> str:
    """26 cyfr w grupach: 12 3456 7890 1234 5678 9012 3456."""
    c = cyfry(tekst)
    if len(c) != 26:
        return tekst.strip()
    return c[:2] + " " + " ".join(c[i:i + 4] for i in range(2, 26, 4))


def opis_identyfikatora(tekst: str) -> tuple[str, bool] | None:
    """Podpowiedź pod polem PESEL/NIP: (komunikat, czy poprawny) albo None, gdy nic nie wpisano."""
    c = cyfry(tekst)
    if not c:
        return None
    if len(c) == 11:
        return ("PESEL poprawny", True) if pesel_poprawny(c) else ("Błędny PESEL: zła cyfra kontrolna", False)
    if len(c) == 10:
        return ("NIP poprawny", True) if nip_poprawny(c) else ("Błędny NIP: zła cyfra kontrolna", False)
    return (f"Wpisano {len(c)} cyfr: PESEL ma 11, NIP ma 10", False)
