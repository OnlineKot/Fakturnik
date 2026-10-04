"""Kontrola komputera przy każdym uruchomieniu: czy wszystko, co chroni dane, działa.

Każde sprawdzenie zwraca stan: True (w porządku), False (problem albo zalecenie) lub None (nie da się
sprawdzić, np. poza Windows). Ostrzeżenie można zignorować (np. komputer bez Secure Boot); zignorowane
ostrzeżenie wraca samo, gdy sprawa się rozwiąże i potem znów popsuje, a w Ustawieniach można
przywrócić wszystkie naraz.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import aktualizacje, urzadzenie, usluga
from .ochrona import katalog_kopii, lista_kopii


@dataclass
class Wynik:
    klucz: str
    nazwa: str
    stan: bool | None
    opis: str
    rada: str = ""
    waga: str = "problem"  # "problem" albo "zalecenie"

    @property
    def ostrzezenie(self) -> bool:
        return self.stan is False


def kontrola(baza, dziennik_ok: bool, program_ok: bool | None) -> list[Wynik]:
    """`dziennik_ok`: łańcuch dziennika cały i nieucięty; `program_ok`: wynik porównania .exe z wydaniem."""
    wyniki = []
    wyniki.append(Wynik("haslo", "Hasło i szyfrowanie", baza.ma_haslo,
                        "Dane zaszyfrowane AES-256" if baza.ma_haslo else "Dane nie są chronione hasłem",
                        "Ustaw hasło w Ustawieniach → Bezpieczeństwo."))
    sprawdzanie = baza.ustawienia().get("sprawdzaj_plik_programu", "1") == "1"
    if not sprawdzanie:
        program_ok = None
    elif program_ok is None and aktualizacje.czy_spakowany():
        program_ok = usluga.stan_programu()  # wynik usługi z ostatniego startu komputera lub godziny
    wyniki.append(Wynik("program", "Oryginalny plik programu", program_ok,
                        {True: "Zgodny z opublikowanym wydaniem (SHA-256)",
                         False: "Różni się od opublikowanego wydania",
                         None: "Sprawdzane przez internet (w wersji .exe)" if sprawdzanie
                         else "Sprawdzanie wyłączone w ustawieniach deweloperskich"}[program_ok],
                        "Pobierz instalator ponownie ze strony wydań i nie wpisuj hasła w tej kopii."))
    sb = urzadzenie.secure_boot()
    wyniki.append(Wynik("secure_boot", "Secure Boot", sb,
                        {True: "Włączony", False: "Wyłączony", None: "Nie da się sprawdzić na tym komputerze"}[sb],
                        "Włącz Secure Boot w ustawieniach UEFI/BIOS komputera (chroni przed złośliwym "
                        "oprogramowaniem uruchamianym przed Windows).", "zalecenie"))
    admin = aktualizacje.zainstalowany() if aktualizacje.czy_spakowany() else None
    wyniki.append(Wynik("instalacja", "Instalacja z uprawnieniami administratora", admin,
                        {True: "Program Files, chroniony przed zmianą", False: "Program może zmienić zwykłe konto",
                         None: "Wersja ze źródeł"}[admin],
                        "Ustawienia → Komputer i urządzenie → Zainstaluj z uprawnieniami administratora."))
    if admin:
        ostatnia = usluga.ostatnia_kopia_chroniona()
        swieza = None
        if ostatnia:
            try:
                swieza = datetime.now() - datetime.strptime(ostatnia, "%Y-%m-%d %H:%M") < timedelta(hours=26)
            except ValueError:
                swieza = None
        wyniki.append(Wynik("usluga", "Usługa kopii chronionych", bool(swieza),
                            f"Ostatnia kopia: {ostatnia}" if ostatnia else "Brak kopii usługi",
                            "Uruchom instalator ponownie, żeby odtworzyć usługę kopii."))
    kopie = lista_kopii(katalog_kopii())
    swieza = bool(kopie) and datetime.now() - datetime.fromtimestamp(kopie[0].stat().st_mtime) < timedelta(days=2)
    wyniki.append(Wynik("kopie", "Kopie w Dokumentach", swieza if kopie else None,
                        f"Ostatnia: {datetime.fromtimestamp(kopie[0].stat().st_mtime):%d.%m.%Y %H:%M}" if kopie
                        else "Jeszcze nie ma kopii", "Sprawdź, czy folder Dokumenty jest dostępny."))
    wyniki.append(Wynik("dziennik", "Dziennik logowań", dziennik_ok,
                        "Nienaruszony (łańcuch SHA-256)" if dziennik_ok else "Zmieniony, ucięty lub usunięto wpisy",
                        "Jeśli to nie Ty, zgłoś to. Po sprawdzeniu możesz rozpocząć nowy dziennik (stary zostaje)."))
    wyniki.append(Wynik("urzadzenie", "Weryfikacja urządzenia", baza.weryfikacja_urzadzenia if baza.ma_haslo else None,
                        "Włączona" if baza.weryfikacja_urzadzenia else "Wyłączona",
                        "Ustawienia → Komputer i urządzenie → Włącz weryfikację urządzenia.", "zalecenie"))
    konto = urzadzenie.konto_administratora()
    wyniki.append(Wynik("konto", "Konto Windows do pracy", None if konto is None else not konto,
                        {True: "Administrator", False: "Zwykłe konto", None: "Nie da się sprawdzić"}[konto],
                        "Do codziennej pracy bezpieczniej używać zwykłego konta Windows.", "zalecenie"))
    return wyniki


def zignorowane(baza) -> set[str]:
    return {k for k in baza.ustawienia().get("ostrzezenia_zignorowane", "").split(",") if k}


def do_pokazania(baza, wyniki: list[Wynik]) -> list[Wynik]:
    """Ostrzeżenia, których użytkownik nie zignorował. Zignorowane, które przestały być problemem,
    są zdejmowane z listy (żeby wróciły, gdy problem się powtórzy)."""
    ignor = zignorowane(baza)
    rozwiazane = {w.klucz for w in wyniki if w.stan is True} & ignor
    if rozwiazane:
        zapisz_zignorowane(baza, ignor - rozwiazane)
    return [w for w in wyniki if w.ostrzezenie and w.klucz not in ignor]


def zapisz_zignorowane(baza, klucze: set[str]) -> None:
    baza.zapisz_ustawienia({"ostrzezenia_zignorowane": ",".join(sorted(klucze))})
