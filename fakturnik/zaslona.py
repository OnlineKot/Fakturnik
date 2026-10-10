"""Zasłona ekranu w stylu klasycznego wygaszacza: czarne tło, a na nim logo gabinetu, nazwa gabinetu,
zegar i data, które wolno jeżdżą po ekranie i odbijają się od krawędzi. Bez napisów-instrukcji.

Sposób odblokowania do wyboru: 5 spacji (domyślnie), PIN (cyfry i Enter) albo 5 spacji, a potem PIN.
Po pięciu błędnych PIN-ach zasłona zgłasza to programowi, który blokuje Windows i siebie.

Spacjami znika tylko po DOKŁADNIE pięciu naciśnięciach i krótkiej pauzie. Sześć i więcej spacji,
przytrzymana spacja albo inny klawisz w serii nic nie dają. Spacje są odbierane przez hak klawiatury
Windows, więc działają zawsze, nawet gdy Windows nie oddał zasłonie fokusu, i nie trafiają do programu
pod zasłoną. Nie czyści schowka i nie wylogowuje:
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

SPACJE = 5
ODSTEP = 1.5         # przerwa między spacjami jednej serii może być aż tak długa (wolne stukanie też działa)
PAUZA = 0.8          # po piątej spacji: tyle ciszy i zasłona znika (szósta spacja w tym czasie psuje serię)
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
    """Odblokowanie dokładnie pięcioma spacjami (bez Qt, do testów).

    Seria to spacje z przerwami krótszymi niż ODSTEP. Dłuższa przerwa zaczyna nową serię, więc
    przypadkowa spacja wcześniej (np. budzenie ekranu) nie przeszkadza. Inny klawisz albo przytrzymana
    spacja kasują serię; kolejna spacja zaczyna od nowa (bez kar i czekania).
    """

    def __init__(self):
        self.serie: list[float] = []

    def nacisniecie(self, spacja: bool, teraz: float, powtorzenie: bool = False) -> None:
        if not spacja or powtorzenie:
            self.serie = []
            return
        if self.serie and teraz - self.serie[-1] >= ODSTEP:
            self.serie = []  # długa przerwa: nowa seria
        self.serie.append(teraz)

    def odblokowac(self, teraz: float) -> bool:
        """Prawda, gdy było dokładnie pięć spacji, a od ostatniej minęła pauza bez kolejnych klawiszy."""
        if len(self.serie) != SPACJE or teraz - self.serie[-1] < PAUZA:
            if self.serie and teraz - self.serie[-1] >= ODSTEP:
                self.serie = []  # niepełna albo za długa seria wygasa
            return False
        return True


class HakKlawiatury:
    """Windows: niskopoziomowy hak klawiatury (WH_KEYBOARD_LL) na czas zasłony.

    Odbiera każdy klawisz niezależnie od tego, które okno ma fokus (Windows często nie pozwala programowi
    w tle przejąć klawiatury), i zatrzymuje go, żeby spacje nie wpisały się do dokumentu pod zasłoną.
    Klawisze wysłane programowo (np. sztuczny Alt przy przenoszeniu okna) przechodzą dalej.
    Ctrl+Alt+Del i Win+L działają zawsze (systemu nie da się zablokować i tak ma być).
    """

    def __init__(self, obsluga):
        self.obsluga = obsluga  # obsluga(vk, powtorzenie)
        self._hak = None
        self._funkcja = None
        self._wcisniete: set[int] = set()

    def wlacz(self) -> bool:
        import sys
        if sys.platform != "win32" or self._hak:
            return bool(self._hak)
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            LRESULT = ctypes.c_ssize_t
            PROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

            class KBDLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                            ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, PROC, wintypes.HINSTANCE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = ctypes.c_void_p
            user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = LRESULT
            user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE
            WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
            LLKHF_INJECTED = 0x10

            def funkcja(kod, wparam, lparam):
                try:
                    if kod == 0:
                        dane = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        if not dane.flags & LLKHF_INJECTED:
                            vk = int(dane.vkCode)
                            if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                                powtorzenie = vk in self._wcisniete
                                self._wcisniete.add(vk)
                                self.obsluga(vk, powtorzenie)
                            elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                                self._wcisniete.discard(vk)
                            return 1  # klawisz nie trafia do innych programów
                except Exception:  # noqa: BLE001 - hak nie może nigdy zatrzymać klawiatury
                    pass
                return user32.CallNextHookEx(None, kod, wparam, lparam)

            self._funkcja = PROC(funkcja)  # referencja musi żyć, dopóki hak jest włączony
            self._user32 = user32
            self._hak = user32.SetWindowsHookExW(13, self._funkcja, kernel32.GetModuleHandleW(None), 0)
        except Exception:  # noqa: BLE001
            self._hak = None
        return bool(self._hak)

    @property
    def wlaczony(self) -> bool:
        return bool(self._hak)

    def wylacz(self) -> None:
        if self._hak:
            try:
                self._user32.UnhookWindowsHookEx(self._hak)
            except Exception:  # noqa: BLE001
                pass
        self._hak = None
        self._wcisniete.clear()


# kody klawiszy Windows: spacja i same klawisze modyfikujące (nie psują serii)
VK_SPACJA = 0x20
VK_MODYFIKATORY = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}
VK_QT = {0x0D: Qt.Key.Key_Return, 0x08: Qt.Key.Key_Backspace, 0x1B: Qt.Key.Key_Escape, VK_SPACJA: Qt.Key.Key_Space}
VK_QT.update({0x30 + i: Qt.Key(Qt.Key.Key_0 + i) for i in range(10)})   # cyfry nad literami
VK_QT.update({0x60 + i: Qt.Key(Qt.Key.Key_0 + i) for i in range(10)})   # klawiatura numeryczna
PROBY_PIN = 5
CZAS_PIN = 20.0      # tyle sekund bez klawisza i wpisywany PIN się kasuje (w trybie spacje+PIN: znów spacje)
MAX_PIN = 8


def cyfra(klawisz) -> str | None:
    k = int(klawisz)
    return str(k - int(Qt.Key.Key_0)) if int(Qt.Key.Key_0) <= k <= int(Qt.Key.Key_9) else None


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


def na_pierwszy_plan(okno: QWidget) -> None:
    """Windows nie pozwala programowi w tle zabrać klawiatury innemu oknu (wtedy spacje trafiałyby do
    tamtego programu). Zasłona jest uruchamiana przez sam program po bezczynności, więc korzysta ze
    standardowego sposobu: na chwilę „naciska” Alt, co Windows traktuje jak działanie użytkownika,
    a potem przenosi okno zasłony na pierwszy plan."""
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = int(okno.winId())
        VK_MENU, KEYEVENTF_KEYUP = 0x12, 0x0002
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    except Exception:  # noqa: BLE001
        pass


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
        if z.tryb != "spacje":
            wys_bloku += 34 * jednostka  # miejsce na kropki PIN-u (stała wysokość: blok nie skacze)
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
        if z.pokaz_kropki():
            # wpisywany PIN: kropki pod datą (bez napisów); czerwone przez chwilę po błędnym PIN-ie
            r = 5 * jednostka
            ile = max(4, len(z.pin))
            odstep_k = 22 * jednostka
            x0 = srodek_x - (ile - 1) * odstep_k / 2
            yk = y + wys_zegara + wys_daty + 24 * jednostka
            kolor = QColor("#c0504d") if time.monotonic() < z.blad_do else QColor("#d9e1e3")
            for i in range(ile):
                p.setPen(kolor)
                p.setBrush(kolor if i < len(z.pin) else Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(x0 + i * odstep_k - r, yk - r, 2 * r, 2 * r))
        p.end()

    def keyPressEvent(self, e):
        if not self.zaslona.hak.wlaczony:
            self.zaslona.klawisz(e.key(), e.isAutoRepeat())

    def mouseMoveEvent(self, _):
        self.zaslona.obudz()

    def mousePressEvent(self, _):
        """Kliknięcie zawsze oddaje klawiaturę zasłonie (Windows na to pozwala), potem działają spacje."""
        self.zaslona.obudz()
        self.zaslona._przejmij_klawiature()

    def closeEvent(self, e):
        if not self.zaslona.zamykanie:
            e.ignore()  # zasłonę zamyka tylko pięć spacji (Alt+F4 nie działa)
            return
        super().closeEvent(e)


class Zaslona(QWidget):
    """Zarządza zasłonami wszystkich monitorów."""
    zamknieta = Signal()
    za_duzo_prob = Signal()

    def __init__(self, nazwa: str = "", gaszenie_min: float = 10, tryb: str = "spacje", sprawdz_pin=None):
        super().__init__()
        self.tryb = tryb if (tryb in ("pin", "spacje_pin") and sprawdz_pin) else "spacje"
        self.sprawdz_pin = sprawdz_pin
        self.pin = ""
        self.faza_pin = self.tryb == "pin"
        self.ostatni_pin = 0.0
        self.bledy_pin = 0
        self.blad_do = 0.0
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
        self.hak = HakKlawiatury(self._klawisz_windows)
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
        self.hak.wlacz()
        for e in self.ekrany:
            e.setMouseTracking(True)
            e.showFullScreen()
            e.raise_()
            self._przenikanie(e, 1.0, POJAWIANIE_MS)
        if self.ekrany:
            self._przejmij_klawiature()
            QTimer.singleShot(300, self, lambda: self._przejmij_klawiature(alt=False))  # okno dopiero się pojawia
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

    def pokaz_kropki(self) -> bool:
        return self.faza_pin and (self.tryb == "spacje_pin" or bool(self.pin) or time.monotonic() < self.blad_do)

    def _spacje_gotowe(self, teraz: float) -> bool:
        """Pięć spacji: w trybie spacji zasłona znika, w trybie spacje+PIN zaczyna się wpisywanie PIN-u."""
        if self.zamykanie or self.tryb == "pin" or self.faza_pin or not self.licznik.odblokowac(teraz):
            return False
        if self.tryb == "spacje":
            self.zamknij()
            return True
        self.licznik = LicznikSpacji()
        self.faza_pin, self.pin, self.ostatni_pin = True, "", teraz
        return False

    def _pilnuj_pinu(self, teraz: float) -> None:
        if self.faza_pin and teraz - self.ostatni_pin > CZAS_PIN:
            self.pin = ""
            if self.tryb == "spacje_pin":
                self.faza_pin = False  # nikt nie wpisał PIN-u: znów potrzebne spacje

    def _klatka(self):
        teraz = time.monotonic()
        self._pilnuj_pinu(teraz)
        if self._spacje_gotowe(teraz):
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

    def _przejmij_klawiature(self, alt: bool = True):
        """alt=False przy cyklicznym pilnowaniu: bez sztucznych naciśnięć (nie budziłyby systemu co sekundę)."""
        if not self.ekrany or self.zamykanie:
            return
        e = self.ekrany[0]
        if alt:
            na_pierwszy_plan(e)
        e.activateWindow()
        e.setFocus()
        e.grabKeyboard()

    def _na_wierzch(self):
        """Inne okno (np. okno hasła) nie przykryje zasłony ani nie przejmie klawiatury."""
        if self.zamykanie:
            return
        if not self._animacja.isActive():
            self._pilnuj_pinu(time.monotonic())
            if self._spacje_gotowe(time.monotonic()):
                return  # pięć spacji w czerni też działa
        for e in self.ekrany:
            e.raise_()
        if self.ekrany and not self.ekrany[0].isActiveWindow():
            self._przejmij_klawiature(alt=False)

    def _klawisz_windows(self, vk: int, powtorzenie: bool):
        if vk in VK_MODYFIKATORY:
            self.obudz()
            return
        self.klawisz(VK_QT.get(vk, Qt.Key.Key_unknown), powtorzenie)

    def klawisz(self, klawisz: int, powtorzenie: bool = False):
        if self.zamykanie:
            return
        ciemno = self._monitor_wylaczony or jasnosc_po_czasie(time.monotonic() - self.aktywnosc, self.gaszenie_s) < 1
        self.obudz()
        if ciemno:
            return  # klawisz tylko budzi zgaszony ekran i nie liczy się do serii
        if klawisz in (Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Meta, Qt.Key.Key_AltGr):
            return  # same klawisze modyfikujące (także sztuczny Alt przy przejmowaniu klawiatury) nie psują serii
        if self.faza_pin:
            self._klawisz_pin(klawisz, powtorzenie)
            return
        spacja = klawisz == Qt.Key.Key_Space
        if spacja and not powtorzenie:
            self.ostatnia_spacja = time.monotonic()
        self.licznik.nacisniecie(spacja, time.monotonic(), powtorzenie)

    def _klawisz_pin(self, klawisz, powtorzenie: bool):
        teraz = time.monotonic()
        self.ostatni_pin = teraz
        if powtorzenie:
            return
        if (c := cyfra(klawisz)) is not None:
            if len(self.pin) < MAX_PIN:
                self.pin += c
        elif klawisz == Qt.Key.Key_Backspace:
            self.pin = self.pin[:-1]
        elif klawisz in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.pin:
                wpisany, self.pin = self.pin, ""
                # sprawdzenie poza hakiem klawiatury (Windows wyłącza hak, który odpowiada zbyt wolno)
                QTimer.singleShot(0, self, lambda w=wpisany: self._sprawdz_pin(w))
        else:
            self.pin = ""  # Esc albo inny klawisz kasuje wpisywanie
        for e in self.ekrany:
            e.update()

    def _sprawdz_pin(self, pin: str):
        if self.zamykanie:
            return
        try:
            ok = bool(self.sprawdz_pin and self.sprawdz_pin(pin))
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.zamknij()
            return
        self.bledy_pin += 1
        self.blad_do = time.monotonic() + 0.8
        self.obudz()
        if self.bledy_pin >= PROBY_PIN:
            self.za_duzo_prob.emit()

    def zamknij(self, natychmiast: bool = False):
        if self.zamykanie:
            return
        self.zamykanie = True
        self.hak.wylacz()
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
        self.hak.wylacz()
        if not self.ekrany:
            return
        self._animacja.stop()
        for e in self.ekrany:
            e.close()
        self.ekrany = []
        self.zamknieta.emit()
        self.deleteLater()
