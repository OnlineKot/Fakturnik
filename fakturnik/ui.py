"""Okno główne programu Fakturnik."""

from datetime import date
from pathlib import Path

import base64

from PySide6.QtCore import QBuffer, QByteArray, QDate, QEvent, QIODevice, QObject, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter,
    QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QInputDialog, QPlainTextEdit, QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from . import druk
from .baza import Baza, Dokument, PlikZajety, Pozycja
from .ochrona import Dziennik, katalog_kopii, kopia_automatyczna
from .szyfrowanie import BledneHaslo

MIN_DLUGOSC_HASLA = 8
BLOKADA_PO_MINUTACH = 10

STYL = """
QMainWindow, QWidget#tlo { background: #f3f5f8; }
QFrame#menu { background: #1f4e74; }
QFrame#menu QPushButton {
    color: #dfe9f2; background: transparent; border: none; text-align: left;
    padding: 12px 18px; font-size: 14px; border-radius: 6px; margin: 2px 8px;
}
QFrame#menu QPushButton:hover { background: #2b628e; }
QFrame#menu QPushButton:checked { background: #ffffff; color: #1f4e74; font-weight: bold; }
QLabel#logo { color: white; font-size: 20px; font-weight: bold; padding: 18px 18px 14px; }
QLabel#tytul { font-size: 20px; font-weight: bold; color: #1c2733; }
QGroupBox {
    background: white; border: 1px solid #d8dee5; border-radius: 8px;
    margin-top: 14px; padding: 14px 12px 12px; font-weight: bold; color: #1f4e74;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QSpinBox {
    background: white; border: 1px solid #c9d1da; border-radius: 5px; padding: 6px; font-weight: normal;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus { border-color: #1f4e74; }
QLineEdit#numer { font-size: 18px; font-weight: bold; color: #1f4e74; }
QPushButton { background: white; border: 1px solid #c9d1da; border-radius: 5px; padding: 7px 14px; }
QPushButton:hover { background: #eef3f8; }
QPushButton#glowny {
    background: #1f7a4d; color: white; border: none; font-size: 17px; font-weight: bold; padding: 14px 34px;
}
QPushButton#glowny:hover { background: #1a6942; }
QPushButton#pacjent { padding: 3px 10px; border-radius: 11px; font-weight: normal; color: #44515f; }
QPushButton#usluga { background: #e8f0f7; border-color: #c2d5e6; color: #1f4e74; }
QLabel#suma { font-size: 22px; font-weight: bold; color: #1c2733; }
QLabel#podpowiedz { color: #6a7785; font-weight: normal; }
QTableWidget { background: white; border: 1px solid #d8dee5; gridline-color: #e3e8ee; font-weight: normal; }
QHeaderView::section { background: #eef2f6; border: none; padding: 6px; font-weight: bold; color: #44515f; }
"""


def sciezka_danych() -> Path:
    katalog = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(katalog) / "fakturnik.db"


def liczba(tekst: str) -> float:
    try:
        return float(tekst.replace(" ", "").replace(",", "."))
    except ValueError:
        return 0.0


def wyczysc_uklad(uklad) -> None:
    """Usuwa od razu wszystkie elementy układu (deleteLater zostawiałby je widoczne do końca zdarzenia)."""
    while uklad.count():
        w = uklad.takeAt(0).widget()
        if w:
            w.hide()
            w.setParent(None)
            w.deleteLater()


# ---------------------------------------------------------------- hasło

