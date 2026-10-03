"""Okno główne programu Fakturnik."""

import base64
from html import escape as html_escape
import sys
import time
from datetime import date
from pathlib import Path

from PySide6.QtCore import (
    QBuffer, QByteArray, QDate, QEvent, QEventLoop, QIODevice, QObject, QPoint, QRect, QSize, QStandardPaths, Qt, QThread,
    QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QImage, QKeySequence, QPixmap, QShortcut,
)
from PySide6.QtPrintSupport import QPrintDialog
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QFileDialog, QFormLayout, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLayout, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QStackedWidget, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import aktualizacje, druk
from .baza import KATEGORIE_PLIKOW, Baza, Dokument, NowszaBaza, Plik, PlikZajety, Pozycja, podsumuj
from .ikony import ikona, pixmapa
from .ochrona import BlokadaPliku, Dziennik, katalog_kopii, kopia_automatyczna
from .system import (
    JednaKopia, autostart_wlaczony, integracja_dostepna, menu_kontekstowe_wlaczone, polecenie_z_argumentow,
    ustaw_autostart, ustaw_menu_kontekstowe, utworz_skrot_na_pulpicie,
)
from .szyfrowanie import BledneHaslo
from .walidacja import formatuj_konto, konto_poprawne, nip_poprawny, opis_identyfikatora
from .wersja import WERSJA
from .widzety import DwuliniowyDelegate, PigulkaDelegate, PodgladKartki, PodgladStron, Powiadomienie, WykresMiesiecy

STRONA_NOWY, STRONA_HISTORIA, STRONA_PRZYCHODY, STRONA_PLIKI, STRONA_USTAWIENIA = range(5)
MIN_DLUGOSC_HASLA = 8
ZASOBY = Path(__file__).parent / "zasoby"

# ---------------------------------------------------------------- wygląd

from .motyw import (  # noqa: E402
    AKCENT, AKCENT_CIEMNY, AKCENT_TLO, CZERWONY, LINIA, MENU, MENU_AKTYWNY, MENU_TEKST, TEKST, TEKST_2,
    TEKST_3, TLO, ZIELONY,
)

STYL = f"""
* {{ font-family: "Inter"; font-size: 13px; color: {TEKST}; }}
QMainWindow, QWidget#tresc, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {TLO}; }}
QDialog {{ background: {TLO}; }}

QFrame#menu {{ background: {MENU}; }}
QFrame#menu QLabel {{ color: white; background: transparent; }}
QFrame#menu QPushButton {{
    background: transparent; border: none; border-radius: 8px; text-align: left;
    padding: 9px 12px; margin: 1px 12px; font-weight: 500; color: {MENU_TEKST};
}}
QFrame#menu QPushButton:hover {{ background: #163a42; color: white; }}
QFrame#menu QPushButton:checked {{ background: {MENU_AKTYWNY}; color: white; font-weight: 600; }}
QLabel#nazwa_programu {{ font-size: 15px; font-weight: 600; color: white; }}
QLabel#gabinet {{ font-size: 11px; color: {MENU_TEKST}; }}
QFrame#menu_linia {{ background: #1f454d; max-height: 1px; border: none; margin: 0 20px; }}

QLabel#tytul {{ font-size: 24px; font-weight: 650; letter-spacing: -0.5px; }}
QLabel#podtytul {{ color: {TEKST_2}; }}
QLabel#sekcja {{ font-size: 14px; font-weight: 600; padding: 0 2px; }}
QLabel#drobny {{ font-size: 12px; color: {TEKST_2}; }}
QLabel#etykieta {{ font-size: 12px; font-weight: 500; color: {TEKST_2}; }}
QLabel#kpi_etykieta {{ font-size: 12px; font-weight: 500; color: {TEKST_2}; }}
QLabel#kpi_wartosc {{ font-size: 26px; font-weight: 650; letter-spacing: -0.6px; }}
QLabel#kpi_zmiana {{ font-size: 12px; font-weight: 500; color: {TEKST_3}; }}
QFrame#karta {{ background: white; border: 1px solid {LINIA}; border-radius: 12px; }}
QFrame#karta QLabel {{ background: transparent; }}
QFrame#papier {{ background: transparent; }}
QFrame#separator {{ background: {LINIA}; max-height: 1px; border: none; }}
QFrame#stopka {{ background: white; border: none; border-top: 1px solid {LINIA}; }}
QLabel#krok_numer {{ background: #e9ecee; color: {TEKST_2}; border-radius: 12px; font-size: 12px; font-weight: 600; }}
QLabel#krok_numer[stan="aktywny"] {{ background: {AKCENT}; color: white; }}
QLabel#krok_numer[stan="zrobiony"] {{ background: {AKCENT_TLO}; color: {AKCENT}; }}
QLabel#krok_tekst {{ color: {TEKST_3}; font-weight: 500; }}
QLabel#krok_tekst[stan="aktywny"] {{ color: {TEKST}; font-weight: 600; }}
QLabel#krok_tekst[stan="zrobiony"] {{ color: {TEKST_2}; }}

QLineEdit, QPlainTextEdit, QComboBox, QDateEdit {{
    background: white; border: 1px solid #d5dade; border-radius: 8px; padding: 7px 10px;
    selection-background-color: #cfe3e7; selection-color: {TEKST};
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {{ border-color: #bcc4ca; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 1px solid {AKCENT}; }}
QLineEdit, QComboBox, QDateEdit, QSpinBox {{ min-height: 20px; }}
QSpinBox {{ background: white; border: 1px solid #d5dade; border-radius: 8px; padding: 6px 8px; }}
QLineEdit#numer {{ font-size: 15px; font-weight: 600; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {LINIA}; padding: 4px;
    selection-background-color: {AKCENT_TLO}; selection-color: {TEKST}; outline: none; }}

QPushButton {{
    background: white; border: 1px solid #d5dade; border-radius: 8px; padding: 7px 13px; font-weight: 500;
}}
QPushButton:hover {{ background: #f6f8f9; border-color: #bcc4ca; }}
QPushButton:pressed {{ background: #eceff1; }}
QPushButton:disabled {{ color: #aab2b9; background: #fafbfb; }}
QPushButton#glowny {{ background: {AKCENT}; border: 1px solid {AKCENT}; color: white; font-weight: 600; padding: 9px 18px; }}
QPushButton#glowny:hover {{ background: {AKCENT_CIEMNY}; border-color: {AKCENT_CIEMNY}; }}
QPushButton#glowny:pressed {{ background: #11444f; }}
QPushButton#glowny:disabled {{ background: #a7c3c9; border-color: #a7c3c9; }}
QPushButton#plaski {{ background: transparent; border: none; color: {AKCENT}; padding: 5px 8px; font-weight: 600; }}
QPushButton#plaski:hover {{ background: {AKCENT_TLO}; }}
QPushButton#chip {{ background: #f1f4f5; border: 1px solid transparent; border-radius: 8px; padding: 6px 11px; font-weight: 500; }}
QPushButton#chip:hover {{ background: {AKCENT_TLO}; border-color: #c5dde1; color: {AKCENT}; }}
QPushButton#pacjent {{ background: white; border: 1px solid {LINIA}; border-radius: 14px;
    padding: 4px 12px; font-weight: 500; color: #36414a; }}
QPushButton#pacjent:hover {{ border-color: {AKCENT}; color: {AKCENT}; }}
QPushButton#niebezpieczny {{ color: {CZERWONY}; }}
QPushButton#niebezpieczny:disabled {{ color: #e2b4ba; }}
QPushButton#szybki {{ background: white; border: 1px solid {LINIA}; border-radius: 12px; padding: 14px 16px;
    text-align: left; font-weight: 600; }}
QPushButton#szybki:hover {{ border-color: {AKCENT}; background: #fbfdfd; }}
QFrame#przelacznik {{ background: #e9ecee; border-radius: 10px; }}
QPushButton#segment {{ background: transparent; border: none; border-radius: 8px; padding: 7px 20px;
    font-weight: 500; color: {TEKST_2}; }}
QPushButton#segment:checked {{ background: white; color: {TEKST}; font-weight: 600; border: 1px solid #d9dee1; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid #c3cbd1; background: white; }}
QCheckBox::indicator:checked {{ background: {AKCENT}; border-color: {AKCENT}; image: url("{(ZASOBY / "zaznaczone.svg").as_posix()}"); }}

QTableWidget {{ background: white; border: none; gridline-color: transparent;
    selection-background-color: {AKCENT_TLO}; selection-color: {TEKST}; outline: none; }}
QTableWidget::item {{ padding: 0 10px; border-bottom: 1px solid #eef0f2; }}
QTableWidget::item:hover {{ background: #f7f9fa; }}
QTableWidget::item:selected {{ background: {AKCENT_TLO}; }}
QHeaderView::section {{ background: white; border: none; border-bottom: 1px solid {LINIA};
    padding: 9px 10px; font-size: 12px; font-weight: 500; color: {TEKST_3}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cdd3d8; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #b4bcc3; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QFrame#pasek_aktualizacji {{ background: {AKCENT_TLO}; border: none; border-bottom: 1px solid #cfe0e3; }}
QFrame#toast {{ background: #141a1f; border-radius: 10px; }}
QFrame#toast QLabel {{ color: white; background: transparent; font-weight: 500; }}
QStatusBar {{ background: {TLO}; color: {TEKST_2}; border: none; }}
QToolTip {{ background: #141a1f; color: white; border: none; padding: 6px 8px; border-radius: 6px; }}
"""


def cien(w: QWidget, rozmycie: int = 24, alfa: int = 16, przesuniecie: int = 2) -> QWidget:
    """Delikatny cień pod kartą (głębia bez krzykliwych efektów)."""
    efekt = QGraphicsDropShadowEffect(w)
    efekt.setBlurRadius(rozmycie)
    efekt.setOffset(0, przesuniecie)
    efekt.setColor(QColor(16, 32, 40, alfa))
    w.setGraphicsEffect(efekt)
    return w


