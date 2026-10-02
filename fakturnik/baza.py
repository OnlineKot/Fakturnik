"""Przechowywanie ustawień, liczników numeracji i wystawionych dokumentów (SQLite)."""

import hmac
import csv
import json
import os
import re
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
    "format_numeru": "{n}/{mm}/{rrrr}",
    "adnotacja": "Zwolnienie z VAT na podstawie art. 43 ust. 1 pkt 19 ustawy z dnia "
                 "11 marca 2004 r. o podatku od towarów i usług.",
    "uslugi": "Leczenie kanałowe;0\nKonsultacja;0",
    "drukarka": "",          # pusta = domyślna drukarka systemu
    "okno_drukarki": "0",    # "1" = pokazuj okno wyboru drukarki przed drukiem
    "kopia": "0",            # "1" = drukuj oryginał i kopię
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
    id: int | None = None

    @property
    def suma(self) -> float:
        return round(sum(p.wartosc for p in self.pozycje), 2)


def formatuj_numer(wzor: str, n: int, d: date) -> str:
    return (wzor.replace("{n}", str(n))
                .replace("{mm}", f"{d.month:02d}")
                .replace("{rrrr}", str(d.year))
                .replace("{rr}", f"{d.year % 100:02d}"))


class PlikZajety(Exception):
    pass


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
        if self.sciezka.exists():
            self.db.deserialize(self._wczytaj(self.sciezka, haslo, ustaw_szyfr=True))
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS ustawienia (klucz TEXT PRIMARY KEY, wartosc TEXT);
            CREATE TABLE IF NOT EXISTS liczniki (miesiac TEXT PRIMARY KEY, ostatni INTEGER);
            CREATE TABLE IF NOT EXISTS dokumenty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numer TEXT NOT NULL,
                data_wystawienia TEXT NOT NULL,
                dane TEXT NOT NULL,
                utworzono TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._utrwal()

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

    def dokumenty(self, szukaj: str = "") -> list[Dokument]:
        wynik = []
        for id_, dane in self.db.execute("SELECT id, dane FROM dokumenty ORDER BY id DESC"):
            d = json.loads(dane)
            d["pozycje"] = [Pozycja(**p) for p in d["pozycje"]]
            dok = Dokument(id=id_, **d)
            if szukaj and szukaj.lower() not in f"{dok.numer} {dok.nabywca}".lower():
                continue
            wynik.append(dok)
        return wynik

    def nabywcy(self) -> dict[str, Dokument]:
        """Ostatni dokument każdego nabywcy (do podpowiedzi przy wpisywaniu)."""
        wynik: dict[str, Dokument] = {}
        for dok in self.dokumenty():
            wynik.setdefault(dok.nabywca, dok)
        return wynik

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
                        "Usługi", "Płatność", "Kwota"])
            for d in reversed(dokumenty):
                w.writerow([d.numer, d.data_wystawienia, d.data_uslugi, d.nabywca, d.nabywca_id,
                            d.nabywca_adres.replace("\n", ", "),
                            " | ".join(f"{p.nazwa} x{p.ilosc:g}" for p in d.pozycje),
                            d.platnosc, f"{d.suma:.2f}".replace(".", ",")])
        return len(dokumenty)

    def przywroc(self, zrodlo: Path | str, haslo: str | None = None) -> None:
        """Zastępuje dane kopią zapasową; obecne hasło (szyfrowanie) zostaje."""
        dane = self._wczytaj(Path(zrodlo), haslo)
        self.db.deserialize(dane)
        self._utrwal()

    def kopia_zapasowa(self, cel: Path | str) -> None:
        """Kopia w tym samym formacie co plik danych (zaszyfrowana, jeśli jest hasło)."""
        self._utrwal()
        Path(cel).write_bytes(self.sciezka.read_bytes())
