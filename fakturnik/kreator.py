"""Kreator pierwszego uruchomienia: dane gabinetu, hasło, cennik, tryb pracy i integracja z Windows."""

import re
from pathlib import Path
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import druk
from .motyw import AKCENT, CZERWONY, MENU, MENU_TEKST, TEKST_2, ZIELONY
from .system import (
    integracja_dostepna, ustaw_autostart, ustaw_menu_kontekstowe, utworz_skrot_na_pulpicie,
)
from .walidacja import formatuj_konto, konto_poprawne, nip_poprawny
from .ui import MIN_DLUGOSC_HASLA, ZASOBY, liczba, liczba_dokumentow, pole, przycisk

KROKI = ["Witaj", "Gabinet", "Hasło", "Cennik", "Tryb pracy", "Windows", "Gotowe"]

STYL_KREATORA = f"""
QFrame#kreator_bok {{ background: {MENU}; }}
QFrame#kreator_bok QLabel {{ color: {MENU_TEKST}; background: transparent; }}
QLabel#kreator_krok {{ padding: 7px 12px; border-radius: 7px; font-weight: 500; }}
QLabel#kreator_krok[stan="aktywny"] {{ background: #1d4851; color: white; font-weight: 600; }}
QLabel#kreator_krok[stan="zrobiony"] {{ color: #d5e4e7; }}
QLabel#kreator_tytul {{ font-size: 22px; font-weight: 650; letter-spacing: -0.4px; }}
QPushButton#wybor {{ background: white; border: 1.5px solid #dfe3e6; border-radius: 12px; padding: 16px;
    text-align: left; font-weight: 500; }}
QPushButton#wybor:checked {{ border-color: {AKCENT}; background: #f3f8f9; }}
"""


def sila_hasla(haslo: str) -> tuple[str, str]:
    punkty = sum([len(haslo) >= 8, len(haslo) >= 12, bool(re.search(r"\d", haslo)),
                  bool(re.search(r"[a-ząćęłńóśźż]", haslo)) and bool(re.search(r"[A-ZĄĆĘŁŃÓŚŹŻ]", haslo)),
                  bool(re.search(r"[^\w\s]", haslo))])
    if len(haslo) < MIN_DLUGOSC_HASLA:
        return f"Za krótkie: minimum {MIN_DLUGOSC_HASLA} znaków", CZERWONY
    if punkty <= 2:
        return "Słabe: dodaj cyfry, wielkie litery lub znaki specjalne", "#b7791f"
    if punkty == 3:
        return "Średnie", "#b7791f"
    return "Silne", ZIELONY