def czcionka_cyfr(rozmiar: int = 13, waga: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Inter z cyframi o stałej szerokości, żeby kwoty w kolumnach równo się układały."""
    f = QFont("Inter")
    f.setPixelSize(rozmiar)
    f.setWeight(waga)
    try:
        f.setFeature(QFont.Tag("tnum"), 1)
    except (AttributeError, TypeError):
        pass
    return f


def zaladuj_czcionki() -> None:
    for plik in sorted((ZASOBY / "czcionki").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(plik))


def sciezka_danych() -> Path:
    katalog = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(katalog) / "fakturnik.db"


def liczba(tekst: str) -> float:
    try:
        return float(tekst.replace(" ", "").replace("\xa0", "").replace(",", "."))
    except ValueError:
        return 0.0


class UkladPlynny(QLayout):
    """Układa elementy w wierszach i zawija je, gdy brakuje miejsca (przyciski usług)."""

    def __init__(self, odstep: int = 6):
        super().__init__()
        self.elementy: list = []
        self.odstep = odstep
        self._wysokosc = 0  # wysokość przy ostatniej szerokości; zgłaszana rodzicowi, żeby niczego nie ściskał

    def addItem(self, element):
        self.elementy.append(element)

    def count(self):
        return len(self.elementy)

    def itemAt(self, i):
        return self.elementy[i] if 0 <= i < len(self.elementy) else None

    def takeAt(self, i):
        return self.elementy.pop(i) if 0 <= i < len(self.elementy) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, szerokosc):
        return self._uloz(QRect(0, 0, szerokosc, 0), tylko_licz=True)

    def setGeometry(self, prostokat):
        super().setGeometry(prostokat)
        wysokosc = self._uloz(prostokat, tylko_licz=False)
        if wysokosc != self._wysokosc:
            self._wysokosc = wysokosc
            QTimer.singleShot(0, self.invalidate)  # liczba wierszy się zmieniła: przelicz układ rodzica

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        rozmiar = QSize()
        for e in self.elementy:
            rozmiar = rozmiar.expandedTo(e.minimumSize())
        m = self.contentsMargins()
        rozmiar += QSize(m.left() + m.right(), m.top() + m.bottom())
        return QSize(rozmiar.width(), max(rozmiar.height(), self._wysokosc))

    def _uloz(self, prostokat, tylko_licz):
        m = self.contentsMargins()
        x, y = prostokat.x() + m.left(), prostokat.y() + m.top()
        prawa = prostokat.right() - m.right()
        wysokosc_wiersza = 0
        for e in self.elementy:
            r = e.sizeHint()
            if x + r.width() > prawa and wysokosc_wiersza:
                x = prostokat.x() + m.left()
                y += wysokosc_wiersza + self.odstep
                wysokosc_wiersza = 0
            if not tylko_licz:
                e.setGeometry(QRect(QPoint(x, y), r))
            x += r.width() + self.odstep
            wysokosc_wiersza = max(wysokosc_wiersza, r.height())
        return y + wysokosc_wiersza - prostokat.y() + m.bottom()


def maskuj_id(identyfikator: str) -> str:
    """PESEL widoczny tylko w końcówce (minimalizacja danych, RODO); NIP firmy pokazujemy w całości."""
    cyfry = "".join(c for c in identyfikator if c.isdigit())
    return "•••••••" + cyfry[-4:] if len(cyfry) == 11 else identyfikator


def wyczysc_uklad(uklad) -> None:
    """Usuwa od razu wszystkie elementy układu (deleteLater zostawiałby je widoczne do końca zdarzenia)."""
    while uklad.count():
        w = uklad.takeAt(0).widget()
        if w:
            w.hide()
            w.setParent(None)
            w.deleteLater()


def przycisk(tekst: str, nazwa_ikony: str | None = None, styl: str | None = None, akcja=None,
             kolor_ikony: str = TEKST_2) -> QPushButton:
    b = QPushButton(tekst)
    if styl:
        b.setObjectName(styl)
    if nazwa_ikony:
        kolor = {"glowny": "white", "plaski": AKCENT, "niebezpieczny": CZERWONY}.get(styl, kolor_ikony)
        b.setIcon(ikona(nazwa_ikony, kolor))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if akcja:
        b.clicked.connect(akcja)
    return b


def karta(z_cieniem: bool = True) -> tuple[QFrame, QVBoxLayout]:
    k = QFrame(objectName="karta")
    if z_cieniem:
        cien(k)
    u = QVBoxLayout(k)
    u.setContentsMargins(18, 16, 18, 16)
    u.setSpacing(10)
    return k, u


def sekcja(tekst: str) -> QLabel:
    return QLabel(tekst, objectName="sekcja")


def separator() -> QFrame:
    return QFrame(objectName="separator", frameShape=QFrame.Shape.HLine)


def pole(etykieta: str, widzet: QWidget) -> QVBoxLayout:
    u = QVBoxLayout()
    u.setAlignment(Qt.AlignmentFlag.AlignTop)
    u.setSpacing(4)
    u.addWidget(QLabel(etykieta, objectName="etykieta"))
    u.addWidget(widzet)
    return u


def naglowek_strony(tytul: str, podtytul: str = "") -> QVBoxLayout:
    u = QVBoxLayout()
    u.setSpacing(2)
    u.addWidget(QLabel(tytul, objectName="tytul"))
    if podtytul:
        u.addWidget(QLabel(podtytul, objectName="podtytul"))
    return u


class Watek(QThread):
    """Uruchamia funkcję w tle (np. sprawdzanie aktualizacji), żeby okno się nie zawieszało."""
    gotowe = Signal(object)
    blad = Signal(str)
    postep = Signal(int)

    def __init__(self, funkcja, *argumenty, z_postepem=False):
        super().__init__()
        self.funkcja, self.argumenty, self.z_postepem = funkcja, argumenty, z_postepem

    def run(self):
        try:
            if self.z_postepem:
                wynik = self.funkcja(*self.argumenty, self.postep.emit)
            else:
                wynik = self.funkcja(*self.argumenty)
            self.gotowe.emit(wynik)
        except Exception as e:  # noqa: BLE001 - każdy błąd ma trafić do okna, a nie zabić wątek
            self.blad.emit(str(e))


# ---------------------------------------------------------------- hasło

class OknoHasla(QDialog):
    """Pyta o hasło; `sprawdz` zwraca True, gdy hasło jest poprawne."""

    def __init__(self, sprawdz, tytul="Fakturnik", parent=None, dziennik: Dziennik | None = None,
                 cel="logowanie", opis="Dane są chronione hasłem."):
        super().__init__(parent)
        self.sprawdz, self.dziennik, self.cel = sprawdz, dziennik, cel
        self.proby = 0
        self.setWindowTitle(tytul)
        self.setFixedWidth(400)
        u = QVBoxLayout(self)
        u.setContentsMargins(32, 30, 32, 24)
        u.setSpacing(10)
        znak = QLabel()
        znak.setPixmap(QPixmap(str(ZASOBY / "ikona.png")).scaled(
            56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        u.addWidget(znak, alignment=Qt.AlignmentFlag.AlignHCenter)
        u.addSpacing(4)
        naglowek = QLabel(tytul, alignment=Qt.AlignmentFlag.AlignHCenter)
        naglowek.setStyleSheet("font-size: 18px; font-weight: 650; letter-spacing: -0.3px;")
        u.addWidget(naglowek)
        if tytul == "Fakturnik":
            u.addWidget(QLabel("by TeodorTeo.com", objectName="drobny", alignment=Qt.AlignmentFlag.AlignHCenter))
        u.addWidget(QLabel(opis, objectName="podtytul", alignment=Qt.AlignmentFlag.AlignHCenter))
        u.addSpacing(6)
        self.pole = QLineEdit(echoMode=QLineEdit.EchoMode.Password, placeholderText="Hasło")
        self.pole.returnPressed.connect(self.sprobuj)
        u.addWidget(self.pole)
        self.blad = QLabel(styleSheet=f"color: {CZERWONY}; font-size: 12px;")
        u.addWidget(self.blad)
        rzad = QHBoxLayout()
        rzad.addStretch()
        rzad.addWidget(przycisk("Anuluj", akcja=self.reject))
        self.ok = przycisk("Otwórz", styl="glowny", akcja=self.sprobuj)
        self.ok.setDefault(True)
        rzad.addWidget(self.ok)
        u.addLayout(rzad)

    # wspólne dla wszystkich okien hasła: zamknięcie i ponowne otwarcie okna nie zeruje licznika prób
    _nieudane = 0
    _blokada_do = 0.0

    def sprobuj(self):
        pozostalo = OknoHasla._blokada_do - time.monotonic()
        if pozostalo > 0:
            self.blad.setText(f"Za dużo błędnych prób. Spróbuj ponownie za {int(pozostalo) + 1} s.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = self.sprawdz(self.pole.text())
        finally:
            QApplication.restoreOverrideCursor()
        if self.dziennik:
            self.dziennik.zapisz(f"{self.cel}: {'udane' if ok else 'NIEUDANE (złe hasło)'}")
        if ok:
            OknoHasla._nieudane = 0
            self.accept()
            return
        OknoHasla._nieudane += 1
        self.pole.clear()
        # po kolejnych błędach coraz dłuższa przerwa (do 5 min), żeby utrudnić zgadywanie
        przerwa = min(2 ** OknoHasla._nieudane, 300) if OknoHasla._nieudane >= 3 else 0
        OknoHasla._blokada_do = time.monotonic() + przerwa
        self.blad.setText("Nieprawidłowe hasło." + (f" Spróbuj ponownie za {przerwa} s." if przerwa else ""))
        if przerwa:
            self.setEnabled(False)
            QTimer.singleShot(przerwa * 1000, lambda: (self.setEnabled(True), self.pole.setFocus()))


class OknoNowegoHasla(QDialog):
    def __init__(self, parent=None, tytul: str = "Ustaw hasło",
                 opis: str = "Hasło szyfruje wszystkie dane (AES-256, klucz z hasła przez PBKDF2-SHA256)."):
        super().__init__(parent)
        self.setWindowTitle("Hasło")
        self.setFixedWidth(420)
        u = QVBoxLayout(self)
        u.setContentsMargins(24, 22, 24, 20)
        u.setSpacing(10)
        t = QLabel(tytul)
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(t)
        info = QLabel(f"{opis} Minimum {MIN_DLUGOSC_HASLA} znaków. Zapomnianego hasła nie da się odzyskać.",
                      objectName="podtytul", wordWrap=True)
        u.addWidget(info)
        self.haslo = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.powtorz = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        u.addLayout(pole("Nowe hasło", self.haslo))
        u.addLayout(pole("Powtórz hasło", self.powtorz))
        self.blad = QLabel(styleSheet=f"color: {CZERWONY}; font-size: 12px;")
        u.addWidget(self.blad)
        rzad = QHBoxLayout()
        rzad.addStretch()
        rzad.addWidget(przycisk("Anuluj", akcja=self.reject))
        rzad.addWidget(przycisk("Zapisz hasło", styl="glowny", akcja=self.zatwierdz))
        u.addLayout(rzad)

    def zatwierdz(self):
        if len(self.haslo.text()) < MIN_DLUGOSC_HASLA:
            self.blad.setText(f"Hasło musi mieć co najmniej {MIN_DLUGOSC_HASLA} znaków.")
        elif self.haslo.text() != self.powtorz.text():
            self.blad.setText("Hasła nie są takie same.")
        else:
            self.accept()


class StraznikBezczynnosci(QObject):
    """Restartuje licznik czasu przy każdym ruchu myszy lub klawiszu."""

    def __init__(self, timer: QTimer):
        super().__init__()
        self.timer = timer

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress):
            self.timer.start()
        return False


# ---------------------------------------------------------------- strony

class Strona(QWidget):
    """Strona z przewijaną treścią i stałymi marginesami."""

    def __init__(self, okno: "OknoGlowne", przewijana: bool = False):
        super().__init__()
        self.okno = okno
        zewn = QVBoxLayout(self)
        zewn.setContentsMargins(0, 0, 0, 0)
        tresc = QWidget(objectName="tresc")
        self.uklad = QVBoxLayout(tresc)
        self.uklad.setContentsMargins(32, 26, 32, 22)
        self.uklad.setSpacing(8)
        if przewijana:
            obszar = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
            obszar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            obszar.setWidget(tresc)
            zewn.addWidget(obszar)
        else:
            zewn.addWidget(tresc)
        self._zewn = zewn

    def stopka(self) -> QHBoxLayout:
        """Pasek na dole strony, zawsze widoczny (poza przewijaną treścią)."""
        pasek = QFrame(objectName="stopka")
        uklad = QHBoxLayout(pasek)
        uklad.setContentsMargins(32, 12, 32, 12)
        self._zewn.addWidget(pasek)
        return uklad

    def odswiez(self):
        pass


MIESIACE_DOP = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
                "października", "listopada", "grudnia"]
MIESIACE_MIEJSC = ["styczniu", "lutym", "marcu", "kwietniu", "maju", "czerwcu", "lipcu", "sierpniu", "wrześniu",
                   "październiku", "listopadzie", "grudniu"]
MIESIACE_KROTKO = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]
DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]


def poprzedni_miesiac(rok: int, mies: int, ile: int = 1) -> tuple[int, int]:
    indeks = rok * 12 + (mies - 1) - ile
    return indeks // 12, indeks % 12 + 1


def kafelek(etykieta: str) -> tuple[QFrame, QLabel, QLabel]:
    k, ku = karta()
    ku.setContentsMargins(18, 16, 18, 16)
    ku.setSpacing(4)
    e = QLabel(etykieta, objectName="kpi_etykieta")
    ku.addWidget(e)
    wartosc = QLabel("—", objectName="kpi_wartosc")
    wartosc.setFont(czcionka_cyfr(26, QFont.Weight.DemiBold))
    ku.addWidget(wartosc)
    zmiana = QLabel(objectName="kpi_zmiana")
    ku.addWidget(zmiana)
    return k, wartosc, zmiana


class StronaPulpit(Strona):
    """Przychody: liczby, wykres i ostatnie dokumenty. Domyślnie zasłonięte, żeby pacjent przy biurku
    nie zobaczył zarobków; kwoty pokazują się po kliknięciu (i haśle, jeśli jest ustawione)."""

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, przewijana=True)
        self.uklad.setSpacing(16)
        gora = QHBoxLayout()
        nag = QVBoxLayout()
        nag.setSpacing(2)
        self.powitanie = QLabel("Przychody", objectName="tytul")
        self.data = QLabel(objectName="podtytul")
        nag.addWidget(self.powitanie)
        nag.addWidget(self.data)
        gora.addLayout(nag)
        gora.addStretch()
        self.btn_ukryj = przycisk("Ukryj", "klodka", akcja=self.zaslon)
        gora.addWidget(self.btn_ukryj, alignment=Qt.AlignmentFlag.AlignBottom)
        self.uklad.addLayout(gora)

        # zasłona: widoczna, dopóki ktoś świadomie nie odsłoni kwot
        self.zaslona, zu = karta()
        zu.setContentsMargins(40, 56, 40, 56)
        zu.setSpacing(10)
        znak = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter)
        znak.setPixmap(pixmapa("podglad", TEKST_3, 34))
        zu.addWidget(znak)
        t = QLabel("Przychody są ukryte", alignment=Qt.AlignmentFlag.AlignHCenter)
        t.setStyleSheet("font-size: 17px; font-weight: 600;")
        zu.addWidget(t)
        zu.addWidget(QLabel("Kwoty pokazują się dopiero po kliknięciu, żeby pacjent przy biurku ich nie zobaczył.\n"
                            "Po wyjściu z tej zakładki znów się chowają.",
                            objectName="podtytul", alignment=Qt.AlignmentFlag.AlignHCenter))
        zu.addSpacing(8)
        zu.addWidget(przycisk("Pokaż przychody", "podglad", "glowny", self.odslon), alignment=Qt.AlignmentFlag.AlignHCenter)
        self.uklad.addWidget(self.zaslona)

        self.zawartosc = QWidget()
        u = QVBoxLayout(self.zawartosc)
        u.setContentsMargins(0, 0, 0, 0)
        u.setSpacing(16)
        self.uklad.addWidget(self.zawartosc, 1)
        self.uklad.addStretch(0)  # luz pod zasłoną, żeby nie rozciągała nagłówka
        self._indeks_luzu = self.uklad.count() - 1

        # --- liczby
        kafle = QHBoxLayout()
        kafle.setSpacing(14)
        k1, self.k_przychod, self.k_przychod_zm = kafelek("Przychód w tym miesiącu")
        k2, self.k_liczba, self.k_liczba_zm = kafelek("Wystawione dokumenty")
        k3, self.k_srednia, self.k_srednia_zm = kafelek("Średnio na dokument")
        k4, self.k_rok, self.k_rok_zm = kafelek("Przychód od początku roku")
        self.k_przychod_et = k1.findChild(QLabel, "kpi_etykieta")
        for k in (k1, k2, k3, k4):
            kafle.addWidget(k, 1)
        u.addLayout(kafle)

        # --- wykres i ostatnie dokumenty
        rzad = QHBoxLayout()
        rzad.setSpacing(14)
        k, ku = karta()
        ku.setContentsMargins(20, 18, 20, 14)
        tyt = QHBoxLayout()
        tyt.addWidget(QLabel("Przychód w ostatnich 12 miesiącach", objectName="sekcja"))
        tyt.addStretch()
        self.suma_12 = QLabel(objectName="drobny")
        tyt.addWidget(self.suma_12)
        ku.addLayout(tyt)
        self.wykres = WykresMiesiecy(druk.zl)
        ku.addWidget(self.wykres, 1)
        rzad.addWidget(k, 3)

        k, ku = karta()
        ku.setContentsMargins(0, 18, 0, 10)
        tyt = QHBoxLayout()
        tyt.setContentsMargins(20, 0, 12, 0)
        tyt.addWidget(QLabel("Ostatnie dokumenty", objectName="sekcja"))
        tyt.addStretch()
        tyt.addWidget(przycisk("Wszystkie", styl="plaski", akcja=lambda: self.okno.przejdz(STRONA_HISTORIA)))
        ku.addLayout(tyt)
        self.ostatnie = QTableWidget(0, 3)
        self.ostatnie.horizontalHeader().setVisible(False)
        self.ostatnie.verticalHeader().setVisible(False)
        self.ostatnie.verticalHeader().setDefaultSectionSize(52)
        self.ostatnie.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ostatnie.setColumnWidth(1, 92)
        self.ostatnie.setColumnWidth(2, 110)
        self.ostatnie.setItemDelegateForColumn(0, DwuliniowyDelegate(self.ostatnie))
        self.ostatnie.setItemDelegateForColumn(1, PigulkaDelegate(self.ostatnie))
        self.ostatnie.setShowGrid(False)
        self.ostatnie.setWordWrap(False)
        self.ostatnie.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ostatnie.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ostatnie.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ostatnie.cellDoubleClicked.connect(self._pokaz)
        ku.addWidget(self.ostatnie, 1)
        self.pusto = QLabel("Nie ma jeszcze dokumentów.\nWystaw pierwszy rachunek przyciskiem powyżej.",
                            objectName="drobny", alignment=Qt.AlignmentFlag.AlignCenter)
        ku.addWidget(self.pusto, 1)
        rzad.addWidget(k, 2)
        u.addLayout(rzad, 1)
        self._docs: list[Dokument] = []

    def _nowy(self, rodzaj: str):
        self.okno.przejdz(STRONA_NOWY)
        self.okno.strona_nowy.ustaw_rodzaj(rodzaj)
        self.okno.strona_nowy.nabywca.setFocus()

    def _pokaz(self, wiersz: int, _kol: int):
        if 0 <= wiersz < len(self._docs):
            self.okno.podglad(self._docs[wiersz], duplikat=True)

    def odswiez(self):
        dzis = date.today()
        self.data.setText(f"{DNI[dzis.weekday()].capitalize()}, {dzis.day} {MIESIACE_DOP[dzis.month - 1]} {dzis.year}")
        self.zaslon()

    def zaslon(self):
        self.zawartosc.hide()
        self.btn_ukryj.hide()
        self.zaslona.show()
        self.uklad.setStretch(self._indeks_luzu, 1)
        self.wykres.ustaw([])
        self.ostatnie.setRowCount(0)

    def odslon(self):
        baza = self.okno.baza
        if baza.ma_haslo and OknoHasla(baza.sprawdz_haslo, "Pokaż przychody", self, self.okno.dziennik,
                                       "podgląd przychodów", "Podaj hasło, aby zobaczyć kwoty.").exec() \
                != QDialog.DialogCode.Accepted:
            return
        self._wypelnij()
        self.zaslona.hide()
        self.uklad.setStretch(self._indeks_luzu, 0)
        self.zawartosc.show()
        self.btn_ukryj.show()

    def _wypelnij(self):
        dzis = date.today()
        baza = self.okno.baza

        teraz = podsumuj(baza.dokumenty(rok=dzis.year, miesiac=dzis.month))
        pr, pm = poprzedni_miesiac(dzis.year, dzis.month)
        # uczciwe porównanie: te same dni poprzedniego miesiąca (np. 1–3 października z 1–3 września)
        do_dnia = podsumuj([d for d in baza.dokumenty(rok=pr, miesiac=pm) if int(d.data_wystawienia[8:10]) <= dzis.day])
        self.k_przychod_et.setText(f"Przychód w {MIESIACE_MIEJSC[dzis.month - 1]}")
        self.k_przychod.setText(f"{druk.zl(teraz.suma)} zł")
        okres = f"1–{dzis.day} {MIESIACE_DOP[pm - 1]}" if dzis.day > 1 else f"1 {MIESIACE_DOP[pm - 1]}"
        if do_dnia.suma:
            zmiana = (teraz.suma - do_dnia.suma) / do_dnia.suma * 100
            znak = "+" if zmiana >= 0 else "−"
            kolor = ZIELONY if zmiana >= 0 else CZERWONY
            self.k_przychod_zm.setText(f'<span style="color:{kolor}; font-weight:600;">{znak}{abs(zmiana):.0f}%</span>'
                                       f" wobec {okres}")
        else:
            self.k_przychod_zm.setText(f"{okres}: {druk.zl(do_dnia.suma)} zł")
        wszystkie_teraz = baza.dokumenty(rok=dzis.year, miesiac=dzis.month)
        faktur = sum(1 for d in wszystkie_teraz if d.wazny and d.tytul == "Faktura")
        self.k_liczba.setText(str(teraz.liczba))
        self.k_liczba_zm.setText(f"rachunki: {teraz.liczba - faktur}, faktury: {faktur}")
        wczesniej = podsumuj(baza.dokumenty(rok=pr, miesiac=pm))
        self.k_srednia.setText(f"{druk.zl(teraz.suma / teraz.liczba) if teraz.liczba else '0,00'} zł")
        self.k_srednia_zm.setText(f"w {MIESIACE_MIEJSC[pm - 1]}: "
                                  f"{druk.zl(wczesniej.suma / wczesniej.liczba) if wczesniej.liczba else '0,00'} zł")
        rok = podsumuj(baza.dokumenty(rok=dzis.year))
        self.k_rok.setText(f"{druk.zl(rok.suma)} zł")
        self.k_rok_zm.setText(f"{liczba_dokumentow(rok.liczba)} w {dzis.year} r.")

        dane = []
        for ile in range(11, -1, -1):
            r, mies = poprzedni_miesiac(dzis.year, dzis.month, ile)
            p = podsumuj(baza.dokumenty(rok=r, miesiac=mies))
            dane.append((MIESIACE_KROTKO[mies - 1], f"{MIESIACE[mies - 1].capitalize()} {r}", p.suma, p.liczba))
        self.wykres.ustaw(dane)
        self.suma_12.setText(f"razem {druk.zl(sum(d[2] for d in dane))} zł")

        self._docs = baza.dokumenty()[:7]
        self.ostatnie.setRowCount(len(self._docs))
        for r, d in enumerate(self._docs):
            opis = QTableWidgetItem(f"{d.nabywca}\n{d.numer}  ·  {druk.data_pl(d.data_wystawienia)}")
            self.ostatnie.setItem(r, 0, opis)
            self.ostatnie.setItem(r, 1, QTableWidgetItem("Anulowany" if d.anulowano else d.tytul))
            kwota = QTableWidgetItem(f"{druk.zl(d.suma)} zł")
            kwota.setFont(czcionka_cyfr(13, QFont.Weight.DemiBold))
            kwota.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if d.anulowano:
                kwota.setForeground(QColor(TEKST_3))
            self.ostatnie.setItem(r, 2, kwota)
        self.ostatnie.setVisible(bool(self._docs))
        self.pusto.setVisible(not self._docs)


class StronaNowy(Strona):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, przewijana=True)
        u = self.uklad
        gora = QHBoxLayout()
        self.naglowek = naglowek_strony("Nowy rachunek", "Numer nadaje się sam: kolejny w danym miesiącu.")
        gora.addLayout(self.naglowek)
        gora.addStretch()
        self.rodzaj_grupa = QButtonGroup(self)
        przelacznik = QFrame(objectName="przelacznik")
        pu = QHBoxLayout(przelacznik)
        pu.setContentsMargins(3, 3, 3, 3)
        pu.setSpacing(2)
        for i, nazwa in enumerate(["Rachunek", "Faktura"]):
            b = QPushButton(nazwa, checkable=True, objectName="segment", cursor=Qt.CursorShape.PointingHandCursor)
            self.rodzaj_grupa.addButton(b, i)
            pu.addWidget(b)
        self.rodzaj_grupa.idClicked.connect(lambda _: self.zmien_rodzaj())
        self.tryb_grupa = QButtonGroup(self)
        przelacznik_trybu = QFrame(objectName="przelacznik")
        pt = QHBoxLayout(przelacznik_trybu)
        pt.setContentsMargins(3, 3, 3, 3)
        pt.setSpacing(2)
        for i, (nazwa, podpowiedz) in enumerate((("Krok po kroku", "Tryb prowadzący: pacjent, usługi, sprawdź i drukuj"),
                                                 ("Jedno okno", "Tryb zaawansowany: wszystko naraz"))):
            b = QPushButton(nazwa, checkable=True, objectName="segment", cursor=Qt.CursorShape.PointingHandCursor)
            b.setToolTip(podpowiedz)
            self.tryb_grupa.addButton(b, i)
            pt.addWidget(b)
        self.tryb_grupa.idClicked.connect(
            lambda i: self.przelacz_tryb("zaawansowany" if i == 1 else "prowadzacy"))
        gora.addWidget(przelacznik_trybu, alignment=Qt.AlignmentFlag.AlignBottom)
        gora.addSpacing(6)
        gora.addWidget(przelacznik, alignment=Qt.AlignmentFlag.AlignBottom)
        u.addLayout(gora)
        u.addSpacing(8)

        # --- pasek kroków (tryb prowadzący)
        self.pasek_krokow = QWidget()
        pk = QHBoxLayout(self.pasek_krokow)
        pk.setContentsMargins(0, 0, 0, 6)
        pk.setSpacing(8)
        self.kroki: list[tuple[QLabel, QLabel]] = []
        for i, nazwa in enumerate(["Pacjent", "Usługi", "Sprawdź i drukuj"]):
            if i:
                linia = QFrame(objectName="separator")
                linia.setFixedWidth(36)
                pk.addWidget(linia)
            numer = QLabel(str(i + 1), alignment=Qt.AlignmentFlag.AlignCenter, objectName="krok_numer")
            numer.setFixedSize(24, 24)
            tekst = QLabel(nazwa, objectName="krok_tekst")
            pk.addWidget(numer)
            pk.addWidget(tekst)
            self.kroki.append((numer, tekst))
        pk.addStretch()
        u.addWidget(self.pasek_krokow)

        self._zegar_podgladu = QTimer(self, singleShot=True, interval=150)
        self._zegar_podgladu.timeout.connect(self.odswiez_podglad)

        # --- karta dokumentu: numer, daty, płatność
        self.karta_dokumentu, kd = karta()
        siatka = QGridLayout()
        siatka.setHorizontalSpacing(14)
        siatka.setVerticalSpacing(12)
        self.numer = QLineEdit(objectName="numer")
        self.numer.setFixedWidth(150)
        self.data_wyst = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.data_uslugi = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.platnosc = QComboBox()
        self.platnosc.addItems(["gotówka", "karta", "przelew"])
        self.data_wyst.dateChanged.connect(self.odswiez_numer)
        for kol, (etykieta, w) in enumerate([("Numer", self.numer), ("Data wystawienia", self.data_wyst),
                                             ("Data usługi", self.data_uslugi), ("Płatność", self.platnosc)]):
            siatka.addLayout(pole(etykieta, w), 0, kol)
        siatka.setColumnStretch(4, 1)
        kd.addLayout(siatka)

        # --- karta nabywcy
        self.karta_nabywcy, kn = karta()
        self.nabywca = QLineEdit(placeholderText="Imię i nazwisko lub nazwa firmy")
        self.nabywca.textEdited.connect(self._podpowiadaj)
        self.nabywca_id = QLineEdit(placeholderText="Opcjonalnie")
        self.nabywca_adres = QLineEdit(placeholderText="Opcjonalnie, np. ul. Długa 1, 00-001 Miasto")
        nab = QGridLayout()
        nab.setHorizontalSpacing(14)
        nab.setVerticalSpacing(12)
        wiersz_pacjenta = QHBoxLayout()
        wiersz_pacjenta.setSpacing(6)
        wiersz_pacjenta.addWidget(self.nabywca, 1)
        wybierz = przycisk("Wybierz…", "uzytkownicy", akcja=self.wybierz_pacjenta)
        wybierz.setToolTip("Lista wszystkich pacjentów (F2)")
        wiersz_pacjenta.addWidget(wybierz)
        kontener = QWidget()
        kontener.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        kontener.setLayout(wiersz_pacjenta)
        wiersz_pacjenta.setContentsMargins(0, 0, 0, 0)
        uklad_pacjenta = pole("Pacjent", kontener)
        self.etykieta_nabywcy = uklad_pacjenta.itemAt(0).widget()
        nab.addLayout(uklad_pacjenta, 0, 0, Qt.AlignmentFlag.AlignTop)
        pole_id = pole("PESEL lub NIP", self.nabywca_id)
        self.podpowiedz_id = QLabel(objectName="drobny")
        pole_id.addWidget(self.podpowiedz_id)
        self.nabywca_id.textChanged.connect(self._sprawdz_id)
        nab.addLayout(pole_id, 0, 1, Qt.AlignmentFlag.AlignTop)
        nab.addLayout(pole("Adres", self.nabywca_adres), 1, 0, 1, 2)
        nab.setColumnStretch(0, 3)
        nab.setColumnStretch(1, 2)
        kn.addLayout(nab)

        # --- blok usług
        self.blok_uslug = QWidget()
        bu = QVBoxLayout(self.blok_uslug)
        bu.setContentsMargins(0, 0, 0, 0)
        bu.setSpacing(8)
        bu.addWidget(sekcja("Usługi"))
        k, ku = karta()
        ku.setContentsMargins(0, 12, 0, 12)
        self.przyciski_uslug = UkladPlynny()
        self.przyciski_uslug.setContentsMargins(16, 0, 16, 4)
        ku.addLayout(self.przyciski_uslug)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Nazwa usługi", "Ilość", "Cena (zł)", "Wartość (zł)"])
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for kol, szer in ((1, 80), (2, 120), (3, 130)):
            h.setSectionResizeMode(kol, QHeaderView.ResizeMode.Fixed)
            self.tabela.setColumnWidth(kol, szer)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.setShowGrid(False)
        self.tabela.setMinimumHeight(150)
        self.tabela.itemChanged.connect(self.przelicz)
        ku.addWidget(self.tabela, 1)
        rzad = QHBoxLayout()
        rzad.setContentsMargins(12, 0, 18, 0)
        rzad.addWidget(przycisk("Dodaj pozycję", "plus", "plaski", lambda: self.dodaj_pozycje()))
        rzad.addWidget(przycisk("Usuń zaznaczoną", "kosz", "plaski", self.usun_pozycje))
        rzad.addStretch()
        razem = QLabel("Razem", objectName="podtytul")
        self.suma = QLabel("0,00 zł")
        self.suma.setStyleSheet("font-size: 22px; font-weight: 600; letter-spacing: -0.3px;")
        rzad.addWidget(razem)
        rzad.addSpacing(10)
        rzad.addWidget(self.suma)
        ku.addLayout(rzad)
        bu.addWidget(k, 1)

        # --- podgląd kartki
        self.ramka_podgladu = QWidget()
        rp = QVBoxLayout(self.ramka_podgladu)
        rp.setContentsMargins(0, 0, 0, 0)
        rp.setSpacing(6)
        naglowek_podgladu = QHBoxLayout()
        naglowek_podgladu.addWidget(QLabel("Podgląd wydruku", objectName="sekcja"))
        naglowek_podgladu.addStretch()
        naglowek_podgladu.addWidget(QLabel("aktualizuje się na bieżąco", objectName="drobny"))
        rp.addLayout(naglowek_podgladu)
        self.kartka = PodgladKartki()
        self.kartka.setCursor(Qt.CursorShape.PointingHandCursor)
        self.kartka.setToolTip("Kliknij, aby zobaczyć pełny podgląd")
        self.kartka.mousePressEvent = lambda _e: self.podglad()
        rp.addWidget(self.kartka, 1)

        # --- tryb zaawansowany: wszystko w jednym oknie
        self.widok_zaawansowany = QWidget()
        wz = QHBoxLayout(self.widok_zaawansowany)
        wz.setContentsMargins(0, 0, 0, 0)
        wz.setSpacing(22)
        self.zaaw_lewa = QVBoxLayout()
        self.zaaw_lewa.setSpacing(10)
        wz.addLayout(self.zaaw_lewa, 3)
        self.zaaw_prawa = QVBoxLayout()
        wz.addLayout(self.zaaw_prawa, 2)

        # --- tryb prowadzący: trzy kroki
        self.widok_prowadzony = QStackedWidget()
        self.kroki_uklady = []
        for tytul, opis in (("Komu wystawiasz dokument?", "Wpisz pacjenta albo wybierz go z listy (F2)."),
                            ("Za jakie usługi?", "Kliknij usługę z cennika albo dodaj pozycję ręcznie."),
                            ("Sprawdź i wydrukuj", "Tak będzie wyglądał wydruk. Możesz jeszcze zmienić datę albo płatność.")):
            strona = QWidget()
            su = QVBoxLayout(strona)
            su.setContentsMargins(0, 0, 0, 0)
            su.setSpacing(10)
            t = QLabel(tytul)
            t.setStyleSheet("font-size: 18px; font-weight: 600;")
            su.addWidget(t)
            su.addWidget(QLabel(opis, objectName="podtytul"))
            su.addSpacing(4)
            self.kroki_uklady.append(su)
            self.widok_prowadzony.addWidget(strona)
        krok3 = QHBoxLayout()
        krok3.setSpacing(22)
        self.krok3_lewa = QVBoxLayout()
        self.krok3_lewa.setSpacing(10)
        krok3.addLayout(self.krok3_lewa, 3)
        self.krok3_prawa = QVBoxLayout()
        krok3.addLayout(self.krok3_prawa, 2)
        self.kroki_uklady[2].addLayout(krok3, 1)
        self.podsumowanie_kroku, ps = karta()
        self.podsumowanie_tekst = QLabel(wordWrap=True)
        ps.addWidget(self.podsumowanie_tekst)

        u.addWidget(self.widok_zaawansowany, 1)
        u.addWidget(self.widok_prowadzony, 1)

        # --- stały pasek na dole, zawsze widoczny
        dol = self.stopka()
        self.btn_wstecz = przycisk("Wstecz", akcja=lambda: self.pokaz_krok(self.krok - 1))
        dol.addWidget(self.btn_wstecz)
        self.kopia = QCheckBox("Drukuj też kopię")
        dol.addWidget(self.kopia)
        dol.addStretch()
        dol.addWidget(QLabel("Do zapłaty", objectName="podtytul"))
        dol.addSpacing(6)
        self.suma_stopka = QLabel("0,00 zł")
        self.suma_stopka.setFont(czcionka_cyfr(18, QFont.Weight.DemiBold))
        dol.addWidget(self.suma_stopka)
        dol.addSpacing(18)
        self.btn_podglad = przycisk("Podgląd", "podglad", akcja=self.podglad)
        self.btn_pdf = przycisk("Zapisz PDF", "pdf", akcja=self.zapisz_pdf)
        dol.addWidget(self.btn_podglad)
        dol.addWidget(self.btn_pdf)
        self.btn_anuluj_edycje = przycisk("Anuluj edycję", akcja=self.zakoncz_edycje)
        self.btn_anuluj_edycje.hide()
        dol.addWidget(self.btn_anuluj_edycje)
        self.edytowany: Dokument | None = None
        self.drukuj_btn = przycisk("Drukuj", "drukarka", "glowny", self.glowna_akcja)
        self.drukuj_btn.setToolTip("F5 lub Ctrl+P")
        dol.addWidget(self.drukuj_btn)
        self.btn_dalej = przycisk("Dalej", "dalej", "glowny", lambda: self.pokaz_krok(self.krok + 1))
        self.btn_dalej.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        dol.addWidget(self.btn_dalej)
        self.krok = 0
        self.tryb = ""

        QShortcut(QKeySequence("F5"), self, self.drukuj)
        QShortcut(QKeySequence("Ctrl+P"), self, self.drukuj)
        QShortcut(QKeySequence("F2"), self, self.wybierz_pacjenta)

        for pole_tekstu in (self.numer, self.nabywca, self.nabywca_id, self.nabywca_adres):
            pole_tekstu.textChanged.connect(self.zaplanuj_podglad)
        for pole_daty in (self.data_wyst, self.data_uslugi):
            pole_daty.dateChanged.connect(self.zaplanuj_podglad)
        self.platnosc.currentIndexChanged.connect(self.zaplanuj_podglad)
        self.tabela.itemChanged.connect(self.zaplanuj_podglad)
        self.tabela.model().rowsRemoved.connect(self.zaplanuj_podglad)
        self.kopia.toggled.connect(self.zaplanuj_podglad)

    def _sprawdz_id(self, tekst: str):
        wynik = opis_identyfikatora(tekst)
        if not wynik:
            self.podpowiedz_id.clear()
            return
        komunikat, ok = wynik
        self.podpowiedz_id.setText(komunikat)
        self.podpowiedz_id.setStyleSheet(f"color: {ZIELONY if ok else CZERWONY};")

    # ---- tryby pracy
    def ustaw_tryb(self, tryb: str):
        """Prowadzący: trzy kroki z przyciskami Dalej/Wstecz. Zaawansowany: wszystko w jednym oknie."""
        self.tryb = tryb
        if tryb == "zaawansowany":
            for w in (self.karta_dokumentu, self.karta_nabywcy):
                self.zaaw_lewa.addWidget(w)
            self.zaaw_lewa.addWidget(self.blok_uslug, 1)
            self.zaaw_prawa.addWidget(self.ramka_podgladu)
            self.widok_prowadzony.hide()
            self.widok_zaawansowany.show()
        else:
            self.kroki_uklady[0].addWidget(self.karta_nabywcy)
            self.kroki_uklady[0].addStretch()
            self.kroki_uklady[1].addWidget(self.blok_uslug, 1)
            self.krok3_lewa.addWidget(self.karta_dokumentu)
            self.krok3_lewa.addWidget(self.podsumowanie_kroku)
            self.krok3_lewa.addStretch()
            self.krok3_prawa.addWidget(self.ramka_podgladu)
            self.widok_zaawansowany.hide()
            self.widok_prowadzony.show()
        self.tryb_grupa.button(1 if tryb == "zaawansowany" else 0).setChecked(True)
        self.pasek_krokow.setVisible(tryb != "zaawansowany")
        self.pokaz_krok(0)

    def przelacz_tryb(self, nowy: str):
        if nowy == self.tryb:
            return
        self.okno.baza.zapisz_ustawienia({"tryb": nowy})
        krok = self.krok
        self.ustaw_tryb(nowy)
        if self.edytowany or self.nabywca.text().strip():
            self.krok = 0
            self.pokaz_krok(2 if nowy == "prowadzacy" and krok == 2 else 0)

    def pokaz_krok(self, krok: int):
        prowadzony = self.tryb != "zaawansowany"
        if prowadzony and krok > self.krok:
            # nie przepuszczaj dalej bez potrzebnych danych
            if self.krok == 0 and not self.nabywca.text().strip():
                self.okno.komunikat("Wpisz pacjenta, żeby przejść dalej", blad=True)
                self.nabywca.setFocus()
                return
            if self.krok == 1 and not self.pozycje():
                self.okno.komunikat("Dodaj przynajmniej jedną usługę", blad=True)
                return
        self.krok = max(0, min(2, krok)) if prowadzony else 2
        if prowadzony:
            self.widok_prowadzony.setCurrentIndex(self.krok)
            for i, (numer, tekst) in enumerate(self.kroki):
                stan = "aktywny" if i == self.krok else ("zrobiony" if i < self.krok else "")
                numer.setProperty("stan", stan)
                tekst.setProperty("stan", stan)
                for w in (numer, tekst):
                    w.style().unpolish(w)
                    w.style().polish(w)
        ostatni = self.krok == 2
        self.btn_wstecz.setVisible(prowadzony and self.krok > 0)
        self.btn_dalej.setVisible(prowadzony and not ostatni)
        for w in (self.drukuj_btn, self.btn_podglad, self.btn_pdf, self.kopia):
            w.setVisible(ostatni)
        if self.edytowany:
            self.kopia.hide()
        if ostatni:
            ile = len(self.pozycje())
            self.podsumowanie_tekst.setText(
                f"<b>{self.rodzaj}</b> dla <b>{html_escape(self.nabywca.text().strip()) or '…'}</b><br>"
                f"Pozycji: {ile}, razem <b>{druk.zl(sum(p.wartosc for p in self.pozycje()))} zł</b>")
            self.zaplanuj_podglad()
        elif self.krok == 0:
            self.nabywca.setFocus()

    # ---- edycja wystawionego dokumentu
    def glowna_akcja(self):
        if self.edytowany:
            self.zapisz_zmiany()
        else:
            self.drukuj()

    def zaladuj_do_edycji(self, dok: Dokument):
        self.edytowany = dok
        self.ustaw_rodzaj(dok.tytul)
        for b in self.rodzaj_grupa.buttons():
            b.setEnabled(False)
        self.numer.setText(dok.numer)
        self.numer.setReadOnly(True)
        self.numer.setToolTip("Numer wystawionego dokumentu się nie zmienia")
        self.data_wyst.blockSignals(True)
        self.data_wyst.setDate(QDate.fromString(dok.data_wystawienia, "yyyy-MM-dd"))
        self.data_wyst.blockSignals(False)
        self.data_uslugi.setDate(QDate.fromString(dok.data_uslugi, "yyyy-MM-dd"))
        self.platnosc.setCurrentText(dok.platnosc)
        self.nabywca.setText(dok.nabywca)
        self.nabywca_id.setText(dok.nabywca_id)
        self.nabywca_adres.setText(dok.nabywca_adres.replace("\n", ", "))
        self.tabela.setRowCount(0)
        for p in dok.pozycje:
            self.dodaj_pozycje(p.nazwa, p.cena, p.ilosc)
        self.drukuj_btn.setText("Zapisz zmiany")
        self.drukuj_btn.setIcon(ikona("ok", "white"))
        self.btn_anuluj_edycje.show()
        self.kopia.hide()
        self.zmien_rodzaj()
        self.pokaz_krok(0)

    def zapisz_zmiany(self):
        dok = self.dokument()
        if not dok or not self.edytowany:
            return
        powod, ok = QInputDialog.getText(self, "Zapisz zmiany", f"Co poprawiono w dokumencie nr {self.edytowany.numer}?\n"
                                         "(zapisze się w historii zmian)")
        if not ok:
            return
        org = self.edytowany
        dok.id, dok.numer, dok.rodzaj, dok.anulowano, dok.powod_anulowania = (
            org.id, org.numer, org.rodzaj, org.anulowano, org.powod_anulowania)
        self.okno.baza.zaktualizuj_dokument(dok, powod)
        self.okno.dziennik.zapisz(f"edycja dokumentu nr {dok.numer}")  # powód zostaje w zaszyfrowanej historii zmian
        self.okno.komunikat(f"Zapisano zmiany w dokumencie nr {dok.numer}")
        self.zakoncz_edycje()
        self.okno.przejdz(STRONA_HISTORIA)
        self.okno.podglad(self.okno.baza.dokument(dok.id), duplikat=True)

    def zakoncz_edycje(self):
        self.edytowany = None
        for b in self.rodzaj_grupa.buttons():
            b.setEnabled(True)
        self.numer.setReadOnly(False)
        self.numer.setToolTip("")
        self.drukuj_btn.setText("Drukuj")
        self.drukuj_btn.setIcon(ikona("drukarka", "white"))
        self.btn_anuluj_edycje.hide()
        self.wyczysc()

    def zaplanuj_podglad(self, *_):
        self._zegar_podgladu.start()

    def dokument_roboczy(self) -> Dokument:
        """Dokument z tego, co wpisano do tej pory (bez sprawdzania), do podglądu na żywo."""
        return Dokument(
            numer=self.numer.text().strip() or "…",
            data_wystawienia=self.data_wyst.date().toPython().isoformat(),
            data_uslugi=self.data_uslugi.date().toPython().isoformat(),
            platnosc=self.platnosc.currentText(),
            nabywca=self.nabywca.text().strip() or "Imię i nazwisko",
            nabywca_adres=self.nabywca_adres.text().strip(),
            nabywca_id=self.nabywca_id.text().strip(),
            rodzaj=self.rodzaj,
            pozycje=self.pozycje())

    def odswiez_podglad(self):
        if self.ramka_podgladu.isVisible() or not self.isVisible():
            self.kartka.ustaw_html(druk.html_dokumentu(self.dokument_roboczy(), self.okno.baza.ustawienia()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        widoczny = self.width() >= 1000
        if widoczny != self.ramka_podgladu.isVisible():
            self.ramka_podgladu.setVisible(widoczny)
            if widoczny:
                self.zaplanuj_podglad()

    def wybierz_pacjenta(self):
        okno = OknoPacjentow(self.okno.baza, self, self.nabywca.text().strip(), self.okno.potwierdz_haslem)
        wynik = okno.exec()
        tekst, ident, adres = self.nabywca.text(), self.nabywca_id.text(), self.nabywca_adres.text()
        self.odswiez()  # lista podpowiedzi mogła się zmienić (nowi lub poprawieni pacjenci)
        self.nabywca.setText(tekst)
        self.nabywca_id.setText(ident)
        self.nabywca_adres.setText(adres)
        if wynik == QDialog.DialogCode.Accepted and okno.wybrany:
            p = okno.wybrany
            self.nabywca.setText(p.nazwa)
            self.nabywca_adres.setText(p.adres.replace("\n", ", "))
            self.nabywca_id.setText(p.identyfikator)

    # ---- dane z formularza
    def odswiez(self):
        u = self.okno.baza.ustawienia()
        self.kopia.setChecked(u["kopia"] == "1")
        wyczysc_uklad(self.przyciski_uslug)
        for linia in u["uslugi"].splitlines():
            nazwa, _, cena = linia.partition(";")
            if not nazwa.strip():
                continue
            tekst = nazwa.strip() + (f"   {druk.zl(liczba(cena))} zł" if liczba(cena) else "")
            b = QPushButton(tekst, objectName="chip", cursor=Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=nazwa.strip(), c=liczba(cena): self.dodaj_usluge(n, c))
            self.przyciski_uslug.addWidget(b)

        # podpowiedzi nazwisk dopiero po wpisaniu 2 liter: nikt przy biurku nie zobaczy listy pacjentów
        self._podpowiedzi = QCompleter([p.nazwa for p in self.okno.baza.pacjenci()], self)
        self._podpowiedzi.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._podpowiedzi.setFilterMode(Qt.MatchFlag.MatchContains)
        self._podpowiedzi.activated.connect(self.uzupelnij_nabywce)
        self.nabywca.setCompleter(None)
        self.odswiez_numer()

    @property
    def rodzaj(self) -> str:
        return "Faktura" if self.rodzaj_grupa.checkedId() == 1 else "Rachunek"

    def ustaw_rodzaj(self, rodzaj: str):
        self.rodzaj_grupa.button(1 if rodzaj == "Faktura" else 0).setChecked(True)
        self.zmien_rodzaj()

    def zmien_rodzaj(self):
        tytul = self.naglowek.itemAt(0).widget()
        podtytul = self.naglowek.itemAt(1).widget()
        if self.edytowany:
            tytul.setText(f"Edycja: {self.edytowany.tytul.lower()} nr {self.edytowany.numer}")
            podtytul.setText("Numer zostaje bez zmian. Poprzednia wersja trafi do historii zmian.")
        else:
            tytul.setText("Nowa faktura" if self.rodzaj == "Faktura" else "Nowy rachunek")
            podtytul.setText("Numer nadaje się sam: kolejny w danym miesiącu.")
        self.zaplanuj_podglad()
        self.etykieta_nabywcy.setText("Nabywca (pacjent lub firma)" if self.rodzaj == "Faktura" else "Pacjent")
        self.odswiez_numer()

    def odswiez_numer(self):
        if self.edytowany:
            return  # przy edycji numer się nie zmienia
        self.numer.setText(self.okno.baza.nastepny_numer(self.data_wyst.date().toPython(), self.rodzaj))

    def uzupelnij_nabywce(self, nazwa: str):
        p = self.okno.baza.pacjent(nazwa)
        if p:
            self.nabywca_adres.setText(p.adres.replace("\n", ", "))
            self.nabywca_id.setText(p.identyfikator)

    def _podpowiadaj(self, tekst: str):
        if len(tekst.strip()) >= 2:
            if self.nabywca.completer() is not self._podpowiedzi:
                self.nabywca.setCompleter(self._podpowiedzi)
                self._podpowiedzi.setCompletionPrefix(tekst)
                self._podpowiedzi.complete()
        elif self.nabywca.completer() is not None:
            self._podpowiedzi.popup().hide()
            self.nabywca.setCompleter(None)

    def dodaj_pozycje(self, nazwa="", cena=0.0, ilosc=1.0):
        self.tabela.blockSignals(True)
        r = self.tabela.rowCount()
        self.tabela.insertRow(r)
        self.tabela.setItem(r, 0, QTableWidgetItem(nazwa))
        self.tabela.setItem(r, 1, QTableWidgetItem(f"{ilosc:g}"))
        self.tabela.setItem(r, 2, QTableWidgetItem(druk.zl(cena) if cena else ""))
        wartosc = QTableWidgetItem()
        wartosc.setFlags(Qt.ItemFlag.ItemIsEnabled)
        wartosc.setForeground(Qt.GlobalColor.darkGray)
        self.tabela.setItem(r, 3, wartosc)
        for kol in (1, 2, 3):
            self.tabela.item(r, kol).setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tabela.blockSignals(False)
        self.przelicz()
        return r

    def dodaj_usluge(self, nazwa, cena):
        for r in range(self.tabela.rowCount()):
            if not self.tabela.item(r, 0).text().strip():
                self.tabela.item(r, 0).setText(nazwa)
                self.tabela.item(r, 2).setText(druk.zl(cena) if cena else "")
                return
        self.dodaj_pozycje(nazwa, cena)

    def usun_pozycje(self):
        r = self.tabela.currentRow()
        if r >= 0:
            self.tabela.removeRow(r)
            if not self.tabela.rowCount():
                self.dodaj_pozycje()
            self.przelicz()

    def pozycje(self) -> list[Pozycja]:
        wynik = []
        for r in range(self.tabela.rowCount()):
            nazwa = self.tabela.item(r, 0).text().strip()
            if nazwa:
                wynik.append(Pozycja(nazwa, liczba(self.tabela.item(r, 1).text()) or 1,
                                     liczba(self.tabela.item(r, 2).text())))
        return wynik

    def przelicz(self, *_):
        self.tabela.blockSignals(True)
        suma = 0.0
        for r in range(self.tabela.rowCount()):
            w = liczba(self.tabela.item(r, 1).text()) * liczba(self.tabela.item(r, 2).text())
            self.tabela.item(r, 3).setText(druk.zl(w) if w else "")
            suma += w
        self.tabela.blockSignals(False)
        self.suma.setText(f"{druk.zl(suma)} zł")
        if hasattr(self, "suma_stopka"):
            self.suma_stopka.setText(f"{druk.zl(suma)} zł")

    def dokument(self) -> Dokument | None:
        if not self.nabywca.text().strip():
            QMessageBox.warning(self, "Brak pacjenta", "Wpisz imię i nazwisko pacjenta.")
            self.nabywca.setFocus()
            return None
        pozycje = self.pozycje()
        if not pozycje:
            QMessageBox.warning(self, "Brak usług", "Dodaj przynajmniej jedną usługę.")
            return None
        return Dokument(
            numer=self.numer.text().strip(),
            data_wystawienia=self.data_wyst.date().toPython().isoformat(),
            data_uslugi=self.data_uslugi.date().toPython().isoformat(),
            platnosc=self.platnosc.currentText(),
            nabywca=self.nabywca.text().strip(),
            nabywca_adres=self.nabywca_adres.text().strip(),
            nabywca_id=self.nabywca_id.text().strip(),
            rodzaj=self.rodzaj,
            pozycje=pozycje)

    def wyczysc(self):
        for p in (self.nabywca, self.nabywca_id, self.nabywca_adres):
            p.clear()
        self.tabela.setRowCount(0)
        self.dodaj_pozycje()
        self.data_wyst.setDate(QDate.currentDate())
        self.data_uslugi.setDate(QDate.currentDate())
        self.platnosc.setCurrentIndex(0)
        self.rodzaj_grupa.button(1 if self.okno.baza.ustawienia()["tytul"] == "Faktura" else 0).setChecked(True)
        self.odswiez()
        self.zmien_rodzaj()
        self.pokaz_krok(0)
        self.nabywca.setFocus()

    # ---- akcje
    def _zatwierdz(self) -> Dokument | None:
        dok = self.dokument()
        if not dok:
            return None
        if not dok.numer:
            QMessageBox.warning(self, "Brak numeru", "Wpisz numer dokumentu.")
            return None
        if self.okno.baza.numer_istnieje(dok.numer):
            odp = QMessageBox.question(self, "Numer już użyty",
                                       f"Dokument nr {dok.numer} już istnieje. Wystawić mimo to?")
            if odp != QMessageBox.StandardButton.Yes:
                return None
        return dok

    def drukuj(self):
        dok = self._zatwierdz()
        if not dok:
            return
        u = self.okno.baza.ustawienia()
        drukarka = druk.przygotuj_drukarke(u)
        if u["okno_drukarki"] == "1" and QPrintDialog(drukarka, self).exec() != QDialog.DialogCode.Accepted:
            return
        self.okno.baza.zapisz_dokument(dok)
        druk.drukuj(druk.html_dokumentu(dok, u, self.kopia.isChecked()), drukarka)
        self.okno.komunikat(f"Wydrukowano: {dok.tytul.lower()} nr {dok.numer}")
        self.wyczysc()

    def zapisz_pdf(self):
        dok = self._zatwierdz()
        if not dok:
            return
        sciezka, _ = QFileDialog.getSaveFileName(
            self, "Zapisz PDF", str(Path.home() / f"{dok.numer.replace('/', '-')}.pdf"), "PDF (*.pdf)")
        if not sciezka:
            return
        u = self.okno.baza.ustawienia()
        self.okno.baza.zapisz_dokument(dok)
        druk.drukuj(druk.html_dokumentu(dok, u, self.kopia.isChecked()), druk.przygotuj_drukarke(u, sciezka))
        self.okno.komunikat(f"Zapisano PDF: {sciezka}")
        self.wyczysc()

    def podglad(self):
        dok = self.dokument()
        if dok:
            self.okno.podglad(dok, self.kopia.isChecked())


MIESIACE = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
            "październik", "listopad", "grudzień"]


def liczba_dokumentow(n: int) -> str:
    if n == 1:
        return "1 dokument"
    return f"{n} dokumenty" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else f"{n} dokumentów"


class OknoPacjentow(QDialog):
    """Wybór pacjenta z listy wszystkich dotychczasowych nabywców, z wyszukiwaniem."""

    def __init__(self, baza: Baza, parent=None, szukaj: str = "", potwierdz_haslem=None):
        super().__init__(parent)
        self.baza = baza
        self.wybrany = None
        self.potwierdz_haslem = potwierdz_haslem or (lambda *_: True)
        self.setWindowTitle("Wybierz pacjenta")
        self.resize(720, 520)
        u = QVBoxLayout(self)
        u.setContentsMargins(22, 20, 22, 18)
        u.setSpacing(10)
        t = QLabel("Pacjenci")
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(t)
        self.szukaj = QLineEdit(szukaj, placeholderText="Szukaj po nazwisku, imieniu lub PESEL")
        self.szukaj.addAction(ikona("szukaj"), QLineEdit.ActionPosition.LeadingPosition)
        self.szukaj.setClearButtonEnabled(True)
        self.szukaj.textChanged.connect(self.odswiez)
        self.szukaj.returnPressed.connect(self.wybierz)
        u.addWidget(self.szukaj)
        k, ku = karta()
        ku.setContentsMargins(0, 4, 0, 4)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Pacjent", "PESEL / NIP", "Ostatnia wizyta", "Dokumentów"])
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for kol, szer in ((1, 140), (2, 110), (3, 110)):
            self.tabela.setColumnWidth(kol, szer)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(34)
        self.tabela.setShowGrid(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.doubleClicked.connect(self.wybierz)
        ku.addWidget(self.tabela)
        self.zaslona_listy = QLabel("Wpisz co najmniej 2 litery nazwiska albo PESEL, aby wyszukać pacjenta.",
                                    objectName="podtytul", alignment=Qt.AlignmentFlag.AlignCenter)
        ku.addWidget(self.zaslona_listy)
        self.pelny_dostep = False
        u.addWidget(k, 1)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Nowy pacjent", "plus", "plaski", self.dodaj))
        rzad.addWidget(przycisk("Edytuj", "edytuj", "plaski", self.edytuj))
        rzad.addWidget(przycisk("Usuń z listy", "kosz", "plaski", self.usun))
        rzad.addWidget(przycisk("Dane osoby", "pdf", "plaski", self.dane_osoby))
        self.btn_wszystko = przycisk("Pokaż wszystkich", "klucz", "plaski", self.pokaz_wszystko)
        rzad.addWidget(self.btn_wszystko)
        self.licznik = QLabel(objectName="drobny")
        rzad.addSpacing(10)
        rzad.addWidget(self.licznik)
        rzad.addStretch()
        rzad.addWidget(przycisk("Anuluj", akcja=self.reject))
        rzad.addWidget(przycisk("Wybierz", styl="glowny", akcja=self.wybierz))
        u.addLayout(rzad)
        self.pacjenci = []
        self.odswiez()
        self.szukaj.setFocus()

    def odswiez(self):
        zablokowane = self.baza.ma_haslo and not self.pelny_dostep and len(self.szukaj.text().strip()) < 2
        self.pacjenci = [] if zablokowane else self.baza.pacjenci(self.szukaj.text())
        self.tabela.setVisible(not zablokowane)
        self.zaslona_listy.setVisible(zablokowane)
        self.btn_wszystko.setVisible(self.baza.ma_haslo and not self.pelny_dostep)
        self.tabela.setRowCount(len(self.pacjenci))
        for r, p in enumerate(self.pacjenci):
            for kol, tekst in enumerate([p.nazwa, maskuj_id(p.identyfikator),
                                         druk.data_pl(p.ostatnia_wizyta) if p.ostatnia_wizyta
                                         else "—", str(p.dokumentow)]):
                self.tabela.setItem(r, kol, QTableWidgetItem(tekst))
        if self.pacjenci:
            self.tabela.selectRow(0)
        self.licznik.setText(f"Pacjentów: {len(self.pacjenci)}")

    def _formularz(self, tytul: str, p=None):
        okno = QDialog(self)
        okno.setWindowTitle(tytul)
        okno.setFixedWidth(440)
        u = QVBoxLayout(okno)
        u.setContentsMargins(24, 22, 24, 20)
        u.setSpacing(10)
        t = QLabel(tytul)
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(t)
        nazwa = QLineEdit(p.nazwa if p else "", placeholderText="Imię i nazwisko lub nazwa firmy")
        ident = QLineEdit(p.identyfikator if p else "", placeholderText="Opcjonalnie")
        adres = QLineEdit(p.adres.replace("\n", ", ") if p else "", placeholderText="Opcjonalnie")
        info = QLabel(objectName="drobny")

        def sprawdz(tekst):
            wynik = opis_identyfikatora(tekst)
            info.setText(wynik[0] if wynik else "")
            info.setStyleSheet(f"color: {ZIELONY if wynik and wynik[1] else CZERWONY};")
        ident.textChanged.connect(sprawdz)
        sprawdz(ident.text())
        u.addLayout(pole("Pacjent", nazwa))
        pi = pole("PESEL lub NIP", ident)
        pi.addWidget(info)
        u.addLayout(pi)
        u.addLayout(pole("Adres", adres))
        r = QHBoxLayout()
        r.addStretch()
        r.addWidget(przycisk("Anuluj", akcja=okno.reject))
        r.addWidget(przycisk("Zapisz", styl="glowny", akcja=lambda: okno.accept() if nazwa.text().strip() else nazwa.setFocus()))
        u.addLayout(r)
        if okno.exec() == QDialog.DialogCode.Accepted:
            return nazwa.text().strip(), ident.text().strip(), adres.text().strip()
        return None

    def pokaz_wszystko(self):
        if self.potwierdz_haslem("pokazanie listy pacjentów", "Podaj hasło, aby zobaczyć wszystkich pacjentów."):
            self.pelny_dostep = True
            self.odswiez()

    def dodaj(self):
        dane = self._formularz("Nowy pacjent")
        if dane:
            self.baza.zapisz_pacjenta(*dane)
            self.szukaj.setText(dane[0])
            self.odswiez()

    def _zaznaczony(self):
        r = self.tabela.currentRow()
        return self.pacjenci[r] if 0 <= r < len(self.pacjenci) else None

    def edytuj(self):
        p = self._zaznaczony()
        if not p:
            return
        dane = self._formularz("Edytuj pacjenta", p)
        if dane:
            self.baza.zapisz_pacjenta(*dane, stara_nazwa=p.nazwa)
            self.odswiez()

    def usun(self):
        p = self._zaznaczony()
        if not p:
            return
        if QMessageBox.question(self, "Usuń z listy", f"Usunąć „{p.nazwa}” z listy pacjentów?\n\n"
                                "Wystawione dokumenty zostaną bez zmian: przepisy podatkowe wymagają ich "
                                "przechowywania (RODO art. 17 ust. 3 lit. b). Dane osobowe z dokumentów usuniesz "
                                "po okresie przechowywania w Ustawienia → RODO.") != QMessageBox.StandardButton.Yes:
            return
        if not self.potwierdz_haslem("usunięcie pacjenta z kartoteki", "Usunięcie pacjenta z listy wymaga hasła."):
            return
        self.baza.usun_pacjenta(p.nazwa)
        self.odswiez()

    def dane_osoby(self):
        """Prawo dostępu (art. 15 RODO): PDF z danymi osoby i listą jej dokumentów."""
        p = self._zaznaczony()
        if not p:
            QMessageBox.information(self, "Dane osoby", "Wyszukaj i zaznacz pacjenta.")
            return
        if not self.potwierdz_haslem("eksport danych osoby (RODO)", "Eksport danych osobowych wymaga hasła."):
            return
        sciezka, _ = QFileDialog.getSaveFileName(self, "Dane osoby (RODO)", str(Path.home() / "dane-osoby.pdf"),
                                                 "PDF (*.pdf)")
        if not sciezka:
            return
        u = self.baza.ustawienia()
        html = druk.html_danych_osoby(p.nazwa, p.identyfikator, p.adres, self.baza.dokumenty_pacjenta(p.nazwa), u)
        druk.drukuj(html, druk.przygotuj_drukarke(u, sciezka))
        QMessageBox.information(self, "Dane osoby", f"Zapisano: {sciezka}")

    def wybierz(self, *_):
        r = self.tabela.currentRow()
        if 0 <= r < len(self.pacjenci):
            self.wybrany = self.pacjenci[r]
            self.accept()


class StronaHistoria(Strona):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno)
        u = self.uklad
        naglowek = QHBoxLayout()
        naglowek.addLayout(naglowek_strony("Historia", "Rachunki i faktury. Szukaj po nazwisku, numerze lub PESEL."))
        naglowek.addStretch()
        for b in (przycisk("Drukuj zestawienie", "drukarka", akcja=self.drukuj_zestawienie),
                  przycisk("Zestawienie PDF", "pdf", akcja=self.zestawienie_pdf),
                  przycisk("Excel", "arkusz", akcja=self.eksport)):
            b.setToolTip("Dotyczy wyników widocznych poniżej")
            naglowek.addWidget(b, alignment=Qt.AlignmentFlag.AlignBottom)
        u.addLayout(naglowek)
        u.addSpacing(10)

        # --- filtry
        filtry = QHBoxLayout()
        filtry.setSpacing(8)
        self.szukaj = QLineEdit(placeholderText="Nazwisko, numer lub PESEL")
        self.szukaj.addAction(ikona("szukaj"), QLineEdit.ActionPosition.LeadingPosition)
        self.szukaj.setClearButtonEnabled(True)
        self.szukaj.textChanged.connect(self.filtruj)
        filtry.addWidget(self.szukaj, 1)
        self.rok = QComboBox()
        self.rok.setMinimumWidth(110)
        self.rok.currentIndexChanged.connect(self.filtruj)
        filtry.addWidget(self.rok)
        self.miesiac = QComboBox()
        self.miesiac.setMinimumWidth(140)
        self.miesiac.addItem("Wszystkie miesiące", 0)
        for i, nazwa in enumerate(MIESIACE, 1):
            self.miesiac.addItem(nazwa.capitalize(), i)
        self.miesiac.currentIndexChanged.connect(self.filtruj)
        filtry.addWidget(self.miesiac)
        self.rodzaj = QComboBox(minimumWidth=150)
        for tekst, dane in (("Rachunki i faktury", None), ("Tylko rachunki", "Rachunek"), ("Tylko faktury", "Faktura")):
            self.rodzaj.addItem(tekst, dane)
        self.rodzaj.currentIndexChanged.connect(self.filtruj)
        filtry.addWidget(self.rodzaj)
        filtry.addWidget(przycisk("Ten miesiąc", "kalendarz", akcja=self.ten_miesiac))
        filtry.addWidget(przycisk("Wyczyść", styl="plaski", akcja=self.wyczysc_filtry))
        u.addLayout(filtry)
        u.addSpacing(4)

        # --- akcje
        akcje = QHBoxLayout()
        akcje.setSpacing(6)
        self.akcje = [przycisk("Podgląd", "podglad", akcja=self.podglad),
                      przycisk("Drukuj duplikat", "drukarka", akcja=self.drukuj),
                      przycisk("Edytuj", "edytuj", akcja=self.edytuj),
                      przycisk("Historia zmian", "historia", akcja=self.historia_zmian),
                      przycisk("Użyj jako wzór", "kopiuj", akcja=self.wzor)]
        self.btn_anuluj = przycisk("Anuluj dokument", "anuluj", "niebezpieczny", self.anuluj)
        for b in self.akcje + [self.btn_anuluj]:
            akcje.addWidget(b)
        akcje.addStretch()
        self.btn_wszystko = przycisk("Pokaż wszystko", "klucz", akcja=self.pokaz_wszystko)
        akcje.addWidget(self.btn_wszystko)
        u.addLayout(akcje)
        u.addSpacing(6)

        k, ku = karta()
        ku.setContentsMargins(0, 4, 0, 4)
        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(["Numer", "Data", "Pacjent", "Rodzaj", "Płatność", "Kwota"])
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tabela.horizontalHeaderItem(5).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for kol, szer in ((0, 130), (1, 110), (3, 120), (4, 110), (5, 140)):
            self.tabela.setColumnWidth(kol, szer)
        self.tabela.setItemDelegateForColumn(3, PigulkaDelegate(self.tabela))
        self.tabela.setWordWrap(False)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.setShowGrid(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.doubleClicked.connect(self.podglad)
        self.tabela.itemSelectionChanged.connect(self._stan_akcji)
        ku.addWidget(self.tabela)
        self.zaslona_listy = QLabel(
            "Wpisz co najmniej 2 znaki (nazwisko, numer lub PESEL), aby wyszukać.\n"
            "Pełna lista jest dostępna po kliknięciu „Pokaż wszystko” i podaniu hasła.",
            objectName="podtytul", alignment=Qt.AlignmentFlag.AlignCenter)
        self.zaslona_listy.setMinimumHeight(160)
        ku.addWidget(self.zaslona_listy)
        self.pelny_dostep = False
        u.addWidget(k, 1)
        self.podsumowanie = QLabel(objectName="drobny")
        u.addWidget(self.podsumowanie)
        self.docs: list[Dokument] = []

    # ---- filtry
    def _wypelnij_lata(self):
        biezacy = self.rok.currentData()
        lata = sorted(set(self.okno.baza.lata()) | {date.today().year}, reverse=True)
        self.rok.blockSignals(True)
        self.rok.clear()
        self.rok.addItem("Wszystkie lata", 0)
        for r in lata:
            self.rok.addItem(str(r), r)
        i = self.rok.findData(biezacy) if biezacy is not None else 0
        self.rok.setCurrentIndex(max(i, 0))
        self.rok.blockSignals(False)

    def ten_miesiac(self):
        dzis = date.today()
        self.rok.blockSignals(True)
        self.rok.setCurrentIndex(max(self.rok.findData(dzis.year), 0))
        self.rok.blockSignals(False)
        self.miesiac.setCurrentIndex(dzis.month)
        self.filtruj()

    def wyczysc_filtry(self):
        self.szukaj.blockSignals(True)
        self.szukaj.clear()
        self.szukaj.blockSignals(False)
        for pole in (self.rok, self.miesiac, self.rodzaj):
            pole.blockSignals(True)
            pole.setCurrentIndex(0)
            pole.blockSignals(False)
        self.filtruj()

    def opis_okresu(self) -> str:
        rok, mies = self.rok.currentData() or 0, self.miesiac.currentData() or 0
        if rok and mies:
            return f"{MIESIACE[mies - 1].capitalize()} {rok}"
        if rok:
            return f"Rok {rok}"
        if mies:
            return f"{MIESIACE[mies - 1].capitalize()} (wszystkie lata)"
        return "Wszystkie dokumenty"

    def _stan_akcji(self):
        d = self.wybrany()
        for b in self.akcje:
            b.setEnabled(d is not None)
        self.btn_anuluj.setEnabled(d is not None and d.wazny)
        self.akcje[2].setEnabled(d is not None and d.wazny)

    def odswiez(self):
        self._wypelnij_lata()
        self.filtruj()

    def pokaz_wszystko(self):
        if self.okno.potwierdz_haslem("pokazanie pełnej listy", "Podaj hasło, aby zobaczyć pełną listę."):
            self.pelny_dostep = True
            self.filtruj()

    def _tylko_wyszukiwanie(self) -> bool:
        """Bez hasła widać tylko wyniki wyszukiwania (min. 2 znaki), nie całą listę nazwisk."""
        zablokowane = self.okno.baza.ma_haslo and not self.pelny_dostep and len(self.szukaj.text().strip()) < 2
        self.tabela.setVisible(not zablokowane)
        self.zaslona_listy.setVisible(zablokowane)
        self.btn_wszystko.setVisible(self.okno.baza.ma_haslo and not self.pelny_dostep)
        return zablokowane

    def filtruj(self, *_):
        self.docs = [] if self._tylko_wyszukiwanie() else self.okno.baza.dokumenty(
            self.szukaj.text(), self.rok.currentData() or None, self.miesiac.currentData() or None,
            self.rodzaj.currentData())
        self.tabela.setRowCount(len(self.docs))
        for r, d in enumerate(self.docs):
            wiersz = [d.numer, druk.data_pl(d.data_wystawienia), d.nabywca, "Anulowany" if d.anulowano else d.tytul,
                      d.platnosc, f"{druk.zl(d.suma)} zł"]
            for kol, tekst in enumerate(wiersz):
                item = QTableWidgetItem(tekst)
                if kol == 0:
                    item.setFont(czcionka_cyfr(13, QFont.Weight.DemiBold))
                if kol == 5:
                    item.setFont(czcionka_cyfr(13, QFont.Weight.Medium))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if d.anulowano and kol != 3:
                    item.setForeground(QColor(TEKST_3))
                    f = item.font()
                    f.setStrikeOut(True)
                    item.setFont(f)
                self.tabela.setItem(r, kol, item)
        self.tabela.clearSelection()
        self._stan_akcji()
        p = podsumuj(self.docs)
        czesci = [f"{self.opis_okresu()}: {liczba_dokumentow(p.liczba)}", f"{druk.zl(p.suma)} zł"]
        czesci += [f"{k} {druk.zl(v)} zł" for k, v in sorted(p.wg_platnosci.items())]
        if p.anulowanych:
            czesci.append(f"anulowane: {p.anulowanych}")
        self.podsumowanie.setText("   •   ".join(czesci))

    def wybrany(self) -> Dokument | None:
        wiersze = self.tabela.selectionModel().selectedRows() if self.tabela.selectionModel() else []
        r = wiersze[0].row() if wiersze else -1
        return self.docs[r] if 0 <= r < len(self.docs) else None

    # ---- akcje na dokumencie
    def drukuj(self):
        if d := self.wybrany():
            u = self.okno.baza.ustawienia()
            druk.drukuj(druk.html_dokumentu(d, u, duplikat=True), druk.przygotuj_drukarke(u))
            self.okno.dziennik.zapisz(f"wydruk duplikatu nr {d.numer}")
            self.okno.komunikat(f"Wydrukowano duplikat nr {d.numer}")

    def podglad(self, *_):
        if d := self.wybrany():
            self.okno.podglad(d, duplikat=True)

    def wzor(self):
        if d := self.wybrany():
            s = self.okno.strona_nowy
            s.nabywca.setText(d.nabywca)
            s.nabywca_adres.setText(d.nabywca_adres.replace("\n", ", "))
            s.nabywca_id.setText(d.nabywca_id)
            s.platnosc.setCurrentText(d.platnosc)
            s.ustaw_rodzaj(d.tytul)
            s.tabela.setRowCount(0)
            for p in d.pozycje:
                s.dodaj_pozycje(p.nazwa, p.cena, p.ilosc)
            self.okno.przejdz(STRONA_NOWY, odswiez=False)
            s.pokaz_krok(2)

    def edytuj(self):
        if d := self.wybrany():
            self.okno.edytuj_dokument(d)

    def historia_zmian(self):
        d = self.wybrany()
        if not d:
            return
        wersje = self.okno.baza.wersje(d.id)
        okno = QDialog(self)
        okno.setWindowTitle(f"Historia zmian: nr {d.numer}")
        okno.resize(620, 400)
        u = QVBoxLayout(okno)
        u.setContentsMargins(22, 20, 22, 18)
        t = QLabel(f"Historia zmian dokumentu nr {d.numer}")
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(t)
        if not wersje:
            u.addWidget(QLabel("Dokument nie był poprawiany.", objectName="podtytul"))
        k, ku = karta()
        ku.setContentsMargins(0, 4, 0, 4)
        tabela = QTableWidget(len(wersje), 4)
        tabela.setHorizontalHeaderLabels(["Zmieniono", "Co poprawiono", "Pacjent przed zmianą", "Kwota przed"])
        tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabela.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        tabela.verticalHeader().setVisible(False)
        tabela.setShowGrid(False)
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r, (kiedy, powod, stara) in enumerate(wersje):
            for kol, tekst in enumerate([kiedy[:16], powod or "—", stara.nabywca, f"{druk.zl(stara.suma)} zł"]):
                tabela.setItem(r, kol, QTableWidgetItem(tekst))
        tabela.setColumnWidth(0, 140)
        tabela.setColumnWidth(2, 170)
        tabela.doubleClicked.connect(lambda i: self.okno.podglad(wersje[i.row()][2]))
        ku.addWidget(tabela)
        u.addWidget(k, 1)
        u.addWidget(QLabel("Dwuklik pokazuje dokument sprzed zmiany.", objectName="drobny"))
        u.addWidget(przycisk("Zamknij", akcja=okno.accept), alignment=Qt.AlignmentFlag.AlignRight)
        okno.exec()

    def anuluj(self):
        d = self.wybrany()
        if not d or not d.wazny:
            return
        if not self.okno.potwierdz_haslem("anulowanie dokumentu", f"Anulowanie dokumentu nr {d.numer} wymaga hasła."):
            return
        powod, ok = QInputDialog.getText(
            self, "Anuluj dokument",
            f"Dokument nr {d.numer} ({d.nabywca}, {druk.zl(d.suma)} zł) zostanie oznaczony jako anulowany.\n"
            "Zostaje w historii, a jego numer nie zostanie użyty ponownie.\n\nPowód (opcjonalnie):")
        if not ok:
            return
        self.okno.baza.anuluj(d.id, powod)
        self.okno.dziennik.zapisz(f"anulowanie dokumentu nr {d.numer}")
        self.okno.komunikat(f"Anulowano dokument nr {d.numer}")
        self.filtruj()

    # ---- zestawienie wyników
    def _html_zestawienia(self) -> str:
        filtr = [f"„{self.szukaj.text().strip()}”"] if self.szukaj.text().strip() else []
        if self.rodzaj.currentData():
            filtr.append(self.rodzaj.currentText().lower())
        return druk.html_zestawienia(self.docs, self.okno.baza.ustawienia(), self.opis_okresu(), ", ".join(filtr))

    def drukuj_zestawienie(self):
        if not self.docs:
            QMessageBox.information(self, "Zestawienie", "Brak dokumentów do zestawienia.")
            return
        u = self.okno.baza.ustawienia()
        drukarka = druk.przygotuj_drukarke(u)
        if QPrintDialog(drukarka, self).exec() != QDialog.DialogCode.Accepted:
            return
        druk.drukuj(self._html_zestawienia(), drukarka)
        self.okno.komunikat("Wydrukowano zestawienie")

    def zestawienie_pdf(self):
        if not self.docs:
            QMessageBox.information(self, "Zestawienie", "Brak dokumentów do zestawienia.")
            return
        nazwa = "zestawienie-" + self.opis_okresu().lower().replace(" ", "-").replace("(", "").replace(")", "")
        sciezka, _ = QFileDialog.getSaveFileName(self, "Zapisz zestawienie", str(Path.home() / f"{nazwa}.pdf"),
                                                 "PDF (*.pdf)")
        if sciezka:
            druk.drukuj(self._html_zestawienia(), druk.przygotuj_drukarke(self.okno.baza.ustawienia(), sciezka))
            self.okno.dziennik.zapisz(f"zestawienie PDF ({self.opis_okresu()})")
            self.okno.komunikat(f"Zapisano zestawienie: {sciezka}")

    def eksport(self):
        nazwa = "rachunki-" + self.opis_okresu().lower().replace(" ", "-").replace("(", "").replace(")", "")
        sciezka, _ = QFileDialog.getSaveFileName(self, "Eksport do Excela", str(Path.home() / f"{nazwa}.csv"),
                                                 "CSV (*.csv)")
        if sciezka:
            n = self.okno.baza.eksport_csv(sciezka, self.docs)
            self.okno.dziennik.zapisz(f"eksport CSV ({n} dokumentów)")
            self.okno.komunikat(f"Wyeksportowano: {liczba_dokumentow(n)} → {sciezka}")


class StronaUstawienia(Strona):
    POLA = [("nazwa", "Nazwa"), ("nip", "NIP"), ("regon", "REGON"), ("miejsce", "Miejsce wystawienia"),
            ("konto", "Nr konta do przelewów"),
            ("format_numeru", "Numer rachunku"),
            ("format_numeru_faktury", "Numer faktury")]

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, przewijana=True)
        u = self.uklad
        gora = QWidget()
        gora.setMaximumWidth(760)
        naglowek = QHBoxLayout(gora)
        naglowek.setContentsMargins(0, 0, 0, 0)
        naglowek.addLayout(naglowek_strony("Ustawienia", "Dane gabinetu, wydruk i bezpieczeństwo."))
        naglowek.addStretch()
        self.btn_zablokuj_ust = przycisk("Zablokuj", "klodka", akcja=self.zablokuj_ustawienia)
        naglowek.addWidget(self.btn_zablokuj_ust, alignment=Qt.AlignmentFlag.AlignBottom)
        self.btn_zapisz = przycisk("Zapisz zmiany", styl="glowny", akcja=self.zapisz)
        naglowek.addWidget(self.btn_zapisz, alignment=Qt.AlignmentFlag.AlignBottom)
        u.addWidget(gora)
        u.addSpacing(10)

        # zasłona: ustawienia otwierają się dopiero po podaniu hasła
        self.zaslona, zu = karta()
        self.zaslona.setMaximumWidth(760)
        zu.setContentsMargins(40, 48, 40, 48)
        zu.setSpacing(10)
        znak = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter)
        znak.setPixmap(pixmapa("klodka", TEKST_3, 32))
        zu.addWidget(znak)
        t = QLabel("Ustawienia są zablokowane", alignment=Qt.AlignmentFlag.AlignHCenter)
        t.setStyleSheet("font-size: 17px; font-weight: 600;")
        zu.addWidget(t)
        zu.addWidget(QLabel("Zmiana danych gabinetu, hasła i kopii zapasowych wymaga hasła.",
                            objectName="podtytul", alignment=Qt.AlignmentFlag.AlignHCenter))
        zu.addSpacing(8)
        zu.addWidget(przycisk("Odblokuj", "klucz", "glowny", self.odblokuj), alignment=Qt.AlignmentFlag.AlignHCenter)
        u.addWidget(self.zaslona)
        self.odblokowane = False

        kolumna = QWidget()
        self.kolumna = kolumna
        kolumna.setMaximumWidth(760)
        lewa = QVBoxLayout(kolumna)
        lewa.setContentsMargins(0, 0, 0, 0)
        lewa.setSpacing(8)
        prawa = lewa
        u.addWidget(kolumna)
        self.pola: dict[str, QLineEdit | QPlainTextEdit | QComboBox] = {}

        # --- gabinet
        lewa.addWidget(sekcja("Gabinet"))
        k, ku = karta()
        f = self._formularz(ku)
        for klucz, etykieta in self.POLA:
            self.pola[klucz] = QLineEdit()
            f.addRow(etykieta, self.pola[klucz])
            if klucz == "nip":
                self.pola["adres"] = QPlainTextEdit(maximumHeight=58)
                f.addRow("Adres", self.pola["adres"])
        for klucz in ("format_numeru", "format_numeru_faktury"):
            self.pola[klucz].setToolTip("{n} = kolejny numer, {mm} = miesiąc, {rrrr} = rok")
        lewa.addWidget(k)
        lewa.addSpacing(10)

        # --- dokument
        lewa.addWidget(sekcja("Dokument"))
        k, ku = karta()
        f = self._formularz(ku)
        self.pola["tytul"] = QComboBox()
        self.pola["tytul"].addItems(["Rachunek", "Faktura"])
        f.addRow("Domyślny dokument", self.pola["tytul"])
        self.pola["adnotacja"] = QPlainTextEdit(maximumHeight=58)
        f.addRow("Adnotacja VAT", self.pola["adnotacja"])
        self.logo = "domyslne"
        self.podglad_logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.podglad_logo.setFixedSize(56, 56)
        self.podglad_logo.setStyleSheet(f"background: {TLO}; border-radius: 8px; color: {TEKST_2}; font-size: 11px;")
        logo = QHBoxLayout()
        logo.setSpacing(10)
        logo.addWidget(self.podglad_logo)
        przyc = QVBoxLayout()
        przyc.setSpacing(2)
        przyc.addWidget(przycisk("Wybierz z pliku…", "obraz", "plaski", self.wybierz_logo),
                        alignment=Qt.AlignmentFlag.AlignLeft)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Logo gabinetu", styl="plaski", akcja=lambda: self.ustaw_logo("domyslne")))
        rzad.addWidget(przycisk("Bez logo", styl="plaski", akcja=lambda: self.ustaw_logo("")))
        rzad.addStretch()
        przyc.addLayout(rzad)
        logo.addLayout(przyc)
        logo.addStretch()
        f.addRow("Logo", logo)
        lewa.addWidget(k)
        lewa.addSpacing(10)

        # --- usługi
        prawa.addWidget(sekcja("Cennik usług"))
        k, ku = karta()
        ku.setContentsMargins(0, 8, 0, 12)
        self.cennik = QTableWidget(0, 2)
        self.cennik.setHorizontalHeaderLabels(["Usługa", "Cena (zł)"])
        self.cennik.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cennik.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.cennik.setColumnWidth(1, 140)
        self.cennik.verticalHeader().setVisible(False)
        self.cennik.verticalHeader().setDefaultSectionSize(36)
        self.cennik.setShowGrid(False)
        self.cennik.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cennik.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cennik.setMinimumHeight(290)
        ku.addWidget(self.cennik)
        rzad = QHBoxLayout()
        rzad.setContentsMargins(12, 0, 12, 0)
        rzad.addWidget(przycisk("Dodaj usługę", "plus", "plaski", lambda: self._dodaj_do_cennika()))
        rzad.addWidget(przycisk("Usuń", "kosz", "plaski", self._usun_z_cennika))
        rzad.addStretch()
        rzad.addWidget(przycisk("W górę", styl="plaski", akcja=lambda: self._przesun_w_cenniku(-1)))
        rzad.addWidget(przycisk("W dół", styl="plaski", akcja=lambda: self._przesun_w_cenniku(1)))
        ku.addLayout(rzad)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- drukowanie
        prawa.addWidget(sekcja("Drukowanie"))
        k, ku = karta()
        f = self._formularz(ku)
        self.pola["drukarka"] = QComboBox()
        f.addRow("Drukarka", self.pola["drukarka"])
        self.okno_drukarki = QCheckBox("Pytaj o drukarkę przed każdym wydrukiem")
        self.kopia = QCheckBox("Domyślnie drukuj oryginał i kopię")
        self.data_wydruku = QCheckBox("Drukuj na dokumencie datę i godzinę wydruku")
        self.data_wygenerowania = QCheckBox("Drukuj na zestawieniach datę i godzinę wygenerowania")
        self.druk_pesel = QCheckBox("Drukuj PESEL pacjenta na rachunku (nie jest wymagany)")
        for w in (self.okno_drukarki, self.kopia, self.data_wydruku, self.data_wygenerowania, self.druk_pesel):
            ku.addWidget(w)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- bezpieczeństwo
        prawa.addWidget(sekcja("Bezpieczeństwo"))
        k, ku = karta()
        stan = QHBoxLayout()
        self.ikona_stanu = QLabel()
        stan.addWidget(self.ikona_stanu, alignment=Qt.AlignmentFlag.AlignTop)
        self.stan_hasla = QLabel(wordWrap=True)
        stan.addWidget(self.stan_hasla, 1)
        ku.addLayout(stan)
        rzad_blokady = QHBoxLayout()
        rzad_blokady.addWidget(QLabel("Blokuj automatycznie po", objectName="etykieta"))
        self.blokada_minut = QSpinBox(minimum=1, maximum=240, suffix=" min bezczynności")
        self.blokada_minut.setFixedWidth(190)
        rzad_blokady.addWidget(self.blokada_minut)
        rzad_blokady.addStretch()
        ku.addLayout(rzad_blokady)
        rzad = QHBoxLayout()
        self.btn_haslo = przycisk("", "klucz", akcja=self.zmien_haslo)
        self.btn_usun_haslo = przycisk("Odszyfruj", "klodka_otwarta", akcja=self.usun_haslo)
        rzad.addWidget(self.btn_haslo)
        rzad.addWidget(self.btn_usun_haslo)
        rzad.addWidget(przycisk("Dziennik logowań", "lista", akcja=self.pokaz_dziennik))
        rzad.addStretch()
        ku.addLayout(rzad)
        ku.addWidget(separator())
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Szyfrowana kopia…", "archiwum", akcja=self.kopia_zapasowa))
        rzad.addWidget(przycisk("Przywróć…", "przywroc", akcja=self.przywroc))
        rzad.addWidget(przycisk("Eksport odszyfrowany…", "pobierz", akcja=self.eksport_odszyfrowany))
        rzad.addStretch()
        ku.addLayout(rzad)
        ku.addWidget(QLabel(f"Kopie automatyczne: {katalog_kopii()}", objectName="drobny", wordWrap=True))
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- RODO
        prawa.addWidget(sekcja("RODO i prywatność"))
        k, ku = karta()
        ku.addWidget(QLabel(
            "Dane pacjentów są zaszyfrowane, listy pokazują tylko wyniki wyszukiwania, a dziennik nie zawiera "
            "nazwisk. Rachunki trzeba przechowywać 5 lat od końca roku, w którym minął termin zapłaty podatku; "
            "po tym czasie dane osobowe można usunąć. Numery i kwoty zostają do rozliczeń.",
            objectName="drobny", wordWrap=True))
        rzad = QHBoxLayout()
        rzad.addWidget(QLabel("Przechowuj dane osobowe przez", objectName="etykieta"))
        self.rodo_lat = QSpinBox(minimum=1, maximum=50, suffix=" lat po roku wystawienia")
        self.rodo_lat.setFixedWidth(230)
        rzad.addWidget(self.rodo_lat)
        rzad.addStretch()
        ku.addLayout(rzad)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Usuń dane po okresie przechowywania…", "tarcza", akcja=self.anonimizuj))
        rzad.addStretch()
        ku.addLayout(rzad)
        ku.addWidget(QLabel("Dane jednej osoby (prawo dostępu) wydrukujesz lub zapiszesz jako PDF "
                            "w Pacjenci → Dane osoby.", objectName="drobny", wordWrap=True))
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- aktualizacje
        prawa.addWidget(sekcja("Praca w tle i Windows"))
        k, ku = karta()
        f = self._formularz(ku)
        self.tryb = QComboBox()
        self.tryb.addItem("Prowadzący: krok po kroku", "prowadzacy")
        self.tryb.addItem("Zaawansowany: wszystko w jednym oknie", "zaawansowany")
        f.addRow("Wystawianie", self.tryb)
        self.w_tle = QCheckBox("Działaj w tle: zamknięcie okna chowa program obok zegara")
        self.autostart = QCheckBox("Uruchamiaj razem z Windows")
        self.menu_kontekstowe = QCheckBox("„Dodaj do Fakturnika” w menu prawego przycisku myszy (PDF i zdjęcia)")
        for w in (self.w_tle, self.autostart, self.menu_kontekstowe):
            ku.addWidget(w)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Utwórz skrót na pulpicie", "plus", akcja=self._skrot))
        rzad.addStretch()
        ku.addLayout(rzad)
        if not integracja_dostepna():
            for w in (self.autostart, self.menu_kontekstowe):
                w.setEnabled(False)
            ku.addWidget(QLabel("Autostart, menu prawego przycisku i skrót działają w wersji .exe na Windows.",
                                objectName="drobny", wordWrap=True))
        prawa.addWidget(k)
        prawa.addSpacing(10)

        prawa.addWidget(sekcja("Aktualizacje"))
        k, ku = karta()
        rzad = QHBoxLayout()
        rzad.addWidget(QLabel(f"Wersja {WERSJA}"))
        rzad.addStretch()
        rzad.addWidget(przycisk("Sprawdź teraz", "odswiez", akcja=lambda: self.okno.sprawdz_aktualizacje(cicho=False)))
        ku.addLayout(rzad)
        self.auto_aktualizacje = QCheckBox("Sprawdzaj przy uruchomieniu programu")
        ku.addWidget(self.auto_aktualizacje)
        ku.addWidget(QLabel("Aktualizacja wymienia tylko program. Dane zostają, a przed instalacją "
                            "program robi ich kopię.", objectName="drobny", wordWrap=True))
        prawa.addWidget(k)
        prawa.addSpacing(14)

        autor = QLabel('<a href="https://teodorteo.com" style="color: #8e8e93; text-decoration: none;">'
                       'TeodorTeo.com</a>', objectName="drobny")
        autor.setOpenExternalLinks(True)
        autor.setCursor(Qt.CursorShape.PointingHandCursor)
        prawa.addWidget(autor, alignment=Qt.AlignmentFlag.AlignHCenter)
        u.addStretch()

    @staticmethod
    def _formularz(uklad: QVBoxLayout) -> QFormLayout:
        f = QFormLayout()
        f.setHorizontalSpacing(16)
        f.setVerticalSpacing(10)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        uklad.addLayout(f)
        return f

    def _skrot(self):
        if utworz_skrot_na_pulpicie():
            self.okno.komunikat("Utworzono skrót na pulpicie")
        else:
            self.okno.komunikat("Skrót można utworzyć tylko w wersji .exe na Windows", blad=True)

    def zablokuj_ustawienia(self):
        self.odblokowane = False
        self._pokaz_stan_blokady()

    def odblokuj(self):
        if self.okno.potwierdz_haslem("odblokowanie ustawień", "Podaj hasło, aby zmienić ustawienia."):
            self.odblokowane = True
            self._pokaz_stan_blokady()

    def _pokaz_stan_blokady(self):
        zablokowane = self.okno.baza.ma_haslo and not self.odblokowane
        self.zaslona.setVisible(zablokowane)
        self.kolumna.setVisible(not zablokowane)
        self.btn_zapisz.setVisible(not zablokowane)
        self.btn_zablokuj_ust.setVisible(self.okno.baza.ma_haslo and not zablokowane)

    def odswiez(self):
        self._pokaz_stan_blokady()
        u = self.okno.baza.ustawienia()
        drukarki = self.pola["drukarka"]
        drukarki.clear()
        drukarki.addItem("Domyślna drukarka systemu", "")
        for nazwa in druk.dostepne_drukarki():
            drukarki.addItem(nazwa, nazwa)
        for klucz, p in self.pola.items():
            if isinstance(p, QComboBox):
                i = p.findData(u[klucz]) if klucz == "drukarka" else p.findText(u[klucz])
                p.setCurrentIndex(max(i, 0))
            elif isinstance(p, QPlainTextEdit):
                p.setPlainText(u[klucz])
            else:
                p.setText(u[klucz])
        self.okno_drukarki.setChecked(u["okno_drukarki"] == "1")
        self.data_wydruku.setChecked(u["druk_data_wydruku"] == "1")
        self.data_wygenerowania.setChecked(u["druk_data_wygenerowania"] == "1")
        self.druk_pesel.setChecked(u["druk_pesel"] == "1")
        self.rodo_lat.setValue(int(liczba(u["rodo_lat"]) or 5))
        self.cennik.setRowCount(0)
        for linia in u["uslugi"].splitlines():
            nazwa, _, cena = linia.partition(";")
            if nazwa.strip():
                self._dodaj_do_cennika(nazwa.strip(), liczba(cena))
        self.kopia.setChecked(u["kopia"] == "1")
        self.auto_aktualizacje.setChecked(u["auto_aktualizacje"] == "1")
        self.tryb.setCurrentIndex(max(self.tryb.findData(u["tryb"]), 0))
        self.blokada_minut.setValue(int(liczba(u["blokada_minut"]) or 10))
        self.w_tle.setChecked(u["w_tle"] == "1")
        self.autostart.setChecked(autostart_wlaczony())
        self.menu_kontekstowe.setChecked(menu_kontekstowe_wlaczone())
        self.ustaw_logo(u["logo"])
        ma = self.okno.baza.ma_haslo
        self.ikona_stanu.setPixmap(pixmapa("tarcza" if ma else "uwaga", ZIELONY if ma else CZERWONY, 18))
        self.stan_hasla.setText(
            f"Dane są zaszyfrowane (AES-256). Program blokuje się po {u['blokada_minut']} min bezczynności."
            if ma else "Dane nie są zaszyfrowane. Ustaw hasło, żeby chronić dane pacjentów.")
        self.btn_haslo.setText("Zmień hasło" if ma else "Ustaw hasło")
        self.btn_usun_haslo.setVisible(ma)

    def zapisz(self):
        wartosci = {}
        for klucz, p in self.pola.items():
            if isinstance(p, QComboBox):
                wartosci[klucz] = p.currentData() if klucz == "drukarka" else p.currentText()
            elif isinstance(p, QPlainTextEdit):
                wartosci[klucz] = p.toPlainText().strip()
            else:
                wartosci[klucz] = p.text().strip()
        if "{n}" not in wartosci["format_numeru"] or "{n}" not in wartosci["format_numeru_faktury"]:
            QMessageBox.warning(self, "Format numeru", "Format numeru musi zawierać {n} (kolejny numer).")
            return
        if wartosci["format_numeru"] == wartosci["format_numeru_faktury"]:
            QMessageBox.warning(self, "Format numeru", "Rachunki i faktury muszą mieć różne formaty numeru, "
                                "np. faktury z przedrostkiem FV/.")
            return
        nip = wartosci["nip"]
        if nip and not nip_poprawny(nip) and QMessageBox.warning(
                self, "NIP", f"NIP „{nip}” ma złą cyfrę kontrolną. Zapisać mimo to?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        konto = wartosci["konto"]
        if konto:
            if not konto_poprawne(konto) and QMessageBox.warning(
                    self, "Numer konta", f"Numer konta „{konto}” wygląda na błędny (zła suma kontrolna). "
                    "Zapisać mimo to?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            wartosci["konto"] = formatuj_konto(konto)
        wartosci["uslugi"] = self._tekst_cennika()
        wartosci["logo"] = self.logo
        wartosci["okno_drukarki"] = "1" if self.okno_drukarki.isChecked() else "0"
        wartosci["druk_data_wydruku"] = "1" if self.data_wydruku.isChecked() else "0"
        wartosci["druk_data_wygenerowania"] = "1" if self.data_wygenerowania.isChecked() else "0"
        wartosci["kopia"] = "1" if self.kopia.isChecked() else "0"
        wartosci["druk_pesel"] = "1" if self.druk_pesel.isChecked() else "0"
        wartosci["rodo_lat"] = str(self.rodo_lat.value())
        wartosci["auto_aktualizacje"] = "1" if self.auto_aktualizacje.isChecked() else "0"
        wartosci["w_tle"] = "1" if self.w_tle.isChecked() else "0"
        wartosci["tryb"] = self.tryb.currentData()
        wartosci["blokada_minut"] = str(self.blokada_minut.value())
        if integracja_dostepna():
            ustaw_autostart(self.autostart.isChecked())
            ustaw_menu_kontekstowe(self.menu_kontekstowe.isChecked())
        self.okno.baza.zapisz_ustawienia(wartosci)
        self.okno.komunikat("Zapisano ustawienia")
        self.okno.strona_nowy.ustaw_tryb(wartosci["tryb"])
        self.okno.ustaw_czas_blokady()
        self.okno.przejdz(STRONA_NOWY)

    def anonimizuj(self):
        lat = self.rodo_lat.value()
        baza = self.okno.baza
        ile = baza.do_anonimizacji(lat)
        granica = baza.granica_retencji(lat)
        if not ile:
            QMessageBox.information(self, "RODO", f"Nie ma dokumentów z {granica} roku ani starszych "
                                    "z danymi osobowymi do usunięcia.")
            return
        if QMessageBox.warning(
                self, "Usuń dane osobowe",
                f"Z {ile} dokumentów wystawionych w {granica} roku i wcześniej zostaną trwale usunięte "
                "imię i nazwisko, PESEL/NIP i adres (także z wcześniejszych wersji i kartoteki). "
                "Numery, daty i kwoty zostają.\n\nTego nie da się cofnąć (poza przywróceniem kopii). Kontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if not self.okno.potwierdz_haslem("Usunięcie danych osobowych"):
            return
        zrobiono = baza.anonimizuj_starsze(lat)
        self.okno.dziennik.zapisz(f"RODO: zanonimizowano {zrobiono} dokumentów do roku {granica}")
        self.okno.komunikat(f"Usunięto dane osobowe z {zrobiono} dokumentów")

    def _dodaj_do_cennika(self, nazwa: str = "", cena: float = 0.0):
        r = self.cennik.rowCount()
        self.cennik.insertRow(r)
        self.cennik.setItem(r, 0, QTableWidgetItem(nazwa))
        cena_item = QTableWidgetItem(druk.zl(cena) if cena else "")
        cena_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.cennik.setItem(r, 1, cena_item)
        if not nazwa:
            self.cennik.setCurrentCell(r, 0)
            self.cennik.editItem(self.cennik.item(r, 0))

    def _usun_z_cennika(self):
        r = self.cennik.currentRow()
        if r >= 0:
            self.cennik.removeRow(r)

    def _przesun_w_cenniku(self, kierunek: int):
        r = self.cennik.currentRow()
        cel = r + kierunek
        if r < 0 or not 0 <= cel < self.cennik.rowCount():
            return
        for kol in range(2):
            a, b = self.cennik.takeItem(r, kol), self.cennik.takeItem(cel, kol)
            self.cennik.setItem(r, kol, b)
            self.cennik.setItem(cel, kol, a)
        self.cennik.setCurrentCell(cel, 0)

    def _tekst_cennika(self) -> str:
        wiersze = []
        for r in range(self.cennik.rowCount()):
            nazwa = (self.cennik.item(r, 0).text() if self.cennik.item(r, 0) else "").strip().replace(";", ",")
            cena = liczba(self.cennik.item(r, 1).text()) if self.cennik.item(r, 1) else 0
            if nazwa:
                wiersze.append(f"{nazwa};{cena:g}")
        return "\n".join(wiersze)

    def ustaw_logo(self, wartosc: str):
        self.logo = wartosc
        dane = druk.logo_bajty({"logo": wartosc})
        if dane:
            obraz = QPixmap()
            obraz.loadFromData(dane)
            self.podglad_logo.setPixmap(obraz.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))
        else:
            self.podglad_logo.clear()
            self.podglad_logo.setText("brak")

    def wybierz_logo(self):
        sciezka, _ = QFileDialog.getOpenFileName(self, "Wybierz logo", str(Path.home()),
                                                 "Obrazy (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not sciezka:
            return
        obraz = QImage(sciezka)
        if obraz.isNull():
            QMessageBox.warning(self, "Logo", "Nie udało się wczytać tego obrazu.")
            return
        if obraz.height() > 400:
            obraz = obraz.scaledToHeight(400, Qt.TransformationMode.SmoothTransformation)
        bufor = QByteArray()
        io = QBuffer(bufor)
        io.open(QIODevice.OpenModeFlag.WriteOnly)
        obraz.save(io, "PNG")
        self.ustaw_logo(base64.b64encode(bytes(bufor)).decode("ascii"))
        self.okno.komunikat("Wybrano logo. Kliknij „Zapisz zmiany”.")

    def _potwierdz_obecne(self) -> bool:
        if not self.okno.baza.ma_haslo:
            return True
        return OknoHasla(self.okno.baza.sprawdz_haslo, "Potwierdź hasło", self, self.okno.dziennik,
                         "potwierdzenie hasła", "Podaj obecne hasło.").exec() == QDialog.DialogCode.Accepted

    def zmien_haslo(self):
        if not self._potwierdz_obecne():
            return
        okno = OknoNowegoHasla(self)
        if okno.exec() == QDialog.DialogCode.Accepted:
            self.okno.dziennik.zapisz("zmiana hasła" if self.okno.baza.ma_haslo else "ustawienie hasła (szyfrowanie)")
            self.okno.baza.ustaw_haslo(okno.haslo.text())
            self.okno.komunikat("Hasło ustawione, dane zaszyfrowane")
            self.odswiez()

    def usun_haslo(self):
        if not self._potwierdz_obecne():
            return
        if QMessageBox.question(self, "Odszyfruj dane", "Hasło zostanie usunięte, a dane przestaną być "
                                "zaszyfrowane. Kontynuować?") == QMessageBox.StandardButton.Yes:
            self.okno.baza.ustaw_haslo(None)
            self.okno.dziennik.zapisz("usunięcie hasła (odszyfrowanie danych)")
            self.okno.komunikat("Hasło usunięte, dane odszyfrowane")
            self.odswiez()

    def pokaz_dziennik(self):
        d = self.okno.dziennik
        okno = QDialog(self)
        okno.setWindowTitle("Dziennik logowań")
        okno.resize(640, 480)
        u = QVBoxLayout(okno)
        u.setContentsMargins(22, 20, 22, 18)
        nienaruszony = d.nienaruszony()
        stan = QHBoxLayout()
        znak = QLabel()
        znak.setPixmap(pixmapa("ok" if nienaruszony else "uwaga", ZIELONY if nienaruszony else CZERWONY, 18))
        stan.addWidget(znak)
        stan.addWidget(QLabel("Dziennik jest nienaruszony (łańcuch SHA-256 się zgadza)." if nienaruszony
                              else "Uwaga: dziennik został zmieniony lub usunięto z niego wpisy."), 1)
        u.addLayout(stan)
        k, ku = karta()
        ku.setContentsMargins(0, 4, 0, 4)
        tabela = QTableWidget(0, 2)
        tabela.setHorizontalHeaderLabels(["Czas", "Zdarzenie"])
        tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabela.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        tabela.verticalHeader().setVisible(False)
        tabela.verticalHeader().setDefaultSectionSize(32)
        tabela.setShowGrid(False)
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        wpisy = list(reversed(d.wpisy()))
        tabela.setRowCount(len(wpisy))
        for r, (czas, zdarzenie, _) in enumerate(wpisy):
            tabela.setItem(r, 0, QTableWidgetItem(czas))
            tabela.setItem(r, 1, QTableWidgetItem(zdarzenie))
        tabela.setColumnWidth(0, 170)
        ku.addWidget(tabela)
        u.addWidget(k, 1)
        u.addWidget(przycisk("Zamknij", akcja=okno.accept), alignment=Qt.AlignmentFlag.AlignRight)
        okno.exec()

    def przywroc(self):
        if not self.okno.potwierdz_haslem("przywracanie kopii", "Przywrócenie danych z kopii wymaga hasła."):
            return
        sciezka, _ = QFileDialog.getOpenFileName(self, "Przywróć z kopii", str(katalog_kopii()),
                                                 "Kopia Fakturnika (*.fkopia *.zip *.db)")
        if not sciezka:
            return
        if QMessageBox.warning(self, "Przywróć z kopii",
                               "Obecne dane zostaną zastąpione danymi z kopii. Kontynuować?",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        haslo = None
        if self._kopia_wymaga_hasla(sciezka) or Baza.czy_kopia_szyfrowana(sciezka):
            haslo, ok = QInputDialog.getText(self, "Hasło kopii", "Hasło, którym zaszyfrowano kopię:",
                                             QLineEdit.EchoMode.Password)
            if not ok:
                return
        # na wszelki wypadek: kopia obecnego stanu, zanim zostanie zastąpiony
        kopia_automatyczna(self.okno.baza.sciezka, nazwa=f"przed-przywroceniem-{date.today().isoformat()}.db")
        try:
            self.okno.baza.przywroc(sciezka, haslo)
        except (BledneHaslo, ValueError, NowszaBaza, PermissionError, KeyError) as e:
            self.okno.dziennik.zapisz("przywrócenie kopii: NIEUDANE")
            QMessageBox.critical(self, "Nie udało się przywrócić", str(e))
            return
        self.okno.dziennik.zapisz("przywrócenie danych z kopii")
        self.okno.komunikat("Przywrócono dane z kopii")
        self.okno.przejdz(STRONA_HISTORIA)

    @staticmethod
    def _kopia_wymaga_hasla(sciezka: str) -> bool:
        import zipfile
        if zipfile.is_zipfile(sciezka):
            with zipfile.ZipFile(sciezka) as z:
                return z.read("fakturnik.db")[:64].startswith(b"FAKTURNIK-AES")
        return Baza.wymaga_hasla(sciezka)

    def eksport_odszyfrowany(self):
        if not self._potwierdz_obecne():
            return
        if self.okno.baza.ma_haslo and QMessageBox.warning(
                self, "Eksport odszyfrowany",
                "Plik nie będzie zaszyfrowany: każdy, kto go otworzy, zobaczy dane pacjentów. Kontynuować?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        sciezka, _ = QFileDialog.getSaveFileName(
            self, "Eksport odszyfrowany", str(Path.home() / f"fakturnik-odszyfrowany-{date.today().isoformat()}.db"),
            "Baza SQLite (*.db)")
        if sciezka:
            self.okno.baza.eksport_odszyfrowany(sciezka)
            self.okno.dziennik.zapisz("eksport odszyfrowanej kopii danych")
            self.okno.komunikat(f"Zapisano: {sciezka}")

    def kopia_zapasowa(self):
        haslo = OknoNowegoHasla(self, "Hasło kopii zapasowej",
                                "Kopia (dane i wrzucone pliki) zostanie zaszyfrowana AES-256 tym hasłem. "
                                "Może być inne niż hasło programu, np. do kopii na pendrive lub w chmurze.")
        if haslo.exec() != QDialog.DialogCode.Accepted:
            return
        nazwa = f"fakturnik-kopia-{date.today().isoformat()}.fkopia"
        sciezka, _ = QFileDialog.getSaveFileName(self, "Szyfrowana kopia zapasowa", str(Path.home() / nazwa),
                                                 "Szyfrowana kopia Fakturnika (*.fkopia)")
        if not sciezka:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.okno.baza.kopia_zaszyfrowana(sciezka, haslo.haslo.text())
        finally:
            QApplication.restoreOverrideCursor()
        self.okno.dziennik.zapisz("szyfrowana kopia zapasowa")
        self.okno.komunikat("Zapisano szyfrowaną kopię zapasową")


# ---------------------------------------------------------------- wrzucone pliki

def rozmiar_tekst(bajty: int) -> str:
    if bajty < 1024 * 1024:
        return f"{max(1, round(bajty / 1024))} KB"
    return f"{bajty / 1024 / 1024:.1f} MB".replace(".", ",")


class OknoOpisuPliku(QDialog):
    """Opis wrzucanych plików: data, rodzaj, pacjent lub kontrahent, notatka."""

    def __init__(self, baza: Baza, nazwy: list[str], parent=None, plik: Plik | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edytuj opis" if plik else "Dodaj pliki")
        self.setFixedWidth(460)
        u = QVBoxLayout(self)
        u.setContentsMargins(24, 22, 24, 20)
        u.setSpacing(10)
        t = QLabel("Edytuj opis pliku" if plik else ("Dodaj plik" if len(nazwy) == 1 else f"Dodaj pliki ({len(nazwy)})"))
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(t)
        lista = QLabel("\n".join(nazwy[:6]) + (f"\n… i {len(nazwy) - 6} więcej" if len(nazwy) > 6 else ""),
                       objectName="drobny", wordWrap=True)
        u.addWidget(lista)
        self.data = QDateEdit(QDate.fromString(plik.data, "yyyy-MM-dd") if plik else QDate.currentDate(),
                              calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.kategoria = QComboBox(editable=True)
        self.kategoria.addItems(KATEGORIE_PLIKOW)
        if plik:
            self.kategoria.setCurrentText(plik.kategoria)
        self.osoba = QLineEdit(plik.osoba if plik else "", placeholderText="Np. pacjent albo firma (opcjonalnie)")
        podpowiedzi = QCompleter(sorted({p.nazwa for p in baza.pacjenci()} | {p.osoba for p in baza.pliki() if p.osoba}))
        podpowiedzi.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        podpowiedzi.setFilterMode(Qt.MatchFlag.MatchContains)
        self.osoba.setCompleter(podpowiedzi)
        self.opis = QLineEdit(plik.opis if plik else "", placeholderText="Np. prąd za wrzesień (opcjonalnie)")
        rzad = QHBoxLayout()
        rzad.addLayout(pole("Data dokumentu", self.data))
        rzad.addLayout(pole("Rodzaj", self.kategoria), 1)
        u.addLayout(rzad)
        u.addLayout(pole("Pacjent lub kontrahent", self.osoba))
        u.addLayout(pole("Opis", self.opis))
        u.addSpacing(4)
        przyciski = QHBoxLayout()
        przyciski.addStretch()
        przyciski.addWidget(przycisk("Anuluj", akcja=self.reject))
        przyciski.addWidget(przycisk("Zapisz" if plik else "Dodaj", styl="glowny", akcja=self.accept))
        u.addLayout(przyciski)

    def wartosci(self) -> dict:
        return {"data": self.data.date().toPython().isoformat(), "kategoria": self.kategoria.currentText().strip(),
                "osoba": self.osoba.text(), "opis": self.opis.text()}


class OknoPodgladuPliku(QDialog):
    def __init__(self, plik: Plik, strony: list, parent=None, drukuj=None):
        super().__init__(parent)
        self.setWindowTitle(plik.nazwa)
        self.resize(820, 960)
        u = QVBoxLayout(self)
        u.setContentsMargins(0, 0, 0, 12)
        obszar = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        tresc = QWidget()
        tresc.setStyleSheet("background: #e9e9ec;")
        lista = QVBoxLayout(tresc)
        lista.setContentsMargins(20, 20, 20, 20)
        lista.setSpacing(16)
        for obraz in strony:
            etykieta = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter)
            pix = QPixmap.fromImage(obraz)
            etykieta.setPixmap(pix.scaledToWidth(min(740, pix.width()), Qt.TransformationMode.SmoothTransformation))
            etykieta.setStyleSheet("background: white;")
            lista.addWidget(etykieta, alignment=Qt.AlignmentFlag.AlignHCenter)
        lista.addStretch()
        obszar.setWidget(tresc)
        u.addWidget(obszar, 1)
        rzad = QHBoxLayout()
        rzad.setContentsMargins(16, 0, 16, 0)
        rzad.addWidget(QLabel(f"{plik.nazwa} • stron: {len(strony)}", objectName="drobny"))
        rzad.addStretch()
        if drukuj:
            rzad.addWidget(przycisk("Drukuj", "drukarka", "glowny", drukuj))
        rzad.addWidget(przycisk("Zamknij", akcja=self.accept))
        u.addLayout(rzad)


class StronaPliki(Strona):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno)
        self.setAcceptDrops(True)
        u = self.uklad
        naglowek = QHBoxLayout()
        naglowek.addLayout(naglowek_strony("Pliki", "Wrzucaj faktury kosztowe, skany i zdjęcia dokumentów: "
                                                    "przeciągnij je tutaj albo kliknij „Dodaj pliki”."))
        naglowek.addStretch()
        naglowek.addWidget(przycisk("Dodaj pliki…", "plus", "glowny", self.dodaj), alignment=Qt.AlignmentFlag.AlignBottom)
        u.addLayout(naglowek)
        u.addSpacing(10)

        filtry = QHBoxLayout()
        filtry.setSpacing(8)
        self.szukaj = QLineEdit(placeholderText="Nazwa pliku, pacjent, kontrahent lub opis")
        self.szukaj.addAction(ikona("szukaj"), QLineEdit.ActionPosition.LeadingPosition)
        self.szukaj.setClearButtonEnabled(True)
        self.szukaj.textChanged.connect(self.filtruj)
        filtry.addWidget(self.szukaj, 1)
        self.rok = QComboBox(minimumWidth=110)
        self.rok.currentIndexChanged.connect(self.filtruj)
        filtry.addWidget(self.rok)
        self.miesiac = QComboBox(minimumWidth=140)
        self.miesiac.addItem("Wszystkie miesiące", 0)
        for i, nazwa in enumerate(MIESIACE, 1):
            self.miesiac.addItem(nazwa.capitalize(), i)
        self.miesiac.currentIndexChanged.connect(self.filtruj)
        filtry.addWidget(self.miesiac)
        self.kategoria = QComboBox(minimumWidth=170)
        self.kategoria.currentIndexChanged.connect(self.filtruj)
        filtry.addWidget(self.kategoria)
        u.addLayout(filtry)
        u.addSpacing(4)

        akcje = QHBoxLayout()
        akcje.setSpacing(6)
        self.akcje = [przycisk("Podgląd", "podglad", akcja=self.podglad),
                      przycisk("Drukuj", "drukarka", akcja=self.drukuj),
                      przycisk("Zapisz kopię…", "pobierz", akcja=self.zapisz_kopie),
                      przycisk("Edytuj opis", "lista", akcja=self.edytuj),
                      przycisk("Usuń", "kosz", "niebezpieczny", self.usun)]
        for b in self.akcje:
            akcje.addWidget(b)
        akcje.addStretch()
        self.btn_wszystko = przycisk("Pokaż wszystko", "klucz", akcja=self.pokaz_wszystko)
        akcje.addWidget(self.btn_wszystko)
        u.addLayout(akcje)
        u.addSpacing(6)

        k, ku = karta()
        ku.setContentsMargins(0, 4, 0, 4)
        self.tabela = QTableWidget(0, 5)
        self.tabela.setHorizontalHeaderLabels(["Data", "Plik", "Rodzaj", "Pacjent / kontrahent", "Rozmiar"])
        self.tabela.horizontalHeaderItem(4).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for kol, szer in ((0, 110), (2, 170), (3, 210), (4, 90)):
            self.tabela.setColumnWidth(kol, szer)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.setShowGrid(False)
        self.tabela.setWordWrap(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.doubleClicked.connect(self.podglad)
        self.tabela.itemSelectionChanged.connect(self._stan_akcji)
        ku.addWidget(self.tabela)
        self.zaslona_listy = QLabel(
            "Wpisz co najmniej 2 znaki (nazwisko, numer lub PESEL), aby wyszukać.\n"
            "Pełna lista jest dostępna po kliknięciu „Pokaż wszystko” i podaniu hasła.",
            objectName="podtytul", alignment=Qt.AlignmentFlag.AlignCenter)
        self.zaslona_listy.setMinimumHeight(160)
        ku.addWidget(self.zaslona_listy)
        self.pelny_dostep = False
        u.addWidget(k, 1)
        self.podsumowanie = QLabel(objectName="drobny")
        u.addWidget(self.podsumowanie)
        self.lista: list[Plik] = []

    # ---- przeciąganie plików na okno
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        sciezki = [Path(url.toLocalFile()) for url in e.mimeData().urls() if url.isLocalFile()]
        self._dodaj_sciezki([p for p in sciezki if p.is_file()])

    # ---- lista
    def odswiez(self):
        for pole_wyboru, wartosci, pierwszy in (
                (self.rok, sorted(set(self.okno.baza.lata_plikow()) | {date.today().year}, reverse=True), "Wszystkie lata"),
                (self.kategoria, sorted(set(KATEGORIE_PLIKOW) | {p.kategoria for p in self.okno.baza.pliki() if p.kategoria}),
                 "Wszystkie rodzaje")):
            obecna = pole_wyboru.currentData()
            pole_wyboru.blockSignals(True)
            pole_wyboru.clear()
            pole_wyboru.addItem(pierwszy, None)
            for w in wartosci:
                pole_wyboru.addItem(str(w), w)
            pole_wyboru.setCurrentIndex(max(pole_wyboru.findData(obecna), 0) if obecna is not None else 0)
            pole_wyboru.blockSignals(False)
        self.filtruj()

    def pokaz_wszystko(self):
        if self.okno.potwierdz_haslem("pokazanie pełnej listy", "Podaj hasło, aby zobaczyć pełną listę."):
            self.pelny_dostep = True
            self.filtruj()

    def _tylko_wyszukiwanie(self) -> bool:
        """Bez hasła widać tylko wyniki wyszukiwania (min. 2 znaki), nie całą listę nazwisk."""
        zablokowane = self.okno.baza.ma_haslo and not self.pelny_dostep and len(self.szukaj.text().strip()) < 2
        self.tabela.setVisible(not zablokowane)
        self.zaslona_listy.setVisible(zablokowane)
        self.btn_wszystko.setVisible(self.okno.baza.ma_haslo and not self.pelny_dostep)
        return zablokowane

    def filtruj(self, *_):
        self.lista = [] if self._tylko_wyszukiwanie() else self.okno.baza.pliki(
            self.szukaj.text(), self.rok.currentData(), self.miesiac.currentData() or None,
            self.kategoria.currentData())
        self.tabela.setRowCount(len(self.lista))
        for r, p in enumerate(self.lista):
            for kol, tekst in enumerate([druk.data_pl(p.data), p.nazwa + (f"  ·  {p.opis}" if p.opis else ""),
                                         p.kategoria, p.osoba, rozmiar_tekst(p.rozmiar)]):
                item = QTableWidgetItem(tekst)
                if kol == 1:
                    item.setIcon(ikona("pdf" if p.typ == "pdf" else "obraz"))
                if kol == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(QColor(TEKST_2))
                self.tabela.setItem(r, kol, item)
        self.tabela.clearSelection()
        self._stan_akcji()
        razem = sum(p.rozmiar for p in self.lista)
        self.podsumowanie.setText(f"Plików: {len(self.lista)}   •   {rozmiar_tekst(razem) if razem else '0 KB'}   •   "
                                  "przechowywane zaszyfrowane (AES-256)")

    def _stan_akcji(self):
        for b in self.akcje:
            b.setEnabled(self.wybrany() is not None)

    def wybrany(self) -> Plik | None:
        wiersze = self.tabela.selectionModel().selectedRows() if self.tabela.selectionModel() else []
        r = wiersze[0].row() if wiersze else -1
        return self.lista[r] if 0 <= r < len(self.lista) else None

    # ---- akcje
    def dodaj(self):
        sciezki, _ = QFileDialog.getOpenFileNames(
            self, "Wybierz pliki", str(Path.home()),
            "Dokumenty (*.pdf *.jpg *.jpeg *.png *.gif *.bmp *.webp *.tif *.tiff);;Wszystkie pliki (*)")
        self._dodaj_sciezki([Path(s) for s in sciezki])

    def _dodaj_sciezki(self, sciezki: list[Path]):
        if not sciezki:
            return
        okno = OknoOpisuPliku(self.okno.baza, [p.name for p in sciezki], self)
        if okno.exec() != QDialog.DialogCode.Accepted:
            return
        w = okno.wartosci()
        dodane, bledy = 0, []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for s in sciezki:
                try:
                    self.okno.baza.dodaj_plik(s, w["data"], w["kategoria"], w["osoba"], w["opis"])
                    dodane += 1
                except (ValueError, OSError) as e:
                    bledy.append(str(e))
        finally:
            QApplication.restoreOverrideCursor()
        if dodane:
            self.okno.dziennik.zapisz(f"dodanie plików ({dodane})")
            self.okno.komunikat(f"Dodano pliki: {dodane}")
        if bledy:
            QMessageBox.warning(self, "Nie wszystkie pliki dodano", "\n".join(bledy[:10]))
        self.odswiez()

    def _tresc(self, p: Plik) -> bytes | None:
        try:
            return self.okno.baza.tresc_pliku(p.id)
        except (ValueError, OSError, KeyError) as e:
            QMessageBox.critical(self, "Nie można otworzyć pliku", str(e))
            return None

    def podglad(self, *_):
        p = self.wybrany()
        if not p or (tresc := self._tresc(p)) is None:
            return
        try:
            strony = druk.strony_pliku(tresc, p.typ, dpi=110)
        except (ValueError, ImportError) as e:
            QMessageBox.critical(self, "Podgląd", str(e))
            return
        OknoPodgladuPliku(p, strony, self, drukuj=lambda: self._drukuj(p, tresc)).exec()

    def drukuj(self):
        p = self.wybrany()
        if p and (tresc := self._tresc(p)) is not None:
            self._drukuj(p, tresc)

    def _drukuj(self, p: Plik, tresc: bytes):
        u = self.okno.baza.ustawienia()
        drukarka = druk.przygotuj_drukarke(u)
        if QPrintDialog(drukarka, self).exec() != QDialog.DialogCode.Accepted:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            druk.drukuj_plik(tresc, p.typ, drukarka)
        except (ValueError, RuntimeError, ImportError) as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Drukowanie", str(e))
            return
        QApplication.restoreOverrideCursor()
        self.okno.dziennik.zapisz(f"wydruk pliku nr {p.id}")
        self.okno.komunikat(f"Wydrukowano: {p.nazwa}")

    def zapisz_kopie(self):
        p = self.wybrany()
        if not p or (tresc := self._tresc(p)) is None:
            return
        sciezka, _ = QFileDialog.getSaveFileName(self, "Zapisz kopię pliku", str(Path.home() / p.nazwa))
        if sciezka:
            Path(sciezka).write_bytes(tresc)
            self.okno.dziennik.zapisz(f"zapis kopii pliku nr {p.id} poza programem")
            self.okno.komunikat(f"Zapisano: {sciezka}")

    def edytuj(self):
        p = self.wybrany()
        if not p:
            return
        okno = OknoOpisuPliku(self.okno.baza, [p.nazwa], self, plik=p)
        if okno.exec() == QDialog.DialogCode.Accepted:
            w = okno.wartosci()
            self.okno.baza.zmien_plik(p.id, w["data"], w["kategoria"], w["osoba"], w["opis"])
            self.odswiez()

    def usun(self):
        p = self.wybrany()
        if not p:
            return
        if not self.okno.potwierdz_haslem("usunięcie pliku", f"Usunięcie pliku „{p.nazwa}” wymaga hasła."):
            return
        if QMessageBox.warning(self, "Usuń plik", f"Usunąć plik „{p.nazwa}” z programu?\n\n"
                               "Zostanie jeszcze w kopiach zapasowych.",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        self.okno.baza.usun_plik(p.id)
        self.okno.dziennik.zapisz(f"usunięcie pliku nr {p.id}")
        self.okno.komunikat(f"Usunięto: {p.nazwa}")
        self.odswiez()


class OknoDokumentu(QDialog):
    """Własny podgląd rachunku lub faktury: strony A4, powiększanie, druk, PDF i edycja."""

    def __init__(self, okno: "OknoGlowne", dok: Dokument, z_kopia: bool = False, duplikat: bool = False):
        super().__init__(okno)
        self.okno, self.dok, self.duplikat = okno, dok, duplikat
        self.html = druk.html_dokumentu(dok, okno.baza.ustawienia(), z_kopia, duplikat)
        self.setWindowTitle(f"{dok.tytul} nr {dok.numer}")
        self.resize(980, 900)
        u = QVBoxLayout(self)
        u.setContentsMargins(0, 0, 0, 0)
        u.setSpacing(0)

        pasek = QFrame(objectName="stopka")
        pu = QHBoxLayout(pasek)
        pu.setContentsMargins(20, 10, 20, 10)
        tytul = QLabel(f"{dok.tytul} nr {dok.numer}")
        tytul.setStyleSheet("font-size: 15px; font-weight: 600;")
        pu.addWidget(tytul)
        opis = f"{dok.nabywca}  ·  {druk.data_pl(dok.data_wystawienia)}"
        if dok.poprawiono:
            opis += f"  ·  poprawiony {druk.data_pl(dok.poprawiono)}"
        if dok.anulowano:
            opis += "  ·  anulowany"
        pu.addWidget(QLabel(opis, objectName="drobny"))
        pu.addStretch()
        pu.addWidget(przycisk("", "minus_lupa", "plaski", lambda: self._skala(self.strony.skala - 0.15)))
        self.procent = QLabel(objectName="drobny")
        self.procent.setFixedWidth(44)
        self.procent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pu.addWidget(self.procent)
        pu.addWidget(przycisk("", "plus_lupa", "plaski", lambda: self._skala(self.strony.skala + 0.15)))
        pu.addWidget(przycisk("Dopasuj", styl="plaski", akcja=self._dopasuj))
        u.addWidget(pasek)

        self.obszar = QScrollArea(frameShape=QFrame.Shape.NoFrame, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.obszar.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: #e7eaec; }")
        self.strony = PodgladStron()
        self.strony.ustaw_html(self.html)
        self.obszar.setWidget(self.strony)
        u.addWidget(self.obszar, 1)

        dol = QFrame(objectName="stopka")
        du = QHBoxLayout(dol)
        du.setContentsMargins(20, 12, 20, 12)
        du.addWidget(QLabel(f"Stron: {self.strony.strony()}", objectName="drobny"))
        du.addStretch()
        if dok.id and not dok.anulowano:
            du.addWidget(przycisk("Edytuj", "edytuj", akcja=self.edytuj))
        du.addWidget(przycisk("Zapisz PDF", "pdf", akcja=self.pdf))
        du.addWidget(przycisk("Drukuj", "drukarka", "glowny", self.drukuj))
        du.addWidget(przycisk("Zamknij", akcja=self.accept))
        u.addWidget(dol)
        QShortcut(QKeySequence("Ctrl++"), self, lambda: self._skala(self.strony.skala + 0.15))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self._skala(self.strony.skala - 0.15))
        QTimer.singleShot(0, self._dopasuj)

    def _skala(self, skala: float):
        self.strony.ustaw_skale(skala)
        self.procent.setText(f"{round(self.strony.skala * 100)}%")

    def _dopasuj(self):
        self._skala((self.obszar.viewport().width() - 2 * PodgladStron.ODSTEP - 4) / PodgladStron.A4.width())

    def drukuj(self):
        u = self.okno.baza.ustawienia()
        drukarka = druk.przygotuj_drukarke(u)
        if QPrintDialog(drukarka, self).exec() != QDialog.DialogCode.Accepted:
            return
        druk.drukuj(self.html, drukarka)
        self.okno.dziennik.zapisz(f"wydruk z podglądu: nr {self.dok.numer}")
        self.okno.komunikat(f"Wydrukowano nr {self.dok.numer}")

    def pdf(self):
        sciezka, _ = QFileDialog.getSaveFileName(
            self, "Zapisz PDF", str(Path.home() / f"{self.dok.numer.replace('/', '-')}.pdf"), "PDF (*.pdf)")
        if sciezka:
            druk.drukuj(self.html, druk.przygotuj_drukarke(self.okno.baza.ustawienia(), sciezka))
            self.okno.komunikat(f"Zapisano PDF: {sciezka}")

    def edytuj(self):
        self.accept()
        self.okno.edytuj_dokument(self.dok)


# ---------------------------------------------------------------- okno główne

class OknoGlowne(QMainWindow):
    def __init__(self, baza: Baza, dziennik: Dziennik):
        super().__init__()
        self.baza = baza
        self.dziennik = dziennik
        self.uruchom_po_zamknieciu: Path | None = None
        self._watki: list[Watek] = []
        self.setWindowTitle("Fakturnik")
        self.resize(1320, 860)
        self.setMinimumSize(1040, 700)

        tlo = QWidget()
        uklad = QHBoxLayout(tlo)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        # --- menu boczne (ciemne, w kolorze marki)
        menu = QFrame(objectName="menu")
        menu.setFixedWidth(232)
        m = QVBoxLayout(menu)
        m.setContentsMargins(0, 22, 0, 16)
        m.setSpacing(2)
        marka = QHBoxLayout()
        marka.setContentsMargins(22, 0, 16, 22)
        marka.setSpacing(11)
        znak = QLabel()
        znak.setPixmap(QPixmap(str(ZASOBY / "ikona.png")).scaled(
            34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        marka.addWidget(znak)
        opis = QVBoxLayout()
        opis.setSpacing(1)
        opis.addWidget(QLabel("Fakturnik", objectName="nazwa_programu"))
        opis.addWidget(QLabel("by TeodorTeo.com", objectName="gabinet"))
        marka.addLayout(opis)
        marka.addStretch()
        m.addLayout(marka)

        self.grupa = QButtonGroup(self)
        for i, (nazwa, ik) in enumerate([("Nowy dokument", "nowy"), ("Historia", "historia"), ("Przychody", "wzrost"),
                                         ("Pliki", "archiwum"), ("Ustawienia", "ustawienia")]):
            b = QPushButton(f"   {nazwa}", checkable=True, cursor=Qt.CursorShape.PointingHandCursor)
            b.setIcon(ikona(ik, MENU_TEKST, aktywny="#ffffff"))
            b.clicked.connect(lambda _=False, i=i: self.przejdz(i))
            self.grupa.addButton(b, i)
            m.addWidget(b)
        m.addStretch()
        m.addWidget(QFrame(objectName="menu_linia"))
        m.addSpacing(8)
        self.btn_blokuj = QPushButton("   Zablokuj", cursor=Qt.CursorShape.PointingHandCursor)
        self.btn_blokuj.setIcon(ikona("klodka", MENU_TEKST))
        self.btn_blokuj.clicked.connect(self.zablokuj)
        m.addWidget(self.btn_blokuj)
        self.etykieta_gabinetu = QLabel(objectName="gabinet")
        self.etykieta_gabinetu.setFixedWidth(190)
        self.etykieta_gabinetu.setStyleSheet("padding: 6px 24px 0; color: #a9c3c8;")
        m.addWidget(self.etykieta_gabinetu)
        wersja = QLabel(f"Wersja {WERSJA}")
        wersja.setStyleSheet("color: #6f8f95; font-size: 11px; padding: 2px 24px 0;")
        m.addWidget(wersja)
        uklad.addWidget(menu)

        # --- treść z paskiem aktualizacji
        prawa = QVBoxLayout()
        prawa.setSpacing(0)
        self.pasek_aktualizacji = QFrame(objectName="pasek_aktualizacji")
        pa = QHBoxLayout(self.pasek_aktualizacji)
        pa.setContentsMargins(32, 8, 20, 8)
        ik = QLabel()
        ik.setPixmap(pixmapa("pobierz", AKCENT, 16))
        pa.addWidget(ik)
        self.tekst_aktualizacji = QLabel()
        pa.addWidget(self.tekst_aktualizacji, 1)
        self.btn_instaluj = przycisk("Zainstaluj", styl="glowny", akcja=self.instaluj_aktualizacje)
        pa.addWidget(self.btn_instaluj)
        pa.addWidget(przycisk("", "zamknij", "plaski", self.pasek_aktualizacji.hide))
        self.pasek_aktualizacji.hide()
        prawa.addWidget(self.pasek_aktualizacji)

        self.strony = QStackedWidget()
        self.strona_pulpit = StronaPulpit(self)
        self.strona_nowy = StronaNowy(self)
        self.strona_historia = StronaHistoria(self)
        self.strona_pliki = StronaPliki(self)
        self.strona_ustawienia = StronaUstawienia(self)
        for s in (self.strona_nowy, self.strona_historia, self.strona_pulpit, self.strona_pliki,
                  self.strona_ustawienia):
            self.strony.addWidget(s)
        prawa.addWidget(self.strony, 1)
        uklad.addLayout(prawa, 1)
        self.setCentralWidget(tlo)
        self.powiadomienie = Powiadomienie(tlo)
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self.strona_pulpit._nowy(self.baza.ustawienia()["tytul"]))

        self.strona_nowy.ustaw_tryb(self.baza.ustawienia()["tryb"])
        self.strona_nowy.wyczysc()
        self.przejdz(STRONA_NOWY)

        # automatyczna blokada po bezczynności (tylko gdy jest hasło)
        self.timer = QTimer(self, singleShot=True)
        self.ustaw_czas_blokady()
        self.timer.timeout.connect(self.zablokuj)
        self.straznik = StraznikBezczynnosci(self.timer)
        QApplication.instance().installEventFilter(self.straznik)
        self.timer.start()

        # praca w tle i strażnik integralności (co minutę)
        self._wyjscie = False
        self._ukryty = False
        self._podpowiedz_zasobnika = False
        self._dziennik_zgloszony = False
        zapamietany = self.baza.ustawienia()["ostatni_wpis_dziennika"]
        self._dziennik_uciety = bool(zapamietany) and not self.dziennik.zawiera(zapamietany)
        self.dziennik.po_zapisie = self._zapamietaj_wpis
        self._utworz_zasobnik()
        self.zegar_straznika = QTimer(self, interval=60 * 1000)
        self.zegar_straznika.timeout.connect(self.sprawdz_integralnosc)
        self.zegar_straznika.start()
        QTimer.singleShot(3000, self.sprawdz_integralnosc)

        self.wydanie: aktualizacje.Wydanie | None = None
        if aktualizacje.czy_spakowany() and self.baza.ustawienia()["auto_aktualizacje"] == "1":
            QTimer.singleShot(2500, lambda: self.sprawdz_aktualizacje(cicho=True))
            QTimer.singleShot(6000, self.sprawdz_program)
        if self.baza.ustawienia()["skonfigurowano"] != "1":
            QTimer.singleShot(200, self.pierwsze_uruchomienie)

    def przejdz(self, i: int, odswiez: bool = True):
        if i != STRONA_PRZYCHODY:
            self.strona_pulpit.zaslon()  # kwoty chowają się zawsze po wyjściu z zakładki
        if i != STRONA_USTAWIENIA:
            self.strona_ustawienia.odblokowane = False  # ustawienia blokują się po wyjściu
        if i != STRONA_HISTORIA:
            self.strona_historia.pelny_dostep = False
        if i != STRONA_PLIKI:
            self.strona_pliki.pelny_dostep = False
        self.grupa.button(i).setChecked(True)
        self.strony.setCurrentIndex(i)
        if odswiez:
            self.strony.currentWidget().odswiez()
        self.btn_blokuj.setVisible(self.baza.ma_haslo)
        self._ustaw_nazwe_gabinetu()

    def ustaw_czas_blokady(self):
        minuty = int(liczba(self.baza.ustawienia()["blokada_minut"]) or 10)
        self.timer.setInterval(max(1, minuty) * 60 * 1000)
        self.timer.start()

    def _ustaw_nazwe_gabinetu(self):
        nazwa = self.baza.ustawienia()["nazwa"].split(",")[0].strip()
        miara = self.etykieta_gabinetu.fontMetrics()
        self.etykieta_gabinetu.setText(miara.elidedText(nazwa, Qt.TextElideMode.ElideRight, 150))
        self.etykieta_gabinetu.setToolTip(nazwa)

    def komunikat(self, tekst: str, blad: bool = False):
        self.powiadomienie.pokaz(tekst, blad)

    def podglad(self, dok: Dokument, z_kopia=False, duplikat=False):
        OknoDokumentu(self, dok, z_kopia, duplikat).exec()

    # ---- aktualizacje
    def _w_tle(self, watek: Watek) -> Watek:
        self._watki.append(watek)
        watek.finished.connect(lambda: self._watki.remove(watek) if watek in self._watki else None)
        watek.start()
        return watek

    def sprawdz_aktualizacje(self, cicho: bool):
        if not cicho:
            self.komunikat("Sprawdzanie aktualizacji…")
        w = Watek(aktualizacje.sprawdz)
        w.gotowe.connect(lambda wydanie: self._wynik_sprawdzenia(wydanie, cicho))
        w.blad.connect(lambda tekst: None if cicho else QMessageBox.warning(self, "Aktualizacje", tekst))
        self._w_tle(w)

    def sprawdz_program(self):
        """Czy działający Fakturnik.exe jest tym samym plikiem, który opublikowano w wydaniu."""
        w = Watek(aktualizacje.sprawdz_wlasny_plik)
        w.gotowe.connect(self._wynik_sprawdzenia_programu)
        w.blad.connect(lambda _: None)
        self._w_tle(w)

    def _wynik_sprawdzenia_programu(self, oryginalny):
        if oryginalny is False:
            tekst = ("Plik programu różni się od opublikowanego wydania (mógł zostać zmieniony). "
                     "Pobierz Fakturnik.exe ponownie ze strony wydań i nie wpisuj hasła w tej kopii.")
            self.dziennik.zapisz("STRAŻNIK: plik programu różni się od opublikowanego wydania")
            self.zasobnik.showMessage("Fakturnik: uwaga", tekst, QSystemTrayIcon.MessageIcon.Warning, 15000)
            QMessageBox.critical(self, "Fakturnik", tekst)

    def _wynik_sprawdzenia(self, wydanie, cicho: bool):
        self.wydanie = wydanie
        if wydanie:
            self.tekst_aktualizacji.setText(f"Dostępna jest nowa wersja {wydanie.wersja}. "
                                            "Dane zostaną zachowane.")
            self.pasek_aktualizacji.show()
        elif not cicho:
            QMessageBox.information(self, "Aktualizacje", f"Masz najnowszą wersję ({WERSJA}).")

    def instaluj_aktualizacje(self):
        if not self.wydanie:
            return
        if not aktualizacje.czy_spakowany():
            QMessageBox.information(self, "Aktualizacje", "Aktualizacje instalują się tylko w wersji .exe.")
            return
        opis = self.wydanie.opis.strip()
        if QMessageBox.question(
                self, "Aktualizacja",
                f"Zainstalować wersję {self.wydanie.wersja}?\n\nProgram zrobi kopię danych, pobierze nową "
                f"wersję, sprawdzi jej sumę kontrolną i uruchomi się ponownie. Dane pacjentów i numeracja "
                f"zostają bez zmian." + (f"\n\nZmiany:\n{opis[:600]}" if opis else "")) \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            kopia_automatyczna(self.baza.sciezka, nazwa=f"przed-aktualizacja-do-{self.wydanie.wersja}.db")
        except OSError as e:
            QMessageBox.critical(self, "Aktualizacja", f"Nie udało się zrobić kopii danych, aktualizacja przerwana.\n{e}")
            return
        self.dziennik.zapisz(f"aktualizacja {WERSJA} -> {self.wydanie.wersja}: kopia danych wykonana")

        cel = Path(sys.executable).with_name("Fakturnik.new.exe")
        postep = QProgressDialog("Pobieranie aktualizacji…", "Anuluj", 0, 100, self)
        postep.setWindowTitle("Aktualizacja")
        postep.setWindowModality(Qt.WindowModality.WindowModal)
        postep.setMinimumDuration(0)
        postep.setCancelButton(None)
        w = Watek(aktualizacje.pobierz, self.wydanie, cel, z_postepem=True)
        w.postep.connect(postep.setValue)
        w.gotowe.connect(lambda nowy: (postep.close(), self._zainstaluj(nowy)))
        w.blad.connect(lambda tekst: (postep.close(), self._blad_aktualizacji(tekst)))
        self._w_tle(w)

    def _blad_aktualizacji(self, tekst: str):
        self.dziennik.zapisz("aktualizacja: NIEUDANA")
        odp = QMessageBox.warning(self, "Aktualizacja", f"{tekst}\n\nOtworzyć stronę z pobraniem, "
                                  "żeby zaktualizować ręcznie?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if odp == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(f"https://github.com/{aktualizacje.REPOZYTORIUM}/releases/latest"))

    def _zainstaluj(self, nowy: Path):
        try:
            self.uruchom_po_zamknieciu = aktualizacje.zainstaluj(Path(nowy))
        except OSError as e:
            self._blad_aktualizacji(f"Nie udało się podmienić programu ({e}). Jeśli program leży w folderze "
                                    "Program Files, przenieś go np. na Pulpit.")
            return
        self.dziennik.zapisz(f"aktualizacja do {self.wydanie.wersja}: zainstalowana")
        QMessageBox.information(self, "Aktualizacja", "Aktualizacja zainstalowana. Program uruchomi się ponownie.")
        self._wyjscie = True
        self.close()

    # ---- blokada i zamykanie
    def edytuj_dokument(self, dok: Dokument):
        if dok.anulowano:
            self.komunikat("Anulowanego dokumentu nie można edytować", blad=True)
            return
        if not self.potwierdz_haslem("edycja dokumentu", f"Edycja dokumentu nr {dok.numer} wymaga hasła."):
            return
        if dok.tytul == "Faktura" and QMessageBox.question(
                self, "Edycja faktury",
                "Wydaną już nabywcy fakturę formalnie poprawia się fakturą korygującą. Edycja tutaj zmienia "
                "zapisany dokument (poprzednia wersja zostaje w historii zmian).\n\nKontynuować?") \
                != QMessageBox.StandardButton.Yes:
            return
        self.przejdz(STRONA_NOWY, odswiez=False)
        self.strona_nowy.zaladuj_do_edycji(dok)

    # ---- hasło do ważnych operacji
    def potwierdz_haslem(self, cel: str, opis: str = "Ta operacja wymaga hasła.") -> bool:
        if not self.baza.ma_haslo:
            return True
        return OknoHasla(self.baza.sprawdz_haslo, "Potwierdź hasłem", self, self.dziennik, cel, opis).exec() \
            == QDialog.DialogCode.Accepted

    # ---- praca w tle (zasobnik obok zegara)
    def _utworz_zasobnik(self):
        self.zasobnik = QSystemTrayIcon(QIcon(str(ZASOBY / "ikona.png")), self)
        self.zasobnik.setToolTip("Fakturnik: działa w tle i pilnuje danych")
        menu = QMenu()
        menu.addAction(ikona("nowy", TEKST_2), "Otwórz Fakturnik", self.pokaz_okno)
        menu.addAction(ikona("plus", TEKST_2), "Nowy rachunek", lambda: self._nowy_z_zasobnika("Rachunek"))
        menu.addAction(ikona("faktura", TEKST_2), "Nowa faktura", lambda: self._nowy_z_zasobnika("Faktura"))
        menu.addSeparator()
        menu.addAction(ikona("klodka", TEKST_2), "Zablokuj", self.zablokuj)
        menu.addAction(ikona("zamknij", TEKST_2), "Zakończ program…", self.zakoncz)
        self._menu_zasobnika = menu
        self.zasobnik.setContextMenu(menu)
        self.zasobnik.activated.connect(
            lambda powod: self.pokaz_okno() if powod in (QSystemTrayIcon.ActivationReason.Trigger,
                                                         QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.zasobnik.show()

    def _w_tle_dostepne(self) -> bool:
        return self.baza.ustawienia()["w_tle"] == "1" and QSystemTrayIcon.isSystemTrayAvailable()

    def ukryj_do_zasobnika(self):
        self.strona_pulpit.zaslon()
        self.hide()
        self._ukryty = True
        if not self._podpowiedz_zasobnika:
            self._podpowiedz_zasobnika = True
            self.zasobnik.showMessage("Fakturnik działa w tle",
                                      "Pilnuje bezpieczeństwa danych. Kliknij ikonę obok zegara, aby go otworzyć.",
                                      QSystemTrayIcon.MessageIcon.Information, 5000)

    def pokaz_okno(self):
        if self._ukryty and self.baza.ma_haslo:
            if OknoHasla(self.baza.sprawdz_haslo, "Fakturnik", dziennik=self.dziennik, cel="otwarcie z zasobnika",
                         opis="Podaj hasło, aby otworzyć program.").exec() != QDialog.DialogCode.Accepted:
                return
        self._ukryty = False
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.timer.start()

    def _nowy_z_zasobnika(self, rodzaj: str):
        self.pokaz_okno()
        if self.isVisible():
            self.przejdz(STRONA_NOWY)
            self.strona_nowy.ustaw_rodzaj(rodzaj)

    def obsluz_polecenie(self, polecenie: dict):
        """Polecenie od drugiej kopii programu: pokaż okno albo dodaj pliki (menu prawego przycisku)."""
        if polecenie.get("akcja") == "w_tle":
            return
        self.pokaz_okno()
        if not self.isVisible():
            return
        if polecenie.get("akcja") == "dodaj" and polecenie.get("pliki"):
            self.przejdz(STRONA_PLIKI)
            self.strona_pliki._dodaj_sciezki([Path(p) for p in polecenie["pliki"]])

    def zakoncz(self):
        if self.baza.ma_haslo:
            if not self.potwierdz_haslem("zakończenie programu", "Podaj hasło, aby wyłączyć Fakturnik.\n"
                                         "Po wyłączeniu program przestaje pilnować danych."):
                return
        elif QMessageBox.question(None, "Fakturnik", "Wyłączyć Fakturnik? Program przestanie pilnować danych.") \
                != QMessageBox.StandardButton.Yes:
            return
        self._wyjscie = True
        self.close()
        QApplication.quit()

    # ---- strażnik integralności
    def sprawdz_integralnosc(self):
        problemy = self.baza.sprawdz_integralnosc(katalog_kopii() / "pliki")
        zapamietany = self.baza.ustawienia()["ostatni_wpis_dziennika"]
        uciety = self._dziennik_uciety or (bool(zapamietany) and not self.dziennik.zawiera(zapamietany))
        if (uciety or not self.dziennik.nienaruszony()) and not self._dziennik_zgloszony:
            self._dziennik_zgloszony = True
            problemy.append("Dziennik logowań został zmieniony, ucięty lub usunięto z niego wpisy.")
        for p in problemy:
            self.dziennik.zapisz(f"STRAŻNIK: {p}")
        if problemy:
            self.zasobnik.showMessage("Fakturnik: wykryto problem z danymi", "\n".join(problemy)[:400],
                                      QSystemTrayIcon.MessageIcon.Warning, 10000)
            if self.isVisible():
                self.komunikat(problemy[0], blad=True)

    def _zapamietaj_wpis(self, skrot: str):
        try:
            self.baza.zapamietaj_wpis_dziennika(skrot)
        except Exception:
            pass  # np. baza już zamknięta przy wyłączaniu programu

    def zablokuj(self):
        if not self.baza.ma_haslo:
            self.timer.start()
            return
        if not self.isVisible():
            self._ukryty = True
            return
        self.dziennik.zapisz("blokada programu")
        if self._w_tle_dostepne():
            self.ukryj_do_zasobnika()  # odblokowanie hasłem po kliknięciu ikony
            return
        self.hide()
        okno = OknoHasla(self.baza.sprawdz_haslo, "Fakturnik jest zablokowany", dziennik=self.dziennik,
                         cel="odblokowanie", opis="Podaj hasło, aby wrócić do pracy.")
        if okno.exec() == QDialog.DialogCode.Accepted:
            self.show()
            self.timer.start()
        else:
            self._wyjscie = True
            self.close()
            QApplication.quit()

    def closeEvent(self, event):
        if not self._wyjscie and self._w_tle_dostepne():
            event.ignore()  # zamknięcie okna = schowanie do zasobnika; program dalej pilnuje danych
            self.ukryj_do_zasobnika()
            return
        self.zegar_straznika.stop()
        if hasattr(self, "zasobnik"):
            self.zasobnik.hide()
        QApplication.instance().removeEventFilter(self.straznik)
        self.timer.stop()
        self.dziennik.zapisz("zamknięcie programu")
        self.baza.zamknij()
        try:
            kopia_automatyczna(self.baza.sciezka)
            self.baza.kopia_plikow(katalog_kopii() / "pliki")
        except OSError:
            pass
        event.accept()

    def pierwsze_uruchomienie(self):
        from .kreator import Kreator
        Kreator(self).exec()
        self.strona_nowy.ustaw_tryb(self.baza.ustawienia()["tryb"])
        self.strona_nowy.wyczysc()
        self.przejdz(STRONA_NOWY)


def uruchom() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Fakturnik")
    app.setOrganizationName("Fakturnik")
    app.setWindowIcon(QIcon(str(ZASOBY / "ikona.png")))
    app.setQuitOnLastWindowClosed(False)  # program może działać w tle bez otwartego okna
    zaladuj_czcionki()
    app.setStyle("Fusion")
    czcionka = QFont("Inter")
    czcionka.setPixelSize(13)
    czcionka.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(czcionka)
    app.setStyleSheet(STYL)
    aktualizacje.posprzataj()
    aktualizacje.zablokuj_program()

    # tylko jedna kopia programu: kolejne uruchomienie przekazuje polecenie działającej i kończy się
    polecenie = polecenie_z_argumentow(sys.argv[1:])
    jedna = JednaKopia()
    if jedna.wyslij_do_dzialajacej(polecenie):
        return 0
    jedna.nasluchuj()

    plik = sciezka_danych()
    dziennik = Dziennik(plik.parent / "dziennik.log")
    try:
        kod, okno = _otworz(app, plik, dziennik, jedna, polecenie)
    except PlikZajety as e:
        QMessageBox.warning(None, "Fakturnik", str(e))
        return 1
    except NowszaBaza as e:
        QMessageBox.warning(None, "Fakturnik", str(e))
        return 1
    if okno and okno.uruchom_po_zamknieciu:
        jedna.zamknij()  # nowa wersja nie może trafić na nasłuch starej, bo uznałaby, że program już działa
        aktualizacje.uruchom_nowa_wersje(okno.uruchom_po_zamknieciu)
    return kod


def _czekaj_w_zasobniku(app: QApplication, plik: Path, jedna: JednaKopia, polecenie: dict) -> dict | None:
    """Start z Windows przy danych chronionych hasłem: program siedzi w zasobniku i już blokuje plik danych,
    a o hasło pyta dopiero, gdy ktoś go otworzy. Zwraca polecenie do wykonania albo None (zakończ)."""
    blokada = BlokadaPliku(plik)
    blokada.zaloz()
    wynik: dict = {}
    petla = QEventLoop()
    zasobnik = QSystemTrayIcon(QIcon(str(ZASOBY / "ikona.png")))
    zasobnik.setToolTip("Fakturnik: działa w tle i pilnuje danych")
    menu = QMenu()

    def otworz(p=None):
        wynik["polecenie"] = p or {"akcja": "pokaz"}
        petla.quit()

    def zakoncz():
        def sprawdz(haslo: str) -> bool:
            try:
                blokada.zwolnij()
                Baza(plik, haslo).zamknij()
                return True
            except BledneHaslo:
                return False
            finally:
                blokada.zaloz()
        if OknoHasla(sprawdz, "Wyłącz Fakturnik", opis="Podaj hasło, aby wyłączyć program.").exec() \
                == QDialog.DialogCode.Accepted:
            wynik["polecenie"] = None
            petla.quit()

    menu.addAction("Otwórz Fakturnik", otworz)
    menu.addSeparator()
    menu.addAction("Zakończ program…", zakoncz)
    zasobnik.setContextMenu(menu)
    zasobnik.activated.connect(lambda powod: otworz() if powod in (QSystemTrayIcon.ActivationReason.Trigger,
                                                                   QSystemTrayIcon.ActivationReason.DoubleClick) else None)
    jedna.polecenie.connect(lambda p: otworz(p) if p.get("akcja") != "w_tle" else None)
    zasobnik.show()
    petla.exec()
    zasobnik.hide()
    jedna.polecenie.disconnect()
    blokada.zwolnij()
    return wynik.get("polecenie")


def _otworz(app: QApplication, plik: Path, dziennik: Dziennik, jedna: JednaKopia,
            polecenie: dict) -> tuple[int, OknoGlowne | None]:
    w_tle = polecenie.get("akcja") == "w_tle" and QSystemTrayIcon.isSystemTrayAvailable()
    if w_tle and Baza.wymaga_hasla(plik):
        polecenie = _czekaj_w_zasobniku(app, plik, jedna, polecenie)
        if polecenie is None:
            return 0, None
        w_tle = False
    if Baza.wymaga_hasla(plik):
        wynik: dict[str, Baza] = {}

        def sprawdz(haslo: str) -> bool:
            try:
                wynik["baza"] = Baza(plik, haslo)
                return True
            except BledneHaslo:
                return False

        if OknoHasla(sprawdz, dziennik=dziennik, opis="Podaj hasło, aby otworzyć program.").exec() \
                != QDialog.DialogCode.Accepted:
            return 0, None
        baza = wynik["baza"]
    else:
        try:
            baza = Baza(plik)
        except ValueError:
            QMessageBox.critical(None, "Fakturnik", f"Plik danych jest uszkodzony lub zmieniony z zewnątrz:\n{plik}\n\n"
                                 f"Przywróć go z kopii automatycznej w:\n{katalog_kopii()}")
            return 1, None
        dziennik.zapisz("uruchomienie programu (bez hasła)")
    try:
        kopia_automatyczna(plik)
        baza.kopia_plikow(katalog_kopii() / "pliki")
    except OSError:
        pass

    okno = OknoGlowne(baza, dziennik)
    jedna.polecenie.connect(okno.obsluz_polecenie)
    if w_tle and okno._w_tle_dostepne() and baza.ustawienia()["skonfigurowano"] == "1":
        okno._ukryty = baza.ma_haslo
    else:
        okno.show()
        if polecenie.get("akcja") == "dodaj":
            QTimer.singleShot(300, lambda: okno.obsluz_polecenie(polecenie))
    return app.exec(), okno