class OknoHasla(QDialog):
    """Pyta o hasło; `sprawdz` zwraca True, gdy hasło jest poprawne."""

    def __init__(self, sprawdz, tytul="Fakturnik: dane chronione hasłem", parent=None,
                 dziennik: Dziennik | None = None, cel="logowanie"):
        super().__init__(parent)
        self.sprawdz = sprawdz
        self.dziennik = dziennik
        self.cel = cel
        self.proby = 0
        self.setWindowTitle(tytul)
        self.setMinimumWidth(360)
        uklad = QVBoxLayout(self)
        uklad.addWidget(QLabel("Podaj hasło, aby otworzyć program:"))
        self.pole = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        uklad.addWidget(self.pole)
        self.blad = QLabel(styleSheet="color: #b3261e;")
        uklad.addWidget(self.blad)
        przyciski = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        przyciski.button(QDialogButtonBox.StandardButton.Ok).setText("Otwórz")
        przyciski.button(QDialogButtonBox.StandardButton.Cancel).setText("Zamknij")
        przyciski.accepted.connect(self.sprobuj)
        przyciski.rejected.connect(self.reject)
        uklad.addWidget(przyciski)

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
        self.blad.setText("Nieprawidłowe hasło." + (f" Spróbuj za {przerwa} s." if przerwa else ""))
        if przerwa:
            self.setEnabled(False)
            QTimer.singleShot(przerwa * 1000, lambda: (self.setEnabled(True), self.pole.setFocus()))


