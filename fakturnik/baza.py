"""Przechowywanie ustawień, liczników numeracji i wystawionych dokumentów (SQLite)."""

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .ochrona import BlokadaPliku, tylko_do_odczytu
from . import konta
from .szyfrowanie import (
    BledneHaslo, Szyfr, WymaganeUrzadzenie, czy_kopia_szyfrowana, czy_powiazane_z_urzadzeniem, czy_zaszyfrowane, nowy_klucz, odszyfruj_kopie, odszyfruj_plik, zaszyfruj_kopie,
    klucz_argon2, sprawdz_weryfikator, weryfikator, zaszyfruj_plik,
)

PLIK_WERYFIKATORA = "weryfikator.json"  # do sprawdzenia hasła przez deinstalator

DOMYSLNE_USTAWIENIA = {
    "nazwa": "",
    "adres": "",
    "nip": "",
    "regon": "",
    "miejsce": "",
    "konto": "",
    "tytul": "Rachunek",     # domyślny rodzaj nowego dokumentu: "Rachunek" albo "Faktura"
    "logo": "domyslne",      # "domyslne", "" (bez logo) albo obraz zapisany w base64
    "format_numeru": "{n}/{mm}/{rrrr}",
    "adnotacja": "Zwolnienie z VAT na podstawie art. 43 ust. 1 pkt 19 ustawy z dnia "
                 "11 marca 2004 r. o podatku od towarów i usług.",
    "uslugi": "",
    "drukarka": "",          # pusta = domyślna drukarka systemu
    "okno_drukarki": "1",    # "1" = przed drukiem pokazuj okno ustawień wydruku
    "kopia": "0",            # "1" = drukuj oryginał i kopię
    "auto_aktualizacje": "1",  # "1" = sprawdzaj aktualizacje przy uruchomieniu
    "skonfigurowano": "0",   # "1" = kreator pierwszego uruchomienia zakończony
    "tryb": "prowadzacy",    # "prowadzacy" (krok po kroku) albo "zaawansowany" (wszystko w jednym oknie)
    "druk_data_wydruku": "0",        # "1" = na dokumencie drukuje się data i godzina wydruku
    "druk_data_wygenerowania": "1",  # "1" = na zestawieniach drukuje się data i godzina wygenerowania
    "blokada_minut": "10",   # automatyczna blokada po tylu minutach bezczynności (gdy jest hasło)
    "w_tle": "1",            # "1" = zamknięcie okna chowa program do zasobnika zamiast go wyłączać
    "format_numeru_faktury": "FV/{n}/{mm}/{rrrr}",
    "format_numeru_korekty": "KOR/{n}/{mm}/{rrrr}",
    "termin_dni": "7",       # termin płatności przy przelewie (dni od wystawienia)
    "druk_qr": "1",          # "1" = kod QR do przelewu (rekomendacja ZBP) na dokumentach płatnych przelewem
    "druk_pesel": "0",       # "1" = PESEL pacjenta drukuje się na rachunku (RODO: domyślnie nie)
    "ostrzezenie_secure_boot": "0",  # "1" = już pokazano wskazówkę o wyłączonym Secure Boot
    "ostatnie_sprawdzenie_logowan": "",  # od kiedy liczyć nieudane logowania do Windows
    "poprzednia_tapeta": "",  # tapeta sprzed ustawienia tapety Fakturnika (do przywrócenia)
    "powiadomienie_startowe": "1",       # "1" = powiadomienie „Komputer zweryfikowany” przy starcie
    "powiadomienia_sekund": "6",         # jak długo widać powiadomienie
    "powiadomienia_dzwiek": "0",         # "1" = dźwięk przy powiadomieniu
    "blokuj_z_komputerem": "1",          # "1" = blokada Windows blokuje też Fakturnik
    "nazwa_wlascicielki": "Właściciel",  # nazwa konta właściciela (w dzienniku i na dokumentach)
    "godziny_pracy": "",               # JSON {0=pon..6=nd: "GG:MM-GG:MM"}; puste = wt 12-18, śr 10-17, czw 12-18, pt 8-14
    "przypomnienie_min": "15",          # ile minut przed końcem godzin przypomnieć
    "wyloguj_po_godzinach": "asystentki",  # "asystentki", "wszyscy" albo "nikt"
    "asystentki_zamkniecie_dnia": "1",  # "1" = asystentka może zrobić zamknięcie dnia bez hasła właściciela
    "druk_wystawil": "1",               # "1" = „Wystawił(a): …” na dokumencie
    "notatki": "",
    "zaslona": "1",                     # zasłona ekranu z ząbkiem po bezczynności komputera (5 spacji = powrót)
    "zaslona_gaszenie_min": "10",       # po ilu minutach zasłony zgasić ekran i monitor (0 = nigdy)
    "zaslona_sekund": "30",             # po ilu sekundach bezczynności pokazać zasłonę
    "schowek_sekund": "30",             # po ilu sekundach czyścić schowek ze skopiowanym hasłem
    "ostatnie_powitanie": "",           # data ostatniego powitania (raz dziennie)
    "skaner_pobrane": "1",              # "1" = sprawdzaj nowe pliki w folderze Pobrane
    "zaslona_odblokowanie": "spacje",   # dowolny | spacje | pin | spacje_pin | haslo (spacja, potem hasło)
    "tapeta_napis": "",                 # własny napis na tapecie (pod nazwą gabinetu)
    "piny": "",                         # PIN-y szybkiego odblokowania (JSON: konto -> sól i skrót Argon2id)
    "pin_bledy": "0",                   # błędne PIN-y od ostatniego logowania pełnym hasłem
    "aktualizacja_widziana": "",        # wersja|kiedy: strażnik aktualizacji (usługa ma ją zainstalować w 3 h)
    "dokumenty_do_plikow": "1",         # "1" = PDF każdego wystawionego dokumentu trafia do Plików
    "pliki_edycja": "0",                # "1" = pliki można opisywać i usuwać (ustawienia deweloperskie)
    "qr_strony": "",                    # strony do pokazania jako kod QR (JSON: nazwa, adres)
    "sprawdzaj_plik_programu": "1",     # "1" = porównuj Fakturnik.exe z sumą SHA-256 wydania (ustawienia deweloperskie)
    "tryb_bez_zabezpieczen": "0",       # "1" = dodatkowe zabezpieczenia wyłączone (ustawienia deweloperskie)
    "przypomnienia": "",                # przypomnienia z godziną (JSON, w zaszyfrowanych danych)
    "kopia_folder": "",      # trzecie miejsce na kopie: pendrive, dysk sieciowy, OneDrive
    "ochrona_ekranu": "1",   # "1" = okna programu niewidoczne dla zrzutów i nagrań ekranu (Windows)
    "rodo_lat": "5",         # ile pełnych lat po roku wystawienia trzymać dane osobowe w dokumentach
    "ostatni_wpis_dziennika": "",  # skrót ostatniego wpisu dziennika (wykrywa ucięcie dziennika)
}
ZANONIMIZOWANO = "[dane usunięte – RODO]"
NAZWA_PLIKU_NA_DYSKU = re.compile(r"[0-9a-f]{32}\.bin")


