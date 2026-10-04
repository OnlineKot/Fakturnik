"""Zasłona ekranu: pełny ekran z żabką i zegarem na wszystkich monitorach, bez żadnych napisów.

Znika po trzech naciśnięciach spacji (w ciągu 2 sekund). Nie czyści schowka i nie wylogowuje:
to szybka zasłona przed wzrokiem pacjentów. Blokada hasłem działa niezależnie od niej.
"""

import math
import time
from datetime import datetime

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

SPACJE = 3
OKNO_SPACJI = 2.0  # sekundy na trzy spacje

_ZABA = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 175">
<ellipse cx="55" cy="163" rx="24" ry="9" fill="#3f9b4a"/><ellipse cx="145" cy="163" rx="24" ry="9" fill="#3f9b4a"/>
<ellipse cx="100" cy="112" rx="82" ry="56" fill="#56b85e"/>
<circle cx="58" cy="56" r="30" fill="#56b85e"/><circle cx="142" cy="56" r="30" fill="#56b85e"/>
<ellipse cx="100" cy="128" rx="54" ry="33" fill="#a9dc8c"/>
{oczy}
<ellipse cx="48" cy="100" rx="11" ry="6.5" fill="#f29aa3" opacity="0.75"/>
<ellipse cx="152" cy="100" rx="11" ry="6.5" fill="#f29aa3" opacity="0.75"/>
<path d="M70 92 Q100 120 130 92" stroke="#1d2b2f" stroke-width="4.5" fill="none" stroke-linecap="round"/>
</svg>"""
_OCZY_OTWARTE = ('<circle cx="58" cy="53" r="19" fill="white"/><circle cx="142" cy="53" r="19" fill="white"/>'
                 '<circle cx="62" cy="56" r="9.5" fill="#1d2b2f"/><circle cx="146" cy="56" r="9.5" fill="#1d2b2f"/>'
                 '<circle cx="66" cy="51" r="3.2" fill="white"/><circle cx="150" cy="51" r="3.2" fill="white"/>')
_OCZY_ZAMKNIETE = ('<path d="M42 55 Q58 66 74 55" stroke="#1d2b2f" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
                   '<path d="M126 55 Q142 66 158 55" stroke="#1d2b2f" stroke-width="4.5" fill="none" '
                   'stroke-linecap="round"/>')


class _Ekran(QWidget):
    """Zasłona jednego monitora."""

    def __init__(self, zaslona: "Zaslona", ekran):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.zaslona = zaslona
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(ekran.geometry())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor("#12343c"))
        gradient.setColorAt(1, QColor("#071a1f"))
        p.fillRect(self.rect(), gradient)
        t = time.monotonic() - self.zaslona.start
        skala = min(w, h) / 1000
        szer = 300 * skala
        wys = szer * 175 / 200
        oddech = math.sin(t * 1.6) * 6 * skala
        x, y = (w - szer) / 2, h * 0.42 - wys / 2 + oddech
        # cień pod żabką
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(QRectF(x + szer * 0.15, h * 0.42 + wys / 2 + 8 * skala, szer * 0.7, 16 * skala))
        mruga = (t % 4.2) > 4.05
        (self.zaslona.zaba_zamknieta if mruga else self.zaslona.zaba).render(p, QRectF(x, y, szer, wys))
        teraz = datetime.now()
        p.setPen(QColor("#e8f3f5"))
        czcionka = QFont(self.font())
        czcionka.setPixelSize(max(40, int(150 * skala)))
        czcionka.setWeight(QFont.Weight.Light)
        p.setFont(czcionka)
        gora = h * 0.42 + wys / 2 + 50 * skala
        p.drawText(QRectF(0, gora, w, 180 * skala), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   f"{teraz:%H:%M}")
        czcionka.setPixelSize(max(16, int(34 * skala)))
        czcionka.setWeight(QFont.Weight.Normal)
        p.setFont(czcionka)
        p.setPen(QColor("#8fb3ba"))
        dni = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
        miesiace = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
                    "października", "listopada", "grudnia"]
        p.drawText(QRectF(0, gora + 175 * skala, w, 60 * skala), Qt.AlignmentFlag.AlignHCenter,
                   f"{dni[teraz.weekday()]}, {teraz.day} {miesiace[teraz.month - 1]}")
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
        self.zaba = QSvgRenderer(QByteArray(_ZABA.format(oczy=_OCZY_OTWARTE).encode()))
        self.zaba_zamknieta = QSvgRenderer(QByteArray(_ZABA.format(oczy=_OCZY_ZAMKNIETE).encode()))
        self.start = time.monotonic()
        self.zamykanie = False
        self._spacje: list[float] = []
        self.ekrany = [_Ekran(self, e) for e in QGuiApplication.screens()]
        self._animacja = QTimer(self, interval=50)
        self._animacja.timeout.connect(self._odswiez)
        self._pilnuj = QTimer(self, interval=1000)
        self._pilnuj.timeout.connect(self._na_wierzch)

    def pokaz(self):
        for e in self.ekrany:
            e.showFullScreen()
            e.raise_()
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
        for e in self.ekrany:
            e.raise_()
        if self.ekrany and not self.ekrany[0].isActiveWindow():
            self.ekrany[0].activateWindow()
            self.ekrany[0].grabKeyboard()

    def klawisz(self, klawisz: int):
        if klawisz != Qt.Key.Key_Space:
            return
        teraz = time.monotonic()
        self._spacje = [t for t in self._spacje if teraz - t <= OKNO_SPACJI] + [teraz]
        if len(self._spacje) >= SPACJE:
            self.zamknij()

    def zamknij(self):
        self.zamykanie = True
        self._animacja.stop()
        self._pilnuj.stop()
        for e in self.ekrany:
            e.releaseKeyboard()
            e.close()
        self.ekrany = []
        self.zamknieta.emit()
        self.deleteLater()