class OknoNowegoHasla(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustaw hasło")
        self.setMinimumWidth(400)
        uklad = QFormLayout(self)
        info = QLabel(f"Hasło zaszyfruje wszystkie dane (AES-256, klucz z hasła przez PBKDF2-SHA256).\n"
                      f"Minimum {MIN_DLUGOSC_HASLA} znaków. Zapomnianego hasła NIE da się odzyskać.")
        info.setWordWrap(True)
        uklad.addRow(info)
        self.haslo = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.powtorz = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        uklad.addRow("Nowe hasło:", self.haslo)
        uklad.addRow("Powtórz hasło:", self.powtorz)
        self.blad = QLabel(styleSheet="color: #b3261e;")
        uklad.addRow(self.blad)
        przyciski = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        przyciski.accepted.connect(self.zatwierdz)
        przyciski.rejected.connect(self.reject)
        uklad.addRow(przyciski)

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

class StronaNowy(QWidget):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__()
        self.okno = okno
        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(24, 20, 24, 20)

        naglowek = QHBoxLayout()
        naglowek.addWidget(QLabel("Nowy rachunek", objectName="tytul"))
        naglowek.addStretch()
        uklad.addLayout(naglowek)

        # --- numer i daty
        dane = QGroupBox("Dokument")
        siatka = QGridLayout(dane)
        self.numer = QLineEdit(objectName="numer")
        self.numer.setMinimumWidth(170)
        self.data_wyst = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.data_uslugi = QDateEdit(QDate.currentDate(), calendarPopup=True, displayFormat="dd.MM.yyyy")
        self.platnosc = QComboBox()
        self.platnosc.addItems(["gotówka", "karta", "przelew"])
        for kol, (etykieta, pole) in enumerate([("Numer", self.numer), ("Data wystawienia", self.data_wyst),
                                                ("Data usługi", self.data_uslugi), ("Płatność", self.platnosc)]):
            siatka.addWidget(QLabel(etykieta, objectName="podpowiedz"), 0, kol)
            siatka.addWidget(pole, 1, kol)
        self.podpowiedz_numeru = QLabel(objectName="podpowiedz")
        siatka.addWidget(self.podpowiedz_numeru, 2, 0, 1, 4)
        self.data_wyst.dateChanged.connect(self.odswiez_numer)
        uklad.addWidget(dane)

        # --- nabywca
        nab = QGroupBox("Nabywca (pacjent)")
        f = QGridLayout(nab)
        self.nabywca = QLineEdit(placeholderText="Imię i nazwisko lub nazwa firmy")
        self.nabywca_id = QLineEdit(placeholderText="PESEL lub NIP (opcjonalnie)")
        self.nabywca_adres = QLineEdit(placeholderText="Adres (opcjonalnie), np. ul. Długa 1, 47-400 Racibórz")
        f.addWidget(self.nabywca, 0, 0)
        f.addWidget(self.nabywca_id, 0, 1)
        f.addWidget(self.nabywca_adres, 1, 0, 1, 2)
        self.ostatni = QHBoxLayout()
        f.addLayout(self.ostatni, 2, 0, 1, 2)
        f.setColumnStretch(0, 2)
        f.setColumnStretch(1, 1)
        uklad.addWidget(nab)

        # --- usługi
        usl = QGroupBox("Usługi")
        u = QVBoxLayout(usl)
        self.przyciski_uslug = QHBoxLayout()
        u.addLayout(self.przyciski_uslug)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Nazwa usługi", "Ilość", "Cena (zł)", "Wartość (zł)"])
        h = self.tabela.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for k in (1, 2, 3):
            h.setSectionResizeMode(k, QHeaderView.ResizeMode.Fixed)
        self.tabela.setColumnWidth(1, 70)
        self.tabela.setColumnWidth(2, 110)
        self.tabela.setColumnWidth(3, 120)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setMinimumHeight(150)
        self.tabela.itemChanged.connect(self.przelicz)
        u.addWidget(self.tabela)
        rzad = QHBoxLayout()
        dodaj = QPushButton("+ Dodaj pozycję")
        dodaj.clicked.connect(lambda: self.dodaj_pozycje())
        usun = QPushButton("Usuń zaznaczoną")
        usun.clicked.connect(self.usun_pozycje)
        rzad.addWidget(dodaj)
        rzad.addWidget(usun)
        rzad.addStretch()
        self.suma = QLabel("Razem: 0,00 zł", objectName="suma")
        rzad.addWidget(self.suma)
        u.addLayout(rzad)
        uklad.addWidget(usl, 1)

        # --- dół
        dol = QHBoxLayout()
        self.kopia = QCheckBox("drukuj też kopię")
        dol.addWidget(self.kopia)
        dol.addStretch()
        podglad = QPushButton("Podgląd")
        podglad.clicked.connect(self.podglad)
        pdf = QPushButton("Zapisz PDF")
        pdf.clicked.connect(self.zapisz_pdf)
        self.drukuj_btn = QPushButton("🖨  Drukuj  (F5)", objectName="glowny")
        self.drukuj_btn.clicked.connect(self.drukuj)
        for w in (podglad, pdf, self.drukuj_btn):
            dol.addWidget(w)
        uklad.addLayout(dol)

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
            tekst = nazwa.strip() + (f"  ({druk.zl(liczba(cena))} zł)" if liczba(cena) else "")
            b = QPushButton(tekst, objectName="usluga")
            b.clicked.connect(lambda _=False, n=nazwa.strip(), c=liczba(cena): self.dodaj_usluge(n, c))
            self.przyciski_uslug.addWidget(b)
        self.przyciski_uslug.addStretch()
        wyczysc_uklad(self.ostatni)
        ostatni = self.okno.baza.ostatni_nabywcy()
        if ostatni:
            self.ostatni.addWidget(QLabel("Ostatni pacjenci:", objectName="podpowiedz"))
            for d in ostatni:
                b = QPushButton(d.nabywca, objectName="pacjent")
                b.clicked.connect(lambda _=False, n=d.nabywca: (self.nabywca.setText(n), self.uzupelnij_nabywce(n)))
                self.ostatni.addWidget(b)
        self.ostatni.addStretch()
        podpowiedzi = QCompleter(sorted(self.okno.baza.nabywcy()))
        podpowiedzi.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        podpowiedzi.activated.connect(self.uzupelnij_nabywce)
        self.nabywca.setCompleter(podpowiedzi)
        self.odswiez_numer()

    def odswiez_numer(self):
        d = self.data_wyst.date().toPython()
        self.numer.setText(self.okno.baza.nastepny_numer(d))
        self.podpowiedz_numeru.setText("Numer nadawany automatycznie: kolejny w miesiącu. Można go poprawić ręcznie.")

    def uzupelnij_nabywce(self, nazwa: str):
        dok = self.okno.baza.nabywcy().get(nazwa)
        if dok:
            self.nabywca_adres.setText(dok.nabywca_adres)
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
        self.tabela.setItem(r, 3, wartosc)
        for k in (1, 2, 3):
            self.tabela.item(r, k).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
            self.tabela.item(r, 3).setText(druk.zl(w))
            suma += w
        self.tabela.blockSignals(False)
        self.suma.setText(f"Razem: {druk.zl(suma)} zł")

    def dokument(self) -> Dokument | None:
        if not self.nabywca.text().strip():
            QMessageBox.warning(self, "Brak nabywcy", "Wpisz imię i nazwisko nabywcy.")
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
        for pole in (self.nabywca, self.nabywca_id, self.nabywca_adres):
            pole.clear()
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


class StronaHistoria(QWidget):
    def __init__(self, okno: "OknoGlowne"):
        super().__init__()
        self.okno = okno
        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(24, 20, 24, 20)
        uklad.addWidget(QLabel("Historia", objectName="tytul"))
        pasek = QHBoxLayout()
        self.szukaj = QLineEdit(placeholderText="Szukaj po numerze lub nazwisku…")
        self.szukaj.textChanged.connect(self.odswiez)
        pasek.addWidget(self.szukaj, 1)
        for tekst, akcja in [("Drukuj ponownie", self.drukuj), ("Podgląd", self.podglad),
                             ("Użyj jako wzór", self.wzor), ("Eksport CSV (Excel)", self.eksport)]:
            b = QPushButton(tekst)
            b.clicked.connect(akcja)
            pasek.addWidget(b)
        uklad.addLayout(pasek)
        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Numer", "Data", "Nabywca", "Kwota (zł)"])
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.doubleClicked.connect(self.podglad)
        uklad.addWidget(self.tabela, 1)
        self.podsumowanie = QLabel(objectName="podpowiedz")
        uklad.addWidget(self.podsumowanie)
        self.docs: list[Dokument] = []

    def odswiez(self):
        self.docs = self.okno.baza.dokumenty(self.szukaj.text())
        self.tabela.setRowCount(len(self.docs))
        for r, d in enumerate(self.docs):
            for k, tekst in enumerate([d.numer, druk.data_pl(d.data_wystawienia), d.nabywca, druk.zl(d.suma)]):
                item = QTableWidgetItem(tekst)
                if k == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabela.setItem(r, k, item)
        self.tabela.resizeColumnToContents(0)
        miesiac = date.today().isoformat()[:7]
        w_miesiacu = [d for d in self.docs if d.data_wystawienia.startswith(miesiac)]
        self.podsumowanie.setText(f"W tym miesiącu wystawiono: {len(w_miesiacu)}, na kwotę "
                                  f"{druk.zl(sum(d.suma for d in w_miesiacu))} zł")

    def eksport(self):
        sciezka, _ = QFileDialog.getSaveFileName(
            self, "Eksport do Excela", str(Path.home() / f"rachunki-{date.today().isoformat()}.csv"), "CSV (*.csv)")
        if sciezka:
            n = self.okno.baza.eksport_csv(sciezka, self.docs)
            self.okno.dziennik.zapisz(f"eksport CSV ({n} dokumentów)")
            self.okno.komunikat(f"Wyeksportowano {n} dokumentów: {sciezka}")

    def wybrany(self) -> Dokument | None:
        r = self.tabela.currentRow()
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
            s.nabywca_adres.setText(d.nabywca_adres)
            s.nabywca_id.setText(d.nabywca_id)
            s.platnosc.setCurrentText(d.platnosc)
            s.tabela.setRowCount(0)
            for p in d.pozycje:
                s.dodaj_pozycje(p.nazwa, p.cena, p.ilosc)
            self.okno.przejdz(0)


class StronaUstawienia(QWidget):
    POLA = [("nazwa", "Nazwa"), ("nip", "NIP"), ("regon", "REGON"), ("miejsce", "Miejsce wystawienia"),
            ("konto", "Nr konta (przelewy)"), ("format_numeru", "Format numeru")]

    def __init__(self, okno: "OknoGlowne"):
        super().__init__()
        self.okno = okno
        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(24, 20, 24, 20)
        uklad.addWidget(QLabel("Ustawienia", objectName="tytul"))
        rzad = QHBoxLayout()
        lewa, prawa = QVBoxLayout(), QVBoxLayout()
        rzad.addLayout(lewa, 1)
        rzad.addLayout(prawa, 1)
        uklad.addLayout(rzad, 1)

        firma = QGroupBox("Dane gabinetu")
        f = QFormLayout(firma)
        self.pola: dict[str, QLineEdit | QPlainTextEdit | QComboBox] = {}
        for klucz, etykieta in self.POLA:
            self.pola[klucz] = QLineEdit()
            f.addRow(etykieta + ":", self.pola[klucz])
            if klucz == "nip":
                self.pola["adres"] = QPlainTextEdit(maximumHeight=60)
                f.addRow("Adres:", self.pola["adres"])
        self.pola["format_numeru"].setToolTip("{n} = kolejny numer, {mm} = miesiąc, {rrrr} = rok")
        lewa.addWidget(firma)

        dok = QGroupBox("Dokument")
        f = QFormLayout(dok)
        self.pola["tytul"] = QComboBox()
        self.pola["tytul"].addItems(["Rachunek", "Faktura"])
        f.addRow("Tytuł:", self.pola["tytul"])
        self.pola["adnotacja"] = QPlainTextEdit(maximumHeight=60)
        f.addRow("Adnotacja VAT:", self.pola["adnotacja"])
        self.logo = "domyslne"
        self.podglad_logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.podglad_logo.setFixedSize(70, 70)
        self.podglad_logo.setStyleSheet("background: white; border: 1px solid #d8dee5; border-radius: 5px;")
        przyciski_logo = QVBoxLayout()
        for tekst, akcja in [("Wybierz logo z pliku…", self.wybierz_logo),
                             ("Logo gabinetu (ząb)", lambda: self.ustaw_logo("domyslne")),
                             ("Bez logo", lambda: self.ustaw_logo(""))]:
            b = QPushButton(tekst)
            b.clicked.connect(akcja)
            przyciski_logo.addWidget(b)
        rzad_logo = QHBoxLayout()
        rzad_logo.addWidget(self.podglad_logo)
        rzad_logo.addLayout(przyciski_logo)
        rzad_logo.addStretch()
        f.addRow("Logo na wydruku:", rzad_logo)
        lewa.addWidget(dok)
        lewa.addStretch()

        uslugi = QGroupBox("Szybkie usługi (przyciski)")
        f = QVBoxLayout(uslugi)
        f.addWidget(QLabel("Jedna usługa w wierszu: nazwa;cena", objectName="podpowiedz"))
        self.pola["uslugi"] = QPlainTextEdit()
        f.addWidget(self.pola["uslugi"])
        prawa.addWidget(uslugi)

        drukowanie = QGroupBox("Drukowanie")
        f = QFormLayout(drukowanie)
        self.pola["drukarka"] = QComboBox()
        f.addRow("Drukarka:", self.pola["drukarka"])
        self.okno_drukarki = QCheckBox("pytaj o drukarkę przed każdym wydrukiem")
        self.kopia = QCheckBox("domyślnie drukuj oryginał i kopię")
        f.addRow(self.okno_drukarki)
        f.addRow(self.kopia)
        prawa.addWidget(drukowanie)

        bezp = QGroupBox("Bezpieczeństwo")
        f = QVBoxLayout(bezp)
        self.stan_hasla = QLabel(objectName="podpowiedz")
        self.stan_hasla.setWordWrap(True)
        f.addWidget(self.stan_hasla)
        rzad_hasla = QHBoxLayout()
        self.btn_haslo = QPushButton()
        self.btn_haslo.clicked.connect(self.zmien_haslo)
        self.btn_usun_haslo = QPushButton("Odszyfruj (usuń hasło)")
        self.btn_usun_haslo.clicked.connect(self.usun_haslo)
        dziennik = QPushButton("Dziennik logowań")
        dziennik.clicked.connect(self.pokaz_dziennik)
        for b in (self.btn_haslo, self.btn_usun_haslo, dziennik):
            rzad_hasla.addWidget(b)
        f.addLayout(rzad_hasla)
        rzad_kopii = QHBoxLayout()
        for tekst, akcja in [("Kopia zapasowa…", self.kopia_zapasowa), ("Przywróć z kopii…", self.przywroc),
                             ("Eksport odszyfrowany…", self.eksport_odszyfrowany)]:
            b = QPushButton(tekst)
            b.clicked.connect(akcja)
            rzad_kopii.addWidget(b)
        f.addLayout(rzad_kopii)
        info = QLabel(f"Kopie automatyczne: {katalog_kopii()}", objectName="podpowiedz")
        info.setWordWrap(True)
        f.addWidget(info)
        prawa.addWidget(bezp)

        zapisz = QPushButton("Zapisz ustawienia", objectName="glowny")
        zapisz.clicked.connect(self.zapisz)
        dol = QHBoxLayout()
        dol.addStretch()
        dol.addWidget(zapisz)
        uklad.addLayout(dol)

    def odswiez(self):
        u = self.okno.baza.ustawienia()
        drukarki = self.pola["drukarka"]
        drukarki.clear()
        drukarki.addItem("(domyślna drukarka Windows)", "")
        for nazwa in druk.dostepne_drukarki():
            drukarki.addItem(nazwa, nazwa)
        for klucz, pole in self.pola.items():
            if isinstance(pole, QComboBox):
                i = pole.findData(u[klucz]) if klucz == "drukarka" else pole.findText(u[klucz])
                pole.setCurrentIndex(max(i, 0))
            elif isinstance(pole, QPlainTextEdit):
                pole.setPlainText(u[klucz])
            else:
                pole.setText(u[klucz])
        self.okno_drukarki.setChecked(u["okno_drukarki"] == "1")
        self.kopia.setChecked(u["kopia"] == "1")
        self.ustaw_logo(u["logo"])
        ma = self.okno.baza.ma_haslo
        self.stan_hasla.setText(
            f"🔒 Dane zaszyfrowane (AES-256). Program blokuje się po {BLOKADA_PO_MINUTACH} min bezczynności."
            if ma else "⚠ Brak hasła: dane nie są zaszyfrowane. Zalecane jest ustawienie hasła.")
        self.btn_haslo.setText("Zmień hasło" if ma else "Ustaw hasło")
        self.btn_usun_haslo.setVisible(ma)

    def zapisz(self):
        wartosci = {}
        for klucz, pole in self.pola.items():
            if isinstance(pole, QComboBox):
                wartosci[klucz] = pole.currentData() if klucz == "drukarka" else pole.currentText()
            elif isinstance(pole, QPlainTextEdit):
                wartosci[klucz] = pole.toPlainText().strip()
            else:
                wartosci[klucz] = pole.text().strip()
        if "{n}" not in wartosci["format_numeru"]:
            QMessageBox.warning(self, "Format numeru", "Format numeru musi zawierać {n}.")
            return
        wartosci["logo"] = self.logo
        wartosci["okno_drukarki"] = "1" if self.okno_drukarki.isChecked() else "0"
        wartosci["kopia"] = "1" if self.kopia.isChecked() else "0"
        self.okno.baza.zapisz_ustawienia(wartosci)
        self.okno.komunikat("Zapisano ustawienia")
        self.okno.przejdz(0)

    def ustaw_logo(self, wartosc: str):
        self.logo = wartosc
        dane = druk.logo_bajty({"logo": wartosc})
        if dane:
            obraz = QPixmap()
            obraz.loadFromData(dane)
            self.podglad_logo.setPixmap(obraz.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
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
        self.okno.komunikat("Logo wybrane: kliknij „Zapisz ustawienia”")

    def _potwierdz_obecne(self) -> bool:
        if not self.okno.baza.ma_haslo:
            return True
        return OknoHasla(self.okno.baza.sprawdz_haslo, "Podaj obecne hasło", self,
                         self.okno.dziennik, "potwierdzenie hasła").exec() == QDialog.DialogCode.Accepted

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
        if QMessageBox.question(self, "Usuń hasło", "Dane przestaną być zaszyfrowane. Kontynuować?") \
                == QMessageBox.StandardButton.Yes:
            self.okno.baza.ustaw_haslo(None)
            self.okno.dziennik.zapisz("usunięcie hasła (odszyfrowanie danych)")
            self.okno.komunikat("Hasło usunięte, dane odszyfrowane")
            self.odswiez()

    def pokaz_dziennik(self):
        d = self.okno.dziennik
        okno = QDialog(self)
        okno.setWindowTitle("Dziennik logowań i operacji")
        okno.resize(620, 480)
        u = QVBoxLayout(okno)
        stan = QLabel("✔ Dziennik nienaruszony (łańcuch SHA-256 się zgadza)." if d.nienaruszony()
                      else "⚠ UWAGA: dziennik został zmieniony lub usunięto z niego wpisy!")
        stan.setStyleSheet("font-weight: bold; color: %s;" % ("#1f7a4d" if d.nienaruszony() else "#b3261e"))
        u.addWidget(stan)
        tabela = QTableWidget(0, 2)
        tabela.setHorizontalHeaderLabels(["Czas", "Zdarzenie"])
        tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabela.verticalHeader().setVisible(False)
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        wpisy = list(reversed(d.wpisy()))
        tabela.setRowCount(len(wpisy))
        for r, (czas, zdarzenie, _) in enumerate(wpisy):
            tabela.setItem(r, 0, QTableWidgetItem(czas))
            tabela.setItem(r, 1, QTableWidgetItem(zdarzenie))
        tabela.resizeColumnToContents(0)
        u.addWidget(tabela)
        zamknij = QPushButton("Zamknij")
        zamknij.clicked.connect(okno.accept)
        u.addWidget(zamknij, alignment=Qt.AlignmentFlag.AlignRight)
        okno.exec()

    def przywroc(self):
        sciezka, _ = QFileDialog.getOpenFileName(self, "Przywróć z kopii", str(katalog_kopii()),
                                                 "Kopia Fakturnika (*.db)")
        if not sciezka:
            return
        if QMessageBox.warning(self, "Przywróć z kopii",
                               "Obecne dane zostaną ZASTĄPIONE danymi z kopii. Kontynuować?",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) \
                != QMessageBox.StandardButton.Yes:
            return
        haslo = None
        if Baza.wymaga_hasla(sciezka):
            haslo, ok = QInputDialog.getText(self, "Hasło kopii", "Podaj hasło, którym zaszyfrowano kopię:",
                                             QLineEdit.EchoMode.Password)
            if not ok:
                return
        try:
            self.okno.baza.przywroc(sciezka, haslo)
        except (BledneHaslo, ValueError) as e:
            self.okno.dziennik.zapisz("przywrócenie kopii: NIEUDANE")
            QMessageBox.critical(self, "Błąd", str(e))
            return
        self.okno.dziennik.zapisz(f"przywrócenie danych z kopii {Path(sciezka).name}")
        self.okno.komunikat("Przywrócono dane z kopii")
        self.okno.przejdz(1)

    def eksport_odszyfrowany(self):
        if not self._potwierdz_obecne():
            return
        if self.okno.baza.ma_haslo and QMessageBox.warning(
                self, "Eksport odszyfrowany",
                "Plik będzie NIEZASZYFROWANY i każdy, kto go otworzy, zobaczy dane pacjentów. Kontynuować?",
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
        self.setWindowTitle("Fakturnik")
        self.resize(1100, 760)

        tlo = QWidget(objectName="tlo")
        uklad = QHBoxLayout(tlo)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        menu = QFrame(objectName="menu")
        menu.setFixedWidth(210)
        m = QVBoxLayout(menu)
        m.setContentsMargins(0, 0, 0, 12)
        m.addWidget(QLabel("Fakturnik", objectName="logo"))
        self.grupa = QButtonGroup(self)
        for i, nazwa in enumerate(["📝  Nowy rachunek", "📋  Historia", "⚙  Ustawienia"]):
            b = QPushButton(nazwa, checkable=True)
            b.clicked.connect(lambda _=False, i=i: self.przejdz(i))
            self.grupa.addButton(b, i)
            m.addWidget(b)
        m.addStretch()
        self.btn_blokuj = QPushButton("🔒  Zablokuj")
        self.btn_blokuj.clicked.connect(self.zablokuj)
        m.addWidget(self.btn_blokuj)
        uklad.addWidget(menu)

        self.strony = QStackedWidget()
        self.strona_nowy = StronaNowy(self)
        self.strona_historia = StronaHistoria(self)
        self.strona_ustawienia = StronaUstawienia(self)
        for s in (self.strona_nowy, self.strona_historia, self.strona_ustawienia):
            self.strony.addWidget(s)
        uklad.addWidget(self.strony, 1)
        self.setCentralWidget(tlo)

        self.strona_nowy.wyczysc()
        self.przejdz(0)

        # automatyczna blokada po bezczynności (tylko gdy jest hasło)
        self.timer = QTimer(self, interval=BLOKADA_PO_MINUTACH * 60 * 1000, singleShot=True)
        self.timer.timeout.connect(self.zablokuj)
        self.straznik = StraznikBezczynnosci(self.timer)
        QApplication.instance().installEventFilter(self.straznik)
        self.timer.start()

        if not self.baza.ustawienia()["nip"]:
            QTimer.singleShot(300, self.pierwsze_uruchomienie)

    def przejdz(self, i: int):
        self.grupa.button(i).setChecked(True)
        self.strony.setCurrentIndex(i)
        self.strony.currentWidget().odswiez()
        self.btn_blokuj.setVisible(self.baza.ma_haslo)

    def komunikat(self, tekst: str):
        self.statusBar().showMessage(tekst, 5000)

    def podglad(self, dok: Dokument, z_kopia=False):
        u = self.baza.ustawienia()
        dialog = QPrintPreviewDialog(druk.przygotuj_drukarke(u), self)
        dialog.setWindowTitle(f"Podgląd: {dok.numer}")
        dialog.paintRequested.connect(lambda p: druk.drukuj(druk.html_dokumentu(dok, u, z_kopia), p))
        dialog.resize(900, 1000)
        dialog.exec()

    def zablokuj(self):
        if not self.baza.ma_haslo or not self.isVisible():
            self.timer.start()
            return
        self.hide()
        self.dziennik.zapisz("blokada programu")
        okno = OknoHasla(self.baza.sprawdz_haslo, "Fakturnik: zablokowany", dziennik=self.dziennik, cel="odblokowanie")
        if okno.exec() == QDialog.DialogCode.Accepted:
            self.show()
            self.timer.start()
        else:
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
            "Uzupełnij dane gabinetu (przede wszystkim NIP) i ustaw ceny usług.\n\n"
            "Zalecamy też ustawienie hasła w sekcji Bezpieczeństwo: dane pacjentów będą wtedy zaszyfrowane.")
        self.przejdz(2)


def uruchom() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Fakturnik")
    app.setOrganizationName("Fakturnik")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "zasoby" / "ikona.png")))
    app.setStyle("Fusion")
    app.setStyleSheet(STYL)
    app.setFont(QFont("Segoe UI", 10))

    plik = sciezka_danych()
    dziennik = Dziennik(plik.parent / "dziennik.log")
    try:
        return _otworz(app, plik, dziennik)
    except PlikZajety as e:
        QMessageBox.warning(None, "Fakturnik", str(e))
        return 1


def _otworz(app: QApplication, plik: Path, dziennik: Dziennik) -> int:
    if Baza.wymaga_hasla(plik):
        wynik: dict[str, Baza] = {}

        def sprawdz(haslo: str) -> bool:
            try:
                wynik["baza"] = Baza(plik, haslo)
                return True
            except BledneHaslo:
                return False

        if OknoHasla(sprawdz, dziennik=dziennik).exec() != QDialog.DialogCode.Accepted:
            return 0
        baza = wynik["baza"]
    else:
        try:
            baza = Baza(plik)
        except ValueError:
            QMessageBox.critical(None, "Fakturnik", f"Plik danych jest uszkodzony lub zmieniony z zewnątrz:\n{plik}\n\n"
                                 f"Przywróć go z kopii automatycznej w:\n{katalog_kopii()}")
            return 1
        dziennik.zapisz("uruchomienie programu (bez hasła)")
    try:
        kopia_automatyczna(plik)
    except OSError:
        pass

    okno = OknoGlowne(baza, dziennik)
    okno.show()
    return app.exec()
