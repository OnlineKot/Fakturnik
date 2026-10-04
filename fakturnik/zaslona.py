"""Zasłona ekranu: pełny ekran z ząbkiem i zegarem na wszystkich monitorach, bez żadnych napisów.

Znika po trzech naciśnięciach spacji (w ciągu 2 sekund). Nie czyści schowka i nie wylogowuje:
to szybka zasłona przed wzrokiem pacjentów. Blokada hasłem działa niezależnie od niej.

Wygląd: płynne pojawienie się i zniknięcie, unoszący się i mrugający ząbek, pulsująca poświata
i migoczące iskierki. Wszystkie rozmiary liczone są od wielkości ekranu, więc nic nie wychodzi
poza krawędzie (mały laptop, duży monitor, ekran pionowy).
"""

import math
import time
from datetime import datetime

from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QLinearGradient, QPainter, QPainterPath, \
    QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

SPACJE = 3
OKNO_SPACJI = 2.0  # sekundy na trzy spacje
POJAWIANIE_MS = 700
ZNIKANIE_MS = 350

_ZAB = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 215">
<path d="M100 22 C72 6 30 14 28 62 C26 98 40 122 48 152 C55 182 60 206 73 206 C88 206 85 162 100 162
         C115 162 112 206 127 206 C140 206 145 182 152 152 C160 122 174 98 172 62 C170 14 128 6 100 22 Z"
      fill="#ffffff" stroke="#d3e6ea" stroke-width="3"/>
