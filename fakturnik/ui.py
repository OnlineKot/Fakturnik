"""Okno główne programu Fakturnik."""

import base64
import hmac
import math
import re
from html import escape as html_escape
import os
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import (
    QBuffer, QFileSystemWatcher, QByteArray, QDate, QEvent, QEventLoop, QIODevice, QObject, QPoint, QRect, QSettings, QSize, QStandardPaths, Qt,
    QThread,
    QTime, QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QImage, QKeySequence, QPixmap, QShortcut,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QFileDialog, QFormLayout, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QStackedWidget, QTimeEdit, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from . import aktualizacje, druk, godziny, gtd, konta, kontrola, mf, narzedzia, urzadzenie, windows
from .baza import KATEGORIE_PLIKOW, Baza, Dokument, NowszaBaza, Plik, PlikZajety, Pozycja, podsumuj
from .ikony import ikona, pixmapa
from .ochrona import BlokadaPliku, Dziennik, katalog_kopii, kopia_automatyczna, lista_kopii, odtworz_z_kopii
from .system import (
    JednaKopia, autostart_wlaczony, integracja_dostepna, menu_kontekstowe_wlaczone, polecenie_z_argumentow,
    ustaw_autostart, ustaw_menu_kontekstowe, utworz_skrot_na_pulpicie,
)
from .szyfrowanie import BledneHaslo, WymaganeUrzadzenie
from .walidacja import formatuj_konto, konto_poprawne, nip_poprawny, opis_identyfikatora
from .wersja import WERSJA
from .widzety import DwuliniowyDelegate, OknoPowiadomienia, PigulkaDelegate, PodgladKartki, PodgladStron, Powiadomienie, WykresMiesiecy

(STRONA_NOWY, STRONA_HISTORIA, STRONA_PRZYCHODY, STRONA_PLIKI, STRONA_NARZEDZIA,
 STRONA_USTAWIENIA) = range(6)
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
QSpinBox, QTimeEdit {{ background: white; border: 1px solid #d5dade; border-radius: 8px; padding: 6px 26px 6px 10px; }}
QTimeEdit:disabled {{ color: #b0b0b5; background: #f5f6f7; }}
QSpinBox:hover, QTimeEdit:hover {{ border-color: #bcc4ca; }}
QSpinBox:focus, QTimeEdit:focus {{ border: 1px solid {AKCENT}; }}
QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{ subcontrol-origin: border; width: 22px; border: none;
    background: transparent; }}
QSpinBox::up-button, QTimeEdit::up-button {{ subcontrol-position: top right; margin: 3px 3px 0 0; }}
QSpinBox::down-button, QTimeEdit::down-button {{ subcontrol-position: bottom right; margin: 0 3px 3px 0; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QTimeEdit::up-button:hover, QTimeEdit::down-button:hover {{ background: {AKCENT_TLO}; border-radius: 4px; }}
QSpinBox::up-arrow, QTimeEdit::up-arrow {{ image: url("{(ZASOBY / "gora.svg").as_posix()}"); width: 12px; height: 12px; }}
QSpinBox::down-arrow, QTimeEdit::down-arrow {{ image: url("{(ZASOBY / "dol.svg").as_posix()}"); width: 12px; height: 12px; }}
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

QDialog#szukanie {{ background: white; border: 1px solid {LINIA}; border-radius: 14px; }}
QDialog#szukanie QListWidget {{ border: none; background: white; outline: none; font-size: 14px; }}
QDialog#szukanie QListWidget::item {{ border-radius: 8px; padding: 4px 8px; color: {TEKST}; }}
QDialog#szukanie QListWidget::item:selected {{ background: {AKCENT_TLO}; color: {AKCENT}; }}
QPushButton#szukaj_menu {{ background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10);
    border-radius: 8px; color: {MENU_TEKST}; text-align: left; padding: 8px 10px; }}
QPushButton#szukaj_menu:hover {{ background: rgba(255,255,255,0.12); color: white; }}
QToolButton#kafelek {{ background: white; border: 1px solid {LINIA}; border-radius: 16px; padding: 22px 10px 16px;
    font-size: 14px; font-weight: 600; color: {TEKST}; }}
QToolButton#kafelek:hover {{ border-color: {AKCENT}; background: #fbfdfd; }}
QToolButton#kafelek:pressed {{ background: {AKCENT_TLO}; }}
QToolButton#wstecz {{ background: white; border: 1px solid {LINIA}; border-radius: 10px; padding: 6px; }}
QToolButton#wstecz:hover {{ border-color: {AKCENT}; background: {AKCENT_TLO}; }}
QToolButton#gwiazdka {{ background: transparent; border: none; border-radius: 6px; padding: 3px; }}
QToolButton#gwiazdka:hover {{ background: {AKCENT_TLO}; }}
QToolButton#gwiazdka::menu-indicator {{ image: none; width: 0; }}
QPushButton#lista_gtd {{ background: transparent; border: none; border-radius: 8px; padding: 8px 10px;
    text-align: left; font-weight: 500; color: {TEKST}; }}
QPushButton#lista_gtd:hover {{ background: #f3f6f7; }}
QPushButton#lista_gtd:checked {{ background: {AKCENT_TLO}; color: {AKCENT}; font-weight: 650; }}
QFrame#zadanie {{ background: white; border: 1px solid {LINIA}; border-radius: 10px; }}
QFrame#zadanie:hover {{ border-color: #c9d6d9; }}
QFrame#zadanie QLabel {{ background: transparent; }}
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


def zapytanie_dozwolone(tekst: str) -> bool:
    """Bez hasła lista pokazuje tylko trafienia konkretnego wyszukiwania, a nie „wszystko z 2026 roku”:
    co najmniej 3 litery nazwiska, pełny PESEL/NIP albo pełny numer dokumentu."""
    t = tekst.strip()
    if sum(c.isalpha() for c in t) >= 3:
        return True
    cyfry = re.sub(r"[\s-]", "", t)
    if cyfry.isdigit() and len(cyfry) >= 10:
        return True
    return bool(re.fullmatch(r"([A-Za-z]+/)?\d+/\d{1,2}/\d{2,4}", t))


def liczba_lub_none(tekst: str) -> float | None:
    """Kwota lub ilość wpisana po polsku: „1 200,50”, „1.200,50”, „150 zł”, „2”. None = nie da się odczytać."""
    t = tekst.strip().lower().replace("zł", "").replace("zl", "")
    t = t.replace(" ", "").replace("\xa0", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "")  # kropki jako separator tysięcy
    t = t.replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?|-?\.\d+", t):
        return None
    wartosc = float(t)
    return wartosc if math.isfinite(wartosc) and abs(wartosc) < 1e9 else None


def liczba(tekst: str) -> float:
    return liczba_lub_none(tekst) or 0.0


def ilosc_z_tekstu(tekst: str) -> float | None:
    """Puste pole ilości = 1; inaczej liczba (None, gdy nieczytelna)."""
    return 1.0 if not tekst.strip() else liczba_lub_none(tekst)


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
        element = uklad.takeAt(0)
        if element.layout():
            wyczysc_uklad(element.layout())  # także zagnieżdżone układy (rzędy przycisków)
        w = element.widget()
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
    opis = QLabel(podtytul, objectName="podtytul")
    opis.hide()  # bez opisów pod tytułami: same nazwy ekranów
    u.addWidget(opis)
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
                 cel="logowanie", opis="Dane są chronione hasłem.", ekran_blokady: dict | None = None,
                 zgoda=None):
        """`sprawdz(haslo)` zwraca True, False albo tekst (odmowa z powodem, np. poza godzinami pracy).
        `ekran_blokady`: {"gabinet", "godziny"} pokazuje zegar i godziny pracy (ekran blokady programu).
        `zgoda`: funkcja wywoływana przyciskiem „Zgoda właściciela” (praca po godzinach)."""
        super().__init__(parent)
        self.sprawdz, self.dziennik, self.cel, self.zgoda = sprawdz, dziennik, cel, zgoda
        self.proby = 0
        self.setWindowTitle(tytul)
        self.setFixedWidth(440 if ekran_blokady else 400)
        u = QVBoxLayout(self)
        u.setContentsMargins(32, 30, 32, 24)
        u.setSpacing(10)
        if ekran_blokady:
            self.zegar_ekranu = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter)
            self.zegar_ekranu.setStyleSheet(f"font-size: 46px; font-weight: 300; color: {AKCENT}; letter-spacing: -1px;")
            self.data_ekranu = QLabel(alignment=Qt.AlignmentFlag.AlignHCenter, objectName="podtytul")
            u.addWidget(self.zegar_ekranu)
            u.addWidget(self.data_ekranu)
            self._tykaj()
            tykanie = QTimer(self, interval=15000)
            tykanie.timeout.connect(self._tykaj)
            tykanie.start()
            if ekran_blokady.get("gabinet"):
                g = QLabel(ekran_blokady["gabinet"], alignment=Qt.AlignmentFlag.AlignHCenter, wordWrap=True)
                g.setStyleSheet("font-weight: 600;")
                u.addWidget(g)
            if ekran_blokady.get("godziny"):
                u.addWidget(QLabel(ekran_blokady["godziny"], objectName="drobny", wordWrap=True,
                                   alignment=Qt.AlignmentFlag.AlignHCenter))
            u.addWidget(separator())
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
        self.btn_zgoda = przycisk("Zgoda właściciela…", "klucz", "plaski", self._zgoda)
        self.btn_zgoda.hide()
        rzad.addWidget(self.btn_zgoda)
        rzad.addStretch()
        rzad.addWidget(przycisk("Anuluj", akcja=self.reject))
        self.ok = przycisk("Otwórz", styl="glowny", akcja=self.sprobuj)
        self.ok.setDefault(True)
        rzad.addWidget(self.ok)
        u.addLayout(rzad)

    def _tykaj(self):
        teraz = datetime.now()
        self.zegar_ekranu.setText(f"{teraz:%H:%M}")
        self.data_ekranu.setText(f"{DNI[teraz.weekday()].capitalize()}, {teraz.day} {MIESIACE_DOP[teraz.month - 1]}")

    def _zgoda(self):
        if self.zgoda and self.zgoda():
            self.blad.setText("Zgoda udzielona. Asystentka może teraz wpisać swoje hasło.")
            self.btn_zgoda.hide()
            self.pole.setFocus()

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
        if isinstance(ok, str):  # hasło dobre, ale dostęp odmówiony (np. poza godzinami pracy)
            if self.dziennik:
                self.dziennik.zapisz(f"{self.cel}: ODMOWA ({ok})")
            self.pole.clear()
            self.blad.setText(ok)
            self.btn_zgoda.setVisible(self.zgoda is not None)
            return
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
                 opis: str = "Hasło szyfruje wszystkie dane (Argon2id, AES-256-GCM i ChaCha20-Poly1305)."):
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


class OchronaEkranu(QObject):
    """Każde okno programu (także okno hasła i podręczne listy) jest niewidoczne dla zrzutów
    i nagrań ekranu innych programów, np. narzędzi AI sterujących komputerem (tylko Windows)."""

    def __init__(self):
        super().__init__()
        self.wlaczona = True

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
            windows.ochrona_przed_przechwytywaniem(int(obj.winId()), self.wlaczona)
        return False

    def ustaw(self, wlacz: bool):
        self.wlaczona = wlacz
        for w in QApplication.topLevelWidgets():
            if w.isVisible():
                windows.ochrona_przed_przechwytywaniem(int(w.winId()), wlacz)


OCHRONA_EKRANU = OchronaEkranu()


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
        if not self.okno.strona_nowy.porzuc_tryb():
            return
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
        rachunkow = sum(1 for d in wszystkie_teraz if d.wazny and d.tytul == "Rachunek")
        korekt = sum(1 for d in wszystkie_teraz if d.wazny and d.jest_korekta)
        self.k_liczba.setText(str(teraz.liczba))
        self.k_liczba_zm.setText(f"rachunki: {rachunkow}, faktury: {faktur}" + (f", korekty: {korekt}" if korekt else ""))
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
        self.btn_biala_lista = przycisk("Pobierz dane firmy z białej listy VAT", "pobierz", "plaski", self.pobierz_firme)
        self.btn_biala_lista.hide()
        pole_id.addWidget(self.btn_biala_lista, alignment=Qt.AlignmentFlag.AlignLeft)
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
        self.korygowany: Dokument | None = None  # faktura, do której wystawiamy fakturę korygującą
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
        self.btn_biala_lista.setVisible(ok and komunikat.startswith("NIP"))

    def pobierz_firme(self):
        """Nazwa i adres nabywcy z oficjalnego wykazu podatników VAT (Ministerstwo Finansów)."""
        self.btn_biala_lista.setEnabled(False)
        w = Watek(mf.szukaj, self.nabywca_id.text())
        w.gotowe.connect(self._firma_pobrana)
        w.blad.connect(lambda tekst: (self.btn_biala_lista.setEnabled(True), self.okno.komunikat(tekst, blad=True)))
        self.okno._w_tle(w)

    def _firma_pobrana(self, firma):
        self.btn_biala_lista.setEnabled(True)
        if firma is None:
            self.okno.komunikat("Tego NIP-u nie ma w wykazie podatników VAT (np. firma zwolniona z VAT)", blad=True)
            return
        if self.nabywca.text().strip() and self.nabywca.text().strip() != firma.nazwa and QMessageBox.question(
                self, "Dane firmy", f"Zastąpić nabywcę danymi z białej listy?\n\n{firma.nazwa}\n{firma.adres}") \
                != QMessageBox.StandardButton.Yes:
            return
        self.nabywca.setText(firma.nazwa)
        self.nabywca_adres.setText(mf.adres_dwulinijkowy(firma.adres))
        self.okno.komunikat(f"Pobrano dane firmy (status VAT: {firma.status_vat or 'brak'})")

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
                f"<b>{'Faktura korygująca' if self.korygowany else self.rodzaj}</b> dla <b>{html_escape(self.nabywca.text().strip()) or '…'}</b><br>"
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
        self.korygowany = None
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
        dok.id, dok.numer, dok.rodzaj, dok.anulowano, dok.powod_anulowania, dok.wystawil = (
            org.id, org.numer, org.rodzaj, org.anulowano, org.powod_anulowania, org.wystawil)
        self.okno.baza.zaktualizuj_dokument(dok, powod)
        self.okno.dziennik.zapisz(f"edycja dokumentu nr {dok.numer}")  # powód zostaje w zaszyfrowanej historii zmian
        self.okno.komunikat(f"Zapisano zmiany w dokumencie nr {dok.numer}")
        self.zakoncz_edycje()
        self.okno.przejdz(STRONA_HISTORIA)
        self.okno.podglad(self.okno.baza.dokument(dok.id), duplikat=True)

    def porzuc_tryb(self) -> bool:
        """Przed nowym dokumentem: wyjście z edycji lub korekty (po potwierdzeniu)."""
        if not (self.edytowany or self.korygowany):
            return True
        if QMessageBox.question(self, "Nowy dokument", "Trwa edycja lub korekta dokumentu. Porzucić zmiany?") \
                != QMessageBox.StandardButton.Yes:
            return False
        self.zakoncz_edycje()
        return True

    def zaladuj_do_korekty(self, dok: Dokument):
        """Faktura korygująca (art. 106j): pozycje i dane nabywcy z faktury, którą poprawiamy."""
        self.zakoncz_edycje()
        self.korygowany = dok
        for b in self.rodzaj_grupa.buttons():
            b.setEnabled(False)
        self.platnosc.setCurrentText(dok.platnosc)
        self.nabywca.setText(dok.nabywca)
        self.nabywca_id.setText(dok.nabywca_id)
        self.nabywca_adres.setText(dok.nabywca_adres.replace("\n", ", "))
        self.data_uslugi.setDate(QDate.fromString(dok.data_uslugi, "yyyy-MM-dd"))
        self.tabela.setRowCount(0)
        for p in dok.pozycje:
            self.dodaj_pozycje(p.nazwa, p.cena, p.ilosc)
        self.drukuj_btn.setText("Wystaw korektę")
        self.btn_anuluj_edycje.show()
        self.zmien_rodzaj()
        self.pokaz_krok(1 if self.tryb != "zaawansowany" else 0)

    def zakoncz_edycje(self):
        self.edytowany = None
        self.korygowany = None
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
            pozycje=self.pozycje(),
            **self._pola_dodatkowe())

    def _pola_dodatkowe(self) -> dict:
        """Termin płatności (przelew) i dane faktury korygowanej."""
        pola = {}
        if self.platnosc.currentText() == "przelew":
            dni = int(liczba(self.okno.baza.ustawienia()["termin_dni"]) or 0)
            pola["termin_platnosci"] = (self.data_wyst.date().toPython() + timedelta(days=dni)).isoformat()
        pola["wystawil"] = self.okno.uzytkownik["nazwa"]
        if self.korygowany:
            k = self.korygowany
            pola.update(korekta_do=k.numer, korekta_data=k.data_wystawienia, korekta_id=k.id or 0,
                        pozycje_przed=[Pozycja(p.nazwa, p.ilosc, p.cena, p.jm) for p in k.pozycje])
        return pola

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
        numer, kopia = self.numer.text(), self.kopia.isChecked()
        self.odswiez()  # lista podpowiedzi mogła się zmienić (nowi lub poprawieni pacjenci)
        self.numer.setText(numer)
        self.kopia.setChecked(kopia)
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
        dzis = QDate.currentDate()
        if not (self.edytowany or self.korygowany or self.ma_niezapisane()) and self.data_wyst.date() < dzis:
            # program działa w tle całymi dniami: pusty formularz zawsze zaczyna od dzisiejszej daty
            self.data_wyst.setDate(dzis)
            self.data_uslugi.setDate(dzis)
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
        if self.korygowany:
            return "Korekta"
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
        elif self.korygowany:
            tytul.setText(f"Korekta faktury nr {self.korygowany.numer}")
            podtytul.setText("Wpisz pozycje tak, jak powinny wyglądać po korekcie. Wydruk pokaże stan przed i po.")
        else:
            tytul.setText("Nowa faktura" if self.rodzaj == "Faktura" else "Nowy rachunek")
            podtytul.setText("Numer nadaje się sam: kolejny w danym miesiącu.")
        self.zaplanuj_podglad()
        self.etykieta_nabywcy.setText("Nabywca (pacjent lub firma)" if self.rodzaj != "Rachunek" else "Pacjent")
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
                wynik.append(Pozycja(nazwa, ilosc_z_tekstu(self.tabela.item(r, 1).text()) or 0.0,
                                     liczba(self.tabela.item(r, 2).text())))
        return wynik

    def bledne_wiersze(self) -> list[int]:
        """Numery wierszy (od 1) z usługą, w których ilości lub ceny nie da się odczytać albo ilość jest zerowa."""
        bledne = []
        for r in range(self.tabela.rowCount()):
            if not self.tabela.item(r, 0).text().strip():
                continue
            ilosc = ilosc_z_tekstu(self.tabela.item(r, 1).text())
            cena_tekst = self.tabela.item(r, 2).text()
            cena = liczba_lub_none(cena_tekst) if cena_tekst.strip() else 0.0
            if not ilosc or ilosc <= 0 or cena is None or cena < 0:
                bledne.append(r + 1)
        return bledne

    def przelicz(self, *_):
        self.tabela.blockSignals(True)
        suma = 0.0
        for r in range(self.tabela.rowCount()):
            w = (ilosc_z_tekstu(self.tabela.item(r, 1).text()) or 0.0) * liczba(self.tabela.item(r, 2).text())
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
        if not pozycje and not self.korygowany:
            QMessageBox.warning(self, "Brak usług", "Dodaj przynajmniej jedną usługę.")
            return None
        if bledne := self.bledne_wiersze():
            QMessageBox.warning(self, "Usługi", f"Sprawdź ilość i cenę w wierszu {', '.join(map(str, bledne))}: "
                                "ilość musi być większa od zera, a cena liczbą (np. 150 albo 1 200,50).")
            return None
        if not self._dane_faktury_kompletne():
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
            pozycje=pozycje,
            **self._pola_dodatkowe())

    def _dane_faktury_kompletne(self) -> bool:
        """Elementy obowiązkowe faktury (art. 106e ustawy o VAT) przed jej wystawieniem."""
        if self.rodzaj == "Rachunek":
            return True
        u = self.okno.baza.ustawienia()
        braki = [n for n, k in (("nazwa gabinetu", "nazwa"), ("adres gabinetu", "adres"), ("NIP gabinetu", "nip"),
                                ("podstawa zwolnienia z VAT (adnotacja)", "adnotacja")) if not u[k].strip()]
        if braki:
            QMessageBox.warning(self, "Faktura niekompletna",
                                "Na fakturze muszą być: " + ", ".join(braki) + ".\n\nUzupełnij je w Ustawieniach.")
            return False
        if not self.nabywca_adres.text().strip():
            QMessageBox.warning(self, "Faktura niekompletna", "Na fakturze musi być adres nabywcy.")
            self.nabywca_adres.setFocus()
            return False
        if self.platnosc.currentText() == "przelew" and not u["konto"].strip() and QMessageBox.question(
                self, "Brak numeru konta", "Płatność przelewem, ale w Ustawieniach nie ma numeru konta gabinetu. "
                "Wystawić mimo to?") != QMessageBox.StandardButton.Yes:
            return False
        return True

    def ma_niezapisane(self) -> bool:
        if self.nabywca.text().strip():
            return True
        return any((it := self.tabela.item(r, 0)) and it.text().strip() for r in range(self.tabela.rowCount()))

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
        if self.korygowany:
            powod, ok = QInputDialog.getText(self, "Faktura korygująca",
                                             f"Przyczyna korekty faktury nr {self.korygowany.numer}:\n"
                                             "(np. błędna cena, zwrot za niewykonaną usługę, błąd w danych nabywcy)")
            if not ok or not powod.strip():
                return None
            dok.powod_korekty = powod.strip()
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
        wybor = self.okno.ustawienia_wydruku(self, f"{dok.tytul} nr {dok.numer}", z_kopia=self.kopia.isChecked())
        if not wybor:
            return
        drukarka, u, z_kopia = wybor
        self.okno.baza.zapisz_dokument(dok)
        druk.drukuj(druk.html_dokumentu(dok, u, z_kopia), drukarka)
        self.okno.komunikat(f"Wydrukowano: {dok.nazwa_druku.lower()} nr {dok.numer}")
        self.zakoncz_edycje()

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
        self.zakoncz_edycje()

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
        self.zaslona_listy = QLabel("Wpisz co najmniej 3 litery nazwiska albo cały PESEL, aby wyszukać pacjenta.",
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
        zablokowane = self.baza.ma_haslo and not self.pelny_dostep and not zapytanie_dozwolone(self.szukaj.text())
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
            try:
                self.baza.zapisz_pacjenta(*dane, nowy=True)
            except ValueError as e:
                QMessageBox.warning(self, "Pacjent", str(e))
                return
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
            try:
                self.baza.zapisz_pacjenta(*dane, stara_nazwa=p.nazwa)
            except ValueError as e:
                QMessageBox.warning(self, "Pacjent", str(e))
                return
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
        for b in (przycisk("Zamknięcie dnia", "kalendarz", akcja=lambda: self.okno.zamkniecie_dnia()),
                  przycisk("Drukuj zestawienie", "drukarka", akcja=self.drukuj_zestawienie),
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
        for tekst, dane in (("Wszystkie dokumenty", None), ("Tylko rachunki", "Rachunek"), ("Tylko faktury", "Faktura"),
                            ("Tylko korekty", "Korekta")):
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
                      przycisk("Użyj jako wzór", "kopiuj", akcja=self.wzor),
                      przycisk("Korekta", "faktura", akcja=self.korekta)]
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
        self.tabela = QTableWidget(0, 7)
        self.tabela.setHorizontalHeaderLabels(["Numer", "Data", "Pacjent", "Rodzaj", "Płatność", "Kwota", "Wystawił(a)"])
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tabela.horizontalHeaderItem(5).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for kol, szer in ((0, 130), (1, 110), (3, 120), (4, 110), (5, 140), (6, 120)):
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
            "Wpisz co najmniej 3 litery nazwiska, pełny numer dokumentu albo PESEL, aby wyszukać.\n"
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
        self.akcje[2].setEnabled(d is not None and d.wazny and not d.jest_korekta)
        self.akcje[4].setEnabled(d is not None and not d.jest_korekta)
        self.akcje[5].setEnabled(d is not None and d.wazny and d.tytul == "Faktura")

    def odswiez(self):
        self._wypelnij_lata()
        self.filtruj()

    def pokaz_wszystko(self):
        if self.okno.potwierdz_haslem("pokazanie pełnej listy", "Podaj hasło, aby zobaczyć pełną listę."):
            self.pelny_dostep = True
            self.filtruj()

    def _dostep_do_zestawien(self) -> bool:
        """Zestawienia i eksport zawierają kwoty i nazwiska: bez wcześniejszego „Pokaż wszystko” pytają o hasło."""
        if self.pelny_dostep or not self.okno.baza.ma_haslo:
            return True
        if self.okno.potwierdz_haslem("zestawienie lub eksport", "Zestawienie i eksport wymagają hasła."):
            self.pelny_dostep = True
            self.filtruj()
            return True
        return False

    def _tylko_wyszukiwanie(self) -> bool:
        """Bez hasła widać tylko wyniki konkretnego wyszukiwania, nie całą listę nazwisk."""
        zablokowane = self.okno.baza.ma_haslo and not self.pelny_dostep and not zapytanie_dozwolone(self.szukaj.text())
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
                      d.platnosc, f"{druk.zl(d.suma)} zł", d.wystawil or "—"]
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
        czesci = [f"{self.opis_okresu()}: {liczba_dokumentow(p.liczba)}"]
        if self.pelny_dostep or not self.okno.baza.ma_haslo:  # kwoty razem tylko po haśle, jak na karcie Przychody
            czesci.append(f"{druk.zl(p.suma)} zł")
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
            wybor = self.okno.ustawienia_wydruku(self, f"Duplikat nr {d.numer}")
            if not wybor:
                return
            drukarka, u, z_kopia = wybor
            druk.drukuj(druk.html_dokumentu(d, u, z_kopia, duplikat=True), drukarka)
            self.okno.dziennik.zapisz(f"wydruk duplikatu nr {d.numer}")
            self.okno.komunikat(f"Wydrukowano duplikat nr {d.numer}")

    def podglad(self, *_):
        if d := self.wybrany():
            self.okno.podglad(d, duplikat=True)

    def korekta(self):
        if d := self.wybrany():
            self.okno.korekta_dokumentu(d)

    def wzor(self):
        if d := self.wybrany():
            s = self.okno.strona_nowy
            s.zakoncz_edycje()
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
    def _html_zestawienia(self, u: dict[str, str] | None = None) -> str:
        filtr = [f"„{self.szukaj.text().strip()}”"] if self.szukaj.text().strip() else []
        if self.rodzaj.currentData():
            filtr.append(self.rodzaj.currentText().lower())
        return druk.html_zestawienia(self.docs, u or self.okno.baza.ustawienia(), self.opis_okresu(),
                                     ", ".join(filtr))

    def drukuj_zestawienie(self):
        if not self._dostep_do_zestawien():
            return
        if not self.docs:
            QMessageBox.information(self, "Zestawienie", "Brak dokumentów do zestawienia.")
            return
        wybor = self.okno.ustawienia_wydruku(self, "Zestawienie", dokument=False, zawsze=True)
        if not wybor:
            return
        drukarka, u, _ = wybor
        druk.drukuj(self._html_zestawienia(u), drukarka)
        self.okno.komunikat("Wydrukowano zestawienie")

    def zestawienie_pdf(self):
        if not self._dostep_do_zestawien():
            return
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
        if not self._dostep_do_zestawien():
            return
        nazwa = "rachunki-" + self.opis_okresu().lower().replace(" ", "-").replace("(", "").replace(")", "")
        sciezka, _ = QFileDialog.getSaveFileName(self, "Eksport do Excela", str(Path.home() / f"{nazwa}.csv"),
                                                 "CSV (*.csv)")
        if sciezka:
            n = self.okno.baza.eksport_csv(sciezka, self.docs)
            self.okno.dziennik.zapisz(f"eksport CSV ({n} dokumentów)")
            self.okno.komunikat(f"Wyeksportowano: {liczba_dokumentow(n)} → {sciezka}")


