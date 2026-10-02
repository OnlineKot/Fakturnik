"""Kwota słownie po polsku, np. 1250.5 -> 'tysiąc dwieście pięćdziesiąt złotych 50/100'."""

JEDNOSTKI = ["", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem",
             "dziewięć", "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście",
             "piętnaście", "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
DZIESIATKI = ["", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt",
              "sześćdziesiąt", "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"]
SETKI = ["", "sto", "dwieście", "trzysta", "czterysta", "pięćset", "sześćset", "siedemset",
         "osiemset", "dziewięćset"]
GRUPY = [("", "", ""), ("tysiąc", "tysiące", "tysięcy"), ("milion", "miliony", "milionów")]


def odmiana(n: int, formy: tuple[str, str, str]) -> str:
    """Wybiera formę: 1 złoty, 2 złote, 5 złotych."""
    if n == 1:
        return formy[0]
    j, d = n % 10, n % 100
    if 2 <= j <= 4 and not 12 <= d <= 14:
        return formy[1]
    return formy[2]


def liczba_slownie(n: int) -> str:
    if n == 0:
        return "zero"
    czesci = []
    grupa = 0
    while n > 0:
        k = n % 1000
        if k:
            r = k % 100
            slowa = [SETKI[k // 100]]
            if r < 20:
                slowa.append(JEDNOSTKI[r])
            else:
                slowa += [DZIESIATKI[r // 10], JEDNOSTKI[r % 10]]
            tekst = " ".join(s for s in slowa if s)
            if grupa > 0:
                nazwa = odmiana(k, GRUPY[grupa])
                tekst = nazwa if k == 1 else f"{tekst} {nazwa}"
            czesci.insert(0, tekst)
        n //= 1000
        grupa += 1
    return " ".join(czesci)


def kwota_slownie(kwota: float) -> str:
    grosze_razem = round(kwota * 100)
    zl, gr = divmod(grosze_razem, 100)
    return f"{liczba_slownie(zl)} {odmiana(zl, ('złoty', 'złote', 'złotych'))} {gr:02d}/100"
