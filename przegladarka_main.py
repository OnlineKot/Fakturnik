"""Bezpieczna przeglądarka Fakturnika jako osobny program (FakturnikPrzegladarka.exe).

Osobny plik, bo silnik przeglądarki (Chromium) jest duży: główny Fakturnik.exe zostaje mały
i szybko się uruchamia, a przeglądarka startuje dopiero, gdy jest potrzebna.
"""

import sys

from fakturnik.przegladarka import uruchom_przegladarke

if __name__ == "__main__":
    sys.exit(uruchom_przegladarke(sys.argv[1:] if "--przegladarka" in sys.argv else ["--przegladarka", *sys.argv[1:]]))