class StronaNarzedzia(Strona):
    """Narzędzia gabinetu: ekran z kafelkami, każde narzędzie na osobnym widoku (powrót strzałką lub Esc)."""

    NARZEDZIA = [  # (klucz, nazwa, ikona)
        ("gtd", "Notatki GTD", "zadania"),
        ("przypomnienia", "Przypomnienia", "dzwonek"),
        ("kasa", "Liczenie kasy", "banknot"),
        ("kalkulator", "Kalkulator", "kalkulator"),
        ("stoper", "Stoper", "stoper"),
        ("minutnik", "Minutnik", "klepsydra"),
        ("daty", "Kalkulator dat", "kalendarz"),
        ("rabat", "Rabat i raty", "procent"),
        ("firma", "Firma po NIP", "budynek"),
        ("numer", "Sprawdź numer", "hash"),
        ("slownie", "Kwota słownie", "tekst"),
        ("hasla", "Generator haseł", "klucz"),
        ("skaner", "Skaner plików", "tarcza"),
    ]

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, przewijana=True)
        u = self.uklad
        naglowek = QHBoxLayout()
        naglowek.setSpacing(10)
        self.btn_wstecz = QToolButton(objectName="wstecz")
        self.btn_wstecz.setIcon(ikona("wstecz", AKCENT, rozmiar=20))
        self.btn_wstecz.setIconSize(QSize(20, 20))
        self.btn_wstecz.setToolTip("Wszystkie narzędzia (Esc)")
        self.btn_wstecz.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wstecz.clicked.connect(lambda: self.pokaz(None))
        self.btn_wstecz.hide()
        naglowek.addWidget(self.btn_wstecz)
        self.tytul_strony = QLabel("Narzędzia", objectName="tytul")
        naglowek.addWidget(self.tytul_strony)
        naglowek.addStretch()
        u.addLayout(naglowek)
        u.addSpacing(10)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, lambda: self.pokaz(None))

        self.stos = QStackedWidget()
        u.addWidget(self.stos, 1)
        # ekran główny: kafelki
        ekran = QWidget()
        siatka = QGridLayout(ekran)
        siatka.setContentsMargins(0, 0, 0, 0)
        siatka.setSpacing(16)
        self.kafelki: dict[str, QToolButton] = {}
        for i, (klucz, nazwa, nazwa_ikony) in enumerate(self.NARZEDZIA):
            k = QToolButton(objectName="kafelek")
            k.setText(nazwa)
            k.setIcon(ikona(nazwa_ikony, AKCENT, rozmiar=34))
            k.setIconSize(QSize(34, 34))
            k.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            k.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            k.setMinimumSize(150, 128)
            k.setCursor(Qt.CursorShape.PointingHandCursor)
            k.clicked.connect(lambda _=False, kl=klucz: self.pokaz(kl))
            cien(k)
            self.kafelki[klucz] = k
            siatka.addWidget(k, i // 4, i % 4)
        siatka.setRowStretch(len(self.NARZEDZIA) // 4 + 1, 1)
        self.stos.addWidget(ekran)
        # widoki narzędzi
        budowa = {"gtd": self._widok_gtd, "przypomnienia": self._karta_przypomnien, "kasa": self._karta_kasy,
                  "kalkulator": self._karta_kalkulatora, "stoper": self._karta_stopera,
                  "minutnik": self._karta_minutnika, "daty": self._karta_dat, "rabat": self._karta_rabatu,
                  "firma": self._karta_firmy, "numer": self._karta_numeru, "slownie": self._karta_slownie,
                  "hasla": self._karta_hasel, "skaner": self._karta_skanera}
        self.widoki: dict[str, int] = {}
        for klucz, _, _ in self.NARZEDZIA:
            w = budowa[klucz]()
            if klucz != "gtd":  # małe narzędzia: wyśrodkowana karta, nie na całą szerokość
                opak = QWidget()
                ou = QHBoxLayout(opak)
                ou.setContentsMargins(0, 0, 0, 0)
                ou.addStretch(1)
                w.setMinimumWidth(460)
                w.setMaximumWidth(680)
                ou.addWidget(w, 3)
                ou.addStretch(1)
                kol = QVBoxLayout()
                kol.addWidget(opak)
                kol.addStretch()
                kontener = QWidget()
                kontener.setLayout(kol)
                kol.setContentsMargins(0, 0, 0, 0)
                w = kontener
            self.widoki[klucz] = self.stos.addWidget(w)
        self._aktywne: str | None = None

    def pokaz(self, klucz: str | None):
        """None = ekran z kafelkami; inaczej widok jednego narzędzia."""
        self._aktywne = klucz
        nazwy = {k: n for k, n, _ in self.NARZEDZIA}
        self.stos.setCurrentIndex(self.widoki[klucz] if klucz else 0)
        self.btn_wstecz.setVisible(klucz is not None)
        self.tytul_strony.setText(nazwy[klucz] if klucz else "Narzędzia")
        if klucz == "gtd":
            self.wpis_gtd.setFocus()
        elif klucz == "kalkulator":
            self.dzialanie.setFocus()
        elif klucz == "firma":
            self.nip.setFocus()
        elif klucz == "numer":
            self.numer.setFocus()
        elif klucz == "slownie":
            self.kwota.setFocus()
        elif klucz == "przypomnienia":
            self.tekst_przyp.setFocus()

    def _odswiez_kafelki(self):
        try:
            zadania = gtd.liczniki(self._gtd)["dzis"]
            przyp = len(self._przypomnienia())
        except Exception:  # noqa: BLE001
            return
        self.kafelki["gtd"].setText("Notatki GTD" + (f"\n{zadania} na dziś" if zadania else ""))
        self.kafelki["przypomnienia"].setText("Przypomnienia" + (f"\n{przyp} zaplanowane" if przyp else ""))

    # ---- firma po NIP, numery, kwota słownie
    def _karta_firmy(self) -> QFrame:
        k, ku = karta()
        rzad = QHBoxLayout()
        self.nip = QLineEdit(placeholderText="NIP, np. 123-456-32-18")
        self.nip.returnPressed.connect(self.szukaj_firmy)
        rzad.addWidget(self.nip, 1)
        self.btn_szukaj = przycisk("Sprawdź", "szukaj", "glowny", self.szukaj_firmy)
        rzad.addWidget(self.btn_szukaj)
        ku.addLayout(rzad)
        self.wynik_firmy = QLabel(wordWrap=True, textFormat=Qt.TextFormat.RichText, objectName="podtytul")
        self.wynik_firmy.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ku.addWidget(self.wynik_firmy)
        self.btn_faktura = przycisk("Wystaw fakturę dla tej firmy", "faktura", akcja=self.faktura_dla_firmy)
        self.btn_faktura.hide()
        ku.addWidget(self.btn_faktura, alignment=Qt.AlignmentFlag.AlignLeft)
        self.firma = None
        return k

    def _karta_numeru(self) -> QFrame:
        k, ku = karta()
        self.numer = QLineEdit(placeholderText="PESEL, NIP albo numer konta")
        self.numer.setStyleSheet("font-size: 16px; padding: 8px 10px;")
        self.numer.textChanged.connect(self._sprawdz_numer)
        ku.addWidget(self.numer)
        self.wynik_numeru = QLabel(wordWrap=True)
        self.wynik_numeru.setStyleSheet("font-size: 15px;")
        ku.addWidget(self.wynik_numeru)
        return k

    def _karta_slownie(self) -> QFrame:
        k, ku = karta()
        self.kwota = QLineEdit(placeholderText="np. 1 250,50")
        self.kwota.setStyleSheet("font-size: 16px; padding: 8px 10px;")
        self.kwota.textChanged.connect(self._slownie)
        ku.addWidget(self.kwota)
        self.slownie = QLabel(wordWrap=True)
        self.slownie.setStyleSheet(f"font-size: 16px; color: {AKCENT};")
        self.slownie.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ku.addWidget(self.slownie)
        ku.addWidget(przycisk("Kopiuj", "kopiuj", akcja=lambda: QApplication.clipboard().setText(self.slownie.text())),
                     alignment=Qt.AlignmentFlag.AlignLeft)
        return k

    # ---- notatki GTD
    def _widok_gtd(self) -> QWidget:
        self._gtd: list = []
        self._widok_listy = "dzis"
        w = QWidget()
        uk = QHBoxLayout(w)
        uk.setContentsMargins(0, 0, 0, 0)
        uk.setSpacing(16)
        # lewa kolumna: listy
        lewa, lu = karta()
        lewa.setFixedWidth(230)
        lu.setSpacing(2)
        self.grupa_list = QButtonGroup(self, exclusive=True)
        self.przyciski_list: dict[str, QPushButton] = {}
        ikony_list = {"dzis": "slonce", "skrzynka": "skrzynka", "nastepne": "dalej", "czekam": "zegar",
                      "kiedys": "chmura", "zrobione": "ok", "notatnik": "notatnik"}
        for klucz, nazwa in gtd.LISTY + [("notatnik", "Notatnik")]:
            if klucz == "zrobione":
                lu.addSpacing(6)
            b = QPushButton(nazwa, objectName="lista_gtd", checkable=True)
            b.setIcon(ikona(ikony_list[klucz], TEKST_2, aktywny=AKCENT))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, kl=klucz: self._wybierz_liste(kl))
            self.grupa_list.addButton(b)
            self.przyciski_list[klucz] = b
            lu.addWidget(b)
        lu.addStretch()
        uk.addWidget(lewa, alignment=Qt.AlignmentFlag.AlignTop)
        # prawa: dodawanie, filtr, zadania albo notatnik
        prawa = QVBoxLayout()
        prawa.setSpacing(10)
        rzad = QHBoxLayout()
        self.wpis_gtd = QLineEdit(placeholderText="Dodaj… np. Zadzwonić do laboratorium @telefon jutro !")
        self.wpis_gtd.setStyleSheet("font-size: 15px; padding: 9px 12px;")
        self.wpis_gtd.returnPressed.connect(self._dodaj_gtd)
        rzad.addWidget(self.wpis_gtd, 1)
        rzad.addWidget(przycisk("Dodaj", "plus", "glowny", self._dodaj_gtd))
        self.rzad_wpisu = QWidget()
        self.rzad_wpisu.setLayout(rzad)
        rzad.setContentsMargins(0, 0, 0, 0)
        prawa.addWidget(self.rzad_wpisu)
        filtr = QHBoxLayout()
        self.naglowek_listy = QLabel()
        self.naglowek_listy.setStyleSheet("font-size: 17px; font-weight: 650;")
        filtr.addWidget(self.naglowek_listy)
        filtr.addStretch()
        self.kontekst_gtd = QComboBox()
        self.kontekst_gtd.setMinimumWidth(170)
        self.kontekst_gtd.currentIndexChanged.connect(lambda _: self._pokaz_gtd())
        filtr.addWidget(self.kontekst_gtd)
        self.btn_wyczysc_gtd = przycisk("Usuń zrobione starsze niż 30 dni", "kosz", akcja=self._wyczysc_gtd)
        filtr.addWidget(self.btn_wyczysc_gtd)
        prawa.addLayout(filtr)
        self.lista_gtd = QVBoxLayout()
        self.lista_gtd.setSpacing(6)
        prawa.addLayout(self.lista_gtd)
        self.pusto_gtd = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.pusto_gtd.setStyleSheet(f"color: {TEKST_3}; font-size: 14px; padding: 40px;")
        prawa.addWidget(self.pusto_gtd)
        # notatnik (dawny notatnik gabinetu, tekst bez zmian)
        self.notatki = QPlainTextEdit(placeholderText="Swobodne notatki gabinetu…")
        self.notatki.setMinimumHeight(420)
        self._zapis_notatek = QTimer(self, singleShot=True, interval=1500)
        self._zapis_notatek.timeout.connect(self._zapisz_notatki)
        self.notatki.textChanged.connect(self._zapis_notatek.start)
        prawa.addWidget(self.notatki)
        self.stan_notatek = QLabel(objectName="drobny")
        prawa.addWidget(self.stan_notatek)
        prawa.addStretch()
        uk.addLayout(prawa, 1)
        self.przyciski_list["dzis"].setChecked(True)
        return w

    def _wczytaj_gtd(self):
        self._gtd = gtd.wczytaj(self.okno.baza.ustawienia().get("gtd", ""))

    def _zapisz_gtd(self):
        self.okno.baza.zapisz_ustawienia({"gtd": gtd.zapisz(self._gtd)})
        self._pokaz_gtd()
        self._odswiez_kafelki()

    def _wybierz_liste(self, klucz: str):
        self._widok_listy = klucz
        self.przyciski_list[klucz].setChecked(True)
        self._pokaz_gtd()

    def _dodaj_gtd(self):
        lista = self._widok_listy if self._widok_listy in gtd.PRZENOSZENIE else "skrzynka"
        zad = gtd.z_linii(self.wpis_gtd.text(), lista=lista)
        if not zad:
            return
        if self._widok_listy == "dzis" and not zad.termin:
            zad.termin = date.today().isoformat()  # dodane w widoku „Dziś” jest na dziś
        self._gtd.append(zad)
        self.wpis_gtd.clear()
        self._zapisz_gtd()

    def _wyczysc_gtd(self):
        self._gtd = gtd.wyczysc_zrobione(self._gtd)
        self._zapisz_gtd()

    def _pokaz_gtd(self):
        notatnik = self._widok_listy == "notatnik"
        for w in (self.notatki, self.stan_notatek):
            w.setVisible(notatnik)
        for w in (self.rzad_wpisu, self.kontekst_gtd):
            w.setVisible(not notatnik)
        self.btn_wyczysc_gtd.setVisible(self._widok_listy == "zrobione")
        licz = gtd.liczniki(self._gtd)
        for klucz, nazwa in gtd.LISTY:
            n = licz[klucz]
            self.przyciski_list[klucz].setText(f"{nazwa}   {n}" if n and klucz != "zrobione" else nazwa)
        # konteksty do filtra (bez gubienia wyboru)
        wybrany = self.kontekst_gtd.currentData() or ""
        self.kontekst_gtd.blockSignals(True)
        self.kontekst_gtd.clear()
        self.kontekst_gtd.addItem("Wszystkie konteksty", "")
        for kon in gtd.konteksty(self._gtd):
            self.kontekst_gtd.addItem(f"@{kon}", kon)
        self.kontekst_gtd.setCurrentIndex(max(0, self.kontekst_gtd.findData(wybrany)))
        self.kontekst_gtd.blockSignals(False)
        self.naglowek_listy.setText(dict(gtd.LISTY + [("notatnik", "Notatnik")])[self._widok_listy])
        while self.lista_gtd.count():
            w = self.lista_gtd.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        if notatnik:
            self.pusto_gtd.hide()
            return
        zadania = gtd.w_widoku(self._gtd, self._widok_listy, self.kontekst_gtd.currentData() or "")
        for z in zadania[:200]:
            self.lista_gtd.addWidget(self._wiersz_gtd(z))
        puste = {"dzis": "Nic na dziś. Zadania z terminem na dziś i ważne (!) pojawią się tutaj.",
                 "skrzynka": "Skrzynka pusta. Wpisz wszystko, co przyjdzie do głowy, a potem rozdziel.",
                 "zrobione": "Brak zrobionych zadań."}
        self.pusto_gtd.setText(puste.get(self._widok_listy, "Pusto."))
        self.pusto_gtd.setVisible(not zadania)

    def _wiersz_gtd(self, z) -> QFrame:
        wiersz = QFrame(objectName="zadanie")
        wu = QHBoxLayout(wiersz)
        wu.setContentsMargins(12, 8, 8, 8)
        wu.setSpacing(10)
        pole = QCheckBox()
        pole.setChecked(z.zrobione)
        pole.setToolTip("Zrobione")
        pole.toggled.connect(lambda stan, x=z: (gtd.odhacz(x, stan), self._zapisz_gtd()))
        wu.addWidget(pole)
        gw = QToolButton(objectName="gwiazdka")
        gw.setIcon(ikona("gwiazdka", "#d99a00" if z.wazne else "#c3c9ce", rozmiar=18))
        gw.setToolTip("Ważne")
        gw.setCursor(Qt.CursorShape.PointingHandCursor)
        gw.clicked.connect(lambda _=False, x=z: (setattr(x, "wazne", not x.wazne), self._zapisz_gtd()))
        wu.addWidget(gw)
        tekst = QLabel(html_escape(z.tekst), wordWrap=True, textFormat=Qt.TextFormat.RichText)
        tekst.setStyleSheet(f"font-size: 14px; {'color: ' + TEKST_3 + '; text-decoration: line-through;' if z.zrobione else ''}")
        tekst.setCursor(Qt.CursorShape.IBeamCursor)
        tekst.mouseDoubleClickEvent = lambda _e, x=z: self._edytuj_gtd(x)
        wu.addWidget(tekst, 1)
        if self._widok_listy == "dzis" and z.lista != "nastepne":
            lst = QLabel(gtd.NAZWY_LIST[z.lista])
            lst.setStyleSheet(f"color: {TEKST_3}; font-size: 12px;")
            wu.addWidget(lst)
        if z.kontekst:
            kon = QLabel(f"@{z.kontekst}")
            kon.setStyleSheet(f"background: {AKCENT_TLO}; color: {AKCENT}; border-radius: 9px; padding: 2px 8px; "
                              "font-size: 12px; font-weight: 600;")
            wu.addWidget(kon)
        if z.termin:
            ter = QLabel(gtd.opis_terminu(z.termin))
            kolor = CZERWONY if z.po_terminie() else (AKCENT if z.termin == date.today().isoformat() else TEKST_2)
            ter.setStyleSheet(f"color: {kolor}; font-size: 12px; font-weight: 600;")
            wu.addWidget(ter)
        wiecej = QToolButton(objectName="gwiazdka")
        wiecej.setIcon(ikona("wiecej", TEKST_2, rozmiar=18))
        wiecej.setToolTip("Przenieś, termin, kontekst, edycja")
        wiecej.setCursor(Qt.CursorShape.PointingHandCursor)
        wiecej.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(wiecej)
        for klucz in gtd.PRZENOSZENIE:
            if klucz != z.lista:
                menu.addAction(f"Przenieś: {gtd.NAZWY_LIST[klucz]}",
                               lambda x=z, kl=klucz: (setattr(x, "lista", kl), setattr(x, "zrobiono", ""),
                                                      self._zapisz_gtd()))
        menu.addSeparator()
        menu.addAction("Termin: dziś", lambda x=z: self._termin_gtd(x, date.today()))
        menu.addAction("Termin: jutro", lambda x=z: self._termin_gtd(x, date.today() + timedelta(days=1)))
        menu.addAction("Termin: za tydzień", lambda x=z: self._termin_gtd(x, date.today() + timedelta(days=7)))
        if z.termin:
            menu.addAction("Bez terminu", lambda x=z: self._termin_gtd(x, None))
        konteksty = menu.addMenu("Kontekst")
        for kon in gtd.konteksty(self._gtd):
            konteksty.addAction(f"@{kon}", lambda x=z, k=kon: (setattr(x, "kontekst", k), self._zapisz_gtd()))
        konteksty.addAction("Bez kontekstu", lambda x=z: (setattr(x, "kontekst", ""), self._zapisz_gtd()))
        menu.addSeparator()
        menu.addAction("Edytuj…", lambda x=z: self._edytuj_gtd(x))
        menu.addAction("Przypomnij o tym…", lambda x=z: (self.pokaz("przypomnienia"),
                                                          self.tekst_przyp.setText(x.tekst),
                                                          self.godzina_przyp.setFocus()))
        menu.addAction("Usuń", lambda x=z: (self._gtd.remove(x), self._zapisz_gtd()))
        wiecej.setMenu(menu)
        wu.addWidget(wiecej)
        return wiersz

    def _termin_gtd(self, z, dzien):
        z.termin = dzien.isoformat() if dzien else ""
        self._zapisz_gtd()

    def _edytuj_gtd(self, z):
        tekst, ok = QInputDialog.getText(self, "Edytuj", "Zadanie:", text=z.tekst)
        if ok and tekst.strip():
            z.tekst = tekst.strip()[:500]
            self._zapisz_gtd()

    @staticmethod
    def _duzy_czas() -> QLabel:
        etykieta = QLabel("00:00", alignment=Qt.AlignmentFlag.AlignCenter)
        etykieta.setStyleSheet(f"color: {AKCENT}; font-size: 72px; font-weight: 300; letter-spacing: -1px;")
        etykieta.setMinimumHeight(100)
        return etykieta

    # ---- stoper
    def _karta_stopera(self) -> QFrame:
        k, ku = karta()
        self.czas_stopera = self._duzy_czas()
        ku.addWidget(self.czas_stopera)
        self._stoper_start: float | None = None
        self._stoper_suma = 0.0
        self._tik_stopera = QTimer(self, interval=100)
        self._tik_stopera.timeout.connect(self._pokaz_stoper)
        rzad = QHBoxLayout()
        self.btn_stoper = przycisk("Start", "odswiez", "glowny", self._stoper_start_stop)
        rzad.addWidget(self.btn_stoper)
        rzad.addWidget(przycisk("Zeruj", akcja=self._stoper_zeruj))
        ku.addLayout(rzad)
        return k

    def _stoper_minelo(self) -> float:
        return self._stoper_suma + (time.monotonic() - self._stoper_start if self._stoper_start else 0.0)

    def _pokaz_stoper(self):
        sekundy = self._stoper_minelo()
        m, s_ = divmod(sekundy, 60)
        self.czas_stopera.setText(f"{int(m):02d}:{int(s_):02d}.{int((s_ % 1) * 10)}")

    def _stoper_start_stop(self):
        if self._stoper_start is None:
            self._stoper_start = time.monotonic()
            self._tik_stopera.start()
            self.btn_stoper.setText("Stop")
        else:
            self._stoper_suma = self._stoper_minelo()
            self._stoper_start = None
            self._tik_stopera.stop()
            self.btn_stoper.setText("Start")
        self._pokaz_stoper()

    def _stoper_zeruj(self):
        self._stoper_start, self._stoper_suma = None, 0.0
        self._tik_stopera.stop()
        self.btn_stoper.setText("Start")
        self._pokaz_stoper()

    # ---- minutnik
    def _karta_minutnika(self) -> QFrame:
        k, ku = karta()
        self.czas_minutnika = self._duzy_czas()
        ku.addWidget(self.czas_minutnika)
        szybkie = QHBoxLayout()
        szybkie.setSpacing(4)
        for minuty in (1, 2, 3, 5, 10, 15):
            b = przycisk(f"{minuty}′", styl="plaski", akcja=lambda _=False, m=minuty: self._minutnik_ustaw(m * 60))
            b.setToolTip(f"{minuty} min")
            szybkie.addWidget(b)
        ku.addLayout(szybkie)
        rzad = QHBoxLayout()
        self.minuty_minutnika = QSpinBox(minimum=1, maximum=180, suffix=" min", value=5)
        rzad.addWidget(self.minuty_minutnika)
        self.btn_minutnik = przycisk("Start", "odswiez", "glowny", self._minutnik_start_stop)
        rzad.addWidget(self.btn_minutnik)
        rzad.addWidget(przycisk("Zeruj", akcja=lambda: self._minutnik_ustaw(self.minuty_minutnika.value() * 60,
                                                                           start=False)))
        ku.addLayout(rzad)
        self._minutnik_koniec: float | None = None
        self._minutnik_zostalo = 5 * 60.0
        self._tik_minutnika = QTimer(self, interval=200)
        self._tik_minutnika.timeout.connect(self._pokaz_minutnik)
        self._pokaz_minutnik()
        return k

    def _minutnik_ustaw(self, sekundy: int, start: bool = True):
        self._minutnik_koniec = None
        self._tik_minutnika.stop()
        self._minutnik_zostalo = float(sekundy)
        self.minuty_minutnika.setValue(max(1, sekundy // 60))
        self.btn_minutnik.setText("Start")
        self._pokaz_minutnik()
        if start:
            self._minutnik_start_stop()

    def _minutnik_start_stop(self):
        if self._minutnik_koniec is None:
            if self._minutnik_zostalo <= 0:
                self._minutnik_zostalo = self.minuty_minutnika.value() * 60.0
            self._minutnik_koniec = time.monotonic() + self._minutnik_zostalo
            self._tik_minutnika.start()
            self.btn_minutnik.setText("Pauza")
        else:
            self._minutnik_zostalo = max(0.0, self._minutnik_koniec - time.monotonic())
            self._minutnik_koniec = None
            self._tik_minutnika.stop()
            self.btn_minutnik.setText("Start")
        self._pokaz_minutnik()

    def _pokaz_minutnik(self):
        zostalo = self._minutnik_zostalo if self._minutnik_koniec is None else self._minutnik_koniec - time.monotonic()
        if self._minutnik_koniec is not None and zostalo <= 0:
            self._minutnik_koniec = None
            self._minutnik_zostalo = 0.0
            self._tik_minutnika.stop()
            self.btn_minutnik.setText("Start")
            QApplication.beep()
            self.okno.powiadom("Minutnik: czas minął", f"Minęło {self.minuty_minutnika.value()} min.", "uwaga",
                               czas_ms=20000)
            zostalo = 0
        m, s_ = divmod(max(0, int(zostalo + 0.999)), 60)
        self.czas_minutnika.setText(f"{m:02d}:{s_:02d}")

    # ---- kalkulator
    def _karta_kalkulatora(self) -> QFrame:
        k, ku = karta()
        self.wynik_kalkulatora = self._duzy_czas()
        self.wynik_kalkulatora.setText("0")
        self.wynik_kalkulatora.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ku.addWidget(self.wynik_kalkulatora)
        self.dzialanie = QLineEdit(placeholderText="np. 900+150 albo 1200*0,9")
        self.dzialanie.textChanged.connect(self._licz)
        ku.addWidget(self.dzialanie)
        self.blad_kalkulatora = QLabel(objectName="drobny")
        ku.addWidget(self.blad_kalkulatora)
        ku.addStretch()
        return k

    def _licz(self, tekst: str):
        from .kalkulator import formatuj, oblicz
        if not tekst.strip():
            self.wynik_kalkulatora.setText("0")
            self.blad_kalkulatora.clear()
            return
        try:
            self.wynik_kalkulatora.setText(formatuj(oblicz(tekst)))
            self.blad_kalkulatora.clear()
        except (ValueError, SyntaxError) as e:
            self.blad_kalkulatora.setText(str(e) if isinstance(e, ValueError) else "Niepełne działanie")

    # ---- przypomnienia
    def _karta_przypomnien(self) -> QFrame:
        k, ku = karta()
        self.tekst_przyp = QLineEdit(placeholderText="Np. oddzwonić do laboratorium")
        self.tekst_przyp.returnPressed.connect(self._dodaj_przypomnienie)
        ku.addWidget(self.tekst_przyp)
        rzad = QHBoxLayout()
        self.godzina_przyp = QLineEdit(placeholderText="14:30 lub +15")
        self.godzina_przyp.setMinimumWidth(100)
        self.godzina_przyp.returnPressed.connect(self._dodaj_przypomnienie)
        rzad.addWidget(self.godzina_przyp, 1)
        szybkie = [("+15′", "+15"), ("+30′", "+30"), ("+1 h", "+60")]
        for opis, wartosc in szybkie:
            rzad.addWidget(przycisk(opis, styl="plaski", akcja=lambda _=False, w=wartosc: (
                self.godzina_przyp.setText(w), self._dodaj_przypomnienie())))
        rzad.addWidget(przycisk("Dodaj", "plus", "glowny", self._dodaj_przypomnienie))
        ku.addLayout(rzad)
        self.lista_przyp = QVBoxLayout()
        self.lista_przyp.setSpacing(4)
        ku.addLayout(self.lista_przyp)
        self.blad_przyp = QLabel(objectName="drobny")
        ku.addWidget(self.blad_przyp)
        ku.addStretch()
        self._zegar_przyp = QTimer(self, interval=20_000)
        self._zegar_przyp.timeout.connect(self._sprawdz_przypomnienia)
        self._zegar_przyp.start()
        return k

    def _przypomnienia(self) -> list[dict]:
        return narzedzia.wczytaj_przypomnienia(self.okno.baza.ustawienia().get("przypomnienia", ""))

    def _zapisz_przypomnienia(self, lista: list[dict]):
        self.okno.baza.zapisz_ustawienia({"przypomnienia": narzedzia.zapisz_przypomnienia(lista)})
        self._pokaz_przypomnienia()

    def _dodaj_przypomnienie(self):
        tekst = self.tekst_przyp.text().strip()
        try:
            kiedy = narzedzia.kiedy_przypomniec(self.godzina_przyp.text() or "+15", datetime.now())
        except ValueError:
            self.blad_przyp.setText("Godzina jak 14:30 albo +15 (za 15 minut).")
            return
        if not tekst:
            self.blad_przyp.setText("Wpisz, o czym przypomnieć.")
            return
        self.blad_przyp.clear()
        self._zapisz_przypomnienia(self._przypomnienia() + [{"kiedy": kiedy.isoformat(timespec="minutes"),
                                                             "tekst": tekst}])
        self.godzina_przyp.clear()
        self.tekst_przyp.clear()

    def _usun_przypomnienie(self, p: dict):
        self._zapisz_przypomnienia([x for x in self._przypomnienia() if x != p])

    def _pokaz_przypomnienia(self):
        while self.lista_przyp.count():
            w = self.lista_przyp.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        dzis = date.today()
        for p in self._przypomnienia()[:8]:
            kiedy = datetime.fromisoformat(p["kiedy"])
            wiersz = QWidget()
            wu = QHBoxLayout(wiersz)
            wu.setContentsMargins(0, 0, 0, 0)
            dzien = "" if kiedy.date() == dzis else ("jutro " if kiedy.date() == dzis + timedelta(days=1)
                                                     else f"{kiedy:%d.%m} ")
            godz = QLabel(f"{dzien}{kiedy:%H:%M}")
            godz.setStyleSheet(f"color: {AKCENT}; font-weight: 650;")
            wu.addWidget(godz)
            opis = QLabel(p["tekst"], wordWrap=True)
            wu.addWidget(opis, 1)
            usun = przycisk("", "kosz", "plaski", lambda _=False, x=p: self._usun_przypomnienie(x))
            usun.setToolTip("Usuń")
            wu.addWidget(usun)
            self.lista_przyp.addWidget(wiersz)

    def _sprawdz_przypomnienia(self):
        try:
            teraz, reszta = narzedzia.do_przypomnienia(self._przypomnienia(), datetime.now())
        except Exception:  # noqa: BLE001 - np. program zablokowany w trakcie
            return
        if not teraz:
            return
        for p in teraz:
            QApplication.beep()
            self.okno.powiadom("Przypomnienie", p["tekst"], "uwaga", czas_ms=30000)
        self._zapisz_przypomnienia(reszta)

    # ---- liczenie kasy
    def _karta_kasy(self) -> QFrame:
        k, ku = karta()
        siatka = QGridLayout()
        siatka.setHorizontalSpacing(8)
        siatka.setVerticalSpacing(4)
        self.ilosci_kasy: dict[int, QSpinBox] = {}
        for i, nominal in enumerate(narzedzia.NOMINALY):
            pole = QSpinBox(minimum=0, maximum=9999)
            pole.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            pole.setMaximumWidth(64)
            pole.valueChanged.connect(self._policz_kase)
            self.ilosci_kasy[nominal] = pole
            wiersz, kol = i % 8, (i // 8) * 2
            siatka.addWidget(QLabel(narzedzia.opis_nominalu(nominal)), wiersz, kol)
            siatka.addWidget(pole, wiersz, kol + 1)
        ku.addLayout(siatka)
        self.suma_kasy = QLabel("0,00 zł")
        self.suma_kasy.setStyleSheet(f"color: {AKCENT}; font-size: 40px; font-weight: 600;")
        ku.addWidget(self.suma_kasy)
        self.porownanie_kasy = QLabel(wordWrap=True, objectName="podtytul")
        ku.addWidget(self.porownanie_kasy)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Porównaj z dzisiejszą gotówką", "wzrost", akcja=self._porownaj_kase))
        rzad.addWidget(przycisk("Wyczyść", akcja=lambda: [p.setValue(0) for p in self.ilosci_kasy.values()]))
        ku.addLayout(rzad)
        ku.addStretch()
        return k

    def _kwota_kasy(self) -> float:
        return narzedzia.suma_kasy({n: p.value() for n, p in self.ilosci_kasy.items()})

    def _policz_kase(self):
        self.suma_kasy.setText(f"{druk.zl(self._kwota_kasy())} zł")
        self.porownanie_kasy.clear()

    def _porownaj_kase(self):
        o = self.okno
        asystentka_moze = not o.jest_wlascicielka and o.baza.ustawienia()["asystentki_zamkniecie_dnia"] == "1"
        if not o.jest_wlascicielka and not asystentka_moze and not o.potwierdz_haslem(
                "porównanie kasy", "Porównanie pokazuje dzisiejszy utarg, dlatego wymaga hasła."):
            return
        dzis = date.today()
        dokumenty = [d for d in o.baza.dokumenty(rok=dzis.year, miesiac=dzis.month)
                     if d.data_wystawienia == dzis.isoformat()]
        gotowka = round(podsumuj(dokumenty).wg_platnosci.get("gotówka", 0), 2)
        roznica = round(self._kwota_kasy() - gotowka, 2)
        if abs(roznica) < 0.005:
            tekst, kolor = f"Zgadza się z gotówką z dokumentów ({druk.zl(gotowka)} zł).", ZIELONY
        else:
            tekst = (f"Gotówka z dokumentów: {druk.zl(gotowka)} zł. "
                     f"{'Nadwyżka' if roznica > 0 else 'Brakuje'}: {druk.zl(abs(roznica))} zł.")
            kolor = CZERWONY
        self.porownanie_kasy.setText(tekst)
        self.porownanie_kasy.setStyleSheet(f"color: {kolor};")
        o.dziennik.zapisz(f"liczenie kasy: różnica {roznica:+.2f} zł")

    # ---- daty
    def _karta_dat(self) -> QFrame:
        k, ku = karta()
        rzad = QHBoxLayout()
        self.data_od = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        rzad.addWidget(self.data_od)
        rzad.addWidget(QLabel("+"))
        self.ile_dat = QSpinBox(minimum=-999, maximum=999, value=6)
        rzad.addWidget(self.ile_dat)
        self.jednostka_dat = QComboBox()
        self.jednostka_dat.addItems(["dni", "tygodnie", "miesiące", "lata"])
        self.jednostka_dat.setCurrentText("miesiące")
        rzad.addWidget(self.jednostka_dat, 1)
        ku.addLayout(rzad)
        szybkie = QHBoxLayout()
        szybkie.setSpacing(4)
        for opis, ile, jedn in (("7 dni", 7, "dni"), ("14 dni", 14, "dni"), ("3 mies.", 3, "miesiące"),
                                ("6 mies.", 6, "miesiące"), ("rok", 1, "lata")):
            szybkie.addWidget(przycisk(opis, styl="plaski", akcja=lambda _=False, i=ile, j=jedn: (
                self.ile_dat.setValue(i), self.jednostka_dat.setCurrentText(j))))
        ku.addLayout(szybkie)
        self.wynik_daty = QLabel()
        self.wynik_daty.setStyleSheet(f"color: {AKCENT}; font-size: 20px; font-weight: 600;")
        self.wynik_daty.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ku.addWidget(self.wynik_daty)
        ku.addSpacing(4)
        rzad2 = QHBoxLayout()
        rzad2.addWidget(QLabel("Do dnia"))
        self.data_do = QDateEdit(QDate.currentDate().addDays(30), calendarPopup=True, displayFormat="dd.MM.yyyy")
        rzad2.addWidget(self.data_do, 1)
        ku.addLayout(rzad2)
        self.roznica_dat = QLabel(objectName="podtytul", wordWrap=True)
        ku.addWidget(self.roznica_dat)
        for sygnal in (self.data_od.dateChanged, self.ile_dat.valueChanged, self.jednostka_dat.currentTextChanged,
                       self.data_do.dateChanged):
            sygnal.connect(self._licz_daty)
        self._licz_daty()
        ku.addStretch()
        return k

    def _licz_daty(self, *_):
        od = self.data_od.date().toPython()
        wynik = narzedzia.przesun_date(od, self.ile_dat.value(), self.jednostka_dat.currentText())
        swieto = narzedzia.swieto(wynik)
        self.wynik_daty.setText(f"{wynik:%d.%m.%Y} · {godziny.DNI[wynik.weekday()]}" + (f" · {swieto}" if swieto else ""))
        do = self.data_do.date().toPython()
        dni = (do - od).days
        self.roznica_dat.setText(f"Od {od:%d.%m} do {do:%d.%m.%Y}: {dni} dni "
                                 f"({narzedzia.dni_robocze(od, do)} roboczych)")

    # ---- rabat i raty
    def _karta_rabatu(self) -> QFrame:
        k, ku = karta()
        forma = QFormLayout()
        self.kwota_rabatu = QLineEdit(placeholderText="np. 2 400")
        self.proc_rabatu = QSpinBox(minimum=0, maximum=100, suffix=" %")
        self.raty = QSpinBox(minimum=1, maximum=48, value=1)
        forma.addRow("Kwota", self.kwota_rabatu)
        forma.addRow("Rabat", self.proc_rabatu)
        forma.addRow("Liczba rat", self.raty)
        ku.addLayout(forma)
        self.wynik_rabatu = QLabel(wordWrap=True, textFormat=Qt.TextFormat.RichText)
        self.wynik_rabatu.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ku.addWidget(self.wynik_rabatu)
        self.kwota_rabatu.textChanged.connect(self._licz_rabat)
        self.proc_rabatu.valueChanged.connect(self._licz_rabat)
        self.raty.valueChanged.connect(self._licz_rabat)
        ku.addStretch()
        return k

    def _licz_rabat(self, *_):
        kwota = liczba_lub_none(self.kwota_rabatu.text())
        if kwota is None:
            self.wynik_rabatu.clear()
            return
        try:
            rabat, po, raty = narzedzia.rabat_i_raty(kwota, self.proc_rabatu.value(), self.raty.value())
        except ValueError as e:
            self.wynik_rabatu.setText(html_escape(str(e)))
            return
        tekst = (f"<span style='font-size:20px; font-weight:600; color:{AKCENT}'>{druk.zl(po)} zł</span>"
                 + (f"<br>rabat {druk.zl(rabat)} zł" if rabat else ""))
        if len(raty) > 1:
            tekst += (f"<br>{len(raty)} rat po {druk.zl(raty[0])} zł"
                      + (f" (ostatnia {druk.zl(raty[-1])} zł)" if raty[-1] != raty[0] else ""))
        self.wynik_rabatu.setText(tekst)

    # ---- generator haseł
    def _karta_hasel(self) -> QFrame:
        k, ku = karta()
        self.haslo_gen = QLineEdit(readOnly=True)
        self.haslo_gen.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace; font-size: 16px;")
        ku.addWidget(self.haslo_gen)
        rzad = QHBoxLayout()
        self.dlugosc_hasla = QSpinBox(minimum=8, maximum=40, value=14, suffix=" znaków")
        rzad.addWidget(self.dlugosc_hasla)
        self.znaki_hasla = QCheckBox("znaki specjalne", checked=True)
        rzad.addWidget(self.znaki_hasla)
        rzad.addStretch()
        ku.addLayout(rzad)
        rzad_schowka = QHBoxLayout()
        rzad_schowka.addWidget(QLabel("Czyść schowek po"))
        self.czas_schowka = QSpinBox(minimum=5, maximum=600, singleStep=5, value=30, suffix=" s")
        self.czas_schowka.valueChanged.connect(
            lambda v: self.okno.baza.zapisz_ustawienia({"schowek_sekund": str(v)}))
        rzad_schowka.addWidget(self.czas_schowka)
        for sekundy in (10, 30, 60, 120):
            rzad_schowka.addWidget(przycisk(f"{sekundy} s" if sekundy < 60 else f"{sekundy // 60} min", styl="plaski",
                                            akcja=lambda _=False, v=sekundy: self.czas_schowka.setValue(v)))
        rzad_schowka.addStretch()
        ku.addLayout(rzad_schowka)
        self._schowek_zostalo = 0
        self._schowek_haslo = ""
        self._tik_schowka = QTimer(self, interval=1000)
        self._tik_schowka.timeout.connect(self._odliczaj_schowek)
        rzad2 = QHBoxLayout()
        rzad2.addWidget(przycisk("Nowe hasło", "odswiez", "glowny", self._nowe_haslo))
        rzad2.addWidget(przycisk("Kopiuj", "kopiuj", akcja=self._kopiuj_haslo))
        rzad2.addStretch()
        ku.addLayout(rzad2)
        self.stan_hasla = QLabel(objectName="drobny")
        ku.addWidget(self.stan_hasla)
        self.dlugosc_hasla.valueChanged.connect(self._nowe_haslo)
        self.znaki_hasla.toggled.connect(self._nowe_haslo)
        self._nowe_haslo()
        ku.addStretch()
        return k

    # ---- skaner plików
    def _karta_skanera(self) -> QFrame:
        k, ku = karta()
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Wybierz pliki…", "plus", "glowny", self._skanuj_wybrane))
        rzad.addWidget(przycisk("Sprawdź folder Pobrane (7 dni)", "pobierz", akcja=self._skanuj_pobrane))
        rzad.addStretch()
        ku.addLayout(rzad)
        self.wyniki_skanera = QLabel(wordWrap=True, textFormat=Qt.TextFormat.RichText)
        self.wyniki_skanera.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ku.addWidget(self.wyniki_skanera)
        ku.addStretch()
        return k

    def _skanuj_wybrane(self):
        sciezki, _ = QFileDialog.getOpenFileNames(self, "Pliki do sprawdzenia", str(katalog_pobranych()))
        if sciezki:
            self._skanuj([Path(p) for p in sciezki])

    def _skanuj_pobrane(self):
        from . import skaner
        pliki = skaner.nowe_pobrane(katalog_pobranych(), time.time() - 7 * 86400, limit=200)
        if not pliki:
            self.wyniki_skanera.setText("W folderze Pobrane nie ma plików z ostatnich 7 dni.")
            return
        self._skanuj(pliki)

    def _skanuj(self, pliki: list[Path]):
        from . import skaner
        self.wyniki_skanera.setText(f"Sprawdzanie {len(pliki)} plików…")
        w = Watek(lambda: [skaner.skanuj(p) for p in pliki])
        w.gotowe.connect(self._pokaz_wyniki_skanu)
        w.blad.connect(lambda t: self.wyniki_skanera.setText(html_escape(t)))
        self.okno._w_tle(w)

    def _pokaz_wyniki_skanu(self, wyniki):
        from . import skaner
        kolory = {skaner.CZYSTY: ZIELONY, skaner.PODEJRZANY: "#b26a00", skaner.ZAGROZENIE: CZERWONY}
        kolejnosc = {skaner.ZAGROZENIE: 0, skaner.PODEJRZANY: 1, skaner.CZYSTY: 2}
        wyniki = sorted(wyniki, key=lambda w: kolejnosc[w.stan])
        zle = sum(w.stan != skaner.CZYSTY for w in wyniki)
        naglowek = (f"<b>Sprawdzono {len(wyniki)} plików.</b> " +
                    (f"<span style='color:{CZERWONY}'>Uwaga: {zle}.</span>" if zle else
                     f"<span style='color:{ZIELONY}'>Wszystkie bez zastrzeżeń.</span>") +
                    (f"<br><span style='color:{TEKST_2}'>Sprawdził: {html_escape(wyniki[0].antywirus)} "
                     "i własna analiza Fakturnika</span>" if wyniki else ""))
        wiersze = [f"<span style='color:{kolory[w.stan]}; font-weight:600'>●</span> {html_escape(w.plik)} — "
                   f"<span style='color:{kolory[w.stan]}'>{html_escape(w.opis)}</span>" for w in wyniki[:60]]
        self.wyniki_skanera.setText(naglowek + "<br><br>" + "<br>".join(wiersze))
        if zle:
            self.okno.dziennik.zapisz(f"SKANER: pliki z uwagami ({zle} z {len(wyniki)})")

    def _nowe_haslo(self, *_):
        self.haslo_gen.setText(narzedzia.generuj_haslo(self.dlugosc_hasla.value(), self.znaki_hasla.isChecked()))
        self.stan_hasla.clear()

    def _kopiuj_haslo(self):
        self._schowek_haslo = self.haslo_gen.text()
        QApplication.clipboard().setText(self._schowek_haslo)
        self._schowek_zostalo = self.czas_schowka.value()
        self._tik_schowka.start()
        self._odliczaj_schowek(odlicz=False)

    def _odliczaj_schowek(self, odlicz: bool = True):
        """Odliczanie do wyczyszczenia schowka; czyści tylko, jeśli nadal jest w nim skopiowane hasło."""
        schowek = QApplication.clipboard()
        if odlicz:
            self._schowek_zostalo -= 1
        if schowek.text() != self._schowek_haslo:  # w międzyczasie skopiowano coś innego
            self._tik_schowka.stop()
            self.stan_hasla.clear()
            return
        if self._schowek_zostalo <= 0:
            schowek.clear()
            self._tik_schowka.stop()
            self._schowek_haslo = ""
            self.stan_hasla.setText("Schowek wyczyszczony.")
            return
        m, sek = divmod(self._schowek_zostalo, 60)
        self.stan_hasla.setText(f"Skopiowano. Schowek wyczyści się za {f'{m} min {sek:02d} s' if m else f'{sek} s'}.")

    def wyczysc_schowek_teraz(self):
        """Przy blokadzie i zamknięciu programu: skopiowane hasło nie zostaje w schowku."""
        if self._schowek_haslo and QApplication.clipboard().text() == self._schowek_haslo:
            QApplication.clipboard().clear()
        self._schowek_haslo = ""
        self._tik_schowka.stop()
        self.stan_hasla.clear()

    @staticmethod
    def _tytul(tytul: str, opis: str) -> QWidget:
        w = QWidget()
        u = QVBoxLayout(w)
        u.setContentsMargins(0, 0, 0, 0)
        u.setSpacing(1)
        t = QLabel(tytul)
        t.setStyleSheet("font-weight: 650; font-size: 14px;")
        u.addWidget(t)
        return w

    def odswiez(self):
        self.notatki.blockSignals(True)
        self.notatki.setPlainText(self.okno.baza.ustawienia()["notatki"])
        self.notatki.blockSignals(False)
        self.stan_notatek.setText("Zapisuje się samo.")
        self._pokaz_przypomnienia()
        self._wczytaj_gtd()
        self._pokaz_gtd()
        self._odswiez_kafelki()
        self.czas_schowka.blockSignals(True)
        try:
            self.czas_schowka.setValue(int(self.okno.baza.ustawienia().get("schowek_sekund") or 30))
        except ValueError:
            pass
        self.czas_schowka.blockSignals(False)

    def _zapisz_notatki(self):
        self.okno.baza.zapisz_ustawienia({"notatki": self.notatki.toPlainText()})
        self.stan_notatek.setText(f"Zapisano {datetime.now():%H:%M}.")

    def szukaj_firmy(self):
        self.btn_szukaj.setEnabled(False)
        self.wynik_firmy.setText("Sprawdzanie…")
        self.btn_faktura.hide()
        w = Watek(mf.szukaj, self.nip.text())
        w.gotowe.connect(self._firma)
        w.blad.connect(lambda tekst: (self.btn_szukaj.setEnabled(True),
                                      self.wynik_firmy.setText(f"<span style='color:{CZERWONY}'>{html_escape(tekst)}</span>")))
        self.okno._w_tle(w)

    def _firma(self, firma):
        self.btn_szukaj.setEnabled(True)
        self.firma = firma
        if firma is None:
            self.wynik_firmy.setText("Brak w wykazie podatników VAT (np. firma zwolniona z VAT lub błędny NIP).")
            return
        kolor = ZIELONY if firma.status_vat == "Czynny" else CZERWONY
        konta_txt = "<br>".join(html_escape(formatuj_konto(k)) for k in firma.konta[:3])
        self.wynik_firmy.setText(
            f"<b>{html_escape(firma.nazwa)}</b><br>{html_escape(mf.adres_dwulinijkowy(firma.adres))}<br>"
            f"Status VAT: <span style='color:{kolor}; font-weight:600'>{html_escape(firma.status_vat or 'brak')}</span>"
            + (f" · REGON {html_escape(firma.regon)}" if firma.regon else "")
            + (f"<br><span style='color:{TEKST_2}'>Konta z białej listy:</span><br>{konta_txt}" if konta_txt else ""))
        self.btn_faktura.show()

    def faktura_dla_firmy(self):
        f = self.firma
        s = self.okno.strona_nowy
        if not f or not s.porzuc_tryb():
            return
        self.okno.przejdz(STRONA_NOWY)
        s.ustaw_rodzaj("Faktura")
        s.nabywca.setText(f.nazwa)
        s.nabywca_adres.setText(mf.adres_dwulinijkowy(f.adres))
        s.nabywca_id.setText(f.nip)
        s.pokaz_krok(1)

    def _sprawdz_numer(self, tekst: str):
        cyfry = "".join(c for c in tekst if c.isalnum())
        if len(cyfry) in (26, 28):
            ok = konto_poprawne(tekst)
            self.wynik_numeru.setText("Numer konta poprawny" if ok else "Błędny numer konta (suma kontrolna)")
            self.wynik_numeru.setStyleSheet(f"color: {ZIELONY if ok else CZERWONY};")
            return
        wynik = opis_identyfikatora(tekst)
        opis = wynik[0] if wynik else ""
        if pesel := narzedzia.dane_z_peselu(tekst):
            opis += (f" · ur. {pesel.urodzenie:%d.%m.%Y}, {pesel.wiek()} "
                     f"{'rok' if pesel.wiek() == 1 else 'lata' if pesel.wiek() % 10 in (2, 3, 4) and pesel.wiek() % 100 not in (12, 13, 14) else 'lat'}"
                     f", {pesel.plec}")
        self.wynik_numeru.setText(opis)
        self.wynik_numeru.setStyleSheet(f"color: {ZIELONY if wynik and wynik[1] else CZERWONY};")

    def _slownie(self, tekst: str):
        from .slownie import kwota_slownie
        kwota = liczba_lub_none(tekst)
        self.slownie.setText(kwota_slownie(kwota) if kwota is not None and kwota >= 0 else "")


class OknoSzukania(QDialog):
    """Szybkie wyszukiwanie (Ctrl+K): ekrany, narzędzia, działania i pacjenci w jednym miejscu."""

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.okno = okno
        self.setObjectName("szukanie")
        self.setFixedWidth(620)
        u = QVBoxLayout(self)
        u.setContentsMargins(14, 14, 14, 14)
        u.setSpacing(8)
        self.pole = QLineEdit(placeholderText="Szukaj: ekran, narzędzie, działanie albo pacjent…")
        self.pole.addAction(ikona("szukaj", AKCENT), QLineEdit.ActionPosition.LeadingPosition)
        self.pole.setStyleSheet("font-size: 16px; padding: 10px 12px;")
        u.addWidget(self.pole)
        self.lista = QListWidget()
        self.lista.setIconSize(QSize(18, 18))
        self.lista.setMinimumHeight(360)
        u.addWidget(self.lista)
        self.polecenia = okno.polecenia()
        self.pacjenci = [p.nazwa for p in okno.baza.pacjenci()]
        self.pole.textChanged.connect(self._filtruj)
        self.pole.returnPressed.connect(self._wykonaj)
        self.lista.itemActivated.connect(lambda _: self._wykonaj())
        self.pole.installEventFilter(self)
        self._filtruj("")

    def eventFilter(self, obj, event):
        if obj is self.pole and event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            krok = 1 if event.key() == Qt.Key.Key_Down else -1
            self.lista.setCurrentRow(max(0, min(self.lista.count() - 1, self.lista.currentRow() + krok)))
            return True
        return super().eventFilter(obj, event)

    def _filtruj(self, tekst: str):
        self.lista.clear()
        wyniki = [(narzedzia.ocena(nazwa, tekst), nazwa, opis, ik, akcja) for nazwa, opis, ik, akcja in self.polecenia]
        if len(tekst.strip()) >= 2:
            wyniki += [(narzedzia.ocena(p, tekst) - 3, p, "Pacjent · historia dokumentów", "uzytkownik",
                        lambda n=p: self.okno.pokaz_pacjenta(n)) for p in self.pacjenci]
        wyniki = sorted((w for w in wyniki if w[0] > 0), key=lambda w: -w[0])[:12]
        for _, nazwa, opis, ik, akcja in wyniki:
            el = QListWidgetItem(ikona(ik, AKCENT), f"{nazwa}    {opis}" if opis else nazwa)
            el.setData(Qt.ItemDataRole.UserRole, akcja)
            el.setSizeHint(QSize(0, 38))
            self.lista.addItem(el)
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def _wykonaj(self):
        el = self.lista.currentItem()
        if not el:
            return
        akcja = el.data(Qt.ItemDataRole.UserRole)
        self.accept()
        QTimer.singleShot(0, akcja)


class StronaUstawienia(Strona):
    POLA = [("nazwa", "Nazwa"), ("nip", "NIP"), ("regon", "REGON"), ("miejsce", "Miejsce wystawienia"),
            ("konto", "Nr konta do przelewów"),
            ("format_numeru", "Numer rachunku"),
            ("format_numeru_faktury", "Numer faktury"),
            ("format_numeru_korekty", "Numer korekty"),
            ("termin_dni", "Termin przelewu (dni)")]

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, przewijana=True)
        self._miniatury_tapet: list = []
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
        for klucz in ("format_numeru", "format_numeru_faktury", "format_numeru_korekty"):
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
        self.okno_drukarki = QCheckBox("Pokazuj ustawienia wydruku przed drukiem (drukarka, liczba egzemplarzy, kopia)")
        self.kopia = QCheckBox("Domyślnie drukuj oryginał i kopię")
        self.data_wydruku = QCheckBox("Drukuj na dokumencie datę i godzinę wydruku")
        self.data_wygenerowania = QCheckBox("Drukuj na zestawieniach datę i godzinę wygenerowania")
        self.druk_pesel = QCheckBox("Drukuj PESEL pacjenta na rachunku (nie jest wymagany)")
        self.druk_qr = QCheckBox("Kod QR do przelewu (skanowany aplikacją banku wypełnia przelew)")
        for w in (self.okno_drukarki, self.kopia, self.data_wydruku, self.data_wygenerowania, self.druk_pesel,
                  self.druk_qr):
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
        self.skaner_pobrane = QCheckBox("Sprawdzaj skanerem nowe pliki w folderze Pobrane (ostrzeżenie przy zagrożeniu)")
        ku.addWidget(self.skaner_pobrane)
        self.ochrona_ekranu = QCheckBox("Ukrywaj okna programu przed zrzutami i nagrywaniem ekranu "
                                        "(np. narzędzia AI, programy zdalnego dostępu)")
        ku.addWidget(self.ochrona_ekranu)
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
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- kopie zapasowe: trzy niezależne miejsca
        prawa.addWidget(sekcja("Kopie zapasowe"))
        k, ku = karta()
        self.stan_kopii = QLabel(objectName="drobny", wordWrap=True, textFormat=Qt.TextFormat.RichText)
        ku.addWidget(self.stan_kopii)
        rzad = QHBoxLayout()
        rzad.addWidget(QLabel("Trzecia kopia", objectName="etykieta"))
        self.kopia_folder = QLineEdit(placeholderText="Pendrive, dysk sieciowy albo folder OneDrive", readOnly=True)
        rzad.addWidget(self.kopia_folder, 1)
        rzad.addWidget(przycisk("Wybierz…", "archiwum", akcja=self._wybierz_folder_kopii))
        rzad.addWidget(przycisk("", "zamknij", "plaski", lambda: self.kopia_folder.clear()))
        ku.addLayout(rzad)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Zrób kopię teraz", "odswiez", akcja=lambda: (self.okno.kopia_ciagla(wymus=True),
                                                                            self._pokaz_stan_kopii())))
        rzad.addStretch()
        ku.addLayout(rzad)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- RODO
        prawa.addWidget(sekcja("RODO i prywatność"))
        k, ku = karta()
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
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- komputer i urządzenie
        prawa.addWidget(sekcja("Komputer i urządzenie"))
        k, ku = karta()
        self.stan_komputera = QLabel(objectName="drobny", wordWrap=True, textFormat=Qt.TextFormat.RichText)
        ku.addWidget(self.stan_komputera)
        rzad = QHBoxLayout()
        self.btn_weryfikacja = przycisk("", "tarcza", akcja=self.przelacz_weryfikacje)
        self.btn_kod = przycisk("Kod odzyskiwania…", "klucz", akcja=self.pokaz_kod)
        rzad.addWidget(self.btn_weryfikacja)
        rzad.addWidget(self.btn_kod)
        rzad.addStretch()
        ku.addLayout(rzad)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Kontrola komputera…", "tarcza", akcja=lambda: (self.okno.pokaz_kontrole(),
                                                                               self._pokaz_stan_komputera())))
        rzad.addWidget(przycisk("Przenieś na inny komputer…", "pobierz", akcja=self.migracja))
        self.btn_instaluj_admin = przycisk("Zainstaluj z uprawnieniami administratora…", "tarcza",
                                           akcja=self.instaluj_jako_admin)
        rzad.addWidget(self.btn_instaluj_admin)
        rzad.addStretch()
        ku.addLayout(rzad)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- konta i godziny pracy
        prawa.addWidget(sekcja("Konta i godziny pracy"))
        k, ku = karta()
        f = self._formularz(ku)
        self.nazwa_wlascicielki = QLineEdit(placeholderText="np. lek. dent. Anna Test")
        f.addRow("Konto właściciela", self.nazwa_wlascicielki)
        self.tabela_kont = QTableWidget(0, 2)
        self.tabela_kont.setHorizontalHeaderLabels(["Konto", "Rola"])
        self.tabela_kont.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabela_kont.verticalHeader().setVisible(False)
        self.tabela_kont.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela_kont.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela_kont.setMaximumHeight(150)
        ku.addWidget(self.tabela_kont)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Dodaj konto asystentki…", "plus", akcja=self.dodaj_konto))
        rzad.addWidget(przycisk("Zmień hasło…", "klucz", akcja=self.zmien_haslo_konta))
        rzad.addWidget(przycisk("Usuń konto…", "kosz", akcja=self.usun_konto))
        rzad.addStretch()
        ku.addLayout(rzad)
        ku.addWidget(separator())
        siatka = QGridLayout()
        siatka.setHorizontalSpacing(10)
        self.dni_pracy = []
        for d, nazwa in enumerate(godziny.DNI):
            pole_dnia = QCheckBox(nazwa.capitalize())
            od = QTimeEdit(displayFormat="HH:mm")
            do = QTimeEdit(displayFormat="HH:mm")
            for w in (od, do):
                w.setFixedWidth(90)
            pole_dnia.toggled.connect(lambda wl, a=od, b=do: (a.setEnabled(wl), b.setEnabled(wl)))
            siatka.addWidget(pole_dnia, d, 0)
            siatka.addWidget(od, d, 1)
            siatka.addWidget(QLabel("–"), d, 2)
            siatka.addWidget(do, d, 3)
            self.dni_pracy.append((pole_dnia, od, do))
        siatka.setColumnStretch(4, 1)
        ku.addLayout(siatka)
        f = self._formularz(ku)
        self.przypomnienie_min = QSpinBox(minimum=0, maximum=120, suffix=" min przed końcem")
        self.przypomnienie_min.setSpecialValueText("bez przypomnienia")
        f.addRow("Przypomnienie", self.przypomnienie_min)
        self.wyloguj_po = QComboBox()
        for tekst, dane in (("Wyloguj asystentki", "asystentki"), ("Wyloguj wszystkich (raz po końcu godzin)", "wszyscy"),
                            ("Nie wylogowuj", "nikt")):
            self.wyloguj_po.addItem(tekst, dane)
        f.addRow("Po godzinach", self.wyloguj_po)
        self.op_zamkniecie_asystentki = QCheckBox("Asystentki mogą robić zamknięcie dnia bez hasła właściciela")
        self.op_druk_wystawil = QCheckBox("Drukuj na dokumencie „Wystawił(a): …”")
        ku.addWidget(self.op_zamkniecie_asystentki)
        ku.addWidget(self.op_druk_wystawil)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- wygaszacz ekranu
        prawa.addWidget(sekcja("Wygaszacz ekranu"))
        k, ku = karta()
        rzad_zaslony = QHBoxLayout()
        self.zaslona_wl = QCheckBox("Włącz wygaszacz z ząbkiem po")
        rzad_zaslony.addWidget(self.zaslona_wl)
        self.zaslona_sekund = QSpinBox(minimum=5, maximum=3600, singleStep=15, suffix=" s bezczynności")
        self.zaslona_sekund.setFixedWidth(190)
        self.zaslona_wl.toggled.connect(self.zaslona_sekund.setEnabled)
        rzad_zaslony.addWidget(self.zaslona_sekund)
        for sek in (30, 60, 120, 300):
            rzad_zaslony.addWidget(przycisk(f"{sek} s" if sek < 60 else f"{sek // 60} min", styl="plaski",
                                            akcja=lambda _=False, v=sek: self.zaslona_sekund.setValue(v)))
        rzad_zaslony.addWidget(przycisk("Pokaż", "pulpit", akcja=lambda: self.okno.pokaz_zaslone()))
        rzad_zaslony.addStretch()
        ku.addLayout(rzad_zaslony)
        rzad_gaszenia = QHBoxLayout()
        rzad_gaszenia.addWidget(QLabel("Gaś ekran i monitor po", objectName="etykieta"))
        self.zaslona_gaszenie = QSpinBox(minimum=0, maximum=240, suffix=" min zasłony")
        self.zaslona_gaszenie.setSpecialValueText("nigdy")
        self.zaslona_gaszenie.setFixedWidth(190)
        self.zaslona_wl.toggled.connect(self.zaslona_gaszenie.setEnabled)
        rzad_gaszenia.addWidget(self.zaslona_gaszenie)
        rzad_gaszenia.addStretch()
        ku.addLayout(rzad_gaszenia)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- powiadomienia
        prawa.addWidget(sekcja("Powiadomienia"))
        k, ku = karta()
        self.op_start = QCheckBox("Powiadomienie „Komputer zweryfikowany” przy każdym uruchomieniu")
        self.op_dzwiek = QCheckBox("Dźwięk przy powiadomieniach")
        self.op_blokada_pc = QCheckBox("Blokuj Fakturnik razem z komputerem (Win + L)")
        for w in (self.op_start, self.op_dzwiek, self.op_blokada_pc):
            ku.addWidget(w)
        rzad = QHBoxLayout()
        rzad.addWidget(QLabel("Pokazuj powiadomienia przez", objectName="etykieta"))
        self.op_sekundy = QSpinBox(minimum=3, maximum=60, suffix=" s")
        self.op_sekundy.setFixedWidth(100)
        rzad.addWidget(self.op_sekundy)
        rzad.addStretch()
        ku.addLayout(rzad)
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- tapeta pulpitu
        prawa.addWidget(sekcja("Tapeta pulpitu"))
        k, ku = karta()
        rzad = QHBoxLayout()
        from . import tapeta
        for klucz, opis in tapeta.WARIANTY.items():
            b = QPushButton(cursor=Qt.CursorShape.PointingHandCursor, objectName="tapeta")
            b.setToolTip(opis["nazwa"])
            b.setIconSize(QSize(150, 84))
            b.setFixedSize(166, 100)
            b.clicked.connect(lambda _=False, k=klucz: self.ustaw_tapete(k))
            self._miniatury_tapet.append((b, klucz))
            kolumna = QVBoxLayout()
            kolumna.addWidget(b)
            kolumna.addWidget(QLabel(opis["nazwa"], objectName="drobny", alignment=Qt.AlignmentFlag.AlignHCenter))
            rzad.addLayout(kolumna)
        rzad.addStretch()
        ku.addLayout(rzad)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Przywróć poprzednią tapetę", "przywroc", akcja=self.przywroc_tapete))
        rzad.addStretch()
        ku.addLayout(rzad)
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
        self.auto_aktualizacje = QCheckBox("Sprawdzaj aktualizacje automatycznie (w instalacji administratora instaluje je usługa)")
        ku.addWidget(self.auto_aktualizacje)
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

    def _pokaz_stan_komputera(self):
        baza = self.okno.baza

        def znak(stan, dobrze: str, zle: str, nie_wiadomo: str = "nie da się sprawdzić") -> str:
            if stan is None:
                return f"<span style='color:{TEKST_2}'>– {nie_wiadomo}</span>"
            return (f"<span style='color:{ZIELONY}'>✓ {dobrze}</span>" if stan
                    else f"<span style='color:{CZERWONY}'>✗ {zle}</span>")

        admin = aktualizacje.zainstalowany() if aktualizacje.czy_spakowany() else None
        konto = urzadzenie.konto_administratora()
        wiersze = [
            f"Komputer: <b>{html_escape(urzadzenie.nazwa_urzadzenia())}</b>",
            "Secure Boot: " + znak(urzadzenie.secure_boot(), "włączony", "wyłączony (włącz w ustawieniach UEFI/BIOS)"),
            "Instalacja: " + znak(admin, "z uprawnieniami administratora (Program Files, usługa kopii)",
                                  "bez uprawnień administratora (użyj przycisku poniżej)", "wersja ze źródeł"),
            "Konto Windows do codziennej pracy: " + znak(None if konto is None else not konto, "zwykłe (zalecane)",
                                                          "administrator (bezpieczniej pracować na zwykłym koncie)"),
            "Weryfikacja urządzenia: " + znak(baza.weryfikacja_urzadzenia,
                                               "włączona (dane otworzą się tylko na tym komputerze)",
                                               "wyłączona"),
        ]
        self.stan_komputera.setText("<br>".join(wiersze))
        self.btn_weryfikacja.setText("Wyłącz weryfikację urządzenia…" if baza.weryfikacja_urzadzenia
                                     else "Włącz weryfikację urządzenia…")
        self.btn_weryfikacja.setEnabled(urzadzenie.dostepne() and baza.ma_haslo)
        self.btn_weryfikacja.setToolTip("" if baza.ma_haslo else "Najpierw ustaw hasło")
        self.btn_kod.setVisible(baza.weryfikacja_urzadzenia)
        self.btn_instaluj_admin.setVisible(admin is False)

    def przelacz_weryfikacje(self):
        baza = self.okno.baza
        katalog = baza.sciezka.parent
        if baza.weryfikacja_urzadzenia:
            if QMessageBox.question(self, "Weryfikacja urządzenia", "Wyłączyć weryfikację urządzenia? Dane znów "
                                    "będzie można otworzyć na innym komputerze samym hasłem.") \
                    != QMessageBox.StandardButton.Yes or not self._potwierdz_obecne():
                return
            baza.powiaz_z_urzadzeniem(None)
            urzadzenie.usun_sekret(katalog)
            self.okno.dziennik.zapisz("weryfikacja urządzenia: wyłączona")
            self.okno.komunikat("Weryfikacja urządzenia wyłączona")
        else:
            if QMessageBox.question(
                    self, "Weryfikacja urządzenia",
                    "Po włączeniu dane (i ich kopie) otworzą się tylko na tym komputerze i tym koncie Windows, "
                    "nawet ktoś znający hasło nie odczyta ich gdzie indziej.\n\nNa nowym komputerze potrzebny "
                    "będzie KOD ODZYSKIWANIA, który za chwilę zobaczysz. Zapisz go lub wydrukuj i przechowuj "
                    "w bezpiecznym miejscu (nie na tym komputerze). Bez kodu i bez pakietu migracji danych nie "
                    "da się przenieść na inny komputer.\n\nWłączyć?") != QMessageBox.StandardButton.Yes:
                return
            if not self._potwierdz_obecne():
                return
            sekret = urzadzenie.nowy_sekret()
            if not OknoKoduOdzyskiwania(urzadzenie.kod_odzyskiwania(sekret), self, potwierdzenie=True).exec():
                return
            try:
                urzadzenie.zapisz_sekret(katalog, sekret)
            except (OSError, urzadzenie.BrakDPAPI) as e:
                QMessageBox.critical(self, "Weryfikacja urządzenia", f"Nie udało się zapisać klucza urządzenia: {e}")
                return
            baza.powiaz_z_urzadzeniem(sekret)
            self.okno.dziennik.zapisz("weryfikacja urządzenia: włączona")
            self.okno.komunikat("Weryfikacja urządzenia włączona")
        self._pokaz_stan_komputera()

    def pokaz_kod(self):
        szyfr = self.okno.baza.szyfr
        if not (szyfr and szyfr.sekret) or not self._potwierdz_obecne():
            return
        self.okno.dziennik.zapisz("wyświetlenie kodu odzyskiwania")
        OknoKoduOdzyskiwania(urzadzenie.kod_odzyskiwania(szyfr.sekret), self).exec()

    def migracja(self):
        odp = QMessageBox.question(
            self, "Przenieś na inny komputer",
            "Program utworzy PAKIET MIGRACJI: jeden plik .fkopia z wszystkimi danymi, ustawieniami i wrzuconymi "
            "plikami, zaszyfrowany osobnym hasłem pakietu (działa na każdym komputerze, także przy włączonej "
            "weryfikacji urządzenia).\n\nNa nowym komputerze: zainstaluj Fakturnik i na pierwszym ekranie "
            "wybierz „Przenieś dane z innego komputera”.\n\nUtworzyć pakiet?")
        if odp == QMessageBox.StandardButton.Yes:
            self.kopia_zapasowa(nazwa_pliku=f"Fakturnik-migracja-{date.today().isoformat()}.fkopia")

    def instaluj_jako_admin(self):
        self.okno.uruchom_instalator_admin(
            "Program pobierze instalator z GitHuba (sprawdzi sumę SHA-256) i go uruchomi. Windows zapyta o zgodę "
            "administratora. Instalator przeniesie Fakturnik do Program Files, włączy usługę kopii i ochronę "
            "przed odinstalowaniem. Dane zostają bez zmian.\n\nKontynuować?")

    def _pokaz_miniatury_tapet(self):
        if getattr(self, "_miniatury_gotowe", False):
            return
        from . import tapeta
        nazwa = self.okno.baza.ustawienia()["nazwa"].split(",")[0].strip()
        for b, klucz in self._miniatury_tapet:
            b.setIcon(QIcon(QPixmap.fromImage(tapeta.wygeneruj(klucz, 480, 270, nazwa).scaled(
                300, 168, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))))
        self._miniatury_gotowe = True

    def ustaw_tapete(self, wariant: str):
        from . import tapeta
        if not windows.na_windows():
            QMessageBox.information(self, "Tapeta", "Tapetę ustawia się w wersji na Windows.")
            return
        ekran = QApplication.primaryScreen()
        rozmiar = ekran.size() * ekran.devicePixelRatio()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            u = self.okno.baza.ustawienia()
            plik = tapeta.zapisz(wariant, self.okno.baza.sciezka.parent, max(1280, rozmiar.width()),
                                 max(720, rozmiar.height()), u["nazwa"].split(",")[0].strip())
            obecna = windows.obecna_tapeta()
            if obecna and "tapeta-" not in Path(obecna).name and not u["poprzednia_tapeta"]:
                self.okno.baza.zapisz_ustawienia({"poprzednia_tapeta": obecna})
            ok = windows.ustaw_tapete(str(plik))
        finally:
            QApplication.restoreOverrideCursor()
        self.okno.komunikat(f"Ustawiono tapetę: {tapeta.WARIANTY[wariant]['nazwa']}" if ok
                            else "Nie udało się ustawić tapety", blad=not ok)

    def przywroc_tapete(self):
        poprzednia = self.okno.baza.ustawienia()["poprzednia_tapeta"]
        if not poprzednia or not Path(poprzednia).exists():
            QMessageBox.information(self, "Tapeta", "Nie ma zapamiętanej poprzedniej tapety. Zmienisz ją w "
                                    "Ustawieniach Windows → Personalizacja → Tło.")
            return
        if windows.ustaw_tapete(poprzednia):
            self.okno.baza.zapisz_ustawienia({"poprzednia_tapeta": ""})
            self.okno.komunikat("Przywrócono poprzednią tapetę")

    def _pokaz_konta(self):
        konta_lista = self.okno.baza.konta()
        self.tabela_kont.setRowCount(len(konta_lista))
        for r, k in enumerate(konta_lista):
            self.tabela_kont.setItem(r, 0, QTableWidgetItem(k["nazwa"]))
            self.tabela_kont.setItem(r, 1, QTableWidgetItem(konta.ROLE.get(k["rola"], k["rola"])))

    def _wybrane_konto(self) -> dict | None:
        r = self.tabela_kont.currentRow()
        lista = self.okno.baza.konta()
        return lista[r] if 0 <= r < len(lista) else None

    def dodaj_konto(self):
        if not self.okno.baza.ma_haslo:
            QMessageBox.information(self, "Konta", "Najpierw ustaw hasło właściciela (szyfrowanie danych).")
            return
        nazwa, ok = QInputDialog.getText(self, "Nowe konto", "Imię asystentki (widoczne w dzienniku i na dokumentach):")
        if not ok or not nazwa.strip():
            return
        okno = OknoNowegoHasla(self, f"Hasło dla: {nazwa.strip()}", "Asystentka będzie logować się tylko tym hasłem.")
        if okno.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.okno.baza.dodaj_konto(nazwa, okno.haslo.text())
        except (ValueError, PermissionError) as e:
            QMessageBox.warning(self, "Konta", str(e))
            return
        self.okno.dziennik.zapisz(f"dodano konto asystentki „{nazwa.strip()}”")
        self._pokaz_konta()
        self.okno.odswiez_uprawnienia()

    def zmien_haslo_konta(self):
        k = self._wybrane_konto()
        if not k:
            QMessageBox.information(self, "Konta", "Zaznacz konto na liście.")
            return
        okno = OknoNowegoHasla(self, f"Nowe hasło: {k['nazwa']}", "Poprzednie hasło tego konta przestanie działać.")
        if okno.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.okno.baza.ustaw_haslo_konta(k["id"], okno.haslo.text())
        except (ValueError, KeyError) as e:
            QMessageBox.warning(self, "Konta", str(e) or "Nie udało się zmienić hasła.")
            return
        self.okno.dziennik.zapisz(f"zmiana hasła konta „{k['nazwa']}”")
        self.okno.komunikat(f"Zmieniono hasło konta {k['nazwa']}")

    def usun_konto(self):
        k = self._wybrane_konto()
        if not k or QMessageBox.question(self, "Usuń konto", f"Usunąć konto „{k['nazwa']}”? Ta osoba nie zaloguje "
                                         "się już do programu. Jej dokumenty i wpisy w dzienniku zostają.") \
                != QMessageBox.StandardButton.Yes:
            return
        self.okno.baza.usun_konto(k["id"])
        self.okno.dziennik.zapisz(f"usunięto konto „{k['nazwa']}”")
        self._pokaz_konta()
        self.okno.odswiez_uprawnienia()
        if QMessageBox.question(self, "Hasło właściciela", "Zalecana jest teraz zmiana hasła właściciela: unieważni "
                                "to klucze z ewentualnych starych kopii pliku kont. Zmienić teraz?") \
                == QMessageBox.StandardButton.Yes:
            self.zmien_haslo()

    def _wybierz_folder_kopii(self):
        folder = QFileDialog.getExistingDirectory(self, "Folder na trzecią kopię", self.kopia_folder.text()
                                                  or str(Path.home()))
        if folder:
            self.kopia_folder.setText(folder)

    def _pokaz_stan_kopii(self):
        from . import usluga
        u = self.okno.baza.ustawienia()
        teraz = self.okno.ostatnia_kopia.strftime("%d.%m %H:%M") if self.okno.ostatnia_kopia else "przy zamknięciu"
        chroniona = usluga.ostatnia_kopia_chroniona()
        folder = u["kopia_folder"]
        wiersze = [
            f"<b>1.</b> Dokumenty, co 10 minut (ostatnio: {teraz})<br>&nbsp;&nbsp;&nbsp;"
            f"{html_escape(str(katalog_kopii()))}",
            "<b>2.</b> Chronione kopie usługi systemowej, co godzinę, nie do usunięcia bez uprawnień "
            "administratora: " + (f"ostatnio {html_escape(chroniona)}" if chroniona else
                                   "<span style='color:#a4303d'>nieaktywne. Zainstaluj program instalatorem "
                                   "FakturnikSetup.exe</span>"),
            "<b>3.</b> " + (f"{html_escape(folder)}, co 10 minut" + ("" if Path(folder).exists() else
                            " <span style='color:#a4303d'>(niedostępny: podłącz dysk)</span>")
                            if folder else "Wybierz pendrive, dysk sieciowy albo folder OneDrive poniżej."),
        ]
        self.stan_kopii.setText("<br>".join(wiersze))

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
        self.druk_qr.setChecked(u["druk_qr"] == "1")
        self.ochrona_ekranu.setChecked(u["ochrona_ekranu"] == "1")
        self.kopia_folder.setText(u["kopia_folder"])
        self.nazwa_wlascicielki.setText(u["nazwa_wlascicielki"])
        g = godziny.wczytaj(u["godziny_pracy"])
        for d, (pole_dnia, od, do) in enumerate(self.dni_pracy):
            przedzial = g.get(d)
            pole_dnia.setChecked(bool(przedzial))
            od.setTime(QTime(*(przedzial[0].hour, przedzial[0].minute) if przedzial else (9, 0)))
            do.setTime(QTime(*(przedzial[1].hour, przedzial[1].minute) if przedzial else (17, 0)))
            od.setEnabled(bool(przedzial))
            do.setEnabled(bool(przedzial))
        self.przypomnienie_min.setValue(int(liczba(u["przypomnienie_min"])))
        self.wyloguj_po.setCurrentIndex(max(self.wyloguj_po.findData(u["wyloguj_po_godzinach"]), 0))
        self.op_zamkniecie_asystentki.setChecked(u["asystentki_zamkniecie_dnia"] == "1")
        self.op_druk_wystawil.setChecked(u["druk_wystawil"] == "1")
        self._pokaz_konta()
        self.op_start.setChecked(u["powiadomienie_startowe"] == "1")
        self.op_dzwiek.setChecked(u["powiadomienia_dzwiek"] == "1")
        self.op_blokada_pc.setChecked(u["blokuj_z_komputerem"] == "1")
        self.op_sekundy.setValue(int(liczba(u["powiadomienia_sekund"]) or 6))
        self._pokaz_stan_kopii()
        self._pokaz_stan_komputera()
        self._pokaz_miniatury_tapet()
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
        self.zaslona_wl.setChecked(u["zaslona"] == "1")
        self.skaner_pobrane.setChecked(u["skaner_pobrane"] == "1")
        self.zaslona_sekund.setValue(int(liczba(u["zaslona_sekund"]) or 30))
        self.zaslona_sekund.setEnabled(u["zaslona"] == "1")
        self.zaslona_gaszenie.setValue(int(liczba(u["zaslona_gaszenie_min"]) or 0))
        self.zaslona_gaszenie.setEnabled(u["zaslona"] == "1")
        self.w_tle.setChecked(u["w_tle"] == "1")
        self.autostart.setChecked(autostart_wlaczony())
        self.menu_kontekstowe.setChecked(menu_kontekstowe_wlaczone())
        self.ustaw_logo(u["logo"])
        ma = self.okno.baza.ma_haslo
        self.ikona_stanu.setPixmap(pixmapa("tarcza" if ma else "uwaga", ZIELONY if ma else CZERWONY, 18))
        self.stan_hasla.setText(
            f"Dane są zaszyfrowane podwójnie (AES-256 i ChaCha20). Program blokuje się po {u['blokada_minut']} min bezczynności."
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
        formaty = [wartosci[k] for k in ("format_numeru", "format_numeru_faktury", "format_numeru_korekty")]
        if any("{n}" not in f for f in formaty):
            QMessageBox.warning(self, "Format numeru", "Format numeru musi zawierać {n} (kolejny numer).")
            return
        if len(set(formaty)) < 3:
            QMessageBox.warning(self, "Format numeru", "Rachunki, faktury i korekty muszą mieć różne formaty numeru, "
                                "np. faktury z przedrostkiem FV/, korekty KOR/.")
            return
        if not wartosci["termin_dni"].isdigit() or int(wartosci["termin_dni"]) > 365:
            QMessageBox.warning(self, "Termin przelewu", "Termin przelewu to liczba dni od 0 do 365.")
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
        wartosci["druk_qr"] = "1" if self.druk_qr.isChecked() else "0"
        wartosci["ochrona_ekranu"] = "1" if self.ochrona_ekranu.isChecked() else "0"
        wartosci["kopia_folder"] = self.kopia_folder.text().strip()
        nowe_godziny = {}
        for d, (pole_dnia, od, do) in enumerate(self.dni_pracy):
            if pole_dnia.isChecked():
                if od.time() >= do.time():
                    QMessageBox.warning(self, "Godziny pracy", f"{godziny.DNI[d].capitalize()}: godzina końca "
                                        "musi być późniejsza niż początku.")
                    return
                nowe_godziny[d] = (od.time().toPython(), do.time().toPython())
        wartosci.update({
            "nazwa_wlascicielki": self.nazwa_wlascicielki.text().strip() or "Właściciel",
            "godziny_pracy": godziny.zapisz(nowe_godziny),
            "przypomnienie_min": str(self.przypomnienie_min.value()),
            "wyloguj_po_godzinach": self.wyloguj_po.currentData(),
            "asystentki_zamkniecie_dnia": "1" if self.op_zamkniecie_asystentki.isChecked() else "0",
            "druk_wystawil": "1" if self.op_druk_wystawil.isChecked() else "0",
        })
        wartosci.update({
            "powiadomienie_startowe": "1" if self.op_start.isChecked() else "0",
            "powiadomienia_dzwiek": "1" if self.op_dzwiek.isChecked() else "0",
            "blokuj_z_komputerem": "1" if self.op_blokada_pc.isChecked() else "0",
            "powiadomienia_sekund": str(self.op_sekundy.value()),
        })
        wartosci["rodo_lat"] = str(self.rodo_lat.value())
        wartosci["auto_aktualizacje"] = "1" if self.auto_aktualizacje.isChecked() else "0"
        wartosci["w_tle"] = "1" if self.w_tle.isChecked() else "0"
        wartosci["tryb"] = self.tryb.currentData()
        wartosci["blokada_minut"] = str(self.blokada_minut.value())
        wartosci["zaslona"] = "1" if self.zaslona_wl.isChecked() else "0"
        wartosci["skaner_pobrane"] = "1" if self.skaner_pobrane.isChecked() else "0"
        wartosci["zaslona_sekund"] = str(self.zaslona_sekund.value())
        wartosci["zaslona_gaszenie_min"] = str(self.zaslona_gaszenie.value())
        if integracja_dostepna():
            ustaw_autostart(self.autostart.isChecked())
            ustaw_menu_kontekstowe(self.menu_kontekstowe.isChecked())
        self.okno.baza.zapisz_ustawienia(wartosci)
        self.okno.komunikat("Zapisano ustawienia")
        self.okno.strona_nowy.ustaw_tryb(wartosci["tryb"])
        self.okno.ustaw_czas_blokady()
        OCHRONA_EKRANU.ustaw(wartosci["ochrona_ekranu"] == "1")
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
                wiersze.append(f"{nazwa};{cena:.2f}")
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
            znacznik_szyfrowania(True)
            self.okno.komunikat("Hasło ustawione, dane zaszyfrowane")
            self.odswiez()

    def usun_haslo(self):
        if not self._potwierdz_obecne():
            return
        if QMessageBox.question(self, "Odszyfruj dane", "Hasło zostanie usunięte, a dane przestaną być "
                                "zaszyfrowane. Kontynuować?") == QMessageBox.StandardButton.Yes:
            self.okno.baza.ustaw_haslo(None)
            znacznik_szyfrowania(False)
            urzadzenie.usun_sekret(self.okno.baza.sciezka.parent)  # bez hasła nie ma też weryfikacji urządzenia
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
        try:
            wymaga = self._kopia_wymaga_hasla(sciezka) or Baza.czy_kopia_szyfrowana(sciezka)
        except (OSError, KeyError, zipfile.BadZipFile):
            QMessageBox.critical(self, "Nie udało się przywrócić", "To nie jest kopia Fakturnika.")
            return
        if wymaga:
            haslo, ok = QInputDialog.getText(self, "Hasło kopii", "Hasło, którym zaszyfrowano kopię:",
                                             QLineEdit.EchoMode.Password)
            if not ok:
                return
        try:
            # na wszelki wypadek: kopia obecnego stanu, zanim zostanie zastąpiony
            kopia_automatyczna(self.okno.baza.sciezka,
                               nazwa=f"przed-przywroceniem-{datetime.now():%Y-%m-%d-%H%M%S}.db")
            self.okno.baza.przywroc(sciezka, haslo)
        except (BledneHaslo, ValueError, NowszaBaza, PermissionError, KeyError, OSError, PlikZajety,
                zipfile.BadZipFile) as e:
            self.okno.dziennik.zapisz("przywrócenie kopii: NIEUDANE")
            QMessageBox.critical(self, "Nie udało się przywrócić", str(e))
            return
        self.okno.dziennik.zapisz("przywrócenie danych z kopii")
        self.okno.komunikat("Przywrócono dane z kopii")
        self.okno.przejdz(STRONA_HISTORIA)

    @staticmethod
    def _kopia_wymaga_hasla(sciezka: str) -> bool:
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

    def kopia_zapasowa(self, *_, nazwa_pliku: str | None = None):
        haslo = OknoNowegoHasla(self, "Hasło kopii zapasowej",
                                "Kopia (dane i wrzucone pliki) zostanie zaszyfrowana podwójnie (AES-256 i ChaCha20) tym hasłem. "
                                "Może być inne niż hasło programu, np. do kopii na pendrive lub w chmurze.")
        if haslo.exec() != QDialog.DialogCode.Accepted:
            return
        nazwa = nazwa_pliku or f"fakturnik-kopia-{date.today().isoformat()}.fkopia"
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


class OknoKontroli(QDialog):
    """Kontrola komputera: co chroni dane, co wymaga uwagi; ostrzeżenia można zignorować i przywrócić."""

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno)
        self.okno = okno
        self.setWindowTitle("Kontrola komputera")
        self.setMinimumWidth(620)
        self.u = QVBoxLayout(self)
        self.u.setContentsMargins(24, 22, 24, 18)
        self.u.setSpacing(10)
        self.odswiez()

    def odswiez(self):
        wyczysc_uklad(self.u)
        wyniki = self.okno.wyniki_kontroli()
        ignor = kontrola.zignorowane(self.okno.baza)
        pokaz = kontrola.do_pokazania(self.okno.baza, wyniki)
        t = QLabel("Kontrola komputera")
        t.setStyleSheet("font-size: 17px; font-weight: 650;")
        self.u.addWidget(t)
        self.u.addWidget(QLabel(f"{urzadzenie.nazwa_urzadzenia()}, {datetime.now():%d.%m.%Y %H:%M}. "
                                + ("Wszystko, co chroni dane, działa." if not pokaz
                                   else f"Wymaga uwagi: {len(pokaz)}."), objectName="podtytul"))
        k, ku = karta()
        for w in wyniki:
            rzad = QHBoxLayout()
            rzad.setSpacing(10)
            znak = QLabel()
            kolor = ZIELONY if w.stan else (TEKST_3 if w.stan is None or w.klucz in ignor else
                                            (CZERWONY if w.waga == "problem" else "#b7791f"))
            znak.setPixmap(pixmapa("ok" if w.stan else ("uwaga" if w.stan is False else "kreska"), kolor, 16))
            rzad.addWidget(znak, alignment=Qt.AlignmentFlag.AlignTop)
            tekst = f"<b>{html_escape(w.nazwa)}</b>: {html_escape(w.opis)}"
            if w.ostrzezenie:
                tekst += f"<br><span style='color:{TEKST_2}'>{html_escape(w.rada)}</span>"
                if w.klucz in ignor:
                    tekst += f" <span style='color:{TEKST_3}'>(zignorowane)</span>"
            opis = QLabel(tekst, wordWrap=True, textFormat=Qt.TextFormat.RichText)
            rzad.addWidget(opis, 1)
            if w.ostrzezenie:
                if w.klucz == "dziennik":
                    rzad.addWidget(przycisk("Nowy dziennik…", styl="plaski", akcja=self._nowy_dziennik),
                                   alignment=Qt.AlignmentFlag.AlignTop)
                if w.klucz in ignor:
                    rzad.addWidget(przycisk("Przywróć", styl="plaski",
                                            akcja=lambda _=False, k=w.klucz: self._ignoruj(k, False)),
                                   alignment=Qt.AlignmentFlag.AlignTop)
                else:
                    rzad.addWidget(przycisk("Ignoruj", styl="plaski",
                                            akcja=lambda _=False, k=w.klucz: self._ignoruj(k, True)),
                                   alignment=Qt.AlignmentFlag.AlignTop)
            ku.addLayout(rzad)
        self.u.addWidget(k)
        r = QHBoxLayout()
        if ignor:
            r.addWidget(przycisk("Przywróć wszystkie ostrzeżenia", "odswiez", "plaski", self._przywroc_wszystkie))
        r.addStretch()
        r.addWidget(przycisk("Sprawdź ponownie", "odswiez", akcja=self.odswiez))
        r.addWidget(przycisk("Zamknij", styl="glowny", akcja=self.accept))
        self.u.addLayout(r)
        self.adjustSize()

    def _ignoruj(self, klucz: str, ignoruj: bool):
        ignor = kontrola.zignorowane(self.okno.baza)
        kontrola.zapisz_zignorowane(self.okno.baza, ignor | {klucz} if ignoruj else ignor - {klucz})
        self.okno.dziennik.zapisz(f"kontrola komputera: {'zignorowano' if ignoruj else 'przywrócono'} "
                                  f"ostrzeżenie „{klucz}”")
        self.odswiez()

    def _przywroc_wszystkie(self):
        kontrola.zapisz_zignorowane(self.okno.baza, set())
        self.okno.dziennik.zapisz("kontrola komputera: przywrócono wszystkie ostrzeżenia")
        self.odswiez()

    def _nowy_dziennik(self):
        if QMessageBox.question(self, "Nowy dziennik", "Obecny dziennik zostanie zamknięty i zachowany obok (tylko "
                                "do odczytu), a nowy zacznie się od wpisu wskazującego stary. Zrób to dopiero po "
                                "sprawdzeniu, kto i dlaczego zmienił dziennik.\n\nKontynuować?") \
                != QMessageBox.StandardButton.Yes:
            return
        if not self.okno.potwierdz_haslem("nowy dziennik", "Rozpoczęcie nowego dziennika wymaga hasła."):
            return
        self.okno.nowy_dziennik()
        self.odswiez()


