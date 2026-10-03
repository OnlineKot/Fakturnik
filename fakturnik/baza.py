"""Przechowywanie ustawień, liczników numeracji i wystawionych dokumentów (SQLite)."""

import hmac
import csv
import json
import os
import re
import shutil
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .ochrona import BlokadaPliku, tylko_do_odczytu
from .szyfrowanie import Szyfr, czy_zaszyfrowane

DOMYSLNE_USTAWIENIA = {
    "nazwa": "Szymon Frydrych, Indywidualna Praktyka Stomatologiczna",
    "adres": "ul. Ocicka 7\n47-400 Racibórz",
    "nip": "",
    "regon": "",
    "miejsce": "Racibórz",
    "konto": "",
    "tytul": "Rachunek",
    "logo": "domyslne",      # "domyslne", "" (bez logo) albo obraz zapisany w base64
    "format_numeru": "{n}/{mm}/{rrrr}",
    "adnotacja": "Zwolnienie z VAT na podstawie art. 43 ust. 1 pkt 19 ustawy z dnia "
                 "11 marca 2004 r. o podatku od towarów i usług.",
    "uslugi": "Leczenie kanałowe;0\nKonsultacja;0",
    "drukarka": "",          # pusta = domyślna drukarka systemu
    "okno_drukarki": "0",    # "1" = pokazuj okno wyboru drukarki przed drukiem
    "kopia": "0",
    "auto_aktualizacje": "1",  # "1" = sprawdzaj aktualizacje przy uruchomieniu            # "1" = drukuj oryginał i kopię
}


@dataclass
class Pozycja:
    nazwa: str
    ilosc: float
    cena: float

    @property
    def wartosc(self) -> float:
        return round(self.ilosc * self.cena, 2)


@dataclass
class Dokument:
    numer: str
    data_wystawienia: str        # RRRR-MM-DD
    data_uslugi: str
    platnosc: str
    nabywca: str
    nabywca_adres: str = ""
    nabywca_id: str = ""         # PESEL lub NIP
    pozycje: list[Pozycja] = field(default_factory=list)
    anulowano: str = ""          # data anulowania (RRRR-MM-DD); pusta = dokument ważny
    powod_anulowania: str = ""
    id: int | None = None

    @property
    def suma(self) -> float:
        return round(sum(p.wartosc for p in self.pozycje), 2)

    @property
    def wazny(self) -> bool:
        return not self.anulowano


@dataclass
class Pacjent:
    nazwa: str
    adres: str
    identyfikator: str           # PESEL lub NIP
    ostatnia_wizyta: str
    dokumentow: int
    suma: float

    @property
    def nazwisko(self) -> str:
        """Do sortowania: przy zapisie "Jan Kowalski" nazwisko to ostatni wyraz."""
        czesci = self.nazwa.split()
        return czesci[-1] if czesci else ""


@dataclass
class Podsumowanie:
    liczba: int
    suma: float
    wg_platnosci: dict[str, float]
    anulowanych: int


def podsumuj(dokumenty: list[Dokument]) -> Podsumowanie:
    wazne = [d for d in dokumenty if d.wazny]
    wg: dict[str, float] = {}
    for d in wazne:
        wg[d.platnosc] = round(wg.get(d.platnosc, 0) + d.suma, 2)
    return Podsumowanie(len(wazne), round(sum(d.suma for d in wazne), 2), wg, len(dokumenty) - len(wazne))


def _bez_ogonkow(tekst: str) -> str:
    """Wyszukiwanie nie zależy od polskich znaków ani wielkości liter ("wisniewski" znajdzie "Wiśniewski")."""
    return tekst.lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))


def formatuj_numer(wzor: str, n: int, d: date) -> str:
    return (wzor.replace("{n}", str(n))
                .replace("{mm}", f"{d.month:02d}")
                .replace("{rrrr}", str(d.year))
                .replace("{rr}", f"{d.year % 100:02d}"))


class PlikZajety(Exception):
    pass


class NowszaBaza(Exception):
    """Dane zapisała nowsza wersja programu; starsza mogłaby je uszkodzić."""


