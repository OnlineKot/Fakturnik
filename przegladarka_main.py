"""Bezpieczna przeglądarka Fakturnika jako osobny program (FakturnikPrzegladarka.exe).

Osobny plik, bo silnik przeglądarki (Chromium) jest duży: główny Fakturnik.exe zostaje mały
i szybko się uruchamia, a przeglądarka startuje dopiero, gdy jest potrzebna.
"""

import os
import sys

# Zmienne PyInstallera tego procesu nie mogą przejść do programów, które uruchamiamy (instalator,
# przeglądarka, nowa wersja): wskazywałyby im nasz folder tymczasowy, który znika po zamknięciu,
# a wtedy nowy proces kończy się błędem „Failed to load Python DLL”.
for _zmienna in [k for k in os.environ if k.startswith(("_PYI", "_MEI"))]:
    del os.environ[_zmienna]
os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

# wtyczki Qt tylko z programu: zmienne środowiskowe użytkownika nie podsuną obcej biblioteki
for _zmienna in [k for k in os.environ if k.startswith(("QT_PLUGIN", "QT_QPA_PLATFORM_PLUGIN", "QML2_IMPORT", "QML_IMPORT"))]:
    del os.environ[_zmienna]

from fakturnik.przegladarka import uruchom_przegladarke

if __name__ == "__main__":
    sys.exit(uruchom_przegladarke(sys.argv[1:] if "--przegladarka" in sys.argv else ["--przegladarka", *sys.argv[1:]]))