class OknoZamykaniaGabinetu(QDialog):
    """„Zamykam gabinet”: podsumowanie dnia i porządki na koniec (kartka, kopia, wylogowanie)."""

    def __init__(self, okno: "OknoGlowne", dokumenty: list):
        super().__init__(okno)
        self.setWindowTitle("Zamykam gabinet")
        self.setFixedWidth(460)
        u = QVBoxLayout(self)
        u.setContentsMargins(26, 24, 26, 20)
        u.setSpacing(10)
        t = QLabel("Zamykam gabinet")
        t.setStyleSheet("font-size: 18px; font-weight: 650;")
        u.addWidget(t)
        dzis = date.today()
        u.addWidget(QLabel(f"{DNI[dzis.weekday()].capitalize()}, {dzis.day} {MIESIACE_DOP[dzis.month - 1]} {dzis.year}",
                           objectName="podtytul"))
        pods = podsumuj(dokumenty)
        k, ku = karta(False)
        siatka = QGridLayout()
        siatka.setHorizontalSpacing(18)
        wiersze = [("Dokumenty", str(pods.liczba))]
        wiersze += [(sposob.capitalize(), f"{druk.zl(pods.wg_platnosci.get(sposob, 0))} zł")
                    for sposob in ("gotówka", "karta", "przelew")]
        wiersze.append(("Razem", f"{druk.zl(pods.suma)} zł"))
        if pods.anulowanych:
            wiersze.append(("Anulowane", str(pods.anulowanych)))
        for r, (etykieta, wartosc) in enumerate(wiersze):
            e = QLabel(etykieta)
            w = QLabel(wartosc, alignment=Qt.AlignmentFlag.AlignRight)
            if etykieta == "Razem":
                for x in (e, w):
                    x.setStyleSheet("font-weight: 650;")
            siatka.addWidget(e, r, 0)
            siatka.addWidget(w, r, 1)
        ku.addLayout(siatka)
        u.addWidget(k)
        self.kartka = QCheckBox("Wydrukuj kartkę podsumowującą")
        self.kopia = QCheckBox("Zrób kopię zapasową teraz")
        self.wyloguj = QCheckBox("Wyloguj i zablokuj program")
        for w, domyslnie in ((self.kartka, False), (self.kopia, True), (self.wyloguj, True)):
            w.setChecked(domyslnie)
            u.addWidget(w)
        self.wyloguj.setVisible(okno.baza.ma_haslo)
        r = QHBoxLayout()
        r.addStretch()
        r.addWidget(przycisk("Anuluj", akcja=self.reject))
        b = przycisk("Zamknij gabinet", "klodka", "glowny", self.accept)
        b.setDefault(True)
        r.addWidget(b)
        u.addLayout(r)


