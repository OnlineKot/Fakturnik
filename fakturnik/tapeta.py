"""Tapety pulpitu w stylu gabinetu, rysowane w rozdzielczości ekranu (ostre także na 4K).

Spokojne, płaskie kolory marki (bez poświat i efektów), ostre logo gabinetu (ząb z narzędziem)
i nazwa gabinetu. Ikony pulpitu są zwykle po lewej stronie, więc ważne elementy stoją z dala od nich.
Mały podpis TeodorTeo.com jest w prawym dolnym rogu, nad paskiem zadań.
"""

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ZASOBY = Path(__file__).parent / "zasoby"

# tlo: kolor tła; logo: (kolor, krycie); uklad: gdzie stoi logo
WARIANTY = {
    "morski": {"nazwa": "Morski (polecana)", "tlo": "#103038", "logo": ("#e8f3f5", 0.10), "uklad": "znak",
               "tekst": "#e8f3f5", "opis": "#86a6ac"},
    "srodek": {"nazwa": "Logo na środku", "tlo": "#0d1b1f", "logo": ("#e8f3f5", 0.92), "uklad": "srodek",
               "tekst": "#e8f3f5", "opis": "#7f9499"},
    "grafit": {"nazwa": "Grafit", "tlo": "#17191b", "logo": ("#5fb3c2", 0.85), "uklad": "rog",
               "tekst": "#e6e8ea", "opis": "#8a9196"},
    "jasny": {"nazwa": "Jasny gabinet", "tlo": "#f2f5f6", "logo": ("#1e6b7b", 0.10), "uklad": "znak",
              "tekst": "#0f2c33", "opis": "#5b6670"},
    "biel": {"nazwa": "Biel z logo", "tlo": "#ffffff", "logo": ("#1e6b7b", 0.95), "uklad": "srodek",
             "tekst": "#0f2c33", "opis": "#5b6670"},
}
STARE_NAZWY = {"turkus": "morski", "granat": "grafit"}  # warianty z poprzednich wersji


def _logo(kolor: str) -> QSvgRenderer:
    svg = (ZASOBY / "logo.svg").read_text(encoding="utf-8").replace("#e8f3f5", kolor)
    return QSvgRenderer(QByteArray(svg.encode("utf-8")))


def wygeneruj(wariant: str, szerokosc: int, wysokosc: int, nazwa_gabinetu: str = "") -> QImage:
    w = WARIANTY.get(STARE_NAZWY.get(wariant, wariant), WARIANTY["morski"])
    obraz = QImage(szerokosc, wysokosc, QImage.Format.Format_RGB32)
    obraz.fill(QColor(w["tlo"]))
    p = QPainter(obraz)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    skala = min(szerokosc / 1920, wysokosc / 1080)
    logo = _logo(w["logo"][0])
    nazwa = nazwa_gabinetu or "Fakturnik"

    def tekst(t: str, px: float, waga, kolor: str, prostokat: QRectF, wyrownanie):
        f = QFont("Inter")
        f.setPixelSize(max(10, int(px)))
        f.setWeight(waga)
        p.setFont(f)
        p.setPen(QColor(kolor))
        p.drawText(prostokat, wyrownanie, t)

    if w["uklad"] == "znak":
        # duży, ledwo widoczny znak wodny po prawej i nazwa gabinetu po prawej na dole
        wys = wysokosc * 0.72
        szer = wys * 80 / 120
        p.setOpacity(w["logo"][1])
        logo.render(p, QRectF(szerokosc * 0.74 - szer / 2, wysokosc * 0.46 - wys / 2, szer, wys))
        p.setOpacity(1.0)
        tekst(nazwa, 30 * skala, QFont.Weight.DemiBold, w["tekst"],
              QRectF(0, wysokosc - 170 * skala, szerokosc - 70 * skala, 40 * skala),
              Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    elif w["uklad"] == "srodek":
        # logo na środku, pod nim nazwa gabinetu (jak na zasłonie ekranu)
        wys = wysokosc * 0.26
        szer = wys * 80 / 120
        p.setOpacity(w["logo"][1])
        logo.render(p, QRectF((szerokosc - szer) / 2, wysokosc * 0.40 - wys / 2, szer, wys))
        p.setOpacity(1.0)
        tekst(nazwa, 34 * skala, QFont.Weight.DemiBold, w["tekst"],
              QRectF(0, wysokosc * 0.40 + wys / 2 + 30 * skala, szerokosc, 50 * skala), Qt.AlignmentFlag.AlignCenter)
    else:
        # małe logo z nazwą w prawym dolnym rogu, reszta pusta
        wys = 120 * skala
        szer = wys * 80 / 120
        x = szerokosc - 90 * skala - szer
        y = wysokosc - 200 * skala - wys
        p.setOpacity(w["logo"][1])
        logo.render(p, QRectF(x, y, szer, wys))
        p.setOpacity(1.0)
        tekst(nazwa, 26 * skala, QFont.Weight.DemiBold, w["tekst"],
              QRectF(0, y + wys + 18 * skala, szerokosc - 90 * skala, 36 * skala),
              Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    tekst("TeodorTeo.com", 13 * skala, QFont.Weight.Normal, w["opis"],
          QRectF(0, wysokosc - 80 * skala, szerokosc - 24 * skala, 20 * skala),
          Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    p.end()
    return obraz


def zapisz(wariant: str, katalog: Path, szerokosc: int, wysokosc: int, nazwa_gabinetu: str = "") -> Path:
    katalog.mkdir(parents=True, exist_ok=True)
    plik = katalog / f"tapeta-{wariant}.png"
    wygeneruj(wariant, szerokosc, wysokosc, nazwa_gabinetu).save(str(plik), "PNG")
    return plik
