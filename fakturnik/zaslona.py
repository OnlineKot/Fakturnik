"""Zasłona ekranu w stylu klasycznego wygaszacza: czarne tło, a na nim logo gabinetu, nazwa gabinetu,
zegar i data, które wolno jeżdżą po ekranie i odbijają się od krawędzi. Bez napisów-instrukcji.

Znika tylko po DOKŁADNIE trzech naciśnięciach spacji i krótkiej pauzie. Cztery i więcej spacji,
przytrzymana spacja albo inny klawisz w serii nic nie dają. Nie czyści schowka i nie wylogowuje:
to szybka zasłona przed wzrokiem pacjentów. Blokada hasłem działa niezależnie od niej.

Ochrona ekranu przed wypaleniem: blok cały czas się przesuwa (żaden piksel nie świeci długo w jednym
miejscu), a po ustawionym czasie zasłona gaśnie do czerni i wyłącza monitor.
Naciśnięcie dowolnego klawisza budzi ekran. W czerni animacja stoi, więc program nie zużywa procesora.
"""

import random
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

SPACJE = 3
OKNO_SPACJI = 2.0    # trzy spacje w ciągu tylu sekund
PAUZA = 0.6          # po trzeciej spacji: tyle ciszy, żeby zasłona zniknęła (czwarta spacja psuje serię)
KARA = 1.2           # po nieudanej serii: tyle ciszy, zanim można zacząć od nowa
POJAWIANIE_MS = 800
ZNIKANIE_MS = 400
GASNIECIE = 3.0      # sekundy przejścia do czerni
KLATKI_MS = 50       # 20 klatek na sekundę wystarcza do płynnego, powolnego ruchu
PREDKOSC = 0.03      # ułamek wysokości ekranu na sekundę (wolno, bez rozpraszania)

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


def odbicie(droga: float, zakres: float) -> float:
    """Pozycja punktu, który jedzie ze stałą prędkością i odbija się od krawędzi (jak logo DVD)."""
    if zakres <= 0:
        return 0.0
    u = (droga / zakres) % 2.0
    return zakres * (u if u <= 1 else 2 - u)


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
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        w, h = float(self.width()), float(self.height())
        teraz_m = time.monotonic()
        jasnosc = jasnosc_po_czasie(teraz_m - z.aktywnosc, z.gaszenie_s)
        if jasnosc <= 0:
            p.end()
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        # klasyczny wygaszacz: czarne tło, jeden blok (nazwa, logo, zegar, data) wolno odbija się od krawędzi
        jednostka = min(w / 1.15, h) / 1000
        wys_logo = 150 * jednostka
        szer_logo = wys_logo * 80 / 120
        teraz = datetime.now()
        zegar = f"{teraz:%H:%M}"
        data = f"{DNI[teraz.weekday()]}, {teraz.day} {MIESIACE[teraz.month - 1]}"
        czcionka_zegara = self._czcionka(self.font(), 96 * jednostka, QFont.Weight.Light)
        czcionka_daty = self._czcionka(self.font(), 24 * jednostka, QFont.Weight.Normal)
        czcionka_nazwy = self._czcionka(self.font(), 24 * jednostka, QFont.Weight.DemiBold)
        teksty = [(czcionka_zegara, zegar), (czcionka_daty, data)] + ([(czcionka_nazwy, z.nazwa)] if z.nazwa else [])
        szer_bloku = szer_logo
        for f, tekst in teksty:
            szer = QFontMetricsF(f).horizontalAdvance(tekst)
            if szer > w * 0.6:
                f.setPixelSize(max(10, int(f.pixelSize() * w * 0.6 / szer)))
                szer = QFontMetricsF(f).horizontalAdvance(tekst)
            szer_bloku = max(szer_bloku, szer)
        wys_nazwy = QFontMetricsF(czcionka_nazwy).height() if z.nazwa else 0
        wys_zegara = QFontMetricsF(czcionka_zegara).height()
        wys_daty = QFontMetricsF(czcionka_daty).height()
        odstep = 18 * jednostka
        wys_bloku = wys_nazwy + (odstep if z.nazwa else 0) + wys_logo + odstep + wys_zegara + wys_daty
        lewo = odbicie((teraz_m - z.start) * PREDKOSC * jednostka * 1000 + z.faza[0] * w, max(0.0, w - szer_bloku))
        gora = odbicie((teraz_m - z.start) * PREDKOSC * 0.77 * jednostka * 1000 + z.faza[1] * h,
                       max(0.0, h - wys_bloku))
        srodek_x = lewo + szer_bloku / 2
        p.setOpacity(jasnosc * min(1.0, (teraz_m - z.start) / 0.8))  # łagodne pojawienie i gaśnięcie
        y = gora
        if z.nazwa:
            p.setFont(czcionka_nazwy)
            p.setPen(QColor("#7f9499"))
            p.drawText(QRectF(lewo, y, szer_bloku, wys_nazwy), Qt.AlignmentFlag.AlignCenter, z.nazwa)
            y += wys_nazwy + odstep
        if z.logo.isValid():
            z.logo.render(p, QRectF(srodek_x - szer_logo / 2, y, szer_logo, wys_logo))
        y += wys_logo + odstep
        p.setFont(czcionka_zegara)
        p.setPen(QColor("#d9e1e3"))
        p.drawText(QRectF(lewo, y, szer_bloku, wys_zegara), Qt.AlignmentFlag.AlignCenter, zegar)
        p.setFont(czcionka_daty)
        p.setPen(QColor("#7f9499"))
        p.drawText(QRectF(lewo, y + wys_zegara, szer_bloku, wys_daty), Qt.AlignmentFlag.AlignCenter, data)
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
        self.faza = (random.random(), random.random())  # każda zasłona zaczyna w innym miejscu
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
            pass
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