class OknoKoduOdzyskiwania(QDialog):
    """Kod odzyskiwania weryfikacji urządzenia: do zapisania lub wydrukowania (nie zostaje na tym komputerze)."""

    def __init__(self, kod: str, parent=None, potwierdzenie: bool = False):
        super().__init__(parent)
        self.kod = kod
        self.setWindowTitle("Kod odzyskiwania")
        self.setFixedWidth(520)
        u = QVBoxLayout(self)
        u.setContentsMargins(26, 24, 26, 20)
        u.setSpacing(12)
        t = QLabel("Kod odzyskiwania")
        t.setStyleSheet("font-size: 17px; font-weight: 650;")
        u.addWidget(t)
        u.addWidget(QLabel("Będzie potrzebny, żeby otworzyć dane na innym komputerze (np. po awarii tego). "
                           "Zapisz go na kartce lub wydrukuj i schowaj razem z ważnymi dokumentami.",
                           objectName="podtytul", wordWrap=True))
        grupy = kod.split("-")
        pole_kodu = QLabel("-".join(grupy[:4]) + "-\n" + "-".join(grupy[4:]), alignment=Qt.AlignmentFlag.AlignCenter)
        pole_kodu.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pole_kodu.setStyleSheet(f"font-family: Consolas, 'Courier New', monospace; font-size: 19px; "
                                f"font-weight: 600; letter-spacing: 2px; background: {TLO}; border-radius: 10px; "
                                f"padding: 16px;")
        u.addWidget(pole_kodu)
        rzad = QHBoxLayout()
        rzad.addWidget(przycisk("Drukuj", "drukarka", akcja=self._drukuj))
        rzad.addStretch()
        u.addLayout(rzad)
        self.potwierdz = None
        if potwierdzenie:
            ostatnia = kod.split("-")[-1]
            self.potwierdz = QLineEdit(placeholderText="Ostatnie 4 znaki kodu")
            self.potwierdz.setMaxLength(4)
            self.potwierdz.textChanged.connect(lambda t: self.ok.setEnabled(t.strip().upper() == ostatnia))
            u.addLayout(pole("Przepisz ostatnie 4 znaki, żeby potwierdzić, że kod jest zapisany", self.potwierdz))
        r = QHBoxLayout()
        r.addStretch()
        if potwierdzenie:
            r.addWidget(przycisk("Anuluj", akcja=self.reject))
        self.ok = przycisk("Zapisałem kod" if potwierdzenie else "Zamknij", styl="glowny", akcja=self.accept)
        self.ok.setEnabled(not potwierdzenie)
        r.addWidget(self.ok)
        u.addLayout(r)

    def _drukuj(self):
        drukarka = druk.przygotuj_drukarke({})
        if QPrintDialog(drukarka, self).exec() == QDialog.DialogCode.Accepted:
            druk.drukuj(f"<html><body style='font-family: Arial; font-size: 12pt;'><h2>Fakturnik: kod odzyskiwania</h2>"
                        f"<p>Komputer: {html_escape(urzadzenie.nazwa_urzadzenia())}, {date.today():%d.%m.%Y}</p>"
                        f"<p style='font-family: Courier New; font-size: 18pt;'><b>{html_escape(self.kod)}</b></p>"
                        "<p>Potrzebny do otwarcia danych Fakturnika na innym komputerze (razem z hasłem). "
                        "Przechowuj w bezpiecznym miejscu.</p></body></html>", drukarka)


