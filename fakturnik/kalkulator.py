"""Bezpieczny kalkulator: tylko liczby, + - * / %, nawiasy i potęga (bez wykonywania kodu)."""

import ast
import math
import operator

DZIALANIA = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
             ast.Mod: operator.mod, ast.Pow: operator.pow}


def oblicz(tekst: str) -> float:
    """„1 200,50 + 10%” nie jest obsługiwane jako procent; „200*1,23”, „(900+150)/2” tak."""
    wyrazenie = tekst.replace(" ", "").replace("\xa0", "").replace(",", ".").replace("×", "*").replace("÷", "/")
    if not wyrazenie or len(wyrazenie) > 200:
        raise ValueError("Wpisz działanie, np. 900+150")
    drzewo = ast.parse(wyrazenie, mode="eval")

    def licz(wezel):
        if isinstance(wezel, ast.Expression):
            return licz(wezel.body)
        if isinstance(wezel, ast.Constant) and isinstance(wezel.value, (int, float)) and not isinstance(wezel.value, bool):
            return float(wezel.value)
        if isinstance(wezel, ast.UnaryOp) and isinstance(wezel.op, (ast.UAdd, ast.USub)):
            v = licz(wezel.operand)
            return v if isinstance(wezel.op, ast.UAdd) else -v
        if isinstance(wezel, ast.BinOp) and type(wezel.op) in DZIALANIA:
            a, b = licz(wezel.left), licz(wezel.right)
            if isinstance(wezel.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise ValueError("Za duża potęga")
            return DZIALANIA[type(wezel.op)](a, b)
        raise ValueError("Dozwolone są tylko liczby i działania + - * / % ( )")

    try:
        wynik = licz(drzewo)
    except ZeroDivisionError:
        raise ValueError("Dzielenie przez zero") from None
    if not math.isfinite(wynik):
        raise ValueError("Wynik poza zakresem")
    return wynik


def formatuj(wynik: float) -> str:
    if abs(wynik - round(wynik)) < 1e-9:
        return f"{round(wynik):,}".replace(",", " ")
    return f"{wynik:,.2f}".replace(",", " ").replace(".", ",")
