"""Zasłona ekranu: pełny ekran z ząbkiem (jak w logo gabinetu) i zegarem na wszystkich monitorach, bez napisów.

Znika tylko po DOKŁADNIE trzech naciśnięciach spacji i krótkiej pauzie. Cztery i więcej spacji,
przytrzymana spacja albo inny klawisz w serii nic nie dają. Nie czyści schowka i nie wylogowuje:
to szybka zasłona przed wzrokiem pacjentów. Blokada hasłem działa niezależnie od niej.

Animacja: zasłona płynnie się pojawia, kontur ząbka i lusterka rysuje się sam, potem ząbek
spokojnie się unosi, po szkliwie co kilka sekund przesuwa się odblask, w tle wolno płyną
rozmyte światła. Rozmiary liczone są od wielkości ekranu, więc nic nie wychodzi poza krawędzie.
"""

import math
import random
import time
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient, QTransform,
)
from PySide6.QtWidgets import QWidget

SPACJE = 3
OKNO_SPACJI = 2.0    # trzy spacje w ciągu tylu sekund
PAUZA = 0.6          # po trzeciej spacji: tyle ciszy, żeby zasłona zniknęła (czwarta spacja psuje serię)
KARA = 1.2           # po nieudanej serii: tyle ciszy, zanim można zacząć od nowa
POJAWIANIE_MS = 800
ZNIKANIE_MS = 400
RYSOWANIE = 1.6      # sekundy rysowania konturu

KOLOR_LINII = QColor("#e8f3f5")
AKCENT = QColor("#5fb3c2")

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
            "października", "listopada", "grudnia"]


class LicznikSpacji:
    """Odblokowanie dokładnie trzema spacjami (bez Qt, do testów)."""

    def __init__(self):
        self.serie: list[float] = []
        self.kara_do = 0.0

    def nacisniecie(self, spacja: bool, teraz: float, powtorzenie: bool = False) -> None:
        if not spacja or powtorzenie or teraz < self.kara_do:
            self.serie = []
            self.kara_do = teraz + KARA
            return
        self.serie = [t for t in self.serie if teraz - t <= OKNO_SPACJI] + [teraz]
        if len(self.serie) > SPACJE:
            self.serie = []
            self.kara_do = teraz + KARA

    def odblokowac(self, teraz: float) -> bool:
        """Prawda, gdy były dokładnie trzy spacje, a od ostatniej minęła pauza bez kolejnych klawiszy."""
        return len(self.serie) == SPACJE and teraz - self.serie[-1] >= PAUZA


def kontur_zeba() -> QPainterPath:
    """Ząbek z logo gabinetu (układ 200 × 215)."""
    s = QPainterPath()
    s.moveTo(100, 30)
    s.cubicTo(74, 12, 30, 18, 30, 66)
    s.cubicTo(30, 100, 44, 124, 50, 152)
    s.cubicTo(57, 184, 62, 206, 75, 206)
    s.cubicTo(90, 206, 86, 160, 100, 160)
    s.cubicTo(114, 160, 110, 206, 125, 206)
    s.cubicTo(138, 206, 143, 184, 150, 152)
    s.cubicTo(156, 124, 170, 100, 170, 66)
    s.cubicTo(170, 18, 126, 12, 100, 30)
    s.closeSubpath()
    return s