class OknoDruku(QDialog):
    """Ustawienia wydruku w programie: drukarka, liczba egzemplarzy i to, co ma się znaleźć na wydruku.

    Zmiany dotyczą tylko tego wydruku; domyślne ustawia się w Ustawieniach (chronionych hasłem).
    """

    def __init__(self, u: dict[str, str], tytul: str, dokument: bool = True, z_kopia: bool = False, parent=None):
        super().__init__(parent)
        self.u = dict(u)
        self.setWindowTitle("Drukowanie")
        self.setFixedWidth(440)
        uk = QVBoxLayout(self)
        uk.setContentsMargins(24, 22, 24, 20)
        uk.setSpacing(12)
        naglowek = QHBoxLayout()
        znak = QLabel()
        znak.setPixmap(pixmapa("drukarka", AKCENT, 22))
        naglowek.addWidget(znak)
        t = QLabel(tytul)
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        naglowek.addWidget(t, 1)
        uk.addLayout(naglowek)

        self.drukarka_pole = QComboBox()
        self.drukarka_pole.addItem("Domyślna drukarka systemu", "")
        for nazwa in druk.dostepne_drukarki():
            self.drukarka_pole.addItem(nazwa, nazwa)
        self.drukarka_pole.setCurrentIndex(max(self.drukarka_pole.findData(u.get("drukarka", "")), 0))
        uk.addLayout(pole("Drukarka", self.drukarka_pole))
        self.egzemplarze = QSpinBox(minimum=1, maximum=20, suffix=" egz.")
        self.egzemplarze.setFixedWidth(120)
        uk.addLayout(pole("Liczba egzemplarzy", self.egzemplarze))

        self.kopia = QCheckBox("Oryginał i kopia")
        self.kopia.setChecked(z_kopia)
        self.data_wydruku = QCheckBox("Data i godzina wydruku na dokumencie")
        self.data_wydruku.setChecked(u.get("druk_data_wydruku") == "1")
        self.pesel = QCheckBox("PESEL pacjenta")
        self.pesel.setChecked(u.get("druk_pesel") == "1")
        self.data_wygenerowania = QCheckBox("Data i godzina wygenerowania")
        self.data_wygenerowania.setChecked(u.get("druk_data_wygenerowania", "1") == "1")
        opcje = (self.kopia, self.data_wydruku, self.pesel) if dokument else (self.data_wygenerowania,)
        if dokument is None:  # wrzucony plik: drukowany tak, jak jest
            opcje = ()
        if opcje:
            uk.addWidget(QLabel("Na wydruku", objectName="etykieta"))
            for w in opcje:
                uk.addWidget(w)
        r = QHBoxLayout()
        r.addWidget(przycisk("Opcje drukarki…", "ustawienia", "plaski", self._opcje_systemowe))
        r.addStretch()
        r.addWidget(przycisk("Anuluj", akcja=self.reject))
        drukuj = przycisk("Drukuj", "drukarka", "glowny", self.accept)
        drukuj.setDefault(True)
        r.addWidget(drukuj)
        uk.addLayout(r)
        self._drukarka: QPrinter | None = None
        self._wybrana_systemowo = ""

    def _opcje_systemowe(self):
        """Okno sterownika drukarki (np. dwustronnie, podajnik, jakość)."""
        drukarka = self.drukarka()
        if QPrintDialog(drukarka, self).exec() == QDialog.DialogCode.Accepted:
            self._drukarka = drukarka
            i = self.drukarka_pole.findData(drukarka.printerName())
            if i >= 0:
                self.drukarka_pole.blockSignals(True)
                self.drukarka_pole.setCurrentIndex(i)
                self.drukarka_pole.blockSignals(False)
            self.egzemplarze.setValue(max(1, drukarka.copyCount()))
            self._wybrana_systemowo = self.drukarka_pole.currentData() or ""

    def ustawienia(self) -> dict[str, str]:
        wynik = dict(self.u)
        wynik["drukarka"] = self.drukarka_pole.currentData() or ""
        wynik["druk_data_wydruku"] = "1" if self.data_wydruku.isChecked() else "0"
        wynik["druk_pesel"] = "1" if self.pesel.isChecked() else "0"
        wynik["druk_data_wygenerowania"] = "1" if self.data_wygenerowania.isChecked() else "0"
        return wynik

    def drukarka(self) -> QPrinter:
        if self._drukarka is not None and self._wybrana_systemowo == (self.drukarka_pole.currentData() or ""):
            drukarka = self._drukarka  # z opcjami ustawionymi w oknie sterownika
        else:
            drukarka = druk.przygotuj_drukarke(self.ustawienia())
        drukarka.setCopyCount(self.egzemplarze.value())
        return drukarka


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
            "Wpisz co najmniej 3 litery nazwiska, pełny numer dokumentu albo PESEL, aby wyszukać.\n"
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
        """Bez hasła widać tylko wyniki konkretnego wyszukiwania, nie całą listę nazwisk."""
        zablokowane = self.okno.baza.ma_haslo and not self.pelny_dostep and not zapytanie_dozwolone(self.szukaj.text())
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
        sciezki = self._sprawdz_skanerem(sciezki)
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

    def _sprawdz_skanerem(self, sciezki: list[Path]) -> list[Path]:
        """Każdy plik przed dodaniem: zagrożenie = odrzucony, podejrzany = tylko po potwierdzeniu."""
        from . import skaner
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            wyniki = [(p, skaner.skanuj(p)) for p in sciezki]
        finally:
            QApplication.restoreOverrideCursor()
        dobre = [p for p, w in wyniki if w.stan == skaner.CZYSTY]
        grozne = [w for _, w in wyniki if w.stan == skaner.ZAGROZENIE]
        podejrzane = [(p, w) for p, w in wyniki if w.stan == skaner.PODEJRZANY]
        if grozne:
            self.okno.dziennik.zapisz(f"SKANER: odrzucono pliki z zagrożeniem ({len(grozne)})")
            QMessageBox.critical(self, "Skaner plików", "Tych plików nie dodano, bo mogą być niebezpieczne:\n\n" +
                                 "\n".join(f"• {w.plik}: {'; '.join(w.powody)}" for w in grozne[:8]))
        if podejrzane:
            odp = QMessageBox.warning(
                self, "Skaner plików", "Te pliki wyglądają podejrzanie:\n\n" +
                "\n".join(f"• {w.plik}: {'; '.join(w.powody)}" for _, w in podejrzane[:8]) +
                "\n\nDodać je mimo to? Wybierz „Nie”, jeśli nie wiesz, skąd pochodzą.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if odp == QMessageBox.StandardButton.Yes:
                dobre += [p for p, _ in podejrzane]
                self.okno.dziennik.zapisz(f"SKANER: dodano mimo ostrzeżenia ({len(podejrzane)})")
        return dobre

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
        wybor = self.okno.ustawienia_wydruku(self, p.nazwa, dokument=None, zawsze=True)
        if not wybor:
            return
        drukarka = wybor[0]
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
        self.okno, self.dok, self.duplikat, self.z_kopia = okno, dok, duplikat, z_kopia
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
        if dok.id and not dok.anulowano and not dok.jest_korekta:
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
        if self.dok.id is None:  # podgląd niezapisanego dokumentu: wystawienie (zapis i numer) jak z formularza
            self.accept()
            self.okno.strona_nowy.drukuj()
            return
        wybor = self.okno.ustawienia_wydruku(self, f"{self.dok.tytul} nr {self.dok.numer}",
                                             z_kopia=self.z_kopia, zawsze=True)
        if not wybor:
            return
        drukarka, u, z_kopia = wybor
        druk.drukuj(druk.html_dokumentu(self.dok, u, z_kopia, self.duplikat), drukarka)
        self.okno.dziennik.zapisz(f"wydruk z podglądu: nr {self.dok.numer}")
        self.okno.komunikat(f"Wydrukowano nr {self.dok.numer}")

    def pdf(self):
        if self.dok.id is None:
            self.accept()
            self.okno.strona_nowy.zapisz_pdf()
            return
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
    def __init__(self, baza: Baza, dziennik: Dziennik, uzytkownik: dict | None = None):
        super().__init__()
        self.baza = baza
        self.dziennik = dziennik
        self.uzytkownik = uzytkownik or self.wlascicielka()
        self.dziennik.kto = self.uzytkownik["nazwa"] if self.baza.konta() else ""
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
        marka.addLayout(opis)
        marka.addStretch()
        m.addLayout(marka)

        szukaj = QPushButton("   Szukaj…", objectName="szukaj_menu", cursor=Qt.CursorShape.PointingHandCursor)
        szukaj.setIcon(ikona("szukaj", MENU_TEKST))
        szukaj.setToolTip("Szybkie wyszukiwanie (Ctrl+K)")
        szukaj.clicked.connect(self.szybkie_szukanie)
        m.addWidget(szukaj)
        m.addSpacing(6)
        self.grupa = QButtonGroup(self)
        for i, (nazwa, ik) in enumerate([("Nowy dokument", "nowy"), ("Historia", "historia"), ("Przychody", "wzrost"),
                                         ("Pliki", "archiwum"), ("Narzędzia", "narzedzia"),
                                         ("Ustawienia", "ustawienia")]):
            b = QPushButton(f"   {nazwa}", checkable=True, cursor=Qt.CursorShape.PointingHandCursor)
            b.setIcon(ikona(ik, MENU_TEKST, aktywny="#ffffff"))
            b.clicked.connect(lambda _=False, i=i: self.przejdz(i))
            self.grupa.addButton(b, i)
            m.addWidget(b)
        m.addStretch()
        m.addWidget(QFrame(objectName="menu_linia"))
        m.addSpacing(8)
        self.etykieta_konta = QLabel()
        self.etykieta_konta.setStyleSheet("padding: 0 24px 6px; color: #dfeef0; font-size: 12px;")
        m.addWidget(self.etykieta_konta)
        self.btn_zamknij_gabinet = QPushButton("   Zamykam gabinet", cursor=Qt.CursorShape.PointingHandCursor)
        self.btn_zamknij_gabinet.setIcon(ikona("kalendarz", MENU_TEKST))
        self.btn_zamknij_gabinet.clicked.connect(self.zamknij_gabinet)
        m.addWidget(self.btn_zamknij_gabinet)
        self.btn_blokuj = QPushButton("   Zablokuj", cursor=Qt.CursorShape.PointingHandCursor)
        self.btn_blokuj.setIcon(ikona("klodka", MENU_TEKST))
        self.btn_blokuj.clicked.connect(self.zablokuj)
        m.addWidget(self.btn_blokuj)
        self.etykieta_gabinetu = QLabel(objectName="gabinet")
        self.etykieta_gabinetu.setFixedWidth(190)
        self.etykieta_gabinetu.setStyleSheet("padding: 6px 24px 0; color: #a9c3c8;")
        m.addWidget(self.etykieta_gabinetu)
        wersja = QLabel(f"Wersja {WERSJA}  ·  TeodorTeo.com")
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
        self.strona_narzedzia = StronaNarzedzia(self)
        self.strona_ustawienia = StronaUstawienia(self)
        for s in (self.strona_nowy, self.strona_historia, self.strona_pulpit, self.strona_pliki,
                  self.strona_narzedzia, self.strona_ustawienia):
            self.strony.addWidget(s)
        prawa.addWidget(self.strony, 1)
        uklad.addLayout(prawa, 1)
        self.setCentralWidget(tlo)
        self.powiadomienie = Powiadomienie(tlo)
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self.strona_pulpit._nowy(self.baza.ustawienia()["tytul"]))
        QShortcut(QKeySequence("Ctrl+K"), self, self.szybkie_szukanie)

        self.strona_nowy.ustaw_tryb(self.baza.ustawienia()["tryb"])
        self.strona_nowy.wyczysc()
        self.przejdz(STRONA_NOWY)
        self.odswiez_uprawnienia()

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
        OCHRONA_EKRANU.ustaw(self.baza.ustawienia()["ochrona_ekranu"] == "1")
        # wylogowanie / wyłączenie komputera: zamknij się normalnie (zapis, kopia), zamiast chować do zasobnika
        QApplication.instance().commitDataRequest.connect(self._koniec_sesji)
        zapamietany = self.baza.ustawienia()["ostatni_wpis_dziennika"]
        self._dziennik_uciety = bool(zapamietany) and not self.dziennik.zawiera(zapamietany)
        self.dziennik.po_zapisie = self._zapamietaj_wpis
        self._utworz_zasobnik()
        self.zegar_straznika = QTimer(self, interval=60 * 1000)
        self.zegar_straznika.timeout.connect(self.sprawdz_integralnosc)
        self.zegar_straznika.start()
        QTimer.singleShot(3000, self.sprawdz_integralnosc)

        self.wydanie: aktualizacje.Wydanie | None = None
        self._restart_argumenty: list[str] = []
        self._aktualizacja_w_toku = False
        if aktualizacje.czy_spakowany() and self.baza.ustawienia()["auto_aktualizacje"] == "1":
            QTimer.singleShot(2500, lambda: self.sprawdz_aktualizacje(cicho=True))
            QTimer.singleShot(6000, self.sprawdz_program)
        # program działa w tle całymi dniami, więc o nowe wersje pyta też co 6 godzin
        self.zegar_aktualizacji = QTimer(self, interval=6 * 60 * 60 * 1000)
        self.zegar_aktualizacji.timeout.connect(self._okresowa_aktualizacja)
        self.zegar_aktualizacji.start()
        # kopie co 10 minut (gdy dane się zmieniły) i sprawdzenie, czy usługa nie zainstalowała nowej wersji
        self.ostatnia_kopia: datetime | None = None
        self._skrot_kopii = ""
        self._blad_kopii_zgloszony = ""
        self.zegar_kopii = QTimer(self, interval=10 * 60 * 1000)
        self.zegar_kopii.timeout.connect(self._co_10_minut)
        self.zegar_kopii.start()
        # godziny pracy: przypomnienie przed końcem i wylogowanie po godzinach
        self._uruchomiono = datetime.now()
        self._przypomniano = ""
        self._koniec_zgloszony = ""
        self.zaslona = None
        self.zegar_zaslony = QTimer(self, interval=2000)
        self.zegar_zaslony.timeout.connect(self._sprawdz_zaslone)
        self.zegar_zaslony.start()
        # skaner folderu Pobrane: nowe pliki sprawdzane w tle, ostrzeżenie tylko przy problemie
        self._sprawdzone_pobrane: dict[str, float] = {}
        self._pobrane_od = time.time()
        self.obserwator_pobranych = QFileSystemWatcher(self)
        if katalog_pobranych().is_dir():
            self.obserwator_pobranych.addPath(str(katalog_pobranych()))
        self._zwloka_pobranych = QTimer(self, singleShot=True, interval=4000)  # pobieranie musi się skończyć
        self.obserwator_pobranych.directoryChanged.connect(lambda _: self._zwloka_pobranych.start())
        self._zwloka_pobranych.timeout.connect(self._skanuj_pobrane)
        self.zegar_godzin = QTimer(self, interval=30 * 1000)
        self.zegar_godzin.timeout.connect(self.sprawdz_godziny)
        self.zegar_godzin.start()
        # ekrany z danymi odświeżają się same (np. przychody, gdy asystentka wystawi dokument)
        self.zegar_odswiezania = QTimer(self, interval=60 * 1000)
        self.zegar_odswiezania.timeout.connect(self._odswiez_widoczna_strone)
        self.zegar_odswiezania.start()
        if self.baza.ustawienia()["skonfigurowano"] != "1":
            QTimer.singleShot(200, self.pierwsze_uruchomienie)
        # kontrola komputera przy każdym uruchomieniu (także przy starcie Windows, gdy program startuje w tle)
        self._program_ok: bool | None = None
        QTimer.singleShot(8000, self.kontrola_startowa)
        QTimer.singleShot(1500, self._wymagaj_instalacji)
        QTimer.singleShot(2500, self.powitanie)
        # dziennik blokowania i odblokowania komputera (oraz logowań i połączeń zdalnych)
        self._zablokowano_windows: datetime | None = None
        windows.sledz_sesje(int(self.winId()))

    def przejdz(self, i: int, odswiez: bool = True):
        if i in (STRONA_PRZYCHODY, STRONA_USTAWIENIA) and not self.jest_wlascicielka:
            i = STRONA_NOWY  # asystentka nie ma dostępu do przychodów ani ustawień
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

    def polecenia(self) -> list[tuple[str, str, str, object]]:
        """(nazwa, opis, ikona, akcja) do szybkiego wyszukiwania; tylko to, do czego konto ma dostęp."""
        n = self.strona_narzedzia
        wynik = [
            ("Nowy rachunek", "Dokument", "plus", lambda: self.strona_pulpit._nowy("Rachunek")),
            ("Nowa faktura", "Dokument", "faktura", lambda: self.strona_pulpit._nowy("Faktura")),
            ("Historia", "Ekran", "historia", lambda: self.przejdz(STRONA_HISTORIA)),
            ("Pliki", "Ekran", "archiwum", lambda: self.przejdz(STRONA_PLIKI)),
            ("Narzędzia", "Ekran", "narzedzia", lambda: (self.przejdz(STRONA_NARZEDZIA), n.pokaz(None))),
            ("Zasłoń ekran", "Działanie", "pulpit", self.pokaz_zaslone),
            ("Zamykam gabinet", "Działanie", "klodka", self.zamknij_gabinet),
            ("Zamknięcie dnia", "Wydruk utargu", "drukarka", self.zamkniecie_dnia),
        ]
        wlaczony = self.baza.ustawienia()["zaslona"] == "1"
        wynik.append(("Wyłącz wygaszacz ekranu" if wlaczony else "Włącz wygaszacz ekranu", "Ustawienie", "pulpit",
                      lambda: self.przelacz_wygaszacz(not wlaczony)))
        if self.baza.ma_haslo:
            wynik.append(("Zablokuj program", "Działanie", "klodka", self.zablokuj))
        if self.jest_wlascicielka:
            wynik += [("Przychody", "Ekran", "wzrost", lambda: self.przejdz(STRONA_PRZYCHODY)),
                      ("Ustawienia", "Ekran", "ustawienia", lambda: self.przejdz(STRONA_USTAWIENIA))]
        for klucz, nazwa, ik in n.NARZEDZIA:
            wynik.append((nazwa, "Narzędzie", ik,
                          lambda k=klucz: (self.przejdz(STRONA_NARZEDZIA), self.strona_narzedzia.pokaz(k))))
        return wynik

    def szybkie_szukanie(self):
        if not self.isVisible() or QApplication.activeModalWidget():
            return
        okno = OknoSzukania(self)
        geo = self.geometry()
        okno.adjustSize()
        okno.move(geo.x() + (geo.width() - okno.width()) // 2, geo.y() + 90)
        okno.exec()

    def pokaz_pacjenta(self, nazwa: str):
        self.przejdz(STRONA_HISTORIA)
        self.strona_historia.szukaj.setText(nazwa)

    def powitanie(self):
        """Raz dziennie, przy pierwszym uruchomieniu: krótkie podsumowanie dnia."""
        u = self.baza.ustawienia()
        dzis = date.today().isoformat()
        if u["skonfigurowano"] != "1" or u.get("ostatnie_powitanie") == dzis:
            return
        self.baza.zapisz_ustawienia({"ostatnie_powitanie": dzis})
        godzina = datetime.now().hour
        tytul = "Dzień dobry" if 5 <= godzina < 18 else "Dobry wieczór"
        imie = (self.uzytkownik or {}).get("nazwa", "")
        if imie and imie not in ("Właściciel", "Właścicielka"):
            tytul += f", {imie}"
        linie = []
        zadania = gtd.liczniki(gtd.wczytaj(u.get("gtd", "")))["dzis"]
        if zadania:
            linie.append(f"Zadania na dziś: {zadania}")
        przyp = narzedzia.wczytaj_przypomnienia(u.get("przypomnienia", ""))
        dzisiejsze = [p for p in przyp if p["kiedy"].startswith(dzis)]
        if dzisiejsze:
            linie.append(f"Przypomnienia: {len(dzisiejsze)}, najbliższe o {dzisiejsze[0]['kiedy'][11:16]}")
        if swieto := narzedzia.swieto(date.today()):
            linie.append(f"Dziś {swieto}")
        linie.append(godziny.opis_stanu(godziny.wczytaj(u["godziny_pracy"]), datetime.now()))
        linie.append("Ctrl+K: szybkie wyszukiwanie")
        self.powiadom(tytul, "\n".join(linie), "info", czas_ms=9000)

    def _skanuj_pobrane(self):
        if self.baza.ustawienia().get("skaner_pobrane") != "1":
            return
        from . import skaner
        nowe = [p for p in skaner.nowe_pobrane(katalog_pobranych(), self._pobrane_od)
                if self._sprawdzone_pobrane.get(str(p)) != p.stat().st_mtime]
        if not nowe:
            return
        for p in nowe:
            self._sprawdzone_pobrane[str(p)] = p.stat().st_mtime
        w = Watek(lambda: [skaner.skanuj(p) for p in nowe])
        w.gotowe.connect(self._wynik_pobranych)
        self._w_tle(w)

    def _wynik_pobranych(self, wyniki):
        from . import skaner
        zle = [w for w in wyniki if w.stan != skaner.CZYSTY]
        if not zle:
            return
        grozne = any(w.stan == skaner.ZAGROZENIE for w in zle)
        self.dziennik.zapisz(f"SKANER: pobrane pliki z uwagami ({len(zle)})")
        self.powiadom("Niebezpieczny plik w Pobranych" if grozne else "Podejrzany plik w Pobranych",
                      "\n".join(f"{w.plik}: {'; '.join(w.powody)}" for w in zle[:3]) +
                      "\nNie otwieraj go, jeśli nie wiesz, skąd pochodzi.", "blad" if grozne else "uwaga",
                      lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(katalog_pobranych()))), czas_ms=20000)

    def przelacz_wygaszacz(self, wlacz: bool):
        self.baza.zapisz_ustawienia({"zaslona": "1" if wlacz else "0"})
        self.dziennik.zapisz("wygaszacz ekranu: " + ("włączony" if wlacz else "wyłączony"))
        self.komunikat("Wygaszacz ekranu " + ("włączony" if wlacz else "wyłączony"))

    def _bezczynnosc(self) -> float:
        """Sekundy bez ruchu myszy i klawiatury: w całym Windows, a gdzie indziej w samym programie."""
        systemowa = windows.bezczynnosc_sekund()
        if systemowa is not None:
            return systemowa
        if self.timer.isActive():
            return max(0, self.timer.interval() - self.timer.remainingTime()) / 1000
        return 0.0

    def _sprawdz_zaslone(self):
        try:
            u = self.baza.ustawienia()
        except Exception:  # noqa: BLE001
            return
        if self.zaslona or u.get("zaslona") != "1" or self._zablokowano_windows:
            return  # przy zablokowanym Windows zasłona nie jest potrzebna (i czekałaby po odblokowaniu)
        if self._bezczynnosc() >= max(5, int(liczba(u.get("zaslona_sekund")) or 30)):
            self.pokaz_zaslone()

    def pokaz_zaslone(self):
        if self.zaslona:
            return
        from .zaslona import Zaslona
        u = self.baza.ustawienia()
        self.zaslona = Zaslona(u["nazwa"].split(",")[0].strip(), float(liczba(u.get("zaslona_gaszenie_min")) or 0))
        self.zaslona.zamknieta.connect(lambda: setattr(self, "zaslona", None))
        self.zaslona.pokaz()

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

    def ustawienia_wydruku(self, rodzic: QWidget, tytul: str, dokument: bool | None = True,
                           z_kopia: bool = False, zawsze: bool = False):
        """Zwraca (drukarka, ustawienia, oryginał i kopia) albo None, gdy wydruk anulowano.

        Okno pokazuje się, gdy włączono je w Ustawieniach albo przy wydrukach, które zawsze o nie pytały.
        """
        u = self.baza.ustawienia()
        if not zawsze and u["okno_drukarki"] != "1":
            return druk.przygotuj_drukarke(u), u, z_kopia
        okno = OknoDruku(u, tytul, dokument, z_kopia, rodzic)
        if okno.exec() != QDialog.DialogCode.Accepted:
            return None
        return okno.drukarka(), okno.ustawienia(), okno.kopia.isChecked()

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

    def _dziennik_ok(self) -> bool:
        zapamietany = self.baza.ustawienia()["ostatni_wpis_dziennika"]
        uciety = self._dziennik_uciety or (bool(zapamietany) and not self.dziennik.zawiera(zapamietany))
        return self.dziennik.nienaruszony() and not uciety

    def wyniki_kontroli(self) -> list:
        return kontrola.kontrola(self.baza, self._dziennik_ok(), self._program_ok)

    def kontrola_startowa(self):
        """Weryfikacja komputera po uruchomieniu: wynik w dzienniku, ostrzeżenia w powiadomieniu."""
        if self.baza.ustawienia()["skonfigurowano"] != "1":
            return  # najpierw kreator pierwszego uruchomienia
        # nieudane logowania do Windows od poprzedniego uruchomienia (np. ktoś próbował w nocy)
        try:
            od = datetime.fromisoformat(self.baza.ustawienia()["ostatnie_sprawdzenie_logowan"])
        except ValueError:
            od = datetime.now() - timedelta(days=1)
        self.baza.zapisz_ustawienia({"ostatnie_sprawdzenie_logowan": datetime.now().isoformat(timespec="seconds")})
        w = Watek(windows.nieudane_logowania, od)
        w.gotowe.connect(self._nieudane_proby)
        self._w_tle(w)
        pokaz = kontrola.do_pokazania(self.baza, self.wyniki_kontroli())
        self.dziennik.zapisz("kontrola komputera: " + ("OK" if not pokaz else
                                                        "uwagi: " + ", ".join(w.klucz for w in pokaz)))
        if pokaz:
            self.powiadom(f"Kontrola komputera: {len(pokaz)} do sprawdzenia",
                          "\n".join(f"• {w.nazwa}: {w.opis}" for w in pokaz[:4]) + "\nKliknij, aby zobaczyć szczegóły.",
                          "uwaga", self._otworz_kontrole, 12000)
        elif self.baza.ustawienia()["powiadomienie_startowe"] == "1":
            self.powiadom("Komputer zweryfikowany", "Szyfrowanie, kopie i ochrona programu działają.", "ok",
                          self._otworz_kontrole, 4500)

    def nativeEvent(self, typ, wiadomosc):
        if windows.na_windows() and typ == b"windows_generic_MSG":
            try:
                zdarzenie = windows.zdarzenie_sesji(int(wiadomosc))
            except (TypeError, ValueError, OSError):
                zdarzenie = None
            if zdarzenie is not None:
                QTimer.singleShot(0, lambda z=zdarzenie: self._zdarzenie_sesji(z))
        return super().nativeEvent(typ, wiadomosc)

    def _zdarzenie_sesji(self, zdarzenie: int):
        opis = windows.ZDARZENIA_SESJI.get(zdarzenie)
        if not opis:
            return
        uzytkownik = os.environ.get("USERNAME", "")
        self.dziennik.zapisz(f"Windows: {opis}" + (f" ({uzytkownik})" if uzytkownik else ""))
        if zdarzenie == windows.BLOKADA:
            self._zablokowano_windows = datetime.now()
            self.strona_narzedzia.wyczysc_schowek_teraz()  # zawsze, także gdy Fakturnik się nie blokuje
            if self.baza.ma_haslo and self.baza.ustawienia()["blokuj_z_komputerem"] == "1":
                self.zablokuj()  # komputer zablokowany: Fakturnik też
        elif zdarzenie == windows.ODBLOKOWANIE:
            od = self._zablokowano_windows or datetime.now() - timedelta(hours=1)
            self._zablokowano_windows = None
            w = Watek(windows.nieudane_logowania, od)
            w.gotowe.connect(self._nieudane_proby)
            self._w_tle(w)
        elif zdarzenie == 0x3:  # ktoś połączył się zdalnie
            self.powiadom("Zdalne połączenie z komputerem", "Ktoś połączył się z tym komputerem zdalnie. "
                          "Jeśli to nie Ty ani Twój serwis, odłącz komputer od internetu.", "blad", czas_ms=20000)

    def _nieudane_proby(self, ile):
        if ile:
            self.dziennik.zapisz(f"Windows: NIEUDANE próby odblokowania lub logowania: {ile}")
            self.powiadom("Nieudane próby odblokowania komputera",
                          f"Ktoś {ile} raz(y) wpisał złe hasło do Windows. Szczegóły w dzienniku Fakturnika.",
                          "uwaga", lambda: (self.pokaz_okno(), self.strona_ustawienia.pokaz_dziennik()
                                            if self.isVisible() else None), 15000)

    def _otworz_kontrole(self):
        self.pokaz_okno()
        if self.isVisible():
            self.pokaz_kontrole()

    def powiadom(self, tytul: str, tekst: str = "", typ: str = "info", akcja=None, czas_ms: int = 6000):
        """Własne powiadomienie Fakturnika w rogu ekranu (zamiast dymków Windows)."""
        if not QApplication.instance().platformName() or QApplication.instance().platformName() == "minimal":
            return
        u = self.baza.ustawienia()
        czas_ms = max(czas_ms, int(liczba(u["powiadomienia_sekund"]) or 6) * 1000)
        if u["powiadomienia_dzwiek"] == "1":
            QApplication.beep()
        OknoPowiadomienia(tytul, tekst, typ, akcja, czas_ms,
                          QPixmap(str(ZASOBY / "ikona.png")).scaled(
                              30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)).pokaz()

    def pokaz_kontrole(self):
        OknoKontroli(self).exec()

    def nowy_dziennik(self):
        archiwum = self.dziennik.archiwizuj()
        self._dziennik_uciety = False
        self._dziennik_zgloszony = False
        if archiwum:
            self.komunikat(f"Rozpoczęto nowy dziennik; poprzedni: {archiwum.name}")

    def sprawdz_godziny(self, teraz: datetime | None = None):
        teraz = teraz or datetime.now()
        u = self.baza.ustawienia()
        g = godziny.wczytaj(u["godziny_pracy"])
        koniec = godziny.koniec_dzis(g, teraz)
        dzis = teraz.date().isoformat()
        minuty = int(liczba(u["przypomnienie_min"]) or 0)
        if koniec and godziny.w_godzinach(g, teraz) and minuty and koniec - teraz <= timedelta(minutes=minuty) \
                and self._przypomniano != dzis:
            self._przypomniano = dzis
            self.powiadom(f"Za {max(1, round((koniec - teraz).total_seconds() / 60))} min koniec godzin pracy",
                          f"Dziś do {koniec:%H:%M}. Kliknij, aby zamknąć gabinet.", "info",
                          lambda: (self.pokaz_okno(), self.zamknij_gabinet() if self.isVisible() else None), 15000)
        if koniec and teraz >= koniec and self._koniec_zgloszony != dzis and self._uruchomiono < koniec:
            self._koniec_zgloszony = dzis
            self.dziennik.zapisz(f"koniec godzin pracy ({koniec:%H:%M})")
            self.powiadom("Godziny pracy się skończyły", f"Dziś pracowano do {koniec:%H:%M}. "
                          + ("Konta asystentek zostały wylogowane." if u["wyloguj_po_godzinach"] != "nikt" else ""),
                          "info", czas_ms=15000)
        # po godzinach: wylogowanie (właściciel może zalogować się zawsze, asystentka za jego zgodą)
        tryb = u["wyloguj_po_godzinach"]
        if tryb == "nikt" or not self.baza.ma_haslo or not self.isVisible():
            return
        if godziny.w_godzinach(g, teraz) or godziny.zgoda_aktywna(teraz):
            return
        asystentka = not self.jest_wlascicielka
        wlascicielka_dzis = tryb == "wszyscy" and self._koniec_zgloszony == dzis \
            and getattr(self, "_wylogowano_dzis", "") != dzis  # właściciela raz, zaraz po końcu godzin
        if asystentka or wlascicielka_dzis:
            self._wylogowano_dzis = dzis
            self.dziennik.zapisz("wylogowanie po godzinach pracy")
            self.zablokuj()

    def _odswiez_widoczna_strone(self):
        if self.isVisible() and not QApplication.activeModalWidget() and self.strony.currentIndex() == STRONA_PRZYCHODY \
                and self.strona_pulpit.zawartosc.isVisible():
            self.strona_pulpit._wypelnij()  # odsłonięte kwoty: tylko nowe liczby, bez ponownego pytania o hasło

    def _co_10_minut(self):
        self.kopia_ciagla()
        if aktualizacje.plik_programu_zmieniony() and not self.uruchom_po_zamknieciu:
            self.uruchom_po_zamknieciu = Path(sys.executable)  # nową wersję zainstalowała usługa
            self.dziennik.zapisz("nowa wersja zainstalowana przez usługę")
            self.tekst_aktualizacji.setText("Zainstalowano nową wersję. Uruchomi się sama, gdy schowasz okno, "
                                            "albo teraz:")
            self.btn_instaluj.setText("Uruchom ponownie")
            self.btn_instaluj.clicked.disconnect()
            self.btn_instaluj.clicked.connect(lambda: self._uruchom_ponownie(w_tle=False))
            self.pasek_aktualizacji.show()
            self._restart_jesli_mozna()

    def kopia_ciagla(self, wymus: bool = False):
        """Kopia 1 (Dokumenty) i 3 (wybrany folder), gdy dane zmieniły się od ostatniej kopii."""
        skrot = self.baza._skrot_zapisu
        if not wymus and skrot == self._skrot_kopii:
            return
        try:
            kopia_automatyczna(self.baza.sciezka)
            self.baza.kopia_plikow(katalog_kopii() / "pliki")
        except OSError as e:
            self.dziennik.zapisz(f"kopia automatyczna: BŁĄD ({e.__class__.__name__})")
            return
        folder = self.baza.ustawienia()["kopia_folder"]
        if folder:
            cel = Path(folder) / "Fakturnik-kopie"
            try:
                kopia_automatyczna(self.baza.sciezka, cel)
                self.baza.kopia_plikow(cel / "pliki")
            except OSError:
                if self._blad_kopii_zgloszony != date.today().isoformat():  # raz dziennie, bez zasypywania
                    self._blad_kopii_zgloszony = date.today().isoformat()
                    self.powiadom("Trzecia kopia niedostępna",
                                  f"Nie można zapisać kopii w {folder}. Podłącz dysk lub sprawdź folder.", "uwaga")
        self._skrot_kopii = skrot
        self.ostatnia_kopia = datetime.now()

    def _okresowa_aktualizacja(self):
        if aktualizacje.czy_spakowany() and self.baza.ustawienia()["auto_aktualizacje"] == "1" \
                and not self.uruchom_po_zamknieciu:
            self.sprawdz_aktualizacje(cicho=True)
        self._restart_jesli_mozna()

    def _restart_jesli_mozna(self):
        """Nowa wersja startuje sama tylko wtedy, gdy nikt nie pracuje w oknie."""
        if self.uruchom_po_zamknieciu and not self.isVisible() and not QApplication.activeModalWidget():
            self._uruchom_ponownie(w_tle=True)

    def _uruchom_ponownie(self, w_tle: bool):
        if self.strona_nowy.edytowany is not None or (self.isVisible() and self.strona_nowy.ma_niezapisane()):
            if QMessageBox.question(self, "Uruchom ponownie", "Na stronie „Nowy dokument” są niezapisane dane. "
                                    "Uruchomić ponownie mimo to?") != QMessageBox.StandardButton.Yes:
                return
        self._restart_argumenty = ["--w-tle"] if w_tle else []
        self._wyjscie = True
        self.close()
        QApplication.quit()

    def sprawdz_program(self):
        """Czy działający Fakturnik.exe jest tym samym plikiem, który opublikowano w wydaniu."""
        if self.uruchom_po_zamknieciu:
            return  # plik już podmieniono na nową wersję
        w = Watek(aktualizacje.sprawdz_wlasny_plik)
        w.gotowe.connect(self._wynik_sprawdzenia_programu)
        w.blad.connect(lambda _: None)
        self._w_tle(w)

    def _wynik_sprawdzenia_programu(self, oryginalny):
        self._program_ok = oryginalny
        if oryginalny is False:
            tekst = ("Plik programu różni się od opublikowanego wydania (mógł zostać zmieniony). "
                     "Pobierz Fakturnik.exe ponownie ze strony wydań i nie wpisuj hasła w tej kopii.")
            self.dziennik.zapisz("STRAŻNIK: plik programu różni się od opublikowanego wydania")
            self.powiadom("Uwaga: plik programu zmieniony", tekst, "blad", czas_ms=15000)
            QMessageBox.critical(self, "Fakturnik", tekst)

    def _wynik_sprawdzenia(self, wydanie, cicho: bool):
        self.wydanie = wydanie
        if not wydanie:
            if not cicho:
                QMessageBox.information(self, "Aktualizacje", f"Masz najnowszą wersję ({WERSJA}).")
            return
        if aktualizacje.czy_spakowany() and aktualizacje.zainstalowany():
            if not cicho:  # Program Files: nową wersję zainstaluje usługa (konto SYSTEM)
                QMessageBox.information(self, "Aktualizacje", f"Dostępna jest wersja {wydanie.wersja}. Zainstaluje ją "
                                        "automatycznie usługa Fakturnika w ciągu godziny, a program uruchomi się "
                                        "ponownie, gdy schowasz okno.")
            return
        self.tekst_aktualizacji.setText(f"Dostępna jest wersja {wydanie.wersja}. Instaluje ją instalator "
                                        "za zgodą administratora; dane zostają.")
        self.pasek_aktualizacji.show()
        if cicho and not self.isVisible():
            self.powiadom("Dostępna aktualizacja", f"Wersja {wydanie.wersja}. Kliknij, aby ją zainstalować.", "info",
                          lambda: (self.pokaz_okno(), self.instaluj_aktualizacje() if self.isVisible() else None))

    def instaluj_aktualizacje(self):
        """Program nigdy nie podmienia sam swojego pliku: aktualizacja idzie przez instalator z okienkiem zgody
        administratora (UAC) albo, w instalacji w Program Files, przez usługę systemową."""
        if not self.wydanie or self._aktualizacja_w_toku or self.uruchom_po_zamknieciu:
            return
        if not aktualizacje.czy_spakowany():
            QMessageBox.information(self, "Aktualizacje", "Aktualizacje instalują się tylko w wersji .exe.")
            return
        if aktualizacje.zainstalowany():
            QMessageBox.information(self, "Aktualizacje", "Nową wersję zainstaluje automatycznie usługa Fakturnika "
                                    "w ciągu godziny, a program uruchomi się ponownie, gdy schowasz okno.")
            return
        opis = self.wydanie.opis.strip()
        self.uruchom_instalator_admin(
            f"Zainstalować wersję {self.wydanie.wersja}?\n\nProgram zrobi kopię danych, pobierze instalator, "
            "sprawdzi jego sumę SHA-256 i uruchomi go. Windows zapyta o zgodę administratora. Fakturnik trafi do "
            "Program Files z usługą kopii, a kolejne aktualizacje będą instalować się same." +
            (f"\n\nZmiany:\n{opis[:500]}" if opis else ""))

    def _wymagaj_instalacji(self):
        """Fakturnik zawsze działa z instalacji z uprawnieniami administratora (Program Files, usługa kopii).
        Uruchomiony bez niej (np. pobrany sam plik .exe) proponuje instalację przy każdym starcie."""
        if sys.platform != "win32" or not aktualizacje.czy_spakowany() or aktualizacje.zainstalowany():
            return
        if self._aktualizacja_w_toku or not self.isVisible():
            return
        okno = QMessageBox(QMessageBox.Icon.Warning, "Instalacja wymagana",
                           "Fakturnik nie jest zainstalowany z uprawnieniami administratora.\n\n"
                           "Bez instalacji nie działa usługa chronionych kopii, ochrona pliku programu "
                           "ani blokada odinstalowania. Program pobierze instalator (sprawdzi sumę SHA-256), "
                           "a Windows zapyta o zgodę administratora. Dane zostają bez zmian.", parent=self)
        teraz = okno.addButton("Zainstaluj teraz", QMessageBox.ButtonRole.AcceptRole)
        okno.addButton("Później", QMessageBox.ButtonRole.RejectRole)
        okno.setDefaultButton(teraz)
        okno.exec()
        if okno.clickedButton() is teraz:
            self.uruchom_instalator_admin("", pytaj=False)

    def uruchom_instalator_admin(self, pytanie: str, pytaj: bool = True):
        if pytaj and QMessageBox.question(self, "Instalacja", pytanie + "\n\nFakturnik zamknie się na czas "
                                          "instalacji.") != QMessageBox.StandardButton.Yes:
            return
        try:
            kopia_automatyczna(self.baza.sciezka, nazwa=f"przed-instalacja-{datetime.now():%Y-%m-%d-%H%M%S}.db")
        except OSError as e:
            QMessageBox.critical(self, "Instalacja", f"Nie udało się zrobić kopii danych, instalacja przerwana.\n{e}")
            return
        cel = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)) / "FakturnikSetup.exe"
        postep = QProgressDialog("Pobieranie instalatora…", "Anuluj", 0, 100, self)
        postep.setWindowTitle("Instalacja")
        postep.setWindowModality(Qt.WindowModality.WindowModal)
        postep.setMinimumDuration(0)
        postep.setCancelButton(None)
        self._aktualizacja_w_toku = True
        w = Watek(aktualizacje.pobierz_instalator, cel, z_postepem=True)
        w.postep.connect(postep.setValue)
        w.gotowe.connect(lambda sciezka: (postep.close(), self._uruchom_instalator(sciezka)))
        w.blad.connect(lambda tekst: (postep.close(), self._blad_aktualizacji(tekst)))
        self._w_tle(w)

    def _uruchom_instalator(self, sciezka: Path):
        """Instalator podmienia program, więc po jego starcie Fakturnik się wyłącza (dane są zapisane)."""
        self._aktualizacja_w_toku = False
        self.dziennik.zapisz("uruchomienie instalatora (zgoda administratora)")
        if not uruchom_jako_administrator(sciezka):
            QMessageBox.warning(self, "Instalacja", f"Nie udało się uruchomić instalatora:\n{sciezka}")
            return
        self._wyjscie = True
        self.uruchom_po_zamknieciu = None
        self.close()
        QApplication.quit()

    def _blad_aktualizacji(self, tekst: str):
        self._aktualizacja_w_toku = False
        self.dziennik.zapisz("aktualizacja: NIEUDANA")
        odp = QMessageBox.warning(self, "Aktualizacja", f"{tekst}\n\nOtworzyć stronę z pobraniem, "
                                  "żeby zaktualizować ręcznie?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if odp == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(f"https://github.com/{aktualizacje.REPOZYTORIUM}/releases/latest"))

    # ---- blokada i zamykanie
    def korekta_dokumentu(self, dok: Dokument):
        if not self.jest_wlascicielka and not self.potwierdz_haslem("korekta faktury",
                                                                    "Wystawienie korekty wymaga zgody właściciela."):
            return
        if dok.tytul != "Faktura" or dok.anulowano:
            QMessageBox.information(self, "Korekta", "Korektę wystawia się do ważnej faktury. Rachunek można "
                                    "poprawić przez Edytuj albo anulować i wystawić nowy.")
            return
        self.przejdz(STRONA_NOWY, odswiez=False)
        self.strona_nowy.zaladuj_do_korekty(dok)

    def edytuj_dokument(self, dok: Dokument):
        if dok.anulowano:
            self.komunikat("Anulowanego dokumentu nie można edytować", blad=True)
            return
        if dok.jest_korekta:
            QMessageBox.information(self, "Edycja", "Fakturę korygującą poprawia się kolejną korektą "
                                    "pierwotnej faktury albo anuluje i wystawia od nowa.")
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
        """Ważne operacje zawsze wymagają hasła właściciela (także gdy pracuje asystentka)."""
        if not self.baza.ma_haslo:
            return True
        if not self.jest_wlascicielka:
            opis += "\n(hasło właściciela)"
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
        menu.addAction(ikona("klodka", TEKST_2), "Zamykam gabinet…",
                       lambda: (self.pokaz_okno(), self.zamknij_gabinet() if self.isVisible() else None))
        menu.addAction(ikona("kalendarz", TEKST_2), "Zamknięcie dnia…", self._zamkniecie_z_zasobnika)
        menu.addAction(ikona("tarcza", TEKST_2), "Kontrola komputera…",
                       lambda: (self.pokaz_okno(), self.pokaz_kontrole() if self.isVisible() else None))
        menu.addSeparator()
        menu.addAction(ikona("pulpit", TEKST_2), "Zasłoń ekran", self.pokaz_zaslone)
        self.akcja_wygaszacza = menu.addAction("Wygaszacz ekranu (ząbek) włączony")
        self.akcja_wygaszacza.setCheckable(True)
        self.akcja_wygaszacza.toggled.connect(self.przelacz_wygaszacz)
        menu.aboutToShow.connect(lambda: (self.akcja_wygaszacza.blockSignals(True),
                                          self.akcja_wygaszacza.setChecked(self.baza.ustawienia()["zaslona"] == "1"),
                                          self.akcja_wygaszacza.blockSignals(False)))
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

    def _zamknij_okna_podrzedne(self):
        """Blokada nie może zostawić na ekranie otwartego podglądu, listy pacjentów itp."""
        for w in QApplication.topLevelWidgets():
            if w is not self and isinstance(w, QDialog) and w.isVisible() and type(w).__name__ != "Kreator":
                w.reject()

    def ukryj_do_zasobnika(self):
        self._zamknij_okna_podrzedne()
        self.strona_pulpit.zaslon()
        self.hide()
        self._ukryty = True
        if self.uruchom_po_zamknieciu:
            QTimer.singleShot(1500, self._restart_jesli_mozna)  # gotowa aktualizacja: nowa wersja startuje w tle
        if not self._podpowiedz_zasobnika:
            self._podpowiedz_zasobnika = True
            self.powiadom("Fakturnik działa w tle",
                          "Pilnuje bezpieczeństwa danych i robi kopie. Kliknij ikonę obok zegara, aby go otworzyć.",
                          "info", self.pokaz_okno, 5000)

    # ---- konta: właściciel i asystentki
    def wlascicielka(self) -> dict:
        nazwa = self.baza.ustawienia()["nazwa_wlascicielki"]
        if nazwa in ("", "Właścicielka"):  # wcześniejsza domyślna nazwa
            nazwa = "Właściciel"
        return {"id": "", "nazwa": nazwa,
                "rola": "wlascicielka"}

    @property
    def jest_wlascicielka(self) -> bool:
        return self.uzytkownik.get("rola") == "wlascicielka"

    def _ustaw_uzytkownika(self, uzytkownik: dict):
        poprzedni = self.uzytkownik.get("nazwa")
        self.uzytkownik = uzytkownik
        self.dziennik.kto = uzytkownik["nazwa"] if self.baza.konta() else ""
        if poprzedni != uzytkownik["nazwa"]:
            self.dziennik.zapisz("zmiana zalogowanego konta")
        self.odswiez_uprawnienia()

    def odswiez_uprawnienia(self):
        """Asystentka nie widzi przychodów ani ustawień; reszta operacji wymaga hasła właściciela."""
        wl = self.jest_wlascicielka
        for i in (STRONA_PRZYCHODY, STRONA_USTAWIENIA):
            self.grupa.button(i).setVisible(wl)
        konta_sa = bool(self.baza.konta())
        self.etykieta_konta.setVisible(konta_sa)
        self.etykieta_konta.setText(f"Zalogowano: {self.uzytkownik['nazwa']}" + ("" if wl else " (asystentka)"))
        self.btn_blokuj.setText("   Wyloguj" if konta_sa else "   Zablokuj")
        if not wl and self.strony.currentIndex() in (STRONA_PRZYCHODY, STRONA_USTAWIENIA):
            self.przejdz(STRONA_NOWY)

    def zaloguj_haslem(self, haslo: str):
        """Hasło właściciela albo konta asystentki; asystentka poza godzinami pracy tylko za zgodą."""
        if self.baza.sprawdz_haslo(haslo):
            self._ustaw_uzytkownika(self.wlascicielka())
            return True
        wynik = konta.zaloguj(self.baza.sciezka.parent, haslo)
        if not wynik or not self.baza.szyfr:
            return False
        wpis, klucz = wynik
        konto = self.baza.konto(wpis["id"])
        if not hmac.compare_digest(klucz, self.baza.szyfr.klucz_hasla) or not konto:
            return False
        if powod := godziny.odmowa(self.baza.ustawienia(), konto["rola"]):
            return powod
        self._ustaw_uzytkownika(konto)
        return True

    def udziel_zgody(self) -> bool:
        if OknoHasla(self.baza.sprawdz_haslo, "Zgoda właściciela", self, self.dziennik, "zgoda na pracę po godzinach",
                     "Praca asystentek po godzinach do końca dnia.\nPodaj hasło właściciela.").exec() \
                != QDialog.DialogCode.Accepted:
            return False
        godziny.udziel_zgody()
        self.dziennik.zapisz("zgoda właściciela na pracę po godzinach (do końca dnia)")
        return True

    def okno_logowania(self, tytul: str, cel: str, opis: str) -> "OknoHasla":
        u = self.baza.ustawienia()
        g = godziny.wczytaj(u["godziny_pracy"])
        return OknoHasla(self.zaloguj_haslem, tytul, dziennik=self.dziennik, cel=cel, opis=opis,
                         ekran_blokady={"gabinet": u["nazwa"].split(",")[0].strip(),
                                        "godziny": godziny.opis_stanu(g, datetime.now())},
                         zgoda=self.udziel_zgody if self.baza.konta() else None)

    def pokaz_okno(self):
        if self._ukryty and self.baza.ma_haslo:
            if self.okno_logowania("Fakturnik", "otwarcie z zasobnika",
                                   "Podaj swoje hasło, aby otworzyć program.").exec() != QDialog.DialogCode.Accepted:
                return
        self._ukryty = False
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.timer.start()

    def _nowy_z_zasobnika(self, rodzaj: str):
        self.pokaz_okno()
        if self.isVisible() and self.strona_nowy.porzuc_tryb():
            self.przejdz(STRONA_NOWY)
            self.strona_nowy.ustaw_rodzaj(rodzaj)

    def _zamkniecie_z_zasobnika(self):
        self.pokaz_okno()
        if self.isVisible():
            self.zamkniecie_dnia()

    def zamkniecie_dnia(self):
        """Raport utargu z dzisiejszego dnia do wydruku (gotówka do przeliczenia w kasie)."""
        asystentka_moze = not self.jest_wlascicielka and self.baza.ustawienia()["asystentki_zamkniecie_dnia"] == "1"
        if not asystentka_moze and not self.potwierdz_haslem("zamknięcie dnia",
                                                             "Raport zawiera kwoty, dlatego wymaga hasła."):
            return
        dzis = date.today()
        dokumenty = [d for d in self.baza.dokumenty(rok=dzis.year, miesiac=dzis.month)
                     if d.data_wystawienia == dzis.isoformat()]
        wybor = self.ustawienia_wydruku(self, "Zamknięcie dnia", dokument=False, zawsze=True)
        if not wybor:
            return
        drukarka, u, _ = wybor
        druk.drukuj(druk.html_zamkniecia_dnia(dokumenty, u, dzis), drukarka)
        self.dziennik.zapisz(f"zamknięcie dnia {dzis.isoformat()} ({len(dokumenty)} dok.)")
        self.komunikat(f"Wydrukowano zamknięcie dnia: {druk.zl(podsumuj(dokumenty).suma)} zł")

    def zamknij_gabinet(self):
        """Koniec dnia jednym przyciskiem: podsumowanie, opcjonalna kartka, kopia, wylogowanie."""
        asystentka_moze = not self.jest_wlascicielka and self.baza.ustawienia()["asystentki_zamkniecie_dnia"] == "1"
        if not asystentka_moze and not self.potwierdz_haslem("zamknięcie gabinetu",
                                                             "Podsumowanie zawiera kwoty, dlatego wymaga hasła."):
            return
        dzis = date.today()
        dokumenty = [d for d in self.baza.dokumenty(rok=dzis.year, miesiac=dzis.month)
                     if d.data_wystawienia == dzis.isoformat()]
        okno = OknoZamykaniaGabinetu(self, dokumenty)
        if okno.exec() != QDialog.DialogCode.Accepted:
            return
        if okno.kartka.isChecked():
            wybor = self.ustawienia_wydruku(self, "Kartka podsumowująca", dokument=False, zawsze=True)
            if wybor:
                drukarka, u, _ = wybor
                druk.drukuj(druk.html_zamkniecia_dnia(dokumenty, u, dzis), drukarka)
        if okno.kopia.isChecked():
            self.kopia_ciagla(wymus=True)
        self.dziennik.zapisz(f"zamknięcie gabinetu ({len(dokumenty)} dok., {druk.zl(podsumuj(dokumenty).suma)} zł)")
        g = godziny.wczytaj(self.baza.ustawienia()["godziny_pracy"])
        nast = godziny.nastepne(g, datetime.now() + timedelta(minutes=1))
        dalej = (f"Następne godziny pracy: {godziny.DNI[nast[0].weekday()]} {nast[0]:%H:%M}–{nast[1]:%H:%M}."
                 if nast else "")
        self.powiadom("Gabinet zamknięty", ("Kopia zapasowa zrobiona. " if okno.kopia.isChecked() else "") + dalej,
                      "ok", czas_ms=8000)
        if okno.wyloguj.isChecked() and self.baza.ma_haslo:
            self.zablokuj()

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
        self.strona_narzedzia.wyczysc_schowek_teraz()
        self._wyjscie = True
        self.uruchom_po_zamknieciu = None  # wyłączenie na życzenie: nowa wersja wystartuje przy następnym uruchomieniu
        self.close()
        QApplication.quit()

    # ---- strażnik integralności
    def sprawdz_integralnosc(self):
        try:
            self._sprawdz_integralnosc()
        except (PlikZajety, OSError):
            pass  # np. plik chwilowo zajęty przez antywirus; sprawdzimy za minutę

    def _sprawdz_integralnosc(self):
        problemy = self.baza.sprawdz_integralnosc(katalog_kopii() / "pliki")
        zapamietany = self.baza.ustawienia()["ostatni_wpis_dziennika"]
        uciety = self._dziennik_uciety or (bool(zapamietany) and not self.dziennik.zawiera(zapamietany))
        if (uciety or not self.dziennik.nienaruszony()) and not self._dziennik_zgloszony:
            self._dziennik_zgloszony = True
            problemy.append("Dziennik logowań został zmieniony, ucięty lub usunięto z niego wpisy.")
        if problemy:  # bez treści: nazwy plików bywają nazwiskami pacjentów, a dziennik nie jest szyfrowany
            self.dziennik.zapisz(f"STRAŻNIK: wykryto problemy z danymi ({len(problemy)})")
        if problemy:
            self.powiadom("Wykryto problem z danymi", "\n".join(problemy)[:400], "blad", czas_ms=12000)
            if self.isVisible():
                self.komunikat(problemy[0], blad=True)

    def _koniec_sesji(self, *_):
        if not self._wyjscie:
            self._wyjscie = True
            self.close()
            QApplication.quit()

    def _zapamietaj_wpis(self, skrot: str):
        try:
            self.baza.zapamietaj_wpis_dziennika(skrot)
        except Exception:
            pass  # np. baza już zamknięta przy wyłączaniu programu

    def zablokuj(self):
        self.strona_narzedzia.wyczysc_schowek_teraz()
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
        self._zamknij_okna_podrzedne()
        self.hide()
        okno = self.okno_logowania("Fakturnik jest zablokowany", "odblokowanie",
                                   "Podaj swoje hasło, aby wrócić do pracy.")
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
        self.kopia_ciagla(wymus=True)
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
    aktualizacje.zablokuj_program()
    aktualizacje.zapamietaj_plik_programu()
    windows.przygotuj_proces()
    app.installEventFilter(OCHRONA_EKRANU)

    # tylko jedna kopia programu: kolejne uruchomienie przekazuje polecenie działającej i kończy się
    argumenty = aktualizacje.czekaj_na_poprzednia(sys.argv[1:])  # po aktualizacji: stara wersja musi się zamknąć
    aktualizacje.posprzataj()  # dopiero teraz stary plik programu jest wolny
    polecenie = polecenie_z_argumentow(argumenty)
    jedna = JednaKopia()
    if jedna.wyslij_do_dzialajacej(polecenie):
        return 0
    jedna.nasluchuj()

    plik = sciezka_danych()
    _obsluga_bledow(plik.parent / "bledy.log")
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
        aktualizacje.uruchom_nowa_wersje(okno.uruchom_po_zamknieciu, okno._restart_argumenty)
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
                Baza(plik, haslo, urzadzenie.wczytaj_sekret(plik.parent)).zamknij()
                return True
            except (BledneHaslo, WymaganeUrzadzenie, ValueError):
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


def uruchom_jako_administrator(sciezka: Path) -> bool:
    """Uruchamia program zawsze z prośbą o zgodę administratora (UAC, polecenie „runas”)."""
    if sys.platform != "win32":
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(sciezka)))
    import ctypes
    wynik = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(sciezka), None, str(sciezka.parent), 1)
    return int(wynik) > 32  # >32 = uruchomiono; 5 = odmowa zgody administratora