@dataclass
class Pozycja:
    nazwa: str
    ilosc: float
    cena: float
    jm: str = "usł."             # jednostka miary (art. 106e ust. 1 pkt 8 ustawy o VAT)

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
    rodzaj: str = ""             # "Rachunek" albo "Faktura"; puste w dokumentach z wersji sprzed faktur
    poprawiono: str = ""         # data ostatniej edycji (RRRR-MM-DD); poprzednie wersje są w historii zmian
    anulowano: str = ""          # data anulowania (RRRR-MM-DD); pusta = dokument ważny
    powod_anulowania: str = ""
    termin_platnosci: str = ""   # RRRR-MM-DD, przy przelewie
    wystawil: str = ""           # kto wystawił (konto właściciela lub asystentki)
    # faktura korygująca (rodzaj "Korekta"): której faktury dotyczy, dlaczego i jak wyglądała przed korektą
    korekta_do: str = ""         # numer korygowanej faktury
    korekta_data: str = ""       # data wystawienia korygowanej faktury
    korekta_id: int = 0
    powod_korekty: str = ""
    pozycje_przed: list[Pozycja] = field(default_factory=list)
    id: int | None = None

    @property
    def suma_po(self) -> float:
        return round(sum(p.wartosc for p in self.pozycje), 2)

    @property
    def suma_przed(self) -> float:
        return round(sum(p.wartosc for p in self.pozycje_przed), 2)

    @property
    def suma(self) -> float:
        """Kwota dokumentu; dla korekty różnica (ujemna = do zwrotu), żeby sumy przychodów się zgadzały."""
        if self.jest_korekta:
            return round(self.suma_po - self.suma_przed, 2)
        return self.suma_po

    @property
    def jest_korekta(self) -> bool:
        return self.rodzaj == "Korekta"

    @property
    def nazwa_druku(self) -> str:
        return "Faktura korygująca" if self.jest_korekta else self.tytul

    @property
    def wazny(self) -> bool:
        return not self.anulowano

    @property
    def tytul(self) -> str:
        return self.rodzaj or "Rachunek"



@dataclass
class Plik:
    """Plik wrzucony do programu (np. faktura kosztowa, skan). Treść leży zaszyfrowana w katalogu `pliki`."""
    id: int
    nazwa: str
    typ: str                     # rozszerzenie: pdf, jpg, png…
    rozmiar: int
    data: str                    # data dokumentu RRRR-MM-DD
    kategoria: str
    osoba: str                   # pacjent albo kontrahent
    opis: str
    dodano: str


KATEGORIA_WYSTAWIONE = "Wystawiony dokument"  # PDF-y dokumentów wystawionych w programie (dodawane samoczynnie)
KATEGORIE_PLIKOW = [KATEGORIA_WYSTAWIONE, "Faktura kosztowa", "Faktura od kontrahenta", "Dokument pacjenta", "Umowa", "Inne"]
TYPY_PLIKOW = {"pdf", "jpg", "jpeg", "png", "gif", "bmp", "webp", "tif", "tiff"}
MAKS_ROZMIAR_PLIKU = 50 * 1024 * 1024


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


def bezpieczna_komorka(wartosc) -> str:
    """Chroni przed „CSV injection”: tekst zaczynający się od =, +, -, @ Excel wykonałby jako formułę."""
    tekst = str(wartosc)
    if re.fullmatch(r"-?\d[\d ]*([.,]\d+)?", tekst):
        return tekst  # zwykła liczba (np. ujemna kwota korekty) zostaje liczbą
    return "'" + tekst if tekst[:1] in ("=", "+", "-", "@", "\t", "\r") else tekst


def dokument_z_danych(id_: int, d: dict) -> Dokument:
    """Dokument z zapisanego JSON-a; pomija pola nieznane tej wersji (np. dodane w innej wersji programu)."""
    znane = {f for f in Dokument.__dataclass_fields__ if f != "id"}
    d = {k: v for k, v in d.items() if k in znane}
    for klucz in ("pozycje", "pozycje_przed"):
        d[klucz] = [Pozycja(nazwa=p["nazwa"], ilosc=p["ilosc"], cena=p["cena"], jm=p.get("jm") or "usł.")
                    for p in d.get(klucz, [])]
    return Dokument(id=id_, **d)


def numer_z_wzoru(wzor: str, numer: str) -> int | None:
    """Odczytuje kolejny numer {n} z gotowego numeru, np. 'FV/7/10/2026' -> 7."""
    regex = re.escape(wzor)
    for znacznik, zamiennik in (("{n}", r"(\d+)"), ("{mm}", r"\d{1,2}"), ("{rrrr}", r"\d{4}"), ("{rr}", r"\d{2}")):
        regex = regex.replace(re.escape(znacznik), zamiennik)
    dopasowanie = re.fullmatch(regex, numer.strip())
    if dopasowanie:
        return int(dopasowanie.group(1))
    zapasowe = re.search(r"\d+", numer)
    return int(zapasowe.group()) if zapasowe else None


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
    2: """
        CREATE TABLE IF NOT EXISTS pliki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL,
            typ TEXT NOT NULL,
            rozmiar INTEGER NOT NULL,
            plik TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            data TEXT NOT NULL,
            kategoria TEXT NOT NULL DEFAULT '',
            osoba TEXT NOT NULL DEFAULT '',
            opis TEXT NOT NULL DEFAULT '',
            dodano TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """,
    3: """
        CREATE TABLE IF NOT EXISTS pacjenci (
            nazwa TEXT PRIMARY KEY,
            identyfikator TEXT NOT NULL DEFAULT '',
            adres TEXT NOT NULL DEFAULT '',
            dodano TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS wersje_dokumentow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dokument_id INTEGER NOT NULL,
            dane TEXT NOT NULL,
            zmieniono TEXT DEFAULT CURRENT_TIMESTAMP,
            powod TEXT NOT NULL DEFAULT ''
        );
    """,
    4: """
        ALTER TABLE pliki ADD COLUMN sha256_dysk TEXT NOT NULL DEFAULT '';
    """,
    5: """
        CREATE TABLE IF NOT EXISTS pliki_dokumentow (
            dokument_id INTEGER NOT NULL,
            odcisk TEXT NOT NULL,
            plik_id INTEGER NOT NULL,
            PRIMARY KEY (dokument_id, odcisk)
        );
    """,
}
WERSJA_DANYCH = max(MIGRACJE)


# PIN: szybkie odblokowanie, gdy program już działa (blokada, zasłona). Nie szyfruje danych — po starcie
# komputera zawsze potrzebne jest pełne hasło. Po PROBY_PIN błędach PIN-y nie działają do logowania hasłem.
MIN_PIN, MAX_PIN = 4, 8
MIN_PIN_RESETU, MAX_PIN_RESETU = 6, 12
PROBY_PIN = 5
ARGON2_PIN = (32768, 2, 1)
ROLA_RESETU = "reset"  # osobne hasło lub PIN do resetu zapomnianego hasła właściciela


def jest_pin(tekst: str, minimum: int = MIN_PIN, maksimum: int = MAX_PIN) -> bool:
    return bool(re.fullmatch(r"[0-9]+", tekst or "")) and minimum <= len(tekst) <= maksimum


def blad_hasla_resetu(tekst: str) -> str | None:
    """Hasło do resetu: zwykłe hasło (min. 8 znaków) albo PIN z co najmniej 6 cyfr."""
    if re.fullmatch(r"[0-9]+", tekst or ""):
        if not jest_pin(tekst, MIN_PIN_RESETU, MAX_PIN_RESETU):
            return f"PIN do resetu musi mieć od {MIN_PIN_RESETU} do {MAX_PIN_RESETU} cyfr."
        if len(set(tekst)) == 1 or tekst in "01234567890123" or tekst in "98765432109876":
            return "Ten PIN jest zbyt łatwy do zgadnięcia (np. 111111, 123456)."
        return None
    if len(tekst or "") < 8:
        return "Hasło do resetu musi mieć co najmniej 8 znaków (albo być PIN-em z 6 cyfr)."
    return None


def wersja_danych(db: sqlite3.Connection) -> int:
    return db.execute("PRAGMA user_version").fetchone()[0]


