"""Własne elementy interfejsu: powiadomienia, etykiety statusu, wykres przychodu, podgląd kartki."""

import math

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRectF, QSizeF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QTextDocument
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout,
    QToolTip, QWidget,
)

from .ikony import pixmapa
from .motyw import AKCENT, AKCENT_SLABY, LINIA, TEKST, TEKST_3


def _czcionka(rozmiar: int, waga: QFont.Weight = QFont.Weight.Normal, cyfry: bool = False) -> QFont:
    f = QFont("Inter")
    f.setPixelSize(rozmiar)
    f.setWeight(waga)
    if cyfry:
        try:
            f.setFeature(QFont.Tag("tnum"), 1)
        except (AttributeError, TypeError):
            pass
    return f


# ---------------------------------------------------------------- powiadomienie

class Powiadomienie(QFrame):
    """Krótki komunikat w prawym górnym rogu okna, znika sam."""

    def __init__(self, rodzic: QWidget):
        super().__init__(rodzic, objectName="toast")
        u = QHBoxLayout(self)
        u.setContentsMargins(14, 11, 18, 11)
        u.setSpacing(10)
        self.znak = QLabel()
        u.addWidget(self.znak)
        self.tekst = QLabel(textFormat=Qt.TextFormat.PlainText)
        u.addWidget(self.tekst)
        self.efekt = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.efekt)
        self.animacja = QPropertyAnimation(self.efekt, b"opacity", self)
        self.animacja.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.zegar = QTimer(self, singleShot=True, interval=3200)
        self.zegar.timeout.connect(self._zgas)
        self.hide()

    def pokaz(self, tekst: str, blad: bool = False):
        self.znak.setPixmap(pixmapa("uwaga" if blad else "ok", "#ff9aa5" if blad else "#7fd6ae", 16))
        self.tekst.setText(tekst)
        self.adjustSize()
        rodzic = self.parentWidget()
        self.move(rodzic.width() - self.width() - 28, rodzic.height() - self.height() - 26)
        self.raise_()
        self.show()
        self.animacja.stop()
        self.animacja.setDuration(160)
        self.animacja.setStartValue(self.efekt.opacity() if self.isVisible() else 0.0)
        self.animacja.setEndValue(1.0)
        self.animacja.start()
        self.zegar.start()

    def _zgas(self):
        self.animacja.stop()
        self.animacja.setDuration(400)
        self.animacja.setStartValue(1.0)
        self.animacja.setEndValue(0.0)
        self.animacja.finished.connect(self._ukryj)
        self.animacja.start()

    def _ukryj(self):
        self.animacja.finished.disconnect(self._ukryj)
        if self.efekt.opacity() < 0.05:
            self.hide()


# ---------------------------------------------------------------- etykieta statusu w tabeli

STYLE_PIGULEK = {
    "Rachunek": ("#eef1f3", "#3b4650"),
    "Faktura": ("#e3eff1", "#16525f"),
    "Korekta": ("#fdf3e1", "#8a5a00"),
    "Anulowany": ("#fbeaec", "#a4303d"),
}


class PigulkaDelegate(QStyledItemDelegate):
    """Rysuje tekst komórki jako zaokrągloną etykietę (Rachunek, Faktura, Anulowany)."""

    def paint(self, malarz: QPainter, opcja, indeks):
        tekst = indeks.data(Qt.ItemDataRole.DisplayRole) or ""
        tlo, kolor = STYLE_PIGULEK.get(tekst, ("#eef1f3", "#3b4650"))
        opt = QStyleOptionViewItem(opcja)
        self.initStyleOption(opt, indeks)
        opt.text = ""
        styl = opcja.widget.style() if opcja.widget else None
        if styl:
            styl.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, malarz, opcja.widget)
        if not tekst:
            return
        malarz.save()
        malarz.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = _czcionka(11, QFont.Weight.DemiBold)
        malarz.setFont(f)
        szer = QFontMetrics(f).horizontalAdvance(tekst) + 16
        wys = 20
        r = QRectF(opcja.rect.x() + 10, opcja.rect.center().y() - wys / 2 + 0.5, szer, wys)
        malarz.setPen(Qt.PenStyle.NoPen)
        malarz.setBrush(QColor(tlo))
        malarz.drawRoundedRect(r, wys / 2, wys / 2)
        malarz.setPen(QColor(kolor))
        malarz.drawText(r, Qt.AlignmentFlag.AlignCenter, tekst)
        malarz.restore()