def potwierdz_odinstalowanie() -> int:
    """Wywoływane przez deinstalator (Fakturnik.exe --odinstaluj). 0 = zgoda, 1 = odmowa.

    Gdy dane na tym komputerze są chronione hasłem, odinstalować można tylko po jego podaniu.
    Dane i kopie zostają na dysku także po odinstalowaniu."""
    from . import usluga
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Fakturnik")
    app.setOrganizationName("Fakturnik")
    zaladuj_czcionki()
    app.setStyle("Fusion")
    app.setStyleSheet(STYL)
    pliki = [d / usluga.PLIK_DANYCH for _, d in usluga.profile_z_danymi()]
    if sciezka_danych().exists() and sciezka_danych() not in pliki:
        pliki.append(sciezka_danych())
    # (katalog z weryfikatorem hasła, plik danych do sprawdzenia, sekret urządzenia)
    chronione = [(p.parent, p, urzadzenie.wczytaj_sekret(p.parent)) for p in pliki if Baza.wymaga_hasla(p)]
    # dane usunięte z profilu nie wyłączają hasła: liczą się też zaszyfrowane kopie usługi
    katalog_kopii_uslugi = usluga.katalog_kopii_chronionych()
    for katalog in (katalog_kopii_uslugi.iterdir() if katalog_kopii_uslugi.is_dir() else []):
        kopie = sorted(katalog.glob("fakturnik-*.db"))
        if kopie and Baza.wymaga_hasla(kopie[-1]):
            chronione.append((katalog, kopie[-1], None))

    def sprawdz(h: str) -> bool:
        return any(Baza.haslo_pasuje(katalog, h, sekret, plik) for katalog, plik, sekret in chronione)

    if chronione:
        okno = OknoHasla(sprawdz, "Odinstaluj Fakturnik",
                         opis="Podaj hasło Fakturnika, aby go odinstalować.\nDane i kopie zostaną na dysku.")
        return 0 if okno.exec() == QDialog.DialogCode.Accepted else 1
    odp = QMessageBox.question(None, "Odinstaluj Fakturnik", "Odinstalować Fakturnik?\n\nDane i kopie zostaną "
                               "na dysku, a program przestanie robić kopie i pilnować danych.")
    return 0 if odp == QMessageBox.StandardButton.Yes else 1


