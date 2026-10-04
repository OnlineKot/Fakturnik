"""Zasłona ekranu: logo gabinetu, nazwa gabinetu i zegar na wszystkich monitorach, bez napisów-instrukcji.

Znika tylko po DOKŁADNIE trzech naciśnięciach spacji i krótkiej pauzie. Cztery i więcej spacji,
przytrzymana spacja albo inny klawisz w serii nic nie dają. Nie czyści schowka i nie wylogowuje:
to szybka zasłona przed wzrokiem pacjentów. Blokada hasłem działa niezależnie od niej.

Ochrona ekranu przed wypaleniem: cały obraz bardzo powoli wędruje po ekranie (żaden piksel nie świeci
długo w jednym miejscu), a po ustawionym czasie zasłona gaśnie do czerni i wyłącza monitor.
Naciśnięcie dowolnego klawisza budzi ekran. W czerni animacja stoi, więc program nie zużywa procesora.
"""

import math
import random
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QGuiApplication, QLinearGradient, QPainter, QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

SPACJE = 3
OKNO_SPACJI = 2.0    # trzy spacje w ciągu tylu sekund
PAUZA = 0.6          # po trzeciej spacji: tyle ciszy, żeby zasłona zniknęła (czwarta spacja psuje serię)
KARA = 1.2           # po nieudanej serii: tyle ciszy, zanim można zacząć od nowa
POJAWIANIE_MS = 800
ZNIKANIE_MS = 400
ODSLANIANIE = 1.4    # sekundy odsłaniania logo
GASNIECIE = 3.0      # sekundy przejścia do czerni
KLATKI_MS = 50       # 20 klatek na sekundę wystarcza do płynnego, powolnego ruchu

LOGO = Path(__file__).parent / "zasoby" / "logo.svg"
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


def przesuniecie(t: float, zapas_x: float, zapas_y: float) -> tuple[float, float]:
    """Powolna wędrówka obrazu po ekranie (krzywa Lissajous, pełny obieg w kilka minut)."""
    return zapas_x * math.sin(t / 47.0), zapas_y * math.sin(t / 71.0 + 1.3)


def jasnosc_po_czasie(t: float, gaszenie_s: float) -> float:
    """1 = pełny obraz, 0 = czerń. Po gaszenie_s sekundach obraz łagodnie gaśnie (0 = nigdy)."""
    if gaszenie_s <= 0 or t < gaszenie_s:
        return 1.0
    return max(0.0, 1.0 - (t - gaszenie_s) / GASNIECIE)