<path d="M48 70 Q49 42 76 36" stroke="#dcedf1" stroke-width="9" fill="none" stroke-linecap="round"/>
{oczy}
<ellipse cx="64" cy="114" rx="10" ry="6" fill="#f6b3bb" opacity="0.8"/>
<ellipse cx="136" cy="114" rx="10" ry="6" fill="#f6b3bb" opacity="0.8"/>
<path d="M86 113 Q100 128 114 113" stroke="#1d2b2f" stroke-width="4.5" fill="none" stroke-linecap="round"/>
</svg>"""
_OCZY_OTWARTE = ('<circle cx="78" cy="96" r="8" fill="#1d2b2f"/><circle cx="122" cy="96" r="8" fill="#1d2b2f"/>'
                 '<circle cx="81" cy="93" r="2.6" fill="white"/><circle cx="125" cy="93" r="2.6" fill="white"/>')
_OCZY_ZAMKNIETE = ('<path d="M69 97 Q78 104 87 97" stroke="#1d2b2f" stroke-width="4" fill="none" stroke-linecap="round"/>'
                   '<path d="M113 97 Q122 104 131 97" stroke="#1d2b2f" stroke-width="4" fill="none" '
                   'stroke-linecap="round"/>')
_ISKIERKI = [(-0.95, -0.55, 1.0, 0.0), (0.98, -0.35, 0.8, 1.3), (-0.78, 0.55, 0.65, 2.1), (0.85, 0.6, 0.9, 0.7),
             (0.1, -1.05, 0.55, 2.8), (-0.35, -0.95, 0.45, 1.9)]  # (x, y względem ząbka, wielkość, faza)

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
            "października", "listopada", "grudnia"]


def _gwiazdka(srodek: QPointF, r: float) -> QPainterPath:
    """Czteroramienna iskierka."""
    s = QPainterPath()
    s.moveTo(srodek.x(), srodek.y() - r)
    for kat in range(1, 8):
        promien = r if kat % 2 == 0 else r * 0.28
        a = math.pi / 2 - kat * math.pi / 4
        s.lineTo(srodek.x() + promien * math.cos(a), srodek.y() - promien * math.sin(a))
    s.closeSubpath()
    return s


class _Ekran(QWidget):
    """Zasłona jednego monitora."""

    def __init__(self, zaslona: "Zaslona", ekran):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.zaslona = zaslona
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(ekran.geometry())
        self.setWindowOpacity(0.0)

    @staticmethod
    def _czcionka(baza: QFont, px: float, waga: QFont.Weight) -> QFont:
        f = QFont(baza)
        f.setPixelSize(max(10, int(px)))
        f.setWeight(waga)
        return f

    def paintEvent(self, _):
        z = self.zaslona
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        t = time.monotonic() - z.start
        tlo = QLinearGradient(0, 0, 0, h)
        tlo.setColorAt(0, QColor("#12343c"))
        tlo.setColorAt(1, QColor("#061519"))
        p.fillRect(self.rect(), tlo)

        # układ: ząbek, zegar i data razem zajmują najwyżej ~78% wysokości i ~80% szerokości ekranu
        jednostka = min(w / 1.15, h) / 1000
        wys_zeba = 260 * jednostka
        szer_zeba = wys_zeba * 200 / 215
        czcionka_zegara = self._czcionka(self.font(), 150 * jednostka, QFont.Weight.Light)
        czcionka_daty = self._czcionka(self.font(), 34 * jednostka, QFont.Weight.Normal)
        teraz = datetime.now()
        zegar = f"{teraz:%H:%M}"
        data = f"{DNI[teraz.weekday()]}, {teraz.day} {MIESIACE[teraz.month - 1]}"
        for f, tekst in ((czcionka_zegara, zegar), (czcionka_daty, data)):  # dopasuj do szerokości
            szer = QFontMetricsF(f).horizontalAdvance(tekst)
            if szer > w * 0.8:
                f.setPixelSize(max(10, int(f.pixelSize() * w * 0.8 / szer)))
        wys_zegara = QFontMetricsF(czcionka_zegara).height()
        wys_daty = QFontMetricsF(czcionka_daty).height()
        odstep = 40 * jednostka
        calosc = wys_zeba + odstep + wys_zegara + wys_daty
        gora = (h - calosc) / 2

        # ząbek: unosi się, podskakuje po spacji, mruga
        unoszenie = math.sin(t * 1.5) * 9 * jednostka
        od_spacji = time.monotonic() - z.ostatnia_spacja
        podskok = math.exp(-od_spacji * 7) * math.sin(od_spacji * 22) * 0.06 if od_spacji < 1 else 0
        skala = 1 + podskok
        srodek = QPointF(w / 2, gora + wys_zeba / 2 + unoszenie)
        # poświata
        puls = 0.5 + 0.5 * math.sin(t * 1.2)
        poswiata = QRadialGradient(srodek, wys_zeba * (0.85 + 0.08 * puls))
        poswiata.setColorAt(0, QColor(94, 180, 196, int(70 + 30 * puls)))
        poswiata.setColorAt(1, QColor(94, 180, 196, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(poswiata)
        p.drawEllipse(srodek, wys_zeba * 1.1, wys_zeba * 1.1)
        # cień (mniejszy, gdy ząbek jest wyżej)
        cien_sz = szer_zeba * (0.62 + unoszenie / (300 * jednostka or 1))
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawEllipse(QPointF(w / 2, gora + wys_zeba + 14 * jednostka), cien_sz / 2, 7 * jednostka)
        # iskierki
        for dx, dy, wielkosc, faza in _ISKIERKI:
            jasnosc = max(0.0, math.sin(t * 1.7 + faza * 2.3))
            if jasnosc <= 0.02:
                continue
            punkt = QPointF(srodek.x() + dx * szer_zeba * 0.78, srodek.y() + dy * wys_zeba * 0.62)
            p.setBrush(QColor(220, 245, 250, int(220 * jasnosc)))
            p.drawPath(_gwiazdka(punkt, 13 * jednostka * wielkosc * (0.6 + 0.4 * jasnosc)))
        mruga = (t % 4.5) > 4.33
        p.save()
        p.translate(srodek)
        p.scale(skala, skala)
        (z.zab_zamkniety if mruga else z.zab).render(p, QRectF(-szer_zeba / 2, -wys_zeba / 2, szer_zeba, wys_zeba))
        p.restore()

        # zegar i data
        y = gora + wys_zeba + odstep
        p.setFont(czcionka_zegara)
        p.setPen(QColor("#e8f3f5"))
        p.drawText(QRectF(0, y, w, wys_zegara), Qt.AlignmentFlag.AlignCenter, zegar)
        p.setFont(czcionka_daty)
        p.setPen(QColor("#8fb3ba"))
        p.drawText(QRectF(0, y + wys_zegara, w, wys_daty), Qt.AlignmentFlag.AlignCenter, data)
        p.end()

    def keyPressEvent(self, e):
        self.zaslona.klawisz(e.key())

    def closeEvent(self, e):
        if not self.zaslona.zamykanie:
            e.ignore()  # zasłonę zamykają tylko trzy spacje (Alt+F4 nie działa)
            return
        super().closeEvent(e)


class Zaslona(QWidget):
    """Zarządza zasłonami wszystkich monitorów."""
    zamknieta = Signal()

    def __init__(self):
        super().__init__()
        self.zab = QSvgRenderer(QByteArray(_ZAB.format(oczy=_OCZY_OTWARTE).encode()))
        self.zab_zamkniety = QSvgRenderer(QByteArray(_ZAB.format(oczy=_OCZY_ZAMKNIETE).encode()))
        self.start = time.monotonic()
        self.ostatnia_spacja = 0.0
        self.zamykanie = False
        self._spacje: list[float] = []
        self._animacje: list[QPropertyAnimation] = []
        self.ekrany = [_Ekran(self, e) for e in QGuiApplication.screens()]
        self._animacja = QTimer(self, interval=33)  # ~30 klatek na sekundę
        self._animacja.timeout.connect(self._odswiez)
        self._pilnuj = QTimer(self, interval=1000)
        self._pilnuj.timeout.connect(self._na_wierzch)

    def _przenikanie(self, ekran: QWidget, do: float, czas_ms: int, po=None):
        a = QPropertyAnimation(ekran, b"windowOpacity", self)
        a.setDuration(czas_ms)
        a.setStartValue(ekran.windowOpacity())
        a.setEndValue(do)
        a.setEasingCurve(QEasingCurve.Type.OutCubic if do > 0 else QEasingCurve.Type.InCubic)
        if po:
            a.finished.connect(po)
        a.start()
        self._animacje.append(a)

    def pokaz(self):
        for e in self.ekrany:
            e.showFullScreen()
            e.raise_()
            self._przenikanie(e, 1.0, POJAWIANIE_MS)
        if self.ekrany:
            self.ekrany[0].activateWindow()
            self.ekrany[0].setFocus()
            self.ekrany[0].grabKeyboard()
        self._animacja.start()
        self._pilnuj.start()

    def _odswiez(self):
        for e in self.ekrany:
            e.update()

    def _na_wierzch(self):
        """Inne okno (np. okno hasła) nie przykryje zasłony ani nie przejmie klawiatury."""
        if self.zamykanie:
            return
        for e in self.ekrany:
            e.raise_()
        if self.ekrany and not self.ekrany[0].isActiveWindow():
            self.ekrany[0].activateWindow()
            self.ekrany[0].grabKeyboard()

    def klawisz(self, klawisz: int):
        if klawisz != Qt.Key.Key_Space or self.zamykanie:
            return
        teraz = time.monotonic()
        self.ostatnia_spacja = teraz
        self._spacje = [t for t in self._spacje if teraz - t <= OKNO_SPACJI] + [teraz]
        if len(self._spacje) >= SPACJE:
            self.zamknij()

    def zamknij(self, natychmiast: bool = False):
        if self.zamykanie:
            return
        self.zamykanie = True
        self._pilnuj.stop()
        for e in self.ekrany:
            e.releaseKeyboard()
        if natychmiast or not self.ekrany:
            self._koniec()
            return
        for i, e in enumerate(self.ekrany):
            self._przenikanie(e, 0.0, ZNIKANIE_MS, self._koniec if i == 0 else None)
        QTimer.singleShot(ZNIKANIE_MS + 300, self, self._koniec)  # gdyby system nie obsługiwał przezroczystości

    def _koniec(self):
        if not self.ekrany:
            return
        self._animacja.stop()
        for e in self.ekrany:
            e.close()
        self.ekrany = []
        self.zamknieta.emit()
        self.deleteLater()