def _obsluga_bledow(log: Path) -> None:
    """Nieoczekiwany błąd nie zamyka programu po cichu: trafia do bledy.log, a użytkownik dostaje komunikat.
    Dane są zapisywane po każdej zmianie, więc błąd nie powoduje ich utraty."""
    import threading
    import traceback
    ostatni = [0.0]

    def obsluz(typ, wartosc, tb):
        if issubclass(typ, KeyboardInterrupt):
            return
        tekst = "".join(traceback.format_exception(typ, wartosc, tb))
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            if log.exists() and log.stat().st_size > 512 * 1024:
                os.replace(log, log.with_suffix(".old.log"))
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}  Fakturnik {WERSJA}\n{tekst}\n")
        except OSError:
            pass
        if QApplication.instance() and time.monotonic() - ostatni[0] > 10:
            ostatni[0] = time.monotonic()
            komunikat = (str(wartosc) if isinstance(wartosc, OSError) else "") or typ.__name__
            QMessageBox.warning(None, "Fakturnik", "Coś poszło nie tak, ale dane są bezpieczne (zapisywane na "
                                f"bieżąco).\n\n{komunikat}\n\nSzczegóły zapisano w pliku:\n{log}")

    sys.excepthook = obsluz
    threading.excepthook = lambda a: obsluz(a.exc_type, a.exc_value, a.exc_traceback)