class Baza:
    """Baza SQLite trzymana w pamięci i zapisywana w całości do pliku po każdej zmianie.

    Gdy ustawione jest hasło, plik jest szyfrowany (patrz szyfrowanie.py).
    """

    def __init__(self, sciezka: Path | str, haslo: str | None = None, sekret: bytes | None = None,
                 klucz_hasla: bytes | None = None):
        self.sciezka = Path(sciezka)
        self._klucz_hasla = klucz_hasla  # zamiast hasła: klucz danych z konta asystentki
        self._sekret = sekret  # sekret urządzenia (weryfikacja urządzenia), gdy dane są z nim powiązane
        self.sciezka.parent.mkdir(parents=True, exist_ok=True)
        self.szyfr: Szyfr | None = None
        self._skrot_zapisu = ""  # SHA-256 ostatnio zapisanego pliku danych (do wykrywania zmian z zewnątrz)
        self.katalog_plikow = self.sciezka.parent / "pliki"
        self.blokada = BlokadaPliku(self.sciezka)
        self.db = sqlite3.connect(":memory:")
        istnial = self.sciezka.exists()
        if istnial:
            try:
                self.db.deserialize(self._wczytaj(self.sciezka, haslo, ustaw_szyfr=True))
                spojnosc = self.db.execute("PRAGMA quick_check").fetchone()[0]
            except sqlite3.DatabaseError:
                spojnosc = "błąd odczytu"
            if spojnosc != "ok":
                raise ValueError("Plik danych jest uszkodzony.")
        self._migruj(kopia_przed=istnial)
        self._zachowaj_ustawienia()
        self._utrwal()
        if haslo and self.szyfr and self.szyfr.wersja < 3:
            self.ustaw_haslo(haslo)  # starszy format: przejście na Argon2id i podwójne szyfrowanie
        elif self.szyfr and self.szyfr.wersja >= 3 and not (self.sciezka.parent / PLIK_WERYFIKATORA).exists():
            self._zapisz_weryfikator()

    def _migruj(self, kopia_przed: bool) -> None:
        """Doprowadza dane do bieżącej wersji układu; przed zmianą zachowuje kopię pliku."""
        self.db.execute("PRAGMA secure_delete = ON")  # usunięte dane są nadpisywane zerami (RODO)
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

    def _zachowaj_ustawienia(self) -> None:
        """Ustawienia przechodzą przez aktualizacje bez zmian: wartości, które ktoś miał (także domyślne,
        nigdy nie zapisane), trafiają do danych, więc nowsza wersja ze zmienionymi wartościami domyślnymi
        ich nie przestawi. Nowe ustawienia dostają wartość domyślną tylko raz, przy pierwszym uruchomieniu."""
        self.db.executemany("INSERT OR IGNORE INTO ustawienia (klucz, wartosc) VALUES (?, ?)",
                            DOMYSLNE_USTAWIENIA.items())
        self.db.commit()

    def _wczytaj(self, sciezka: Path, haslo: str | None, ustaw_szyfr: bool = False) -> bytes:
        dane = Path(sciezka).read_bytes()
        if czy_zaszyfrowane(dane):
            klucz = self._klucz_hasla if ustaw_szyfr else None
            if haslo is None and klucz is None:
                raise PermissionError("Dane są chronione hasłem.")
            sekret = self._sekret or (self.szyfr.sekret if self.szyfr else None)
            dane, szyfr = Szyfr.otworz(dane, haslo, sekret, klucz)
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
    def da_sie_otworzyc(sciezka: Path | str, haslo: str | None, sekret: bytes | None = None) -> bool:
        """Czy plik (np. kopia automatyczna) otwiera się tym hasłem i jest nieuszkodzony. Niczego nie zmienia."""
        try:
            dane = Path(sciezka).read_bytes()
            if czy_zaszyfrowane(dane):
                if haslo is None:
                    return False
                dane, _ = Szyfr.otworz(dane, haslo, sekret)
            elif haslo is not None or not dane.startswith(b"SQLite format 3"):
                # dane chronione hasłem nie mogą zostać zastąpione plikiem bez szyfrowania
                return False
            db = sqlite3.connect(":memory:")
            db.deserialize(dane)
            return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        except (BledneHaslo, WymaganeUrzadzenie, OSError, ValueError, sqlite3.DatabaseError):
            return False

    @staticmethod
    def powiazany_z_urzadzeniem(sciezka: Path | str) -> bool:
        try:
            with open(sciezka, "rb") as f:
                return czy_powiazane_z_urzadzeniem(f.read(64))
        except OSError:
            return False

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
        return hmac.compare_digest(self.szyfr.klucz_dla(haslo), self.szyfr.klucz_hasla)

    def ustaw_haslo(self, haslo: str | None) -> None:
        """Ustawia, zmienia (nowy tekst) lub usuwa (None) hasło i od razu przepisuje plik.
        Zmiana hasła zachowuje weryfikację urządzenia; usunięcie hasła ją wyłącza (wymaga hasła)."""
        sekret = self.szyfr.sekret if self.szyfr else None
        self.szyfr = Szyfr(haslo, sekret=sekret) if haslo else None
        self._sekret = self.szyfr.sekret if self.szyfr else None
        self._utrwal()
        self._zapisz_weryfikator()
        if self.szyfr:
            self._odnow_konta()
        else:  # bez hasła nie ma szyfrowania, więc i kont asystentek, PIN-ów ani hasła do resetu
            self.db.execute("DELETE FROM ustawienia WHERE klucz IN ('konta_klucze', 'piny')")
            self._utrwal()
            konta.zapisz(self.sciezka.parent, [])

    # ---------- konta asystentek ----------
    def _klucze_kont(self) -> dict:
        try:
            return json.loads(self.ustawienia().get("konta_klucze") or "{}")
        except ValueError:
            return {}

    def konta(self) -> list[dict]:
        """Aktywne konta: [{id, nazwa, rola}] (z zaszyfrowanych danych, nie z pliku kont)."""
        return [{"id": i, "nazwa": k["nazwa"], "rola": k["rola"]} for i, k in self._klucze_kont().items()
                if k["rola"] != ROLA_RESETU]

    def konto_aktywne(self, id_: str) -> bool:
        return id_ in self._klucze_kont()

    def konto(self, id_: str) -> dict | None:
        """Rola i nazwa konta z zaszyfrowanych danych (plik kont da się edytować, więc mu nie ufamy)."""
        k = self._klucze_kont().get(id_)
        return {"id": id_, "nazwa": k["nazwa"], "rola": k["rola"]} if k else None

    def dodaj_konto(self, nazwa: str, haslo: str, rola: str = "asystentka") -> str:
        if not self.szyfr:
            raise PermissionError("Konta asystentek wymagają hasła właściciela (szyfrowania danych).")
        nazwa = nazwa.strip()
        if not nazwa or any(k["nazwa"].lower() == nazwa.lower() for k in self.konta()):
            raise ValueError("Podaj inną nazwę konta (np. imię asystentki).")
        if any(konta.sprawdz_haslo(w, haslo) for w in konta.wczytaj(self.sciezka.parent)):
            raise ValueError("To hasło ma już inne konto. Każde konto musi mieć własne hasło.")
        # hasło do resetu może być PIN-em, więc jego klucz jest wyliczany dużo wolniej (256 MiB, 4 przebiegi)
        parametry = konta.ARGON2_RESETU if rola == ROLA_RESETU else None
        wpis, klucz_konta = konta.nowe_konto(nazwa, haslo, rola, self.szyfr.klucz_hasla, parametry)
        klucze = self._klucze_kont()
        klucze[wpis["id"]] = {"nazwa": nazwa, "rola": rola, "klucz": base64.b64encode(klucz_konta).decode("ascii")}
        self.zapisz_ustawienia({"konta_klucze": json.dumps(klucze)})
        konta.zapisz(self.sciezka.parent, konta.wczytaj(self.sciezka.parent) + [wpis])
        return wpis["id"]

    def usun_konto(self, id_: str) -> None:
        klucze = self._klucze_kont()
        klucze.pop(id_, None)
        piny = self._piny()
        piny.pop(id_, None)
        self.zapisz_ustawienia({"konta_klucze": json.dumps(klucze), "piny": json.dumps(piny)})
        konta.zapisz(self.sciezka.parent, [w for w in konta.wczytaj(self.sciezka.parent) if w["id"] != id_])

    def ustaw_haslo_konta(self, id_: str, haslo: str) -> None:
        klucze = self._klucze_kont()
        if id_ not in klucze or not self.szyfr:
            raise KeyError(id_)
        wpisy = konta.wczytaj(self.sciezka.parent)
        if any(konta.sprawdz_haslo(w, haslo) for w in wpisy if w["id"] != id_):
            raise ValueError("To hasło ma już inne konto. Każde konto musi mieć własne hasło.")
        klucz_konta = base64.b64decode(klucze[id_]["klucz"])
        stary = next((w for w in wpisy if w["id"] == id_),
                     {"id": id_, "nazwa": klucze[id_]["nazwa"], "rola": klucze[id_]["rola"]})
        nowy = konta.nowe_haslo(stary, haslo, klucz_konta, self.szyfr.klucz_hasla)
        konta.zapisz(self.sciezka.parent, [w for w in wpisy if w["id"] != id_] + [nowy])

    # ---------- hasło (lub PIN) do resetu zapomnianego hasła ----------
    @property
    def ma_haslo_resetu(self) -> bool:
        return any(k["rola"] == ROLA_RESETU for k in self._klucze_kont().values())

    def ustaw_haslo_resetu(self, haslo: str) -> None:
        """Osobny klucz dostępu (jak konto) tylko do ustawienia nowego hasła właściciela."""
        if (blad := blad_hasla_resetu(haslo)):
            raise ValueError(blad)
        if self.sprawdz_haslo(haslo):
            raise ValueError("Hasło do resetu musi być inne niż hasło właściciela.")
        self.usun_haslo_resetu()
        self.dodaj_konto("Reset hasła", haslo, ROLA_RESETU)

    def usun_haslo_resetu(self) -> None:
        for id_, k in list(self._klucze_kont().items()):
            if k["rola"] == ROLA_RESETU:
                self.usun_konto(id_)

    # ---------- PIN szybkiego odblokowania ----------
    def _piny(self) -> dict:
        try:
            return json.loads(self.ustawienia().get("piny") or "{}")
        except ValueError:
            return {}

    def ma_pin(self, id_konta: str) -> bool:
        return id_konta in self._piny()

    @property
    def sa_piny(self) -> bool:
        return bool(self._piny())

    def ustaw_pin(self, id_konta: str, pin: str) -> None:
        if not self.szyfr:
            raise PermissionError("PIN działa tylko przy danych chronionych hasłem.")
        if not jest_pin(pin):
            raise ValueError(f"PIN musi mieć od {MIN_PIN} do {MAX_PIN} cyfr.")
        if len(set(pin)) == 1 or pin in "01234567890123" or pin in "98765432109876":
            raise ValueError("Ten PIN jest zbyt łatwy do zgadnięcia (np. 1111, 1234).")
        piny = self._piny()
        for inne, w in piny.items():
            if inne != id_konta and hmac.compare_digest(
                    klucz_argon2(pin, base64.b64decode(w["sol"]), ARGON2_PIN), base64.b64decode(w["skrot"])):
                raise ValueError("Ten PIN ma już inne konto. Każde konto musi mieć własny PIN.")
        sol = os.urandom(16)
        piny[id_konta] = {"sol": base64.b64encode(sol).decode("ascii"),
                          "skrot": base64.b64encode(klucz_argon2(pin, sol, ARGON2_PIN)).decode("ascii")}
        self.zapisz_ustawienia({"piny": json.dumps(piny), "pin_bledy": "0"})

    def usun_pin(self, id_konta: str) -> None:
        piny = self._piny()
        if piny.pop(id_konta, None) is not None:
            self.zapisz_ustawienia({"piny": json.dumps(piny)})

    @property
    def piny_zablokowane(self) -> bool:
        try:
            return int(self.ustawienia().get("pin_bledy") or 0) >= PROBY_PIN
        except ValueError:
            return True

    def sprawdz_pin(self, pin: str) -> str | None:
        """Id konta, do którego pasuje PIN (właściciel: ""), albo None. Liczy błędy; po PROBY_PIN
        błędach PIN-y nie działają, dopóki ktoś nie zaloguje się pełnym hasłem."""
        piny = self._piny()
        if not piny or not jest_pin(pin) or self.piny_zablokowane:
            return None
        for id_konta, w in piny.items():
            if id_konta and not self.konto_aktywne(id_konta):
                continue
            try:
                if hmac.compare_digest(klucz_argon2(pin, base64.b64decode(w["sol"]), ARGON2_PIN),
                                       base64.b64decode(w["skrot"])):
                    if self.ustawienia().get("pin_bledy") != "0":
                        self.zapisz_ustawienia({"pin_bledy": "0"})
                    return id_konta
            except (KeyError, ValueError):
                continue
        bledy = int(self.ustawienia().get("pin_bledy") or 0) + 1
        self.zapisz_ustawienia({"pin_bledy": str(bledy)})
        return None

    def zaloguj_pelnym_haslem(self) -> None:
        """Po zalogowaniu hasłem licznik błędnych PIN-ów się zeruje."""
        if self.ustawienia().get("pin_bledy") not in ("0", ""):
            self.zapisz_ustawienia({"pin_bledy": "0"})

    def _odnow_konta(self) -> None:
        """Po zmianie hasła właściciela: klucze danych wszystkich kont na nowo (bez haseł asystentek)."""
        klucze = self._klucze_kont()
        wpisy = konta.wczytaj(self.sciezka.parent)
        if not wpisy:
            return
        konta.zapisz(self.sciezka.parent, [
            konta.odnow_klucz_danych(w, base64.b64decode(klucze[w["id"]]["klucz"]), self.szyfr.klucz_hasla)
            for w in wpisy if w["id"] in klucze])

    # ---------- weryfikacja urządzenia ----------
    def _zapisz_weryfikator(self) -> None:
        """Weryfikator hasła dla deinstalatora (patrz szyfrowanie.weryfikator); bez hasła jest usuwany."""
        plik = self.sciezka.parent / PLIK_WERYFIKATORA
        try:
            if self.szyfr and self.szyfr.wersja >= 3:
                tymczasowy = plik.with_suffix(".tmp")
                tymczasowy.write_text(json.dumps(weryfikator(self.szyfr)), encoding="utf-8")
                os.replace(tymczasowy, plik)
            else:
                plik.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def haslo_pasuje(katalog: Path, haslo: str, sekret: bytes | None = None, plik: Path | None = None) -> bool:
        """Czy to hasło danych w katalogu (także bez sekretu urządzenia, np. z konta administratora)."""
        try:
            dane = json.loads((Path(katalog) / PLIK_WERYFIKATORA).read_text(encoding="utf-8"))
            if sprawdz_weryfikator(dane, haslo):
                return True
        except (OSError, ValueError):
            pass
        return Baza.da_sie_otworzyc(plik or Path(katalog) / "fakturnik.db", haslo, sekret)

    @property
    def weryfikacja_urzadzenia(self) -> bool:
        return bool(self.szyfr and self.szyfr.sekret)

    def powiaz_z_urzadzeniem(self, sekret: bytes | None) -> None:
        """Przepisuje plik tak, by do odczytu potrzebny był też sekret urządzenia (None = wyłącza)."""
        if not self.szyfr:
            raise PermissionError("Weryfikacja urządzenia wymaga ustawionego hasła.")
        self.szyfr = self.szyfr.z_sekretem(sekret)
        self._sekret = sekret
        self._utrwal()

    def _utrwal(self) -> None:
        """Zatwierdza zmiany i zapisuje plik atomowo (najpierw plik tymczasowy, potem podmiana)."""
        self.db.commit()
        dane = self.db.serialize()
        if self.szyfr:
            dane = self.szyfr.zaszyfruj(dane)
        tymczasowy = self.sciezka.with_suffix(".tmp")
        skrot = hashlib.sha256(dane).hexdigest()
        with open(tymczasowy, "wb") as f:
            f.write(dane)
            f.flush()
            os.fsync(f.fileno())
        self.blokada.zwolnij()
        try:
            for proba in range(10):
                try:
                    os.replace(tymczasowy, self.sciezka)
                    self._skrot_zapisu = skrot  # dopiero po udanym zapisie: inaczej strażnik spróbuje ponownie
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

    def zapamietaj_wpis_dziennika(self, skrot: str) -> None:
        """Bez osobnego zapisu na dysk: trafi do pliku przy najbliższej zmianie danych."""
        self.db.execute("INSERT OR REPLACE INTO ustawienia VALUES ('ostatni_wpis_dziennika', ?)", (skrot,))

    # ---------- numeracja ----------
    def _klucz_licznika(self, d: date, rodzaj: str) -> str:
        """Licznik zależy od tego, co jest w formacie numeru: z miesiącem liczy od nowa co miesiąc,
        tylko z rokiem co rok, bez daty ciągle. Rachunki, faktury i korekty mają osobne liczniki;
        klucz rachunków bez prefiksu (zgodność ze starszymi danymi)."""
        prefiks = {"Faktura": "FV:", "Korekta": "KOR:"}.get(rodzaj, "")
        wzor = self._wzor_numeru(rodzaj)
        if "{mm}" in wzor:
            return prefiks + f"{d.year}-{d.month:02d}"
        if "{rrrr}" in wzor or "{rr}" in wzor:
            return prefiks + f"{d.year}"
        return prefiks + "ciagly"

    def _wzor_numeru(self, rodzaj: str) -> str:
        u = self.ustawienia()
        return {"Faktura": u["format_numeru_faktury"], "Korekta": u["format_numeru_korekty"]}.get(
            rodzaj, u["format_numeru"])

    def nastepny_numer(self, d: date, rodzaj: str = "Rachunek") -> str:
        wiersz = self.db.execute("SELECT ostatni FROM liczniki WHERE miesiac = ?",
                                 (self._klucz_licznika(d, rodzaj),)).fetchone()
        n = (wiersz[0] if wiersz else 0) + 1
        return formatuj_numer(self._wzor_numeru(rodzaj), n, d)

    def _podbij_licznik(self, numer: str, d: date, rodzaj: str = "Rachunek") -> None:
        n = numer_z_wzoru(self._wzor_numeru(rodzaj), numer)
        if not n:
            return
        klucz = self._klucz_licznika(d, rodzaj)
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
        self._podbij_licznik(dok.numer, date.fromisoformat(dok.data_wystawienia), dok.tytul)
        self._zapamietaj_pacjenta(dok.nabywca, dok.nabywca_id, dok.nabywca_adres)
        self._utrwal()
        dok.id = kursor.lastrowid
        return dok

    def zaktualizuj_dokument(self, dok: Dokument, powod: str = "") -> Dokument:
        """Zapisuje poprawiony dokument pod tym samym numerem; poprzednia wersja trafia do historii zmian."""
        stary = self.db.execute("SELECT dane FROM dokumenty WHERE id = ?", (dok.id,)).fetchone()
        if not stary:
            raise KeyError(dok.id)
        self.db.execute("INSERT INTO wersje_dokumentow (dokument_id, dane, powod) VALUES (?, ?, ?)",
                        (dok.id, stary[0], powod.strip()))
        dok.poprawiono = date.today().isoformat()
        dane = asdict(dok)
        dane.pop("id")
        self.db.execute("UPDATE dokumenty SET numer = ?, data_wystawienia = ?, dane = ? WHERE id = ?",
                        (dok.numer, dok.data_wystawienia, json.dumps(dane, ensure_ascii=False), dok.id))
        self._zapamietaj_pacjenta(dok.nabywca, dok.nabywca_id, dok.nabywca_adres)
        self._utrwal()
        return dok

    def wersje(self, id_: int) -> list[tuple[str, str, Dokument]]:
        """Poprzednie wersje dokumentu: (kiedy zmieniono, powód, dokument sprzed zmiany), od najnowszej."""
        return [(kiedy, powod, dokument_z_danych(id_, json.loads(dane))) for kiedy, powod, dane in self.db.execute(
            "SELECT zmieniono, powod, dane FROM wersje_dokumentow WHERE dokument_id = ? ORDER BY id DESC", (id_,))]

    # ---------- kartoteka pacjentów ----------
    def _zapamietaj_pacjenta(self, nazwa: str, identyfikator: str = "", adres: str = "") -> None:
        nazwa = nazwa.strip()
        if not nazwa:
            return
        self.db.execute("DELETE FROM ustawienia WHERE klucz = ?", (f"ukryty_pacjent:{nazwa}",))
        self.db.execute(
            "INSERT INTO pacjenci (nazwa, identyfikator, adres) VALUES (?, ?, ?) "
            "ON CONFLICT(nazwa) DO UPDATE SET identyfikator = CASE WHEN excluded.identyfikator != '' "
            "THEN excluded.identyfikator ELSE identyfikator END, "
            "adres = CASE WHEN excluded.adres != '' THEN excluded.adres ELSE adres END",
            (nazwa, identyfikator.strip(), adres.strip()))

    def zapisz_pacjenta(self, nazwa: str, identyfikator: str = "", adres: str = "", stara_nazwa: str = "",
                        nowy: bool = False) -> None:
        """Dodaje albo poprawia pacjenta w kartotece (bez zmiany wystawionych już dokumentów)."""
        zmiana_nazwy = bool(stara_nazwa) and stara_nazwa != nazwa.strip()
        if (zmiana_nazwy or nowy) and self.db.execute(
                "SELECT 1 FROM pacjenci WHERE nazwa = ?", (nazwa.strip(),)).fetchone():
            raise ValueError(f"Pacjent „{nazwa.strip()}” już jest w kartotece. Wybierz go z listy albo popraw jego dane.")
        self.db.execute("DELETE FROM ustawienia WHERE klucz = ?", (f"ukryty_pacjent:{nazwa.strip()}",))
        if stara_nazwa and stara_nazwa != nazwa.strip():
            self.db.execute("DELETE FROM pacjenci WHERE nazwa = ?", (stara_nazwa,))
        self.db.execute("INSERT OR REPLACE INTO pacjenci (nazwa, identyfikator, adres) VALUES (?, ?, ?)",
                        (nazwa.strip(), identyfikator.strip(), adres.strip()))
        self._utrwal()

    def usun_pacjenta(self, nazwa: str) -> None:
        """Usuwa pacjenta z kartoteki; wystawione dokumenty zostają nietknięte."""
        self.db.execute("DELETE FROM pacjenci WHERE nazwa = ?", (nazwa,))
        self.db.execute("INSERT OR REPLACE INTO ustawienia VALUES (?, ?)",
                        (f"ukryty_pacjent:{nazwa}", "1"))
        self._utrwal()

    def dokumenty(self, szukaj: str = "", rok: int | None = None, miesiac: int | None = None,
                  rodzaj: str | None = None) -> list[Dokument]:
        """Dokumenty od najnowszego; `szukaj` dopasowuje nazwisko/imię, numer lub PESEL/NIP."""
        wzor = _bez_ogonkow(szukaj.strip())
        prefiks = f"{rok:04d}-" if rok else ""
        if rok and miesiac:
            prefiks += f"{miesiac:02d}-"
        wynik = []
        for id_, dane in self.db.execute(
                "SELECT id, dane FROM dokumenty WHERE data_wystawienia LIKE ? ORDER BY data_wystawienia DESC, id DESC",
                (prefiks + "%",)):
            dok = dokument_z_danych(id_, json.loads(dane))
            if miesiac and not rok and int(dok.data_wystawienia[5:7]) != miesiac:
                continue
            if rodzaj and dok.tytul != rodzaj:
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
        return dokument_z_danych(id_, json.loads(wiersz[0]))

    def _zapisz_zmiane(self, dok: Dokument) -> Dokument:
        dane = asdict(dok)
        dane.pop("id")
        self.db.execute("UPDATE dokumenty SET dane = ? WHERE id = ?", (json.dumps(dane, ensure_ascii=False), dok.id))
        self._utrwal()
        return dok

    def anuluj(self, id_: int, powod: str = "") -> Dokument:
        """Oznacza dokument jako anulowany. Nie usuwa go, żeby numeracja nie miała dziur."""
        dok = self.dokument(id_)
        if dok is None:
            raise KeyError(id_)
        dok.anulowano = date.today().isoformat()
        dok.powod_anulowania = powod.strip()
        return self._zapisz_zmiane(dok)

    # ---------- RODO ----------
    @staticmethod
    def granica_retencji(lat: int, dzis: date | None = None) -> int:
        """Ostatni rok, którego dokumenty można już zanonimizować (rok wystawienia + `lat` pełnych lat)."""
        return (dzis or date.today()).year - lat - 1

    def do_anonimizacji(self, lat: int, dzis: date | None = None) -> int:
        granica = self.granica_retencji(lat, dzis)
        return sum(1 for d in self.dokumenty() if int(d.data_wystawienia[:4]) <= granica
                   and d.nabywca != ZANONIMIZOWANO)

    def anonimizuj_starsze(self, lat: int, dzis: date | None = None) -> int:
        """Usuwa dane osobowe z dokumentów po okresie przechowywania (numery i kwoty zostają do rozliczeń).

        Czyści nabywcę, PESEL/NIP i adres w dokumentach, ich wcześniejszych wersjach, kartotece
        pacjentów (gdy pacjent nie ma nowszych dokumentów) i opisach wrzuconych plików z tych lat.
        Zwraca liczbę zanonimizowanych dokumentów.
        """
        if lat < 1:
            raise ValueError("Okres przechowywania musi wynosić co najmniej rok.")
        granica = self.granica_retencji(lat, dzis)
        stare, nowsi = [], set()
        for d in self.dokumenty():
            if int(d.data_wystawienia[:4]) > granica:
                nowsi.add(d.nabywca)
            elif d.nabywca != ZANONIMIZOWANO:
                stare.append(d)
        for d in stare:
            nazwa = d.nabywca
            d.nabywca, d.nabywca_id, d.nabywca_adres = ZANONIMIZOWANO, "", ""
            dane = asdict(d)
            dane.pop("id")
            self.db.execute("UPDATE dokumenty SET dane = ? WHERE id = ?", (json.dumps(dane, ensure_ascii=False), d.id))
            for id_wersji, surowe in list(self.db.execute(
                    "SELECT id, dane FROM wersje_dokumentow WHERE dokument_id = ?", (d.id,))):
                w = json.loads(surowe)
                w.update(nabywca=ZANONIMIZOWANO, nabywca_id="", nabywca_adres="")
                self.db.execute("UPDATE wersje_dokumentow SET dane = ? WHERE id = ?",
                                (json.dumps(w, ensure_ascii=False), id_wersji))
            if nazwa not in nowsi:
                self.db.execute("DELETE FROM pacjenci WHERE nazwa = ?", (nazwa,))
                self.db.execute("DELETE FROM ustawienia WHERE klucz = ?", (f"ukryty_pacjent:{nazwa}",))
        self.db.execute("UPDATE pliki SET osoba = '', opis = '' WHERE CAST(substr(data, 1, 4) AS INTEGER) <= ?",
                        (granica,))
        for d in stare:
            self.db.execute("UPDATE wersje_dokumentow SET powod = '' WHERE dokument_id = ?", (d.id,))
            # PDF-y tych dokumentów w Plikach zawierają dane osobowe, więc znikają razem z nimi
            for plik_id, in list(self.db.execute("SELECT plik_id FROM pliki_dokumentow WHERE dokument_id = ?",
                                                 (d.id,))):
                self._usun_plik(plik_id)
        self.db.commit()
        self.db.execute("VACUUM")  # przepisuje bazę od nowa, bez śladów starych wartości
        self._utrwal()
        return len(stare)

    def dokumenty_pacjenta(self, nazwa: str) -> list[Dokument]:
        """Wszystkie dokumenty jednej osoby (prawo dostępu do danych, art. 15 RODO)."""
        return [d for d in self.dokumenty() if d.nabywca == nazwa]



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
        """Kartoteka pacjentów (zapamiętani + nabywcy z dokumentów), alfabetycznie po nazwisku."""
        ukryci = {k.split(":", 1)[1] for k, in self.db.execute(
            "SELECT klucz FROM ustawienia WHERE klucz LIKE 'ukryty_pacjent:%'")}
        zebrani: dict[str, Pacjent] = {}
        for dok in self.dokumenty():
            if dok.nabywca in ukryci or dok.nabywca == ZANONIMIZOWANO:
                continue
            p = zebrani.get(dok.nabywca)
            if p is None:
                p = zebrani[dok.nabywca] = Pacjent(dok.nabywca, dok.nabywca_adres, dok.nabywca_id,
                                                   dok.data_wystawienia, 0, 0.0)
            p.dokumentow += 1
            if dok.wazny:
                p.suma = round(p.suma + dok.suma, 2)
        for nazwa, identyfikator, adres in self.db.execute("SELECT nazwa, identyfikator, adres FROM pacjenci"):
            p = zebrani.get(nazwa)
            if p is None:
                zebrani[nazwa] = Pacjent(nazwa, adres, identyfikator, "", 0, 0.0)
            else:  # dane z kartoteki są nowsze niż z dokumentów
                p.adres = adres or p.adres
                p.identyfikator = identyfikator or p.identyfikator
        wzor = _bez_ogonkow(szukaj.strip())
        wynik = [p for p in zebrani.values()
                 if not wzor or all(s in _bez_ogonkow(f"{p.nazwa} {p.identyfikator}") for s in wzor.split())]
        return sorted(wynik, key=lambda p: (_bez_ogonkow(p.nazwisko), _bez_ogonkow(p.nazwa)))

    def pacjent(self, nazwa: str) -> Pacjent | None:
        return next((p for p in self.pacjenci() if p.nazwa == nazwa), None)

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
                w.writerow([bezpieczna_komorka(x) for x in [d.numer, d.data_wystawienia, d.data_uslugi, d.nabywca, d.nabywca_id,
                            d.nabywca_adres.replace("\n", ", "),
                            " | ".join(f"{p.nazwa} x{p.ilosc:g}" for p in d.pozycje),
                            d.platnosc, f"{d.suma:.2f}".replace(".", ","),
                            f"anulowany {d.anulowano}" if d.anulowano else "ważny"]])
        return len(dokumenty)

    def przywroc(self, zrodlo: Path | str, haslo: str | None = None) -> None:
        """Zastępuje dane kopią zapasową; obecne hasło (szyfrowanie) zostaje."""
        zrodlo = Path(zrodlo)
        if self.czy_kopia_szyfrowana(zrodlo):
            if haslo is None:
                raise PermissionError("Kopia jest zaszyfrowana hasłem.")
            zawartosc = io.BytesIO(odszyfruj_kopie(zrodlo.read_bytes(), haslo))
            with zipfile.ZipFile(zawartosc) as z:
                dane = z.read("fakturnik.db")
                if not dane.startswith(b"SQLite format 3"):
                    raise ValueError("To nie jest kopia Fakturnika.")
                self.katalog_plikow.mkdir(parents=True, exist_ok=True)
                for nazwa in z.namelist():
                    cel = self.katalog_plikow / Path(nazwa).name
                    if nazwa.startswith("pliki/") and nazwa.endswith(".bin") and not cel.exists():
                        cel.write_bytes(z.read(nazwa))
        elif zipfile.is_zipfile(zrodlo):
            with zipfile.ZipFile(zrodlo) as z:
                tymczasowy = self.sciezka.with_name("przywracanie.tmp")
                tymczasowy.write_bytes(z.read("fakturnik.db"))
                try:
                    dane = self._wczytaj(tymczasowy, haslo)
                finally:
                    tymczasowy.unlink(missing_ok=True)
                self.katalog_plikow.mkdir(parents=True, exist_ok=True)
                for nazwa in z.namelist():
                    cel = self.katalog_plikow / Path(nazwa).name
                    if nazwa.startswith("pliki/") and nazwa.endswith(".bin") and not cel.exists():
                        cel.write_bytes(z.read(nazwa))
        else:
            dane = self._wczytaj(zrodlo, haslo)
        proba = sqlite3.connect(":memory:")
        proba.deserialize(dane)
        if wersja_danych(proba) > WERSJA_DANYCH:
            raise NowszaBaza("Kopia pochodzi z nowszej wersji Fakturnika. Najpierw zaktualizuj program.")
        self.db.deserialize(dane)
        self._migruj(kopia_przed=False)
        self._utrwal()

    def kopia_zapasowa(self, cel: Path | str) -> None:
        """Kopia danych w tym samym formacie co plik danych (zaszyfrowana, jeśli jest hasło).

        Gdy `cel` ma rozszerzenie .zip, kopia zawiera też wszystkie wrzucone pliki (zaszyfrowane).
        """
        self._utrwal()
        cel = Path(cel)
        if cel.suffix.lower() != ".zip":
            cel.write_bytes(self.sciezka.read_bytes())
            return
        with zipfile.ZipFile(cel, "w", zipfile.ZIP_STORED) as z:
            z.writestr("fakturnik.db", self.sciezka.read_bytes())
            for nazwa in self._nazwy_plikow():
                sciezka = self.katalog_plikow / nazwa
                if sciezka.exists():
                    z.write(sciezka, f"pliki/{nazwa}")

    def sprawdz_integralnosc(self, katalog_kopii_plikow: Path | None = None) -> list[str]:
        """Sprawdza, czy nikt nie zmienił ani nie usunął danych poza programem, i naprawia, co się da.

        Plik danych: program ma w pamięci aktualną bazę, więc zmieniony lub usunięty plik odtwarza.
        Wrzucone pliki: brakujące przywraca z kopii automatycznych (jeśli tam są).
        Zwraca listę komunikatów o tym, co wykryto (pusta = wszystko w porządku).
        """
        problemy = []
        try:
            na_dysku = hashlib.sha256(self.sciezka.read_bytes()).hexdigest() if self.sciezka.exists() else ""
        except OSError:
            na_dysku = None  # plik chwilowo zablokowany przez system – sprawdzimy następnym razem
        if na_dysku is not None and na_dysku != self._skrot_zapisu:
            self._utrwal()
            problemy.append("Plik danych został " + ("usunięty" if not na_dysku else "zmieniony")
                            + " poza programem. Odtworzono go z aktualnych danych programu.")
        for id_, nazwa, plik, skrot_dysk, skrot_tresci in self.db.execute(
                "SELECT id, plik, nazwa, sha256_dysk, sha256 FROM pliki").fetchall():
            if not NAZWA_PLIKU_NA_DYSKU.fullmatch(nazwa):
                continue
            sciezka = self.katalog_plikow / nazwa
            kopia = katalog_kopii_plikow / nazwa if katalog_kopii_plikow else None
            if sciezka.exists():
                # zawartość pliku na dysku: porównanie ze skrótem zapisanym przy dodaniu
                try:
                    dane = sciezka.read_bytes()
                except OSError:
                    continue
                skrot = hashlib.sha256(dane).hexdigest()
                if not skrot_dysk:  # plik dodany przed tą wersją: zapamiętaj skrót, jeśli treść się zgadza
                    try:
                        if hashlib.sha256(odszyfruj_plik(dane, self._klucz_plikow())).hexdigest() == skrot_tresci:
                            self.db.execute("UPDATE pliki SET sha256_dysk = ? WHERE id = ?", (skrot, id_))
                            self._utrwal()
                            continue
                    except ValueError:
                        pass
                elif skrot == skrot_dysk:
                    continue
                if kopia and kopia.exists() and (not skrot_dysk or
                                                 hashlib.sha256(kopia.read_bytes()).hexdigest() == skrot_dysk):
                    tylko_do_odczytu(sciezka, False)
                    shutil.copyfile(kopia, sciezka)
                    tylko_do_odczytu(sciezka, True)
                    problemy.append(f"Plik nr {id_} został zmieniony poza programem. Przywrócono oryginał z kopii.")
                else:
                    problemy.append(f"Plik nr {id_} został zmieniony poza programem i nie ma go w kopiach. "
                                    "Przywróć pełną kopię zapasową.")
                continue
            if kopia and kopia.exists():
                self.katalog_plikow.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(kopia, sciezka)
                tylko_do_odczytu(sciezka, True)
                problemy.append(f"Plik „{plik}” został usunięty poza programem. Przywrócono go z kopii.")
            else:
                problemy.append(f"Brak pliku „{plik}” i nie ma go w kopiach. Przywróć pełną kopię zapasową.")
        self.blokada.zaloz()
        return problemy

    def kopia_zaszyfrowana(self, cel: Path | str, haslo: str) -> None:
        """Jeden plik .fkopia: dane i wrzucone pliki zaszyfrowane AES-256 osobnym hasłem kopii."""
        bufor = io.BytesIO()
        with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
            self.db.commit()
            z.writestr("fakturnik.db", self.db.serialize())  # w środku jawna baza; chroni ją hasło kopii
            for nazwa in self._nazwy_plikow():
                sciezka = self.katalog_plikow / nazwa
                if sciezka.exists():
                    z.write(sciezka, f"pliki/{nazwa}")
        tymczasowy = Path(str(cel) + ".tmp")
        tymczasowy.write_bytes(zaszyfruj_kopie(bufor.getvalue(), haslo))
        os.replace(tymczasowy, cel)

    @staticmethod
    def czy_kopia_szyfrowana(sciezka: Path | str) -> bool:
        with open(sciezka, "rb") as f:
            return czy_kopia_szyfrowana(f.read(32))

    def kopia_plikow(self, katalog: Path) -> int:
        """Dokłada do `katalog` pliki, których tam jeszcze nie ma (pliki nigdy się nie zmieniają)."""
        katalog.mkdir(parents=True, exist_ok=True)
        dodano = 0
        for nazwa in self._nazwy_plikow():
            zrodlo, cel = self.katalog_plikow / nazwa, katalog / nazwa
            if zrodlo.exists() and not cel.exists():
                shutil.copyfile(zrodlo, cel)
                dodano += 1
        return dodano

    # ---------- wrzucone pliki ----------
    def _nazwy_plikow(self) -> list[str]:
        """Nazwy plików na dysku; nazwy spoza wzoru (np. z podrobionej kopii: „../..”) są pomijane."""
        return [n for n, in self.db.execute("SELECT plik FROM pliki") if NAZWA_PLIKU_NA_DYSKU.fullmatch(n)]

    def _sciezka_pliku(self, nazwa: str) -> Path:
        if not NAZWA_PLIKU_NA_DYSKU.fullmatch(nazwa):
            raise ValueError("Nieprawidłowa nazwa pliku w bazie.")
        return self.katalog_plikow / nazwa

    def _klucz_plikow(self) -> bytes:
        zapisany = self.ustawienia().get("klucz_plikow")
        if zapisany:
            return base64.b64decode(zapisany)
        klucz = nowy_klucz()
        self.zapisz_ustawienia({"klucz_plikow": base64.b64encode(klucz).decode("ascii")})
        return klucz

    @staticmethod
    def _plik_z_wiersza(w) -> Plik:
        return Plik(id=w[0], nazwa=w[1], typ=w[2], rozmiar=w[3], data=w[4], kategoria=w[5], osoba=w[6],
                    opis=w[7], dodano=w[8] or "")

    _POLA_PLIKU = "id, nazwa, typ, rozmiar, data, kategoria, osoba, opis, dodano"

    def dodaj_plik(self, zrodlo: Path | str, data: str | None = None, kategoria: str = "", osoba: str = "",
                   opis: str = "") -> Plik:
        zrodlo = Path(zrodlo)
        return self.dodaj_plik_z_bajtow(zrodlo.name, zrodlo.read_bytes(), data, kategoria, osoba, opis)

    def dodaj_plik_z_bajtow(self, nazwa: str, tresc: bytes, data: str | None = None, kategoria: str = "",
                            osoba: str = "", opis: str = "", utrwal: bool = True) -> Plik:
        zrodlo = Path(nazwa)
        typ = zrodlo.suffix.lower().lstrip(".")
        if typ not in TYPY_PLIKOW:
            raise ValueError(f"Nieobsługiwany rodzaj pliku: {zrodlo.name}. Można dodać PDF lub zdjęcie.")
        from .skaner import typ_z_zawartosci
        if typ_z_zawartosci(tresc) in ("exe", "skrypt"):
            raise ValueError(f"Plik {zrodlo.name} to program, a nie dokument. Nie został dodany.")
        if len(tresc) > MAKS_ROZMIAR_PLIKU:
            raise ValueError(f"Plik {zrodlo.name} jest za duży (maksymalnie {MAKS_ROZMIAR_PLIKU // 2**20} MB).")
        self.katalog_plikow.mkdir(parents=True, exist_ok=True)
        nazwa_na_dysku = f"{uuid.uuid4().hex}.bin"
        cel = self.katalog_plikow / nazwa_na_dysku
        tymczasowy = cel.with_suffix(".tmp")
        zaszyfrowane = zaszyfruj_plik(tresc, self._klucz_plikow())
        with open(tymczasowy, "wb") as f:
            f.write(zaszyfrowane)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tymczasowy, cel)
        tylko_do_odczytu(cel, True)
        kursor = self.db.execute(
            "INSERT INTO pliki (nazwa, typ, rozmiar, plik, sha256, data, kategoria, osoba, opis, sha256_dysk) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (zrodlo.name, typ, len(tresc), nazwa_na_dysku, hashlib.sha256(tresc).hexdigest(),
             data or date.today().isoformat(), kategoria, osoba.strip(), opis.strip(),
             hashlib.sha256(zaszyfrowane).hexdigest()))
        if utrwal:
            self._utrwal()
        return self.plik(kursor.lastrowid)

    # ---------- wystawione dokumenty w Plikach ----------
    @staticmethod
    def odcisk_dokumentu(dok: Dokument) -> str:
        """Skrót treści dokumentu: nowy PDF w Plikach powstaje tylko, gdy dokument naprawdę się zmienił."""
        dane = asdict(dok)
        dane.pop("id", None)
        return hashlib.sha256(json.dumps(dane, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def dokument_w_plikach(self, dok: Dokument) -> bool:
        return self.db.execute("SELECT 1 FROM pliki_dokumentow WHERE dokument_id = ? AND odcisk = ?",
                               (dok.id, self.odcisk_dokumentu(dok))).fetchone() is not None

    def dodaj_pdf_dokumentu(self, dok: Dokument, pdf: bytes) -> Plik | None:
        """Zapisuje PDF wystawionego dokumentu w Plikach (raz dla każdej wersji dokumentu)."""
        if dok.id is None:
            raise ValueError("Dokument nie jest zapisany.")
        if self.dokument_w_plikach(dok):
            return None
        stan = "anulowany" if dok.anulowano else ("poprawiony" if dok.poprawiono else "")
        numer = dok.numer.replace("/", "-")
        nazwa = f"{dok.tytul} {numer}{' ' + stan if stan else ''}.pdf"
        opis = f"{dok.tytul} nr {dok.numer}" + (f" ({stan} {dok.anulowano or dok.poprawiono})" if stan else "")
        plik = self.dodaj_plik_z_bajtow(nazwa, pdf, dok.data_wystawienia, KATEGORIA_WYSTAWIONE, dok.nabywca,
                                        opis, utrwal=False)
        self.db.execute("INSERT OR REPLACE INTO pliki_dokumentow (dokument_id, odcisk, plik_id) VALUES (?, ?, ?)",
                        (dok.id, self.odcisk_dokumentu(dok), plik.id))
        self._utrwal()
        return plik

    def dokumenty_bez_pdf(self) -> list[Dokument]:
        """Dokumenty, których bieżąca wersja nie ma jeszcze PDF-u w Plikach."""
        return [d for d in self.dokumenty() if not self.dokument_w_plikach(d)]

    def plik(self, id_: int) -> Plik | None:
        w = self.db.execute(f"SELECT {self._POLA_PLIKU} FROM pliki WHERE id = ?", (id_,)).fetchone()
        return self._plik_z_wiersza(w) if w else None

    def tresc_pliku(self, id_: int) -> bytes:
        """Odszyfrowana treść pliku; sprawdza też, czy plik nie został podmieniony."""
        w = self.db.execute("SELECT plik, sha256 FROM pliki WHERE id = ?", (id_,)).fetchone()
        if not w:
            raise KeyError(id_)
        sciezka = self._sciezka_pliku(w[0])
        if not sciezka.exists():
            raise FileNotFoundError("Brak pliku na dysku. Przywróć go z kopii zapasowej.")
        tresc = odszyfruj_plik(sciezka.read_bytes(), self._klucz_plikow())
        if hashlib.sha256(tresc).hexdigest() != w[1]:
            raise ValueError("Suma kontrolna pliku się nie zgadza.")
        return tresc

    def pliki(self, szukaj: str = "", rok: int | None = None, miesiac: int | None = None,
              kategoria: str | None = None) -> list[Plik]:
        wzor = _bez_ogonkow(szukaj.strip())
        wynik = []
        for w in self.db.execute(f"SELECT {self._POLA_PLIKU} FROM pliki ORDER BY data DESC, id DESC"):
            p = self._plik_z_wiersza(w)
            if rok and int(p.data[:4]) != rok:
                continue
            if miesiac and int(p.data[5:7]) != miesiac:
                continue
            if kategoria and p.kategoria != kategoria:
                continue
            if wzor and not all(s in _bez_ogonkow(f"{p.nazwa} {p.osoba} {p.opis} {p.kategoria}")
                                for s in wzor.split()):
                continue
            wynik.append(p)
        return wynik

    @property
    def pliki_zmienialne(self) -> bool:
        """Pliki są niezmienialne (archiwum): opis i usuwanie tylko po włączeniu w ustawieniach deweloperskich."""
        return self.ustawienia().get("pliki_edycja") == "1"

    def zmien_plik(self, id_: int, data: str, kategoria: str, osoba: str, opis: str) -> None:
        if not self.pliki_zmienialne:
            raise PermissionError("Pliki są tylko do odczytu.")
        self.db.execute("UPDATE pliki SET data = ?, kategoria = ?, osoba = ?, opis = ? WHERE id = ?",
                        (data, kategoria, osoba.strip(), opis.strip(), id_))
        self._utrwal()

    def usun_plik(self, id_: int) -> None:
        if not self.pliki_zmienialne:
            raise PermissionError("Pliki są tylko do odczytu.")
        self._usun_plik(id_)

    def _usun_plik(self, id_: int) -> None:
        w = self.db.execute("SELECT plik FROM pliki WHERE id = ?", (id_,)).fetchone()
        if not w:
            return
        self.db.execute("DELETE FROM pliki WHERE id = ?", (id_,))
        self.db.execute("DELETE FROM pliki_dokumentow WHERE plik_id = ?", (id_,))
        self._utrwal()
        sciezka = self._sciezka_pliku(w[0])
        if sciezka.exists():
            tylko_do_odczytu(sciezka, False)
            sciezka.unlink()

    def lata_plikow(self) -> list[int]:
        return [int(r[0]) for r in self.db.execute("SELECT DISTINCT substr(data, 1, 4) FROM pliki ORDER BY 1 DESC")]