# ---------------------------------------------------------------- wykres przychodu

def ladny_krok(wartosc: float) -> float:
    """Zaokrągla krok osi do 1, 2, 2,5 lub 5 × 10^k."""
    if wartosc <= 0:
        return 1
    potega = 10 ** math.floor(math.log10(wartosc))
    for m in (1, 2, 2.5, 5, 10):
        if wartosc <= m * potega:
            return m * potega
    return 10 * potega


def kwota_skrot(v: float) -> str:
    if v >= 1000:
        tys = v / 1000
        return (f"{tys:.1f}".rstrip("0").rstrip(".").replace(".", ",")) + " tys."
    return f"{v:.0f}"


class WykresMiesiecy(QWidget):
    """Słupki przychodu z ostatnich miesięcy; bieżący miesiąc w kolorze marki, reszta jaśniejsza."""

    def __init__(self, formatuj_kwote):
        super().__init__()
        self.formatuj = formatuj_kwote
        self.dane: list[tuple[str, str, float, int]] = []  # (skrót, pełna nazwa, kwota, liczba dokumentów)
        self.nad: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(230)

    def ustaw(self, dane):
        self.dane = dane
        self.update()

    def _geometria(self):
        lewo, prawo, gora, dol = 58, 8, 22, 30
        obszar = QRectF(lewo, gora, max(1, self.width() - lewo - prawo), max(1, self.height() - gora - dol))
        slot = obszar.width() / max(1, len(self.dane))
        return obszar, slot

    def paintEvent(self, _):
        if not self.dane:
            return
        m = QPainter(self)
        m.setRenderHint(QPainter.RenderHint.Antialiasing)
        obszar, slot = self._geometria()
        maks = max(d[2] for d in self.dane)
        krok = ladny_krok(maks / 4 if maks else 250)
        sufit = max(krok, math.ceil(maks / krok) * krok)
        osie = _czcionka(11, cyfry=True)
        m.setFont(osie)

        # siatka i oś Y
        n = int(round(sufit / krok))
        for k in range(n + 1):
            y = obszar.bottom() - obszar.height() * k / n
            m.setPen(QColor("#dfe3e6" if k == 0 else "#eff1f3"))
            m.drawLine(int(obszar.left()), int(y), int(obszar.right()), int(y))
            m.setPen(QColor(TEKST_3))
            m.drawText(QRectF(0, y - 8, obszar.left() - 10, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, kwota_skrot(k * krok))

        ostatni = len(self.dane) - 1
        for i, (skrot, _, kwota, _) in enumerate(self.dane):
            x0 = obszar.left() + slot * i
            if i == self.nad:
                m.setPen(Qt.PenStyle.NoPen)
                m.setBrush(QColor("#f2f5f6"))
                m.drawRoundedRect(QRectF(x0 + 2, obszar.top() - 6, slot - 4, obszar.height() + 6), 6, 6)
            szer = min(24.0, slot * 0.56)
            wys = obszar.height() * (kwota / sufit) if sufit else 0
            if wys >= 1:
                x = x0 + (slot - szer) / 2
                y = obszar.bottom() - wys
                sciezka = QPainterPath()
                sciezka.addRoundedRect(QRectF(x, y, szer, wys), min(4, wys / 2), min(4, wys / 2))
                dol = QPainterPath()
                dol.addRect(QRectF(x, y + wys / 2, szer, wys / 2))
                m.setPen(Qt.PenStyle.NoPen)
                m.setBrush(QColor(AKCENT if i == ostatni else AKCENT_SLABY))
                m.drawPath(sciezka.united(dol))
                if i == ostatni:
                    m.setFont(_czcionka(11, QFont.Weight.DemiBold, cyfry=True))
                    m.setPen(QColor(TEKST))
                    etykieta = self.formatuj(kwota) + " zł"
                    szer_tekstu = m.fontMetrics().horizontalAdvance(etykieta) + 4
                    lewa = min(max(0.0, x + szer / 2 - szer_tekstu / 2), self.width() - szer_tekstu)
                    m.drawText(QRectF(lewa, y - 20, szer_tekstu, 16), Qt.AlignmentFlag.AlignCenter, etykieta)
            m.setFont(_czcionka(11, QFont.Weight.DemiBold if i == ostatni else QFont.Weight.Normal))
            m.setPen(QColor(TEKST if i == ostatni else TEKST_3))
            m.drawText(QRectF(x0, obszar.bottom() + 8, slot, 16), Qt.AlignmentFlag.AlignCenter, skrot)
        m.end()

    def mouseMoveEvent(self, e):
        obszar, slot = self._geometria()
        i = int((e.position().x() - obszar.left()) // slot) if e.position().x() >= obszar.left() else -1
        i = i if 0 <= i < len(self.dane) else None
        if i != self.nad:
            self.nad = i
            self.update()
        if i is None:
            QToolTip.hideText()
            return
        _, pelna, kwota, ile = self.dane[i]
        QToolTip.showText(self.mapToGlobal(QPoint(int(obszar.left() + slot * (i + 0.5)), int(obszar.top()))),
                          f"{pelna}\n{self.formatuj(kwota)} zł  ·  dokumentów: {ile}", self)

    def leaveEvent(self, _):
        self.nad = None
        QToolTip.hideText()
        self.update()


# ---------------------------------------------------------------- podgląd kartki A4

class PodgladKartki(QWidget):
    """Pomniejszona kartka A4 z dokumentem dokładnie takim, jak pójdzie do druku."""

    A4 = QSizeF(794, 1123)  # piksele przy 96 dpi
    MARGINES = 57            # 15 mm

    def __init__(self):
        super().__init__()
        self.dokument = QTextDocument()
        self.dokument.setDocumentMargin(0)
        self.dokument.setPageSize(QSizeF(self.A4.width() - 2 * self.MARGINES, self.A4.height() - 2 * self.MARGINES))
        self.setMinimumSize(260, 360)

    def ustaw_html(self, html: str):
        self.dokument.setHtml(html)
        self.update()

    def paintEvent(self, _):
        m = QPainter(self)
        m.setRenderHint(QPainter.RenderHint.Antialiasing)
        m.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        skala = min((self.width() - 28) / self.A4.width(), (self.height() - 28) / self.A4.height())
        szer, wys = self.A4.width() * skala, self.A4.height() * skala
        kartka = QRectF((self.width() - szer) / 2, 10, szer, wys)
        # miękki cień pod kartką
        for i, alfa in enumerate((10, 8, 6, 4)):
            m.setPen(Qt.PenStyle.NoPen)
            m.setBrush(QColor(16, 32, 40, alfa))
            m.drawRoundedRect(kartka.adjusted(-i - 1, -i + 1, i + 1, i + 3), 3 + i, 3 + i)
        m.setBrush(QColor("white"))
        m.setPen(QColor(LINIA))
        m.drawRoundedRect(kartka, 2, 2)
        m.save()
        m.translate(kartka.topLeft())
        m.scale(skala, skala)
        m.translate(self.MARGINES, self.MARGINES)
        m.setClipRect(QRectF(0, 0, self.A4.width() - 2 * self.MARGINES, self.A4.height() - 2 * self.MARGINES))
        self.dokument.drawContents(m)
        m.restore()
        m.end()


class DwuliniowyDelegate(QStyledItemDelegate):
    """Komórka z wyraźną pierwszą linią (np. pacjent) i szarą drugą (numer, data)."""

    def paint(self, malarz: QPainter, opcja, indeks):
        tekst = indeks.data(Qt.ItemDataRole.DisplayRole) or ""
        gora, _, dol = tekst.partition("\n")
        opt = QStyleOptionViewItem(opcja)
        self.initStyleOption(opt, indeks)
        opt.text = ""
        if opcja.widget:
            opcja.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, malarz, opcja.widget)
        malarz.save()
        r = opcja.rect.adjusted(14, 0, -6, 0)
        f1 = _czcionka(13, QFont.Weight.Medium)
        f2 = _czcionka(12, cyfry=True)
        h1, h2 = QFontMetrics(f1).height(), QFontMetrics(f2).height()
        y = r.center().y() - (h1 + h2 + 2) / 2
        malarz.setFont(f1)
        malarz.setPen(QColor(TEKST))
        malarz.drawText(QRectF(r.x(), y, r.width(), h1), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        QFontMetrics(f1).elidedText(gora, Qt.TextElideMode.ElideRight, r.width()))
        malarz.setFont(f2)
        malarz.setPen(QColor(TEKST_3))
        malarz.drawText(QRectF(r.x(), y + h1 + 2, r.width(), h2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        dol)
        malarz.restore()


class PodgladStron(QWidget):
    """Wszystkie strony dokumentu jako kartki A4 jedna pod drugą, z powiększaniem (do okna podglądu)."""

    A4 = QSizeF(794, 1123)
    MARGINES = 57
    ODSTEP = 24

    def __init__(self):
        super().__init__()
        self.dokument = QTextDocument()
        self.dokument.setDocumentMargin(0)
        self.tresc = QSizeF(self.A4.width() - 2 * self.MARGINES, self.A4.height() - 2 * self.MARGINES)
        self.dokument.setPageSize(self.tresc)
        self.skala = 1.0

    def ustaw_html(self, html: str):
        self.dokument.setHtml(html)
        self._zmien_rozmiar()

    def ustaw_skale(self, skala: float):
        self.skala = max(0.4, min(2.5, skala))
        self._zmien_rozmiar()

    def strony(self) -> int:
        return max(1, self.dokument.pageCount())

    def _zmien_rozmiar(self):
        szer = int(self.A4.width() * self.skala + 2 * self.ODSTEP)
        wys = int(self.strony() * (self.A4.height() * self.skala + self.ODSTEP) + self.ODSTEP)
        self.setFixedSize(szer, wys)
        self.update()

    def paintEvent(self, _):
        m = QPainter(self)
        m.setRenderHint(QPainter.RenderHint.Antialiasing)
        m.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        szer, wys = self.A4.width() * self.skala, self.A4.height() * self.skala
        for i in range(self.strony()):
            kartka = QRectF(self.ODSTEP, self.ODSTEP + i * (wys + self.ODSTEP), szer, wys)
            for j, alfa in enumerate((12, 8, 5)):
                m.setPen(Qt.PenStyle.NoPen)
                m.setBrush(QColor(16, 32, 40, alfa))
                m.drawRoundedRect(kartka.adjusted(-j - 1, -j + 1, j + 1, j + 3), 2 + j, 2 + j)
            m.setBrush(QColor("white"))
            m.setPen(QColor(LINIA))
            m.drawRect(kartka)
            m.save()
            m.translate(kartka.topLeft())
            m.scale(self.skala, self.skala)
            m.translate(self.MARGINES, self.MARGINES - i * self.tresc.height())
            obszar = QRectF(0, i * self.tresc.height(), self.tresc.width(), self.tresc.height())
            m.setClipRect(obszar)
            self.dokument.drawContents(m, obszar)
            m.restore()
        m.end()


class OknoPowiadomienia(QWidget):
    """Własne powiadomienie Fakturnika w prawym dolnym rogu ekranu (nad paskiem zadań), także gdy okno
    programu jest schowane. Wjeżdża z boku, znika samo po kilku sekundach albo po kliknięciu; kliknięcie
    wykonuje akcję (np. otwiera szczegóły). Kilka powiadomień układa się jedno nad drugim."""

    otwarte: list["OknoPowiadomienia"] = []
    KOLORY = {"info": "#5fc4b4", "ok": "#7fd6ae", "uwaga": "#f2c66d", "blad": "#ff9aa5"}
    IKONY = {"info": "tarcza", "ok": "ok", "uwaga": "uwaga", "blad": "uwaga"}

    def __init__(self, tytul: str, tekst: str = "", typ: str = "info", akcja=None, czas_ms: int = 6000,
                 logo=None):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.akcja = akcja
        self.setFixedWidth(360)
        self.setCursor(Qt.CursorShape.PointingHandCursor if akcja else Qt.CursorShape.ArrowCursor)
        karta = QFrame(self)
        karta.setObjectName("powiadomienie")
        karta.setStyleSheet(
            "QFrame#powiadomienie { background: #0f2c33; border: 1px solid #23505a; border-radius: 14px; }"
            "QLabel { background: transparent; color: #dfeef0; }")
        zew = QHBoxLayout(self)
        zew.setContentsMargins(10, 10, 10, 10)
        zew.addWidget(karta)
        u = QHBoxLayout(karta)
        u.setContentsMargins(16, 14, 14, 14)
        u.setSpacing(12)
        znak = QLabel()
        if logo is not None:
            znak.setPixmap(logo)
        else:
            znak.setPixmap(pixmapa(self.IKONY.get(typ, "tarcza"), self.KOLORY.get(typ, "#5fc4b4"), 22))
        u.addWidget(znak, alignment=Qt.AlignmentFlag.AlignTop)
        kolumna = QVBoxLayout()
        kolumna.setSpacing(3)
        naglowek = QHBoxLayout()
        t = QLabel(tytul, textFormat=Qt.TextFormat.PlainText, wordWrap=True)
        t.setStyleSheet("font-weight: 650; font-size: 13px; color: white;")
        naglowek.addWidget(t, 1)
        zrodlo = QLabel("Fakturnik")
        zrodlo.setStyleSheet(f"font-size: 11px; color: {self.KOLORY.get(typ, '#5fc4b4')};")
        naglowek.addWidget(zrodlo, alignment=Qt.AlignmentFlag.AlignTop)
        kolumna.addLayout(naglowek)
        if tekst:
            opis = QLabel(tekst, textFormat=Qt.TextFormat.PlainText, wordWrap=True)
            opis.setStyleSheet("font-size: 12px; color: #a9c3c8;")
            kolumna.addWidget(opis)
        u.addLayout(kolumna, 1)
        self.adjustSize()
        self.efekt = QGraphicsOpacityEffect(self)
        self.efekt.setOpacity(0.0)
        self.setGraphicsEffect(self.efekt)
        self._przezroczystosc = QPropertyAnimation(self.efekt, b"opacity", self)
        self._ruch = QPropertyAnimation(self, b"pos", self)
        for a in (self._przezroczystosc, self._ruch):
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.setDuration(260)
        self.zegar = QTimer(self, singleShot=True, interval=czas_ms)
        self.zegar.timeout.connect(self.zgas)

    def pokaz(self):
        from PySide6.QtGui import QGuiApplication
        ekran = QGuiApplication.primaryScreen().availableGeometry()
        wysokosc = sum(o.height() for o in OknoPowiadomienia.otwarte if o.isVisible())
        cel = QPoint(ekran.right() - self.width() - 8, ekran.bottom() - self.height() - 8 - wysokosc)
        OknoPowiadomienia.otwarte.append(self)
        self.move(cel + QPoint(40, 0))
        self.show()
        self._ruch.setStartValue(cel + QPoint(40, 0))
        self._ruch.setEndValue(cel)
        self._przezroczystosc.setStartValue(0.0)
        self._przezroczystosc.setEndValue(1.0)
        self._ruch.start()
        self._przezroczystosc.start()
        self.zegar.start()
        return self

    def enterEvent(self, e):
        self.zegar.stop()  # najechanie myszą zatrzymuje znikanie
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.zegar.start(2500)
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        akcja, self.akcja = self.akcja, None
        self.zgas()
        if akcja:
            akcja()

    def zgas(self):
        self.zegar.stop()
        self._przezroczystosc.stop()
        self._przezroczystosc.setStartValue(self.efekt.opacity())
        self._przezroczystosc.setEndValue(0.0)
        self._przezroczystosc.finished.connect(self._zamknij)
        self._przezroczystosc.start()

    def _zamknij(self):
        if self in OknoPowiadomienia.otwarte:
            OknoPowiadomienia.otwarte.remove(self)
        self.close()
