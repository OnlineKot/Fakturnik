"""Okno główne programu Fakturnik."""

import base64
import subprocess
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import (
    QBuffer, QByteArray, QDate, QEvent, QIODevice, QObject, QPoint, QRect, QSize, QStandardPaths, Qt, QThread,
    QTimer, QUrl, Signal,
)
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLayout, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import aktualizacje, druk
from .baza import Baza, Dokument, NowszaBaza, PlikZajety, Pozycja
from .ikony import ikona, pixmapa
from .ochrona import Dziennik, katalog_kopii, kopia_automatyczna
from .szyfrowanie import BledneHaslo
from .wersja import WERSJA

MIN_DLUGOSC_HASLA = 8
BLOKADA_PO_MINUTACH = 10
ZASOBY = Path(__file__).parent / "zasoby"

# ---------------------------------------------------------------- wygląd

AKCENT = "#1e6b7b"          # morski z logo gabinetu
AKCENT_CIEMNY = "#175866"
AKCENT_TLO = "#e3eef0"
TEKST = "#1d1d1f"
TEKST_2 = "#6e6e73"
LINIA = "#e5e5ea"
TLO = "#f5f5f7"
CZERWONY = "#c4314b"
ZIELONY = "#2f7d4f"

STYL = f"""
* {{ font-family: "Inter"; font-size: 13px; color: {TEKST}; }}
QMainWindow, QWidget#tresc, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {TLO}; }}
QDialog {{ background: {TLO}; }}

QFrame#menu {{ background: #ececef; border-right: 1px solid #dcdce0; }}
QFrame#menu QPushButton {{
    background: transparent; border: none; border-radius: 7px; text-align: left;
    padding: 7px 10px; margin: 1px 10px; font-weight: 500; color: #3a3a3c;
}}
QFrame#menu QPushButton:hover {{ background: #e1e1e5; }}
QFrame#menu QPushButton:checked {{ background: {AKCENT_TLO}; color: {AKCENT}; font-weight: 600; }}
QLabel#nazwa_programu {{ font-size: 15px; font-weight: 600; }}
QLabel#wersja {{ font-size: 11px; color: {TEKST_2}; }}

QLabel#tytul {{ font-size: 22px; font-weight: 600; letter-spacing: -0.3px; }}
QLabel#podtytul {{ color: {TEKST_2}; }}
QLabel#sekcja {{ font-size: 11px; font-weight: 600; color: {TEKST_2}; letter-spacing: 0.4px; padding: 0 2px; }}
QLabel#drobny {{ font-size: 12px; color: {TEKST_2}; }}
QLabel#etykieta {{ font-size: 12px; color: {TEKST_2}; }}
QFrame#karta {{ background: white; border: 1px solid {LINIA}; border-radius: 12px; }}
QFrame#karta QLabel {{ background: transparent; }}
QFrame#separator {{ background: {LINIA}; max-height: 1px; border: none; }}

QLineEdit, QPlainTextEdit, QComboBox, QDateEdit {{
    background: white; border: 1px solid #d2d2d7; border-radius: 7px; padding: 6px 9px;
    selection-background-color: {AKCENT_TLO}; selection-color: {TEKST};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 1px solid {AKCENT}; }}
QLineEdit, QComboBox, QDateEdit {{ min-height: 20px; }}
QLineEdit#numer {{ font-size: 15px; font-weight: 600; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {LINIA}; selection-background-color: {AKCENT_TLO}; }}

QPushButton {{
    background: white; border: 1px solid #d2d2d7; border-radius: 7px; padding: 6px 12px; font-weight: 500;
}}
QPushButton:hover {{ background: #f7f7f9; border-color: #c4c4ca; }}
QPushButton:pressed {{ background: #ededf0; }}
QPushButton:disabled {{ color: #b0b0b5; }}
QPushButton#glowny {{ background: {AKCENT}; border: 1px solid {AKCENT}; color: white; font-weight: 600; padding: 8px 18px; }}
QPushButton#glowny:hover {{ background: {AKCENT_CIEMNY}; border-color: {AKCENT_CIEMNY}; }}
QPushButton#glowny:disabled {{ background: #a9c4ca; border-color: #a9c4ca; }}
QPushButton#plaski {{ background: transparent; border: none; color: {AKCENT}; padding: 4px 6px; }}
QPushButton#plaski:hover {{ background: {AKCENT_TLO}; }}
QPushButton#chip {{ background: #f2f2f4; border: none; border-radius: 6px; padding: 5px 10px; font-weight: 500; }}
QPushButton#chip:hover {{ background: {AKCENT_TLO}; color: {AKCENT}; }}
QPushButton#pacjent {{ background: transparent; border: 1px solid {LINIA}; border-radius: 6px;
    padding: 3px 11px; font-weight: 400; color: #3a3a3c; }}
QPushButton#pacjent:hover {{ border-color: {AKCENT}; color: {AKCENT}; }}
QPushButton#niebezpieczny {{ color: {CZERWONY}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid #c4c4ca; background: white; }}
QCheckBox::indicator:checked {{ background: {AKCENT}; border-color: {AKCENT}; image: url("{(ZASOBY / "zaznaczone.svg").as_posix()}"); }}

QTableWidget {{ background: white; border: none; gridline-color: transparent;
    selection-background-color: {AKCENT_TLO}; selection-color: {TEKST}; outline: none; }}
QTableWidget::item {{ padding: 0 8px; border-bottom: 1px solid #f0f0f2; }}
QHeaderView::section {{ background: white; border: none; border-bottom: 1px solid {LINIA};
    padding: 8px; font-size: 11px; font-weight: 600; color: {TEKST_2}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #c7c7cc; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QFrame#pasek_aktualizacji {{ background: {AKCENT_TLO}; border: none; border-bottom: 1px solid #cfe0e3; }}
QStatusBar {{ background: {TLO}; color: {TEKST_2}; border-top: 1px solid {LINIA}; }}
QStatusBar QLabel {{ color: {TEKST_2}; }}
QToolTip {{ background: white; border: 1px solid {LINIA}; padding: 4px; }}
"""


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
        self._uloz(prostokat, tylko_licz=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        rozmiar = QSize()
        for e in self.elementy:
            rozmiar = rozmiar.expandedTo(e.minimumSize())
        m = self.contentsMargins()
        return rozmiar + QSize(m.left() + m.right(), m.top() + m.bottom())

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


def karta() -> tuple[QFrame, QVBoxLayout]:
    k = QFrame(objectName="karta")
    u = QVBoxLayout(k)
    u.setContentsMargins(18, 16, 18, 16)
    u.setSpacing(10)
    return k, u


def sekcja(tekst: str) -> QLabel:
    return QLabel(tekst.upper(), objectName="sekcja")


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
        self.setFixedWidth(380)
        u = QVBoxLayout(self)
        u.setContentsMargins(28, 26, 28, 22)
        u.setSpacing(10)
        znak = QLabel()
        znak.setPixmap(pixmapa("klodka", AKCENT, 30))
        u.addWidget(znak, alignment=Qt.AlignmentFlag.AlignHCenter)
        naglowek = QLabel(tytul, alignment=Qt.AlignmentFlag.AlignHCenter)
        naglowek.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(naglowek)
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

    def sprobuj(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = self.sprawdz(self.pole.text())
        finally:
            QApplication.restoreOverrideCursor()
        if self.dziennik:
            self.dziennik.zapisz(f"{self.cel}: {'udane' if ok else 'NIEUDANE (złe hasło)'}")
        if ok:
            self.accept()
            return
        self.proby += 1
        self.pole.clear()
        # po kolejnych błędach coraz dłuższa przerwa, żeby utrudnić zgadywanie
        przerwa = min(2 ** self.proby, 60) if self.proby >= 3 else 0
        self.blad.setText("Nieprawidłowe hasło." + (f" Spróbuj ponownie za {przerwa} s." if przerwa else ""))
        if przerwa:
            self.setEnabled(False)
            QTimer.singleShot(przerwa * 1000, lambda: (self.setEnabled(True), self.pole.setFocus()))


class OknoNowegoHasla(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hasło")
        self.setFixedWidth(420)
        u = QVBoxLayout(self)
        u.setContentsMargins(24, 22, 24, 20)
        u.setSpacing(10)
        t = QLabel("Ustaw hasło")
        t.setStyleSheet("font-size: 16px; font-weight: 600;")
        u.addWidget(t)
        info = QLabel("Hasło szyfruje wszystkie dane (AES-256, klucz z hasła przez PBKDF2-SHA256). "
                      f"Minimum {MIN_DLUGOSC_HASLA} znaków. Zapomnianego hasła nie da się odzyskać.",
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

    def odswiez(self):
        pass


class StronaNowy(Strona):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno)
        u = self.uklad
        u.addLayout(naglowek_strony("Nowy rachunek", "Numer nadaje się sam: kolejny w danym miesiącu."))
        u.addSpacing(10)

        # --- dokument i nabywca w jednej karcie
        k, ku = karta()
        siatka = QGridLayout()
        siatka.setHorizontalSpacing(14)
        siatka.setVerticalSpacing(12)
        self.numer = QLineEdit(objectName="numer")
        self.numer.setFixedWidth(180)
        self.data_wyst = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.data_uslugi = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.platnosc = QComboBox()
        self.platnosc.addItems(["gotówka", "karta", "przelew"])
        self.data_wyst.dateChanged.connect(self.odswiez_numer)
        for kol, (etykieta, w) in enumerate([("Numer", self.numer), ("Data wystawienia", self.data_wyst),
                                             ("Data usługi", self.data_uslugi), ("Płatność", self.platnosc)]):
            siatka.addLayout(pole(etykieta, w), 0, kol)
        siatka.setColumnStretch(4, 1)
        ku.addLayout(siatka)
        ku.addWidget(separator())

        self.nabywca = QLineEdit(placeholderText="Imię i nazwisko lub nazwa firmy")
        self.nabywca_id = QLineEdit(placeholderText="Opcjonalnie")
        self.nabywca_adres = QLineEdit(placeholderText="Opcjonalnie, np. ul. Długa 1, 47-400 Racibórz")
        nab = QGridLayout()
        nab.setHorizontalSpacing(14)
        nab.setVerticalSpacing(12)
        nab.addLayout(pole("Pacjent", self.nabywca), 0, 0)
        nab.addLayout(pole("PESEL lub NIP", self.nabywca_id), 0, 1)
        nab.addLayout(pole("Adres", self.nabywca_adres), 1, 0, 1, 2)
        nab.setColumnStretch(0, 3)
        nab.setColumnStretch(1, 2)
        ku.addLayout(nab)
        self.ostatni = QHBoxLayout()
        self.ostatni.setSpacing(6)
        ku.addLayout(self.ostatni)
        u.addWidget(k)
        u.addSpacing(8)

        # --- usługi
        u.addWidget(sekcja("Usługi"))
        k, ku = karta()
        ku.setContentsMargins(0, 12, 0, 12)
        self.przyciski_uslug = UkladPlynny()
        self.przyciski_uslug.setContentsMargins(16, 0, 16, 4)
        ku.addLayout(self.przyciski_uslug)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["NAZWA USŁUGI", "ILOŚĆ", "CENA (ZŁ)", "WARTOŚĆ (ZŁ)"])
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
        u.addWidget(k, 1)
        u.addSpacing(10)

        # --- akcje
        dol = QHBoxLayout()
        self.kopia = QCheckBox("Drukuj też kopię")
        dol.addWidget(self.kopia)
        dol.addStretch()
        dol.addWidget(przycisk("Podgląd", "podglad", akcja=self.podglad))
        dol.addWidget(przycisk("Zapisz PDF", "pdf", akcja=self.zapisz_pdf))
        self.drukuj_btn = przycisk("Drukuj", "drukarka", "glowny", self.drukuj)
        self.drukuj_btn.setToolTip("F5 lub Ctrl+P")
        dol.addWidget(self.drukuj_btn)
        u.addLayout(dol)

        QShortcut(QKeySequence("F5"), self, self.drukuj)
        QShortcut(QKeySequence("Ctrl+P"), self, self.drukuj)

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

        wyczysc_uklad(self.ostatni)
        ostatni = self.okno.baza.ostatni_nabywcy()
        if ostatni:
            self.ostatni.addWidget(QLabel("Ostatnio:", objectName="drobny"))
            for d in ostatni:
                b = QPushButton(d.nabywca, objectName="pacjent", cursor=Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _=False, n=d.nabywca: (self.nabywca.setText(n), self.uzupelnij_nabywce(n)))
                self.ostatni.addWidget(b)
        self.ostatni.addStretch()

        podpowiedzi = QCompleter(sorted(self.okno.baza.nabywcy()))
        podpowiedzi.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        podpowiedzi.setFilterMode(Qt.MatchFlag.MatchContains)
        podpowiedzi.activated.connect(self.uzupelnij_nabywce)
        self.nabywca.setCompleter(podpowiedzi)
        self.odswiez_numer()

    def odswiez_numer(self):
        self.numer.setText(self.okno.baza.nastepny_numer(self.data_wyst.date().toPython()))

    def uzupelnij_nabywce(self, nazwa: str):
        dok = self.okno.baza.nabywcy().get(nazwa)
        if dok:
            self.nabywca_adres.setText(dok.nabywca_adres.replace("\n", ", "))
            self.nabywca_id.setText(dok.nabywca_id)

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
            pozycje=pozycje)

    def wyczysc(self):
        for p in (self.nabywca, self.nabywca_id, self.nabywca_adres):
            p.clear()
        self.tabela.setRowCount(0)
        self.dodaj_pozycje()
        self.data_wyst.setDate(QDate.currentDate())
        self.data_uslugi.setDate(QDate.currentDate())
        self.platnosc.setCurrentIndex(0)
        self.odswiez()
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
        self.okno.komunikat(f"Wydrukowano: {u['tytul'].lower()} nr {dok.numer}")
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


class StronaHistoria(Strona):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno)
        u = self.uklad
        u.addLayout(naglowek_strony("Historia", "Wszystkie wystawione dokumenty."))
        u.addSpacing(10)

        pasek = QHBoxLayout()
        self.szukaj = QLineEdit(placeholderText="Szukaj po numerze lub nazwisku")
        self.szukaj.addAction(ikona("szukaj"), QLineEdit.ActionPosition.LeadingPosition)
        self.szukaj.setClearButtonEnabled(True)
        self.szukaj.textChanged.connect(self.odswiez)
        pasek.addWidget(self.szukaj, 1)
        pasek.addSpacing(8)
        self.akcje = [przycisk("Drukuj ponownie", "drukarka", akcja=self.drukuj),
                      przycisk("Podgląd", "podglad", akcja=self.podglad),
                      przycisk("Użyj jako wzór", "kopiuj", akcja=self.wzor)]
        for b in self.akcje:
            pasek.addWidget(b)
        pasek.addWidget(przycisk("Eksport do Excela", "arkusz", akcja=self.eksport))
        u.addLayout(pasek)
        u.addSpacing(6)

        k, ku = karta()
        ku.setContentsMargins(0, 4, 0, 4)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["NUMER", "DATA", "PACJENT", "KWOTA"])
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tabela.setColumnWidth(0, 130)
        self.tabela.setColumnWidth(1, 120)
        self.tabela.setColumnWidth(3, 130)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.setShowGrid(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.doubleClicked.connect(self.podglad)
        self.tabela.itemSelectionChanged.connect(self._stan_akcji)
        ku.addWidget(self.tabela)
        u.addWidget(k, 1)
        self.podsumowanie = QLabel(objectName="drobny")
        u.addWidget(self.podsumowanie)
        self.docs: list[Dokument] = []

    def _stan_akcji(self):
        for b in self.akcje:
            b.setEnabled(self.wybrany() is not None)

    def odswiez(self):
        self.docs = self.okno.baza.dokumenty(self.szukaj.text())
        self.tabela.setRowCount(len(self.docs))
        for r, d in enumerate(self.docs):
            for kol, tekst in enumerate([d.numer, druk.data_pl(d.data_wystawienia), d.nabywca, f"{druk.zl(d.suma)} zł"]):
                item = QTableWidgetItem(tekst)
                if kol == 0:
                    item.setFont(QFont("Inter", -1, QFont.Weight.Medium))
                self.tabela.setItem(r, kol, item)
        self.tabela.clearSelection()
        self._stan_akcji()
        miesiac = date.today().isoformat()[:7]
        w_miesiacu = [d for d in self.docs if d.data_wystawienia.startswith(miesiac)]
        self.podsumowanie.setText(f"W tym miesiącu: {len(w_miesiacu)} • {druk.zl(sum(d.suma for d in w_miesiacu))} zł")

    def eksport(self):
        sciezka, _ = QFileDialog.getSaveFileName(
            self, "Eksport do Excela", str(Path.home() / f"rachunki-{date.today().isoformat()}.csv"), "CSV (*.csv)")
        if sciezka:
            n = self.okno.baza.eksport_csv(sciezka, self.docs)
            self.okno.dziennik.zapisz(f"eksport CSV ({n} dokumentów)")
            self.okno.komunikat(f"Wyeksportowano dokumenty ({n}): {sciezka}")

    def wybrany(self) -> Dokument | None:
        wiersze = self.tabela.selectionModel().selectedRows() if self.tabela.selectionModel() else []
        r = wiersze[0].row() if wiersze else -1
        return self.docs[r] if 0 <= r < len(self.docs) else None

    def drukuj(self):
        if d := self.wybrany():
            u = self.okno.baza.ustawienia()
            druk.drukuj(druk.html_dokumentu(d, u), druk.przygotuj_drukarke(u))
            self.okno.komunikat(f"Wydrukowano ponownie nr {d.numer}")

    def podglad(self, *_):
        if d := self.wybrany():
            self.okno.podglad(d)

    def wzor(self):
        if d := self.wybrany():
            s = self.okno.strona_nowy
            s.nabywca.setText(d.nabywca)
            s.nabywca_adres.setText(d.nabywca_adres.replace("\n", ", "))
            s.nabywca_id.setText(d.nabywca_id)
            s.platnosc.setCurrentText(d.platnosc)
            s.tabela.setRowCount(0)
            for p in d.pozycje:
                s.dodaj_pozycje(p.nazwa, p.cena, p.ilosc)
            self.okno.przejdz(0, odswiez=False)


class StronaUstawienia(Strona):
    POLA = [("nazwa", "Nazwa"), ("nip", "NIP"), ("regon", "REGON"), ("miejsce", "Miejsce wystawienia"),
            ("konto", "Nr konta do przelewów"), ("format_numeru", "Format numeru")]

    def __init__(self, okno: "OknoGlowne"):
        super().__init__(okno, przewijana=True)
        u = self.uklad
        gora = QWidget()
        gora.setMaximumWidth(760)
        naglowek = QHBoxLayout(gora)
        naglowek.setContentsMargins(0, 0, 0, 0)
        naglowek.addLayout(naglowek_strony("Ustawienia", "Dane gabinetu, wydruk i bezpieczeństwo."))
        naglowek.addStretch()
        naglowek.addWidget(przycisk("Zapisz zmiany", styl="glowny", akcja=self.zapisz),
                           alignment=Qt.AlignmentFlag.AlignBottom)
        u.addWidget(gora)
        u.addSpacing(10)

        kolumna = QWidget()
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
        self.pola["format_numeru"].setToolTip("{n} = kolejny numer, {mm} = miesiąc, {rrrr} = rok")
        lewa.addWidget(k)
        lewa.addSpacing(10)

        # --- dokument
        lewa.addWidget(sekcja("Dokument"))
        k, ku = karta()
        f = self._formularz(ku)
        self.pola["tytul"] = QComboBox()
        self.pola["tytul"].addItems(["Rachunek", "Faktura"])
        f.addRow("Tytuł", self.pola["tytul"])
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
        przyc.addWidget(przycisk("Wybierz z pliku…", "obraz", "plaski", self.wybierz_logo))
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
        prawa.addWidget(sekcja("Szybkie usługi"))
        k, ku = karta()
        ku.addWidget(QLabel("Jedna usługa w wierszu, w formacie: nazwa;cena", objectName="drobny"))
        self.pola["uslugi"] = QPlainTextEdit()
        self.pola["uslugi"].setMinimumHeight(110)
        ku.addWidget(self.pola["uslugi"])
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
        ku.addWidget(self.okno_drukarki)
        ku.addWidget(self.kopia)
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
        rzad.addWidget(przycisk("Kopia zapasowa…", "archiwum", akcja=self.kopia_zapasowa))
        rzad.addWidget(przycisk("Przywróć…", "przywroc", akcja=self.przywroc))
        rzad.addWidget(przycisk("Eksport odszyfrowany…", "pobierz", akcja=self.eksport_odszyfrowany))
        rzad.addStretch()
        ku.addLayout(rzad)
        ku.addWidget(QLabel(f"Kopie automatyczne: {katalog_kopii()}", objectName="drobny", wordWrap=True))
        prawa.addWidget(k)
        prawa.addSpacing(10)

        # --- aktualizacje
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

    def odswiez(self):
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
        self.kopia.setChecked(u["kopia"] == "1")
        self.auto_aktualizacje.setChecked(u["auto_aktualizacje"] == "1")
        self.ustaw_logo(u["logo"])
        ma = self.okno.baza.ma_haslo
        self.ikona_stanu.setPixmap(pixmapa("tarcza" if ma else "uwaga", ZIELONY if ma else CZERWONY, 18))
        self.stan_hasla.setText(
            f"Dane są zaszyfrowane (AES-256). Program blokuje się po {BLOKADA_PO_MINUTACH} min bezczynności."
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
        if "{n}" not in wartosci["format_numeru"]:
            QMessageBox.warning(self, "Format numeru", "Format numeru musi zawierać {n}.")
            return
        wartosci["logo"] = self.logo
        wartosci["okno_drukarki"] = "1" if self.okno_drukarki.isChecked() else "0"
        wartosci["kopia"] = "1" if self.kopia.isChecked() else "0"
        wartosci["auto_aktualizacje"] = "1" if self.auto_aktualizacje.isChecked() else "0"
        self.okno.baza.zapisz_ustawienia(wartosci)
        self.okno.komunikat("Zapisano ustawienia")
        self.okno.przejdz(0)

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
        tabela.setHorizontalHeaderLabels(["CZAS", "ZDARZENIE"])
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
        sciezka, _ = QFileDialog.getOpenFileName(self, "Przywróć z kopii", str(katalog_kopii()),
                                                 "Kopia Fakturnika (*.db)")
        if not sciezka:
            return
        if QMessageBox.warning(self, "Przywróć z kopii",
                               "Obecne dane zostaną zastąpione danymi z kopii. Kontynuować?",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        haslo = None
        if Baza.wymaga_hasla(sciezka):
            haslo, ok = QInputDialog.getText(self, "Hasło kopii", "Hasło, którym zaszyfrowano kopię:",
                                             QLineEdit.EchoMode.Password)
            if not ok:
                return
        # na wszelki wypadek: kopia obecnego stanu, zanim zostanie zastąpiony
        kopia_automatyczna(self.okno.baza.sciezka, nazwa=f"przed-przywroceniem-{date.today().isoformat()}.db")
        try:
            self.okno.baza.przywroc(sciezka, haslo)
        except (BledneHaslo, ValueError, NowszaBaza) as e:
            self.okno.dziennik.zapisz("przywrócenie kopii: NIEUDANE")
            QMessageBox.critical(self, "Nie udało się przywrócić", str(e))
            return
        self.okno.dziennik.zapisz(f"przywrócenie danych z kopii {Path(sciezka).name}")
        self.okno.komunikat("Przywrócono dane z kopii")
        self.okno.przejdz(1)

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
        nazwa = f"fakturnik-kopia-{date.today().isoformat()}.db"
        sciezka, _ = QFileDialog.getSaveFileName(self, "Kopia zapasowa", str(Path.home() / nazwa),
                                                 "Kopia Fakturnika (*.db)")
        if sciezka:
            self.okno.baza.kopia_zapasowa(sciezka)
            self.okno.dziennik.zapisz("ręczna kopia zapasowa")
            self.okno.komunikat("Zapisano kopię zapasową" +
                                (" (zaszyfrowaną tym samym hasłem)" if self.okno.baza.ma_haslo else ""))


# ---------------------------------------------------------------- okno główne

class OknoGlowne(QMainWindow):
    def __init__(self, baza: Baza, dziennik: Dziennik):
        super().__init__()
        self.baza = baza
        self.dziennik = dziennik
        self.uruchom_po_zamknieciu: Path | None = None
        self._watki: list[Watek] = []
        self.setWindowTitle("Fakturnik")
        self.resize(1180, 800)
        self.setMinimumSize(980, 680)

        tlo = QWidget()
        uklad = QHBoxLayout(tlo)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        # --- menu boczne
        menu = QFrame(objectName="menu")
        menu.setFixedWidth(220)
        m = QVBoxLayout(menu)
        m.setContentsMargins(0, 20, 0, 14)
        m.setSpacing(2)
        marka = QHBoxLayout()
        marka.setContentsMargins(20, 0, 16, 18)
        marka.setSpacing(10)
        znak = QLabel()
        znak.setPixmap(QPixmap(str(ZASOBY / "ikona.png")).scaled(
            30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        marka.addWidget(znak)
        opis = QVBoxLayout()
        opis.setSpacing(0)
        opis.addWidget(QLabel("Fakturnik", objectName="nazwa_programu"))
        opis.addWidget(QLabel(f"wersja {WERSJA}", objectName="wersja"))
        marka.addLayout(opis)
        marka.addStretch()
        m.addLayout(marka)

        self.grupa = QButtonGroup(self)
        for i, (nazwa, ik) in enumerate([("Nowy rachunek", "nowy"), ("Historia", "historia"),
                                         ("Ustawienia", "ustawienia")]):
            b = QPushButton(f"  {nazwa}", checkable=True, cursor=Qt.CursorShape.PointingHandCursor)
            b.setIcon(ikona(ik, "#5b5b60", aktywny=AKCENT))
            b.clicked.connect(lambda _=False, i=i: self.przejdz(i))
            self.grupa.addButton(b, i)
            m.addWidget(b)
        m.addStretch()
        self.btn_blokuj = QPushButton("  Zablokuj", cursor=Qt.CursorShape.PointingHandCursor)
        self.btn_blokuj.setIcon(ikona("klodka", "#5b5b60"))
        self.btn_blokuj.clicked.connect(self.zablokuj)
        m.addWidget(self.btn_blokuj)
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
        self.strona_nowy = StronaNowy(self)
        self.strona_historia = StronaHistoria(self)
        self.strona_ustawienia = StronaUstawienia(self)
        for s in (self.strona_nowy, self.strona_historia, self.strona_ustawienia):
            self.strony.addWidget(s)
        prawa.addWidget(self.strony, 1)
        uklad.addLayout(prawa, 1)
        self.setCentralWidget(tlo)
        self.statusBar().setSizeGripEnabled(False)

        self.strona_nowy.wyczysc()
        self.przejdz(0)

        # automatyczna blokada po bezczynności (tylko gdy jest hasło)
        self.timer = QTimer(self, interval=BLOKADA_PO_MINUTACH * 60 * 1000, singleShot=True)
        self.timer.timeout.connect(self.zablokuj)
        self.straznik = StraznikBezczynnosci(self.timer)
        QApplication.instance().installEventFilter(self.straznik)
        self.timer.start()

        self.wydanie: aktualizacje.Wydanie | None = None
        if aktualizacje.czy_spakowany() and self.baza.ustawienia()["auto_aktualizacje"] == "1":
            QTimer.singleShot(2500, lambda: self.sprawdz_aktualizacje(cicho=True))
        if not self.baza.ustawienia()["nip"]:
            QTimer.singleShot(300, self.pierwsze_uruchomienie)

    def przejdz(self, i: int, odswiez: bool = True):
        self.grupa.button(i).setChecked(True)
        self.strony.setCurrentIndex(i)
        if odswiez:
            self.strony.currentWidget().odswiez()
        self.btn_blokuj.setVisible(self.baza.ma_haslo)

    def komunikat(self, tekst: str):
        self.statusBar().showMessage(tekst, 6000)

    def podglad(self, dok: Dokument, z_kopia=False):
        u = self.baza.ustawienia()
        dialog = QPrintPreviewDialog(druk.przygotuj_drukarke(u), self)
        dialog.setWindowTitle(f"Podgląd: {dok.numer}")
        dialog.paintRequested.connect(lambda p: druk.drukuj(druk.html_dokumentu(dok, u, z_kopia), p))
        dialog.resize(900, 1000)
        dialog.exec()

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
        self.close()

    # ---- blokada i zamykanie
    def zablokuj(self):
        if not self.baza.ma_haslo or not self.isVisible():
            self.timer.start()
            return
        self.hide()
        self.dziennik.zapisz("blokada programu")
        okno = OknoHasla(self.baza.sprawdz_haslo, "Fakturnik jest zablokowany", dziennik=self.dziennik,
                         cel="odblokowanie", opis="Podaj hasło, aby wrócić do pracy.")
        if okno.exec() == QDialog.DialogCode.Accepted:
            self.show()
            self.timer.start()
        else:
            self.close()
            QApplication.quit()

    def closeEvent(self, event):
        self.dziennik.zapisz("zamknięcie programu")
        self.baza.zamknij()
        try:
            kopia_automatyczna(self.baza.sciezka)
        except OSError:
            pass
        event.accept()

    def pierwsze_uruchomienie(self):
        QMessageBox.information(
            self, "Witaj w Fakturniku",
            "Uzupełnij dane gabinetu (przede wszystkim NIP) i ceny usług.\n\n"
            "Ustaw też hasło w sekcji Bezpieczeństwo: dane pacjentów będą wtedy zaszyfrowane.")
        self.przejdz(2)


def uruchom() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Fakturnik")
    app.setOrganizationName("Fakturnik")
    app.setWindowIcon(QIcon(str(ZASOBY / "ikona.png")))
    zaladuj_czcionki()
    app.setStyle("Fusion")
    czcionka = QFont("Inter")
    czcionka.setPixelSize(13)
    czcionka.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(czcionka)
    app.setStyleSheet(STYL)
    aktualizacje.posprzataj()

    plik = sciezka_danych()
    dziennik = Dziennik(plik.parent / "dziennik.log")
    try:
        kod, okno = _otworz(app, plik, dziennik)
    except PlikZajety as e:
        QMessageBox.warning(None, "Fakturnik", str(e))
        return 1
    except NowszaBaza as e:
        QMessageBox.warning(None, "Fakturnik", str(e))
        return 1
    if okno and okno.uruchom_po_zamknieciu:
        subprocess.Popen([str(okno.uruchom_po_zamknieciu)], close_fds=True)
    return kod


def _otworz(app: QApplication, plik: Path, dziennik: Dziennik) -> tuple[int, OknoGlowne | None]:
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
    except OSError:
        pass

    okno = OknoGlowne(baza, dziennik)
    okno.show()
    return app.exec(), okno
