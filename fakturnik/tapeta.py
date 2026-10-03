"""Tapeta pulpitu w stylu Fakturnika, rysowana w rozdzielczości ekranu (ostra także na 4K).

Polecana: „Turkus nocą” – ciemny morski turkus z miękkim światłem, duży, ledwo widoczny ząb jako znak
wodny i dyskretna nazwa gabinetu w rogu. Spokojna, nie męczy oczu i nie przeszkadza ikonom pulpitu.
"""

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient

ZASOBY = Path(__file__).parent / "zasoby"

WARIANTY = {
    "turkus": {"nazwa": "Turkus nocą (polecana)", "tlo": ("#123842", "#06171b"), "swiatlo": ("#2a8a9b", 150),
               "drugie": ("#5fc4b4", 45), "znak": ("#ffffff", 0.07), "tekst": "#e8f4f5", "opis": "#8fb3b9"},
    "granat": {"nazwa": "Granat", "tlo": ("#14243a", "#060b14"), "swiatlo": ("#2f5d8c", 140),
               "drugie": ("#7fa7d9", 35), "znak": ("#ffffff", 0.06), "tekst": "#e9eef6", "opis": "#93a5bf"},
    "jasny": {"nazwa": "Jasny gabinet", "tlo": ("#fbfcfc", "#dfeaec"), "swiatlo": ("#ffffff", 220),
              "drugie": ("#9fd3cf", 60), "znak": ("#1e6b7b", 0.07), "tekst": "#0f2c33", "opis": "#5b6670"},
}


def _zab(kolor: str, wysokosc: int) -> QImage:
    """Biały ząb z ikony programu, przekolorowany i przeskalowany (znak wodny)."""
    ikona = QImage(str(ZASOBY / "ikona.png")).convertToFormat(QImage.Format.Format_ARGB32)
    maska = QImage(ikona.size(), QImage.Format.Format_ARGB32)
    maska.fill(Qt.GlobalColor.transparent)
    c = QColor(kolor)
    for y in range(ikona.height()):
        for x in range(ikona.width()):
            p = QColor(ikona.pixel(x, y))
            jasnosc = min(p.red(), p.green(), p.blue())
            if jasnosc > 120:  # biały ząb na morskim tle ikony
                alfa = int(255 * min(1.0, (jasnosc - 120) / 120) * ikona.pixelColor(x, y).alphaF())
                maska.setPixelColor(x, y, QColor(c.red(), c.green(), c.blue(), alfa))
    przyciete = maska.copy(maska.rect().adjusted(130, 80, -130, -80))
    return przyciete.scaledToHeight(wysokosc, Qt.TransformationMode.SmoothTransformation)


def wygeneruj(wariant: str, szerokosc: int, wysokosc: int, nazwa_gabinetu: str = "") -> QImage:
    w = WARIANTY.get(wariant, WARIANTY["turkus"])
    obraz = QImage(szerokosc, wysokosc, QImage.Format.Format_RGB32)
    p = QPainter(obraz)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    tlo = QLinearGradient(0, 0, szerokosc, wysokosc)
    tlo.setColorAt(0, QColor(w["tlo"][0]))
    tlo.setColorAt(1, QColor(w["tlo"][1]))
    p.fillRect(obraz.rect(), tlo)

    for (kolor, alfa), srodek, promien in ((w["swiatlo"], (0.30, 0.32), 0.75), (w["drugie"], (0.85, 0.85), 0.55)):
        c = QColor(kolor)
        poswiata = QRadialGradient(QPointF(szerokosc * srodek[0], wysokosc * srodek[1]), max(szerokosc, wysokosc) * promien)
        c.setAlpha(alfa)
        poswiata.setColorAt(0, c)
        c.setAlpha(0)
        poswiata.setColorAt(1, c)
        p.fillRect(obraz.rect(), poswiata)

    znak = _zab(w["znak"][0], int(wysokosc * 0.78))
    p.setOpacity(w["znak"][1])
    p.drawImage(QPointF(szerokosc * 0.80 - znak.width() / 2, wysokosc * 0.47 - znak.height() / 2), znak)
    p.setOpacity(1.0)

    # podpis w lewym dolnym rogu (ikony pulpitu są zwykle po lewej u góry)
    skala = wysokosc / 1080
    margines = int(56 * skala)
    rozmiar_ikony = int(52 * skala)
    ikona = QImage(str(ZASOBY / "ikona.png")).scaled(rozmiar_ikony, rozmiar_ikony,
                                                     Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)
    dol = wysokosc - margines - int(90 * skala)  # nad paskiem zadań
    p.drawImage(QPointF(margines, dol), ikona)
    tytul = QFont("Inter")
    tytul.setPixelSize(max(12, int(26 * skala)))
    tytul.setWeight(QFont.Weight.DemiBold)
    p.setFont(tytul)
    p.setPen(QColor(w["tekst"]))
    x = margines + rozmiar_ikony + int(18 * skala)
    p.drawText(QRectF(x, dol - 4 * skala, szerokosc * 0.6, 34 * skala), Qt.AlignmentFlag.AlignVCenter,
               nazwa_gabinetu or "Fakturnik")
    opis = QFont("Inter")
    opis.setPixelSize(max(10, int(15 * skala)))
    p.setFont(opis)
    p.setPen(QColor(w["opis"]))
    p.drawText(QRectF(x, dol + 28 * skala, szerokosc * 0.6, 24 * skala), Qt.AlignmentFlag.AlignVCenter,
               "Fakturnik  ·  by TeodorTeo.com")
    p.end()
    return obraz


def zapisz(wariant: str, katalog: Path, szerokosc: int, wysokosc: int, nazwa_gabinetu: str = "") -> Path:
    katalog.mkdir(parents=True, exist_ok=True)
    plik = katalog / f"tapeta-{wariant}.png"
    wygeneruj(wariant, szerokosc, wysokosc, nazwa_gabinetu).save(str(plik), "PNG")
    return plik