def _zaloguj_konto(plik: Path, haslo: str, sekret: bytes | None, wynik: dict):
    """Logowanie asystentki przy starcie: True, tekst odmowy (np. poza godzinami) albo None (to nie jej hasło)."""
    konto = konta.zaloguj(plik.parent, haslo)
    if not konto:
        return None
    wpis, klucz = konto
    try:
        baza = Baza(plik, None, sekret, klucz_hasla=klucz)
    except (BledneHaslo, WymaganeUrzadzenie, ValueError):
        return None
    if not (dane_konta := baza.konto(wpis["id"])):
        baza.zamknij()
        return None
    if powod := godziny.odmowa(baza.ustawienia(), dane_konta["rola"]):
        baza.zamknij()
        return powod
    wynik["baza"] = baza
    wynik["uzytkownik"] = dane_konta
    return True


def _nowe_urzadzenie(plik: Path, haslo: str, dziennik: Dziennik, wynik: dict) -> bool:
    """Dane są powiązane z innym urządzeniem (nowy komputer, nowe konto Windows): potrzebny kod odzyskiwania.
    Po poprawnym kodzie i haśle to urządzenie zostaje zweryfikowane (klucz zapisany przez Windows)."""
    kod, ok = QInputDialog.getText(
        None, "Weryfikacja urządzenia",
        "Dane Fakturnika są powiązane z innym komputerem lub kontem Windows.\n\n"
        "Wpisz kod odzyskiwania (8 grup po 4 znaki), aby otworzyć je na tym urządzeniu:")
    if not ok:
        return False
    sekret = urzadzenie.sekret_z_kodu(kod)
    try:
        if sekret is None:
            raise WymaganeUrzadzenie
        wynik["baza"] = Baza(plik, haslo, sekret)
    except WymaganeUrzadzenie:
        dziennik.zapisz("weryfikacja urządzenia: NIEUDANA (zły kod odzyskiwania)")
        QMessageBox.warning(None, "Weryfikacja urządzenia", "Nieprawidłowy kod odzyskiwania.")
        return False
    except BledneHaslo:
        return False
    try:
        urzadzenie.zapisz_sekret(plik.parent, sekret)
    except (OSError, urzadzenie.BrakDPAPI):
        pass  # bez zapamiętania: przy następnym uruchomieniu znów zapyta o kod
    dziennik.zapisz(f"weryfikacja urządzenia: nowe urządzenie {urzadzenie.nazwa_urzadzenia()} (kod odzyskiwania)")
    return True


def katalog_pobranych() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation) or Path.home())


def znacznik_szyfrowania(ustaw: bool | None = None) -> bool:
    """Zapamiętane w rejestrze użytkownika (HKCU), że dane są szyfrowane: wtedy plik bez szyfrowania
    w miejscu danych oznacza podmianę z zewnątrz i nie zostanie otwarty."""
    ustawienia = QSettings("Fakturnik", "Fakturnik")
    if ustaw is not None:
        ustawienia.setValue("dane_zaszyfrowane", int(ustaw))
    return str(ustawienia.value("dane_zaszyfrowane", 0)) == "1"


def _zaproponuj_kopie(plik: Path, haslo: str | None, powod: str, dziennik: Dziennik,
                      sekret: bytes | None = None) -> bool:
    """Szuka najnowszej kopii automatycznej, która się otwiera (tym hasłem), i proponuje jej przywrócenie.

    Sprawdza tylko 3 najnowsze kopie: każda próba z hasłem to kosztowne wyliczenie klucza.
    """
    from . import usluga
    chronione = usluga.katalog_kopii_chronionych() / (os.environ.get("USERNAME") or os.environ.get("USER") or "?")
    kopie = sorted(lista_kopii() + lista_kopii(chronione), key=lambda k: k.stat().st_mtime, reverse=True)
    for kopia in kopie[:3]:
        if not Baza.da_sie_otworzyc(kopia, haslo, sekret):
            continue
        kiedy = datetime.fromtimestamp(kopia.stat().st_mtime)
        odp = QMessageBox.question(
            None, "Fakturnik", f"{powod}\n\nZnaleziono kopię automatyczną z {kiedy:%d.%m.%Y, %H:%M}. "
            "Przywrócić ją?\n\nObecny plik nie zostanie usunięty (zostanie obok z dopiskiem „uszkodzony”). "
            "Dokumenty wystawione po utworzeniu kopii trzeba będzie wpisać ponownie.")
        if odp != QMessageBox.StandardButton.Yes:
            return False
        odtworz_z_kopii(plik, kopia)
        dziennik.zapisz(f"odtworzenie danych z kopii automatycznej z {kiedy:%Y-%m-%d %H:%M}")
        return True
    return False


def _otworz(app: QApplication, plik: Path, dziennik: Dziennik, jedna: JednaKopia,
            polecenie: dict) -> tuple[int, OknoGlowne | None]:
    w_tle = polecenie.get("akcja") == "w_tle" and QSystemTrayIcon.isSystemTrayAvailable()
    if w_tle and Baza.wymaga_hasla(plik):
        polecenie = _czekaj_w_zasobniku(app, plik, jedna, polecenie)
        if polecenie is None:
            return 0, None
        w_tle = False
    wynik: dict = {}
    if Baza.wymaga_hasla(plik):
        sekret = urzadzenie.wczytaj_sekret(plik.parent)

        def sprawdz(haslo: str):
            try:
                wynik["baza"] = Baza(plik, haslo, sekret)
                return True
            except WymaganeUrzadzenie:
                return _nowe_urzadzenie(plik, haslo, dziennik, wynik)
            except BledneHaslo:
                konto = _zaloguj_konto(plik, haslo, sekret, wynik)
                if konto is not None:
                    return konto
                powod = ("To hasło nie otwiera aktualnego pliku danych, ale otwiera kopię automatyczną. "
                         "Jeśli zmieniano hasło po dacie tej kopii, wpisz nowe hasło. Jeśli nie, plik danych "
                         "mógł zostać uszkodzony.")
            except ValueError:
                powod = "Plik danych jest uszkodzony."
            except (NowszaBaza, PlikZajety) as e:
                wynik["blad"] = e  # okno hasła się zamknie, a komunikat pokaże uruchom()
                return True
            if _zaproponuj_kopie(plik, haslo, powod, dziennik, sekret):
                try:
                    wynik["baza"] = Baza(plik, haslo, sekret)
                    return True
                except (BledneHaslo, ValueError):
                    pass
            return False

        def zgoda() -> bool:
            if OknoHasla(lambda h: Baza.da_sie_otworzyc(plik, h, sekret), "Zgoda właściciela", dziennik=dziennik,
                         cel="zgoda na pracę po godzinach",
                         opis="Praca asystentek po godzinach do końca dnia.\nPodaj hasło właściciela.").exec() \
                    != QDialog.DialogCode.Accepted:
                return False
            godziny.udziel_zgody()
            dziennik.zapisz("zgoda właściciela na pracę po godzinach (do końca dnia)")
            return True

        if OknoHasla(sprawdz, dziennik=dziennik, opis="Podaj swoje hasło, aby otworzyć program.",
                     ekran_blokady={"gabinet": "", "godziny": ""},
                     zgoda=zgoda if konta.wczytaj(plik.parent) else None).exec() != QDialog.DialogCode.Accepted:
            return 0, None
        if "blad" in wynik:
            raise wynik["blad"]
        baza = wynik["baza"]
    else:
        if plik.exists() and znacznik_szyfrowania():
            dziennik.zapisz("STRAŻNIK: plik danych bez szyfrowania zamiast zaszyfrowanego (podmiana)")
            haslo, ok = QInputDialog.getText(
                None, "Fakturnik", "Plik danych został podmieniony na niezaszyfrowany (zmiana z zewnątrz).\n"
                "Nie zostanie otwarty. Podaj hasło, aby przywrócić ostatnią zaszyfrowaną kopię:",
                QLineEdit.EchoMode.Password)
            if not ok or not _zaproponuj_kopie(plik, haslo, "Podmieniony plik danych.", dziennik):
                QMessageBox.critical(None, "Fakturnik", "Nie otwarto podmienionego pliku danych:\n"
                                     f"{plik}\n\nPrzywróć zaszyfrowaną kopię z katalogu:\n{katalog_kopii()}")
                return 1, None
            return _otworz(app, plik, dziennik, jedna, polecenie)
        try:
            baza = Baza(plik)
        except ValueError:
            if not _zaproponuj_kopie(plik, None, "Plik danych jest uszkodzony lub zmieniony z zewnątrz.", dziennik):
                QMessageBox.critical(None, "Fakturnik", f"Plik danych jest uszkodzony lub zmieniony z zewnątrz:\n"
                                     f"{plik}\n\nPrzywróć go z kopii (Ustawienia → Przywróć) albo z katalogu:\n"
                                     f"{katalog_kopii()}")
                return 1, None
            baza = Baza(plik)
        dziennik.zapisz("uruchomienie programu (bez hasła)")
    try:
        kopia_automatyczna(plik)
        baza.kopia_plikow(katalog_kopii() / "pliki")
    except OSError:
        pass

    if baza.ma_haslo:
        znacznik_szyfrowania(True)
    okno = OknoGlowne(baza, dziennik, wynik.get("uzytkownik"))
    jedna.polecenie.connect(okno.obsluz_polecenie)
    if w_tle and okno._w_tle_dostepne() and baza.ustawienia()["skonfigurowano"] == "1":
        okno._ukryty = baza.ma_haslo
    else:
        okno.show()
        if polecenie.get("akcja") == "dodaj":
            QTimer.singleShot(300, lambda: okno.obsluz_polecenie(polecenie))
    return app.exec(), okno