def lusterko() -> QPainterPath:
    """Lusterko dentystyczne: trzonek wychodzący z ząbka i owalna główka (jak w logo)."""
    s = QPainterPath()
    s.moveTo(118, 64)
    s.lineTo(156, 8)
    glowka = QPainterPath()
    glowka.addEllipse(QPointF(0, 0), 8, 14)
    s.addPath(QTransform().translate(161, -2).rotate(34).map(glowka))
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

        # rozmyte światła płynące powoli w górę
        p.setPen(Qt.PenStyle.NoPen)
        for x0, predkosc, r, faza in z.swiatla:
            y = (1.15 - ((t * predkosc + faza) % 1.3)) * h
            x = (x0 + 0.02 * math.sin(t * 0.3 + faza * 6)) * w
            promien = r * min(w, h)
            g = QRadialGradient(QPointF(x, y), promien)
            g.setColorAt(0, QColor(95, 179, 194, 38))
            g.setColorAt(1, QColor(95, 179, 194, 0))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, y), promien, promien)

        # układ: ząbek, zegar i data mieszczą się w ~80% wysokości i szerokości ekranu
        jednostka = min(w / 1.15, h) / 1000
        wys_zeba = 270 * jednostka
        skala = wys_zeba / 215
        teraz = datetime.now()
        zegar = f"{teraz:%H:%M}"
        data = f"{DNI[teraz.weekday()]}, {teraz.day} {MIESIACE[teraz.month - 1]}"
        czcionka_zegara = self._czcionka(self.font(), 150 * jednostka, QFont.Weight.Light)
        czcionka_daty = self._czcionka(self.font(), 34 * jednostka, QFont.Weight.Normal)
        for f, tekst in ((czcionka_zegara, zegar), (czcionka_daty, data)):
            szer = QFontMetricsF(f).horizontalAdvance(tekst)
            if szer > w * 0.8:
                f.setPixelSize(max(10, int(f.pixelSize() * w * 0.8 / szer)))
        wys_zegara = QFontMetricsF(czcionka_zegara).height()
        wys_daty = QFontMetricsF(czcionka_daty).height()
        odstep = 46 * jednostka
        gora = (h - (wys_zeba + odstep + wys_zegara + wys_daty)) / 2

        # ząbek: rysuje się, potem spokojnie się unosi
        postep = min(1.0, t / RYSOWANIE)
        postep = 1 - (1 - postep) ** 3
        unoszenie = math.sin(t * 1.1) * 7 * jednostka
        srodek = QPointF(w / 2, gora + wys_zeba / 2 + unoszenie)
        oddech = 0.5 + 0.5 * math.sin(t * 0.9)
        poswiata = QRadialGradient(srodek, wys_zeba * (0.95 + 0.06 * oddech))
        poswiata.setColorAt(0, QColor(95, 179, 194, int((55 + 25 * oddech) * postep)))
        poswiata.setColorAt(1, QColor(95, 179, 194, 0))
        p.setBrush(poswiata)
        p.drawEllipse(srodek, wys_zeba * 1.05, wys_zeba * 1.05)
        # fala po każdej spacji (bez zdradzania, ile ich było)
        od_spacji = time.monotonic() - z.ostatnia_spacja
        if od_spacji < 0.9:
            k = od_spacji / 0.9
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(232, 243, 245, int(90 * (1 - k))), 2 * jednostka + 0.5))
            p.drawEllipse(srodek, wys_zeba * (0.55 + 0.45 * k), wys_zeba * (0.55 + 0.45 * k))

        p.save()
        p.translate(srodek.x() - 100 * skala, srodek.y() - 107 * skala)
        p.scale(skala, skala)
        zab = z.zab
        # wypełnienie szkliwa pojawia się po narysowaniu konturu
        wypelnienie = max(0.0, min(1.0, (t - RYSOWANIE * 0.7) / 0.8))
        if wypelnienie > 0:
            szkliwo = QLinearGradient(0, 20, 0, 206)
            szkliwo.setColorAt(0, QColor(255, 255, 255, int(46 * wypelnienie)))
            szkliwo.setColorAt(1, QColor(255, 255, 255, int(10 * wypelnienie)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(szkliwo)
            p.drawPath(zab)
            # odblask przesuwający się po szkliwie co 7 s
            faza = (t - RYSOWANIE) % 7.0
            if 0 <= faza < 1.6:
                x = -60 + faza / 1.6 * 320
                blask = QLinearGradient(x - 40, 0, x + 40, 60)
                blask.setColorAt(0, QColor(255, 255, 255, 0))
                blask.setColorAt(0.5, QColor(255, 255, 255, int(70 * wypelnienie)))
                blask.setColorAt(1, QColor(255, 255, 255, 0))
                p.save()
                p.setClipPath(zab)
                p.fillRect(QRectF(0, 0, 200, 215), QBrush(blask))
                p.restore()
        grubosc = 7.0
        for sciezka, dlugosc, kolor in ((zab, z.dl_zeba, KOLOR_LINII), (z.lusterko, z.dl_lusterka, AKCENT)):
            pioro = QPen(kolor, grubosc, Qt.PenStyle.CustomDashLine, Qt.PenCapStyle.RoundCap,
                         Qt.PenJoinStyle.RoundJoin)
            jednostki = dlugosc / grubosc + 1
            pioro.setDashPattern([jednostki, jednostki])
            pioro.setDashOffset(jednostki * (1 - postep))
            p.setPen(pioro)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(sciezka)
        p.restore()

        # zegar i data pojawiają się po ząbku
        widocznosc = max(0.0, min(1.0, (t - 0.5) / 0.9))
        y = gora + wys_zeba + odstep + (1 - widocznosc) * 12 * jednostka
        p.setFont(czcionka_zegara)
        p.setPen(QColor(232, 243, 245, int(255 * widocznosc)))
        p.drawText(QRectF(0, y, w, wys_zegara), Qt.AlignmentFlag.AlignCenter, zegar)
        p.setFont(czcionka_daty)
        p.setPen(QColor(143, 179, 186, int(255 * widocznosc)))
        p.drawText(QRectF(0, y + wys_zegara, w, wys_daty), Qt.AlignmentFlag.AlignCenter, data)
        p.end()

    def keyPressEvent(self, e):
        self.zaslona.klawisz(e.key(), e.isAutoRepeat())

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
        self.zab = kontur_zeba()
        self.lusterko = lusterko()
        self.dl_zeba = self.zab.length()
        self.dl_lusterka = self.lusterko.length()
        los = random.Random(7)
        self.swiatla = [(los.random(), 0.012 + los.random() * 0.02, 0.06 + los.random() * 0.1, los.random())
                        for _ in range(9)]
        self.start = time.monotonic()
        self.ostatnia_spacja = 0.0
        self.zamykanie = False
        self.licznik = LicznikSpacji()
        self._animacje: list[QPropertyAnimation] = []
        self.ekrany = [_Ekran(self, e) for e in QGuiApplication.screens()]
        self._animacja = QTimer(self, interval=33)  # ~30 klatek na sekundę
        self._animacja.timeout.connect(self._klatka)
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

    def _klatka(self):
        if not self.zamykanie and self.licznik.odblokowac(time.monotonic()):
            self.zamknij()
            return
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

    def klawisz(self, klawisz: int, powtorzenie: bool = False):
        if self.zamykanie:
            return
        spacja = klawisz == Qt.Key.Key_Space
        if spacja and not powtorzenie:
            self.ostatnia_spacja = time.monotonic()
        self.licznik.nacisniecie(spacja, time.monotonic(), powtorzenie)

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