def wylacz_monitor() -> None:
    """Windows: monitor przechodzi w stan wyłączenia (budzi go ruch myszy lub klawisz)."""
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER = 0xFFFF, 0x0112, 0xF170
        ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
    except Exception:  # noqa: BLE001
        pass


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
        w, h = float(self.width()), float(self.height())
        teraz_m = time.monotonic()
        t = teraz_m - z.start
        jasnosc = jasnosc_po_czasie(teraz_m - z.aktywnosc, z.gaszenie_s)
        if jasnosc <= 0:
            p.fillRect(self.rect(), Qt.GlobalColor.black)
            p.end()
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
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
            g.setColorAt(0, QColor(95, 179, 194, 34))
            g.setColorAt(1, QColor(95, 179, 194, 0))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, y), promien, promien)

        # układ: logo, zegar, data i nazwa gabinetu; całość wędruje po ekranie, ale nigdy poza krawędzie
        jednostka = min(w / 1.15, h) / 1000
        wys_logo = 250 * jednostka
        szer_logo = wys_logo * 80 / 120
        teraz = datetime.now()
        zegar = f"{teraz:%H:%M}"
        data = f"{DNI[teraz.weekday()]}, {teraz.day} {MIESIACE[teraz.month - 1]}"
        czcionka_zegara = self._czcionka(self.font(), 140 * jednostka, QFont.Weight.Light)
        czcionka_daty = self._czcionka(self.font(), 32 * jednostka, QFont.Weight.Normal)
        czcionka_nazwy = self._czcionka(self.font(), 30 * jednostka, QFont.Weight.DemiBold)
        teksty = [(czcionka_zegara, zegar), (czcionka_daty, data)] + ([(czcionka_nazwy, z.nazwa)] if z.nazwa else [])
        szer_tresci = szer_logo
        for f, tekst in teksty:
            szer = QFontMetricsF(f).horizontalAdvance(tekst)
            if szer > w * 0.7:
                f.setPixelSize(max(10, int(f.pixelSize() * w * 0.7 / szer)))
                szer = QFontMetricsF(f).horizontalAdvance(tekst)
            szer_tresci = max(szer_tresci, szer)
        wys_nazwy = QFontMetricsF(czcionka_nazwy).height() if z.nazwa else 0
        wys_zegara = QFontMetricsF(czcionka_zegara).height()
        wys_daty = QFontMetricsF(czcionka_daty).height()
        odstep = 36 * jednostka
        calosc = wys_nazwy + (odstep * 0.6 if z.nazwa else 0) + wys_logo + odstep + wys_zegara + wys_daty
        dx, dy = przesuniecie(t, max(0.0, (w - szer_tresci) / 2 - 40 * jednostka),
                              max(0.0, (h - calosc) / 2 - 30 * jednostka))
        srodek_x = w / 2 + dx
        gora = (h - calosc) / 2 + dy

        if z.nazwa:
            p.setFont(czcionka_nazwy)
            p.setPen(QColor(143, 179, 186, 230))
            p.drawText(QRectF(srodek_x - w / 2, gora, w, wys_nazwy), Qt.AlignmentFlag.AlignCenter, z.nazwa)
            gora += wys_nazwy + odstep * 0.6

        # logo: odsłania się od dołu, potem lekko się unosi; za nim oddychająca poświata
        postep = min(1.0, t / ODSLANIANIE)
        postep = 1 - (1 - postep) ** 3
        unoszenie = math.sin(t * 1.1) * 6 * jednostka
        srodek_logo = QPointF(srodek_x, gora + wys_logo / 2 + unoszenie)
        oddech = 0.5 + 0.5 * math.sin(t * 0.9)
        poswiata = QRadialGradient(srodek_logo, wys_logo * (0.9 + 0.06 * oddech))
        poswiata.setColorAt(0, QColor(95, 179, 194, int((50 + 25 * oddech) * postep)))
        poswiata.setColorAt(1, QColor(95, 179, 194, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(poswiata)
        p.drawEllipse(srodek_logo, wys_logo, wys_logo)
        prost = QRectF(srodek_logo.x() - szer_logo / 2, srodek_logo.y() - wys_logo / 2, szer_logo, wys_logo)
        if z.logo.isValid():
            p.save()
            p.setClipRect(QRectF(prost.left() - 10, prost.bottom() - prost.height() * postep - 2,
                                 prost.width() + 20, prost.height() * postep + 4))
            z.logo.render(p, prost)
            p.restore()

        # zegar i data
        widocznosc = max(0.0, min(1.0, (t - 0.4) / 0.9))
        y = gora + wys_logo + odstep + (1 - widocznosc) * 12 * jednostka
        p.setFont(czcionka_zegara)
        p.setPen(QColor(232, 243, 245, int(255 * widocznosc)))
        p.drawText(QRectF(srodek_x - w / 2, y, w, wys_zegara), Qt.AlignmentFlag.AlignCenter, zegar)
        p.setFont(czcionka_daty)
        p.setPen(QColor(143, 179, 186, int(255 * widocznosc)))
        p.drawText(QRectF(srodek_x - w / 2, y + wys_zegara, w, wys_daty), Qt.AlignmentFlag.AlignCenter, data)
        if jasnosc < 1:  # łagodne gaśnięcie do czerni
            p.fillRect(self.rect(), QColor(0, 0, 0, int(255 * (1 - jasnosc))))
        p.end()

    def keyPressEvent(self, e):
        self.zaslona.klawisz(e.key(), e.isAutoRepeat())

    def mouseMoveEvent(self, _):
        self.zaslona.obudz()

    def closeEvent(self, e):
        if not self.zaslona.zamykanie:
            e.ignore()  # zasłonę zamykają tylko trzy spacje (Alt+F4 nie działa)
            return
        super().closeEvent(e)


class Zaslona(QWidget):
    """Zarządza zasłonami wszystkich monitorów."""
    zamknieta = Signal()

    def __init__(self, nazwa: str = "", gaszenie_min: float = 10):
        super().__init__()
        self.logo = QSvgRenderer(str(LOGO))
        self.nazwa = nazwa.strip()
        self.gaszenie_s = max(0.0, gaszenie_min) * 60
        los = random.Random(7)
        self.swiatla = [(los.random(), 0.012 + los.random() * 0.02, 0.06 + los.random() * 0.1, los.random())
                        for _ in range(7)]
        self.start = time.monotonic()
        self.aktywnosc = self.start  # od tej chwili liczy się czas do zgaszenia
        self._monitor_wylaczony = False
        self.ostatnia_spacja = 0.0
        self.zamykanie = False
        self.licznik = LicznikSpacji()
        self._animacje: list[QPropertyAnimation] = []
        self.ekrany = [_Ekran(self, e) for e in QGuiApplication.screens()]
        self._animacja = QTimer(self, interval=KLATKI_MS)
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
            e.setMouseTracking(True)
            e.showFullScreen()
            e.raise_()
            self._przenikanie(e, 1.0, POJAWIANIE_MS)
        if self.ekrany:
            self.ekrany[0].activateWindow()
            self.ekrany[0].setFocus()
            self.ekrany[0].grabKeyboard()
        self._animacja.start()
        self._pilnuj.start()

    def obudz(self):
        """Klawisz albo ruch myszy po zgaszeniu: obraz wraca (licznik spacji działa dalej)."""
        teraz = time.monotonic()
        if jasnosc_po_czasie(teraz - self.aktywnosc, self.gaszenie_s) < 1:
            self.start = teraz - ODSLANIANIE  # bez ponownego odsłaniania logo
        self.aktywnosc = teraz
        self._monitor_wylaczony = False
        if not self._animacja.isActive() and not self.zamykanie:
            self._animacja.start()

    def _klatka(self):
        teraz = time.monotonic()
        if not self.zamykanie and self.licznik.odblokowac(teraz):
            self.zamknij()
            return
        if jasnosc_po_czasie(teraz - self.aktywnosc, self.gaszenie_s) <= 0:
            for e in self.ekrany:
                e.update()  # ostatnia klatka: czerń
            self._animacja.stop()  # w czerni nic się nie rusza: zero pracy procesora
            if not self._monitor_wylaczony:
                self._monitor_wylaczony = True
                wylacz_monitor()
            return
        for e in self.ekrany:
            e.update()

    def _na_wierzch(self):
        """Inne okno (np. okno hasła) nie przykryje zasłony ani nie przejmie klawiatury."""
        if self.zamykanie:
            return
        if not self._animacja.isActive() and self.licznik.odblokowac(time.monotonic()):
            self.zamknij()  # trzy spacje w czerni też działają
            return
        for e in self.ekrany:
            e.raise_()
        if self.ekrany and not self.ekrany[0].isActiveWindow():
            self.ekrany[0].activateWindow()
            self.ekrany[0].grabKeyboard()

    def klawisz(self, klawisz: int, powtorzenie: bool = False):
        if self.zamykanie:
            return
        self.obudz()
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