class Kreator(QDialog):
    def __init__(self, okno):
        super().__init__(okno)
        self.okno = okno
        self.baza = okno.baza
        self.setWindowTitle("Fakturnik: pierwsze uruchomienie")
        self.setStyleSheet(STYL_KREATORA)
        self.resize(940, 640)
        self.logo = self.baza.ustawienia()["logo"]
        u = QHBoxLayout(self)
        u.setContentsMargins(0, 0, 0, 0)
        u.setSpacing(0)

        # --- lewy pasek z krokami
        bok = QFrame(objectName="kreator_bok")
        bok.setFixedWidth(230)
        b = QVBoxLayout(bok)
        b.setContentsMargins(18, 26, 18, 20)
        b.setSpacing(4)
        znak = QLabel()
        znak.setPixmap(QPixmap(str(ZASOBY / "ikona.png")).scaled(
            40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        b.addWidget(znak)
        nazwa = QLabel("Fakturnik")
        nazwa.setStyleSheet("color: white; font-size: 16px; font-weight: 600; padding: 8px 0 0;")
        b.addWidget(nazwa)
        autor = QLabel("by TeodorTeo.com")
        autor.setStyleSheet("font-size: 11px; padding: 0 0 18px;")
        b.addWidget(autor)
        self.etykiety = []
        for i, k in enumerate(KROKI):
            e = QLabel(f"{i + 1}.  {k}", objectName="kreator_krok")
            b.addWidget(e)
            self.etykiety.append(e)
        b.addStretch()

        # --- treść
        prawa = QVBoxLayout()
        prawa.setContentsMargins(40, 34, 40, 24)
        prawa.setSpacing(14)
        self.strony = QStackedWidget()
        prawa.addWidget(self.strony, 1)
        self.blad = QLabel(styleSheet=f"color: {CZERWONY}; font-size: 12px;")
        prawa.addWidget(self.blad)
        przyciski = QHBoxLayout()
        self.btn_wstecz = przycisk("Wstecz", akcja=lambda: self.idz(self.krok - 1))
        przyciski.addWidget(self.btn_wstecz)
        przyciski.addStretch()
        self.btn_dalej = przycisk("Dalej", styl="glowny", akcja=self.dalej)
        przyciski.addWidget(self.btn_dalej)
        prawa.addLayout(przyciski)
        u.addWidget(bok)
        u.addLayout(prawa, 1)

        for budowa in (self._witaj, self._gabinet, self._haslo, self._cennik, self._tryb, self._windows,
                       self._gotowe):
            strona = QWidget()
            su = QVBoxLayout(strona)
            su.setContentsMargins(0, 0, 0, 0)
            su.setSpacing(12)
            budowa(su)
            self.strony.addWidget(strona)
        self.krok = 0
        self.idz(0)

    # ---- pomocnicze
    @staticmethod
    def _naglowek(u: QVBoxLayout, tytul: str, opis: str):
        u.addWidget(QLabel(tytul, objectName="kreator_tytul"))
        o = QLabel(opis, objectName="podtytul", wordWrap=True)
        u.addWidget(o)
        u.addSpacing(6)

    # ---- kroki
    def _witaj(self, u):
        self._naglowek(u, "Witaj w Fakturniku",
                       "Program do wystawiania i drukowania rachunków i faktur oraz przechowywania dokumentów "
                       "gabinetu. Za chwilę wpiszesz dane gabinetu i ustawisz hasło. Zajmie to około dwóch minut.")
        for tytul, opis in (("Bezpieczny", "Dane są szyfrowane (AES-256) i chronione hasłem. Program pilnuje, "
                                           "żeby nikt ich nie zmienił ani nie usunął."),
                            ("Działa bez internetu", "Wszystko zostaje na tym komputerze. Internet jest potrzebny "
                                                     "tylko do sprawdzania aktualizacji."),
                            ("Prosty", "Rachunek wystawisz w trzech krokach albo w jednym oknie: jak wolisz.")):
            k = QFrame(objectName="karta")
            ku = QVBoxLayout(k)
            ku.setContentsMargins(18, 14, 18, 14)
            t = QLabel(tytul)
            t.setStyleSheet("font-weight: 600;")
            ku.addWidget(t)
            ku.addWidget(QLabel(opis, objectName="podtytul", wordWrap=True))
            u.addWidget(k)
        u.addSpacing(6)
        migracja = QHBoxLayout()
        migracja.addWidget(QLabel("Masz już Fakturnik na innym komputerze?", objectName="podtytul"))
        migracja.addWidget(przycisk("Przenieś dane z innego komputera…", "pobierz", "plaski", self.importuj))
        migracja.addStretch()
        u.addLayout(migracja)
        u.addStretch()

    def importuj(self):
        """Migracja: pakiet .fkopia (albo pełna kopia .zip/.db) z poprzedniego komputera zamiast wpisywania od nowa."""
        from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        from . import urzadzenie
        from .baza import NowszaBaza
        from .szyfrowanie import BledneHaslo, WymaganeUrzadzenie
        from .ui import OknoNowegoHasla
        sciezka, _ = QFileDialog.getOpenFileName(self, "Pakiet migracji lub kopia Fakturnika", "",
                                                 "Kopia Fakturnika (*.fkopia *.zip *.db)")
        if not sciezka:
            return
        haslo = None
        if self.baza.czy_kopia_szyfrowana(sciezka) or Path(sciezka).suffix.lower() in (".db", ".zip"):
            haslo, ok = QInputDialog.getText(self, "Hasło", "Hasło pakietu migracji (albo hasło programu z poprzedniego "
                                             "komputera, jeśli to zwykła kopia):", QLineEdit.EchoMode.Password)
            if not ok:
                return
        try:
            try:
                self.baza.przywroc(sciezka, haslo or None)
            except WymaganeUrzadzenie:
                kod, ok = QInputDialog.getText(self, "Kod odzyskiwania", "Ta kopia jest powiązana z poprzednim "
                                               "komputerem. Wpisz kod odzyskiwania:")
                sekret = urzadzenie.sekret_z_kodu(kod) if ok else None
                if not sekret:
                    return
                self.baza._sekret = sekret
                try:
                    self.baza.przywroc(sciezka, haslo or None)
                finally:
                    self.baza._sekret = None
        except (BledneHaslo, WymaganeUrzadzenie) as e:
            QMessageBox.warning(self, "Przeniesienie danych", f"Nie udało się otworzyć kopii: {e}")
            return
        except (ValueError, NowszaBaza, PermissionError, KeyError, OSError) as e:
            QMessageBox.warning(self, "Przeniesienie danych", str(e) or "To nie jest kopia Fakturnika.")
            return
        self.okno.dziennik.zapisz("przeniesienie danych z innego komputera")
        okno = OknoNowegoHasla(self, "Hasło na tym komputerze", "Dane zostały przeniesione. Ustaw hasło, które "
                               "będzie je chronić na tym komputerze.")
        while okno.exec() != QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Hasło", "Hasło jest wymagane, żeby dane pacjentów były zaszyfrowane.")
        self.baza.ustaw_haslo(okno.haslo.text())
        self.baza.zapisz_ustawienia({"skonfigurowano": "1"})
        if integracja_dostepna():
            ustaw_autostart(True)
        QMessageBox.information(self, "Przeniesienie danych", f"Przeniesiono: {liczba_dokumentow(len(self.baza.dokumenty()))}, "
                                "ustawienia gabinetu i wrzucone pliki. Możesz pracować.")
        self.accept()

    def _gabinet(self, u):
        self._naglowek(u, "Dane gabinetu", "Te dane drukują się na każdym rachunku i fakturze. "
                                           "Pola z gwiazdką są wymagane.")
        ust = self.baza.ustawienia()
        self.p_nazwa = QLineEdit(ust["nazwa"], placeholderText="Np. Jan Kowalski, Indywidualna Praktyka Lekarska")
        self.p_adres = QPlainTextEdit(ust["adres"], placeholderText="Ulica i numer\nKod pocztowy i miasto")
        self.p_adres.setFixedHeight(62)
        self.p_miejsce = QLineEdit(ust["miejsce"], placeholderText="Miasto")
        self.p_nip = QLineEdit(ust["nip"], placeholderText="10 cyfr")
        self.p_regon = QLineEdit(ust["regon"], placeholderText="Opcjonalnie")
        self.p_konto = QLineEdit(ust["konto"], placeholderText="Opcjonalnie, do przelewów")
        self.nip_info = QLabel(objectName="drobny")
        self.p_nip.textChanged.connect(self._sprawdz_nip)
        s = QGridLayout()
        s.setHorizontalSpacing(14)
        s.setVerticalSpacing(10)
        s.addLayout(pole("Nazwa *", self.p_nazwa), 0, 0, 1, 2)
        s.addLayout(pole("Adres *", self.p_adres), 1, 0, 1, 2)
        s.addLayout(pole("Miejsce wystawienia *", self.p_miejsce), 2, 0, Qt.AlignmentFlag.AlignTop)
        nip = pole("NIP *", self.p_nip)
        nip.addWidget(self.nip_info)
        s.addLayout(nip, 2, 1, Qt.AlignmentFlag.AlignTop)
        s.addLayout(pole("REGON", self.p_regon), 3, 0)
        s.addLayout(pole("Nr konta", self.p_konto), 3, 1)
        u.addLayout(s)
        logo = QHBoxLayout()
        self.podglad_logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.podglad_logo.setFixedSize(48, 48)
        self.podglad_logo.setStyleSheet("background: #f1f4f5; border-radius: 8px; color: #8a949d; font-size: 11px;")
        logo.addWidget(QLabel("Logo na wydruku", objectName="etykieta"))
        logo.addSpacing(8)
        logo.addWidget(self.podglad_logo)
        logo.addWidget(przycisk("Logo z zębem", styl="plaski", akcja=lambda: self._logo("domyslne")))
        logo.addWidget(przycisk("Z pliku…", styl="plaski", akcja=self._logo_z_pliku))
        logo.addWidget(przycisk("Bez logo", styl="plaski", akcja=lambda: self._logo("")))
        logo.addStretch()
        u.addLayout(logo)
        self._logo(self.logo)
        self._sprawdz_nip(self.p_nip.text())
        for w in (self.p_nazwa, self.p_miejsce, self.p_nip, self.p_regon, self.p_konto):
            w.textChanged.connect(lambda _: self.blad.clear())
        self.p_adres.textChanged.connect(self.blad.clear)
        u.addStretch()

    def _sprawdz_nip(self, tekst: str):
        if not tekst.strip():
            self.nip_info.clear()
            return
        ok = nip_poprawny(tekst)
        self.nip_info.setText("NIP poprawny" if ok else "Błędny NIP: sprawdź cyfry")
        self.nip_info.setStyleSheet(f"color: {ZIELONY if ok else CZERWONY};")

    def _logo(self, wartosc: str):
        self.logo = wartosc
        dane = druk.logo_bajty({"logo": wartosc})
        if dane:
            pix = QPixmap()
            pix.loadFromData(dane)
            self.podglad_logo.setPixmap(pix.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
        else:
            self.podglad_logo.clear()
            self.podglad_logo.setText("brak")

    def _logo_z_pliku(self):
        ust = self.okno.strona_ustawienia
        ust.wybierz_logo()
        self._logo(ust.logo)

    def _haslo(self, u):
        self.haslo_ustawione = self.baza.ma_haslo
        if self.haslo_ustawione:
            self._naglowek(u, "Hasło", "Hasło jest już ustawione, a dane są zaszyfrowane. "
                                       "Możesz je zmienić później w Ustawieniach.")
            u.addStretch()
            return
        self._naglowek(u, "Ustaw hasło",
                       "Hasło szyfruje wszystkie dane pacjentów i chroni ustawienia, przychody, usuwanie "
                       "i wyłączanie programu. Zapisz je w bezpiecznym miejscu: zapomnianego hasła "
                       "nie da się odzyskać.")
        self.h1 = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.h2 = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.sila = QLabel(objectName="drobny")
        self.h1.textChanged.connect(self._pokaz_sile)
        u.addLayout(pole("Hasło", self.h1))
        u.addWidget(self.sila)
        u.addLayout(pole("Powtórz hasło", self.h2))
        u.addStretch()

    def _pokaz_sile(self, haslo: str):
        tekst, kolor = sila_hasla(haslo)
        self.sila.setText(tekst if haslo else "")
        self.sila.setStyleSheet(f"color: {kolor}; font-weight: 500;")

    def _cennik(self, u):
        self._naglowek(u, "Cennik usług", "Usługi z cennika dodasz do rachunku jednym kliknięciem. "
                                          "Możesz to też uzupełnić później w Ustawieniach.")
        self.cennik = QTableWidget(0, 2)
        self.cennik.setHorizontalHeaderLabels(["Usługa", "Cena (zł)"])
        self.cennik.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cennik.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.cennik.setColumnWidth(1, 130)
        self.cennik.verticalHeader().setVisible(False)
        self.cennik.verticalHeader().setDefaultSectionSize(34)
        self.cennik.setShowGrid(False)
        self.cennik.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        ramka = QFrame(objectName="karta")
        ru = QVBoxLayout(ramka)
        ru.setContentsMargins(0, 6, 0, 8)
        ru.addWidget(self.cennik)
        rzad = QHBoxLayout()
        rzad.setContentsMargins(10, 0, 10, 0)
        rzad.addWidget(przycisk("Dodaj usługę", "plus", "plaski", lambda: self._dodaj_usluge()))
        rzad.addWidget(przycisk("Usuń", "kosz", "plaski", lambda: self.cennik.removeRow(self.cennik.currentRow())))
        rzad.addStretch()
        ru.addLayout(rzad)
        u.addWidget(ramka, 1)
        for linia in self.baza.ustawienia()["uslugi"].splitlines():
            nazwa, _, cena = linia.partition(";")
            if nazwa.strip():
                self._dodaj_usluge(nazwa.strip(), liczba(cena))
        if not self.cennik.rowCount():
            self._dodaj_usluge(edytuj=False)

    def _dodaj_usluge(self, nazwa: str = "", cena: float = 0.0, edytuj: bool = True):
        r = self.cennik.rowCount()
        self.cennik.insertRow(r)
        self.cennik.setItem(r, 0, QTableWidgetItem(nazwa))
        c = QTableWidgetItem(druk.zl(cena) if cena else "")
        c.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.cennik.setItem(r, 1, c)
        if not nazwa and edytuj:
            self.cennik.setCurrentCell(r, 0)
            self.cennik.editItem(self.cennik.item(r, 0))

    def _tryb(self, u):
        self._naglowek(u, "Jak chcesz wystawiać dokumenty?", "Możesz to zmienić w każdej chwili przyciskiem "
                                                             "na ekranie wystawiania albo w Ustawieniach.")
        self.tryby = QButtonGroup(self)
        for i, (tytul, opis, wartosc) in enumerate((
                ("Prowadzący: krok po kroku", "Trzy proste kroki: pacjent, usługi, sprawdź i drukuj. "
                                              "Polecany na początek i dla nowych osób w gabinecie.", "prowadzacy"),
                ("Zaawansowany: jedno okno", "Wszystkie pola i podgląd wydruku naraz. Najszybszy, "
                                             "gdy już znasz program.", "zaawansowany"))):
            b = QPushButton(checkable=True, objectName="wybor", cursor=Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(84)
            bu = QVBoxLayout(b)
            bu.setContentsMargins(18, 14, 18, 14)
            bu.setSpacing(4)
            for tekst, styl in ((tytul, "font-size: 15px; font-weight: 600;"), (opis, f"color: {TEKST_2};")):
                e = QLabel(tekst, wordWrap=True)
                e.setStyleSheet(styl + " background: transparent;")
                e.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                bu.addWidget(e)
            b.setProperty("wartosc", wartosc)
            self.tryby.addButton(b, i)
            u.addWidget(b)
        self.tryby.button(0 if self.baza.ustawienia()["tryb"] != "zaawansowany" else 1).setChecked(True)
        u.addStretch()

    def _windows(self, u):
        self._naglowek(u, "Działanie w tle", "Fakturnik może działać obok zegara: wtedy pilnuje integralności "
                                             "i bezpieczeństwa danych, a otworzysz go jednym kliknięciem.")
        dostepne = integracja_dostepna()
        self.o_tle = QCheckBox("Działaj w tle (zamknięcie okna chowa program obok zegara)")
        self.o_autostart = QCheckBox("Uruchamiaj razem z Windows")
        self.o_menu = QCheckBox("Dodaj „Dodaj do Fakturnika” do menu prawego przycisku myszy (PDF i zdjęcia)")
        self.o_skrot = QCheckBox("Utwórz skrót na pulpicie")
        for w in (self.o_tle, self.o_autostart, self.o_menu, self.o_skrot):
            w.setChecked(True)
            u.addWidget(w)
        if not dostepne:
            for w in (self.o_autostart, self.o_menu, self.o_skrot):
                w.setChecked(False)
                w.setEnabled(False)
            u.addWidget(QLabel("Autostart, menu prawego przycisku i skrót działają w wersji .exe na Windows.",
                               objectName="drobny", wordWrap=True))
        u.addStretch()

    def _gotowe(self, u):
        self._naglowek(u, "Gotowe", "Wszystko ustawione. Możesz wystawić pierwszy dokument.")
        self.podsumowanie = QLabel(wordWrap=True)
        self.podsumowanie.setStyleSheet(f"color: {TEKST_2}; line-height: 150%;")
        u.addWidget(self.podsumowanie)
        u.addStretch()

    # ---- nawigacja
    def idz(self, krok: int):
        self.krok = max(0, min(len(KROKI) - 1, krok))
        self.strony.setCurrentIndex(self.krok)
        for i, e in enumerate(self.etykiety):
            e.setProperty("stan", "aktywny" if i == self.krok else ("zrobiony" if i < self.krok else ""))
            e.style().unpolish(e)
            e.style().polish(e)
        self.btn_wstecz.setVisible(self.krok > 0)
        self.btn_dalej.setText({0: "Zaczynamy", len(KROKI) - 1: "Rozpocznij pracę"}.get(self.krok, "Dalej"))
        self.blad.clear()
        if self.krok == len(KROKI) - 1:
            self.podsumowanie.setText(
                f"<b>{escape(self.p_nazwa.text().strip())}</b><br>NIP {escape(self.p_nip.text().strip())}<br><br>"
                f"Hasło: {'ustawione' if self.haslo_ustawione or self.h1.text() else 'brak'}<br>"
                f"Usług w cenniku: {len(self._uslugi())}<br>"
                f"Tryb: {'prowadzący' if self.tryby.checkedId() == 0 else 'zaawansowany'}<br>"
                f"Działanie w tle: {'tak' if self.o_tle.isChecked() else 'nie'}")

    def _uslugi(self) -> list[str]:
        wynik = []
        for r in range(self.cennik.rowCount()):
            n = (self.cennik.item(r, 0).text() if self.cennik.item(r, 0) else "").strip().replace(";", ",")
            c = liczba(self.cennik.item(r, 1).text()) if self.cennik.item(r, 1) else 0
            if n:
                wynik.append(f"{n};{c:.2f}")
        return wynik

    def _sprawdz_krok(self) -> str:
        if self.krok == 1:
            brak = [n for n, w in (("nazwę", self.p_nazwa.text()), ("adres", self.p_adres.toPlainText()),
                                   ("miejsce wystawienia", self.p_miejsce.text()), ("NIP", self.p_nip.text()))
                    if not w.strip()]
            if brak:
                return "Uzupełnij: " + ", ".join(brak) + "."
            if not nip_poprawny(self.p_nip.text()):
                return "NIP ma złą cyfrę kontrolną. Sprawdź, czy nie ma literówki."
            if self.p_konto.text().strip() and not konto_poprawne(self.p_konto.text()):
                return "Numer konta wygląda na błędny (zła suma kontrolna)."
        if self.krok == 2 and not self.haslo_ustawione:
            if len(self.h1.text()) < MIN_DLUGOSC_HASLA:
                return f"Hasło musi mieć co najmniej {MIN_DLUGOSC_HASLA} znaków."
            if self.h1.text() != self.h2.text():
                return "Hasła nie są takie same."
        return ""

    def dalej(self):
        blad = self._sprawdz_krok()
        if blad:
            self.blad.setText(blad)
            return
        if self.krok < len(KROKI) - 1:
            self.idz(self.krok + 1)
        else:
            self.zakoncz()

    def zakoncz(self):
        konto = self.p_konto.text().strip()
        self.baza.zapisz_ustawienia({
            "nazwa": self.p_nazwa.text().strip(), "adres": self.p_adres.toPlainText().strip(),
            "miejsce": self.p_miejsce.text().strip(), "nip": self.p_nip.text().strip(),
            "regon": self.p_regon.text().strip(), "konto": formatuj_konto(konto) if konto else "",
            "logo": self.logo, "uslugi": "\n".join(self._uslugi()),
            "tryb": self.tryby.checkedButton().property("wartosc"),
            "w_tle": "1" if self.o_tle.isChecked() else "0", "skonfigurowano": "1"})
        if not self.haslo_ustawione:
            self.baza.ustaw_haslo(self.h1.text())
            self.okno.dziennik.zapisz("ustawienie hasła (szyfrowanie) w kreatorze")
        if integracja_dostepna():
            ustaw_autostart(self.o_autostart.isChecked())
            ustaw_menu_kontekstowe(self.o_menu.isChecked())
            if self.o_skrot.isChecked():
                utworz_skrot_na_pulpicie()
        self.okno.dziennik.zapisz("zakończenie kreatora pierwszego uruchomienia")
        self.accept()