# Wersja układu danych (PRAGMA user_version). Każda zmiana tabel to nowy wpis w MIGRACJE,
# dzięki czemu nowsza wersja programu przerabia stare dane zamiast je gubić.
# Nigdy nie zmieniaj ani nie usuwaj istniejących wpisów, tylko dopisuj kolejne.
MIGRACJE: dict[int, str] = {
    1: """
        CREATE TABLE IF NOT EXISTS ustawienia (klucz TEXT PRIMARY KEY, wartosc TEXT);
        CREATE TABLE IF NOT EXISTS liczniki (miesiac TEXT PRIMARY KEY, ostatni INTEGER);
        CREATE TABLE IF NOT EXISTS dokumenty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numer TEXT NOT NULL,
            data_wystawienia TEXT NOT NULL,
            dane TEXT NOT NULL,
            utworzono TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """,
}
WERSJA_DANYCH = max(MIGRACJE)


def wersja_danych(db: sqlite3.Connection) -> int:
    return db.execute("PRAGMA user_version").fetchone()[0]


class Baza:
    """Baza SQLite trzymana w pamięci i zapisywana w całości do pliku po każdej zmianie.

    Gdy ustawione jest hasło, plik jest szyfrowany (patrz szyfrowanie.py).
    """

    def __init__(self, sciezka: Path | str, haslo: str | None = None):
        self.sciezka = Path(sciezka)
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        self.szyfr: Szyfr | None = None
        self.blokada = BlokadaPliku(self.sciezka)
        self.db = sqlite3.connect(":memory:")
        istnial = self.sciezka.exists()
        if istnial:
            self.db.deserialize(self._wczytaj(self.sciezka, haslo, ustaw_szyfr=True))
        self._migruj(kopia_przed=istnial)
        self._utrwal()

    def _migruj(self, kopia_przed: bool) -> None:
        """Doprowadza dane do bieżącej wersji układu; przed zmianą zachowuje kopię pliku."""
        wersja = wersja_danych(self.db)
        if wersja > WERSJA_DANYCH:
            raise NowszaBaza("Dane zapisała nowsza wersja Fakturnika. Zaktualizuj program, "
                             "żeby ich nie uszkodzić.")
        if wersja == WERSJA_DANYCH:
            return
        if kopia_przed and self.sciezka.exists():
            kopia = self.sciezka.with_name(f"{self.sciezka.stem}-przed-migracja-v{wersja}{self.sciezka.suffix}")
            if not kopia.exists():
                shutil.copyfile(self.sciezka, kopia)
        for numer in range(wersja + 1, WERSJA_DANYCH + 1):
            with self.db:
                self.db.executescript(MIGRACJE[numer])
                self.db.execute(f"PRAGMA user_version = {numer}")

    def _wczytaj(self, sciezka: Path, haslo: str | None, ustaw_szyfr: bool = False) -> bytes:
        dane = Path(sciezka).read_bytes()
        if czy_zaszyfrowane(dane):
            if haslo is None:
                raise PermissionError("Dane są chronione hasłem.")
            dane, szyfr = Szyfr.otworz(dane, haslo)
            if ustaw_szyfr:
                self.szyfr = szyfr
        elif not dane.startswith(b"SQLite format 3"):
            raise ValueError("To nie jest plik Fakturnika.")
        return dane

    def zamknij(self) -> None:
        """Zdejmuje blokadę Windows, ale zostawia plik jako "tylko do odczytu"."""
        self.blokada.zwolnij()
        tylko_do_odczytu(self.sciezka, True)

    @staticmethod
    def wymaga_hasla(sciezka: Path | str) -> bool:
        sciezka = Path(sciezka)
        if not sciezka.exists():
            return False
        with open(sciezka, "rb") as f:
            return czy_zaszyfrowane(f.read(64))

    @property
    def ma_haslo(self) -> bool:
        return self.szyfr is not None

    def sprawdz_haslo(self, haslo: str) -> bool:
        """Do odblokowania ekranu: porównuje klucz wyliczony z podanego hasła z bieżącym."""
        if not self.szyfr:
            return True
        return hmac.compare_digest(Szyfr(haslo, self.szyfr.sol).klucz, self.szyfr.klucz)

    def ustaw_haslo(self, haslo: str | None) -> None:
        """Ustawia, zmienia (nowy tekst) lub usuwa (None) hasło i od razu przepisuje plik."""
        self.szyfr = Szyfr(haslo) if haslo else None
        self._utrwal()

    def _utrwal(self) -> None:
        """Zatwierdza zmiany i zapisuje plik atomowo (najpierw plik tymczasowy, potem podmiana)."""
        self.db.commit()
        dane = self.db.serialize()
        if self.szyfr:
            dane = self.szyfr.zaszyfruj(dane)
        tymczasowy = self.sciezka.with_suffix(".tmp")
        with open(tymczasowy, "wb") as f:
            f.write(dane)
            f.flush()
            os.fsync(f.fileno())
        self.blokada.zwolnij()
        try:
            for proba in range(10):
                try:
                    os.replace(tymczasowy, self.sciezka)
                    break
                except PermissionError:
                    # plik chwilowo trzymany np. przez antywirus lub drugą kopię programu
                    if proba == 9:
                        raise PlikZajety(
                            "Plik danych jest zablokowany. Czy Fakturnik nie jest już uruchomiony?") from None
                    time.sleep(0.2)
        finally:
            self.blokada.zaloz()

    # ---------- ustawienia ----------
    def ustawienia(self) -> dict[str, str]:
        wynik = dict(DOMYSLNE_USTAWIENIA)
        wynik.update(dict(self.db.execute("SELECT klucz, wartosc FROM ustawienia")))
        return wynik

    def zapisz_ustawienia(self, wartosci: dict[str, str]) -> None:
        self.db.executemany("INSERT OR REPLACE INTO ustawienia VALUES (?, ?)", wartosci.items())
        self._utrwal()

    # ---------- numeracja ----------
    def nastepny_numer(self, d: date) -> str:
        klucz = f"{d.year}-{d.month:02d}"
        wiersz = self.db.execute("SELECT ostatni FROM liczniki WHERE miesiac = ?", (klucz,)).fetchone()
        n = (wiersz[0] if wiersz else 0) + 1
        return formatuj_numer(self.ustawienia()["format_numeru"], n, d)

    def _podbij_licznik(self, numer: str, d: date) -> None:
        dopasowanie = re.match(r"\s*(\d+)", numer)
        if not dopasowanie:
            return
        n = int(dopasowanie.group(1))
        klucz = f"{d.year}-{d.month:02d}"
        self.db.execute(
            "INSERT INTO liczniki VALUES (?, ?) "
            "ON CONFLICT(miesiac) DO UPDATE SET ostatni = MAX(ostatni, excluded.ostatni)",
            (klucz, n))

    # ---------- dokumenty ----------
    def numer_istnieje(self, numer: str) -> bool:
        return self.db.execute("SELECT 1 FROM dokumenty WHERE numer = ?", (numer,)).fetchone() is not None

    def zapisz_dokument(self, dok: Dokument) -> Dokument:
        dane = asdict(dok)
        dane.pop("id")
        kursor = self.db.execute(
            "INSERT INTO dokumenty (numer, data_wystawienia, dane) VALUES (?, ?, ?)",
            (dok.numer, dok.data_wystawienia, json.dumps(dane, ensure_ascii=False)))
        self._podbij_licznik(dok.numer, date.fromisoformat(dok.data_wystawienia))
        self._utrwal()
        dok.id = kursor.lastrowid
        return dok

    def dokumenty(self, szukaj: str = "", rok: int | None = None, miesiac: int | None = None) -> list[Dokument]:
        """Dokumenty od najnowszego; `szukaj` dopasowuje nazwisko/imię, numer lub PESEL/NIP."""
        wzor = _bez_ogonkow(szukaj.strip())
        prefiks = f"{rok:04d}-" if rok else ""
        if rok and miesiac:
            prefiks += f"{miesiac:02d}-"
        wynik = []
        for id_, dane in self.db.execute(
                "SELECT id, dane FROM dokumenty WHERE data_wystawienia LIKE ? ORDER BY data_wystawienia DESC, id DESC",
                (prefiks + "%",)):
            d = json.loads(dane)
            d["pozycje"] = [Pozycja(**p) for p in d["pozycje"]]
            dok = Dokument(id=id_, **d)
            if miesiac and not rok and int(dok.data_wystawienia[5:7]) != miesiac:
                continue
            if wzor and not all(slowo in _bez_ogonkow(f"{dok.numer} {dok.nabywca} {dok.nabywca_id}")
                                for slowo in wzor.split()):
                continue
            wynik.append(dok)
        return wynik

    def dokument(self, id_: int) -> Dokument | None:
        wiersz = self.db.execute("SELECT dane FROM dokumenty WHERE id = ?", (id_,)).fetchone()
        if not wiersz:
            return None
        d = json.loads(wiersz[0])
        d["pozycje"] = [Pozycja(**p) for p in d["pozycje"]]
        return Dokument(id=id_, **d)

    def anuluj(self, id_: int, powod: str = "") -> Dokument:
        """Oznacza dokument jako anulowany. Nie usuwa go, żeby numeracja nie miała dziur."""
        dok = self.dokument(id_)
        if dok is None:
            raise KeyError(id_)
        dok.anulowano = date.today().isoformat()
        dok.powod_anulowania = powod.strip()
        dane = asdict(dok)
        dane.pop("id")
        self.db.execute("UPDATE dokumenty SET dane = ? WHERE id = ?", (json.dumps(dane, ensure_ascii=False), id_))
        self._utrwal()
        return dok

    def lata(self) -> list[int]:
        return [int(r[0]) for r in self.db.execute(
            "SELECT DISTINCT substr(data_wystawienia, 1, 4) FROM dokumenty ORDER BY 1 DESC")]

    def nabywcy(self) -> dict[str, Dokument]:
        """Ostatni dokument każdego nabywcy (do podpowiedzi przy wpisywaniu)."""
        wynik: dict[str, Dokument] = {}
        for dok in self.dokumenty():
            wynik.setdefault(dok.nabywca, dok)
        return wynik

    def pacjenci(self, szukaj: str = "") -> list[Pacjent]:
        """Lista pacjentów z dotychczasowych dokumentów, alfabetycznie po nazwisku."""
        zebrani: dict[str, Pacjent] = {}
        for dok in self.dokumenty(szukaj):
            p = zebrani.get(dok.nabywca)
            if p is None:
                p = zebrani[dok.nabywca] = Pacjent(dok.nabywca, dok.nabywca_adres, dok.nabywca_id,
                                                   dok.data_wystawienia, 0, 0.0)
            p.dokumentow += 1
            if dok.wazny:
                p.suma = round(p.suma + dok.suma, 2)
        return sorted(zebrani.values(), key=lambda p: (_bez_ogonkow(p.nazwisko), _bez_ogonkow(p.nazwa)))

    def ostatni_nabywcy(self, ile: int = 8) -> list[Dokument]:
        return list(self.nabywcy().values())[:ile]

    def eksport_odszyfrowany(self, cel: Path | str) -> None:
        """Zwykły, niezaszyfrowany plik SQLite (do archiwum lub innego programu)."""
        Path(cel).write_bytes(self.db.serialize())

    def eksport_csv(self, cel: Path | str, dokumenty: list[Dokument] | None = None) -> int:
        dokumenty = self.dokumenty() if dokumenty is None else dokumenty
        with open(cel, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel poprawnie czyta polskie znaki
            w = csv.writer(f, delimiter=";")
            w.writerow(["Numer", "Data wystawienia", "Data usługi", "Nabywca", "PESEL/NIP", "Adres",
                        "Usługi", "Płatność", "Kwota", "Status"])
            for d in reversed(dokumenty):
                w.writerow([d.numer, d.data_wystawienia, d.data_uslugi, d.nabywca, d.nabywca_id,
                            d.nabywca_adres.replace("\n", ", "),
                            " | ".join(f"{p.nazwa} x{p.ilosc:g}" for p in d.pozycje),
                            d.platnosc, f"{d.suma:.2f}".replace(".", ","),
                            f"anulowany {d.anulowano}" if d.anulowano else "ważny"])
        return len(dokumenty)

    def przywroc(self, zrodlo: Path | str, haslo: str | None = None) -> None:
        """Zastępuje dane kopią zapasową; obecne hasło (szyfrowanie) zostaje."""
        dane = self._wczytaj(Path(zrodlo), haslo)
        proba = sqlite3.connect(":memory:")
        proba.deserialize(dane)
        if wersja_danych(proba) > WERSJA_DANYCH:
            raise NowszaBaza("Kopia pochodzi z nowszej wersji Fakturnika. Najpierw zaktualizuj program.")
        self.db.deserialize(dane)
        self._migruj(kopia_przed=False)
        self._utrwal()

    def kopia_zapasowa(self, cel: Path | str) -> None:
        """Kopia w tym samym formacie co plik danych (zaszyfrowana, jeśli jest hasło)."""
        self._utrwal()
        Path(cel).write_bytes(self.sciezka.read_bytes())
