"""Dodatki tylko dla Windows: ochrona okien przed nagrywaniem ekranu, restart po aktualizacji systemu,
grupowanie na pasku zadań i znacznik działającego programu dla instalatora.

Każda funkcja poza Windows (lub gdy funkcja systemu jest niedostępna) po prostu nic nie robi,
a błąd wywołania systemowego nigdy nie zatrzymuje programu.
"""

import sys

ID_APLIKACJI = "TeodorTeo.Fakturnik"
NAZWA_MUTEKSU = "FakturnikUruchomiony"  # ten sam w instalatorze (AppMutex): instalator poprosi o zamknięcie

WDA_NONE = 0x0
WDA_MONITOR = 0x1
WDA_EXCLUDEFROMCAPTURE = 0x11  # Windows 10 2004 i nowsze: okno znika z nagrań i zrzutów ekranu

_muteks = None


def na_windows() -> bool:
    return sys.platform == "win32"


def przygotuj_proces() -> None:
    """Wywoływane raz przy starcie programu."""
    if not na_windows():
        return
    import ctypes
    global _muteks
    try:
        # własna ikona i nazwa na pasku zadań oraz w powiadomieniach (zamiast „python”)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APLIKACJI)
    except (AttributeError, OSError):
        pass
    try:
        _muteks = ctypes.windll.kernel32.CreateMutexW(None, False, NAZWA_MUTEKSU)
    except (AttributeError, OSError):
        pass
    try:
        # po ponownym uruchomieniu komputera przez aktualizację Windows program wraca sam (w tle)
        ctypes.windll.kernel32.RegisterApplicationRestart("--w-tle --restart", 0)
    except (AttributeError, OSError):
        pass


def ochrona_przed_przechwytywaniem(okno_hwnd: int, wlacz: bool) -> bool:
    """Wyłącza (lub przywraca) widoczność okna w zrzutach i nagraniach ekranu innych programów.

    Programy robiące zrzuty ekranu (także narzędzia AI „sterujące komputerem”, nagrywarki i większość
    programów zdalnego dostępu) zobaczą w tym miejscu czarny prostokąt. Zwraca True, gdy się udało.
    """
    if not na_windows() or not okno_hwnd:
        return False
    import ctypes
    from ctypes import wintypes
    try:
        ustaw = ctypes.windll.user32.SetWindowDisplayAffinity
    except (AttributeError, OSError):
        return False
    ustaw.argtypes = [wintypes.HWND, wintypes.DWORD]
    ustaw.restype = wintypes.BOOL
    if not wlacz:
        return bool(ustaw(okno_hwnd, WDA_NONE))
    return bool(ustaw(okno_hwnd, WDA_EXCLUDEFROMCAPTURE) or ustaw(okno_hwnd, WDA_MONITOR))


# ---------------------------------------------------------------- blokowanie i odblokowanie komputera

WM_WTSSESSION_CHANGE = 0x02B1
ZDARZENIA_SESJI = {
    0x1: "podłączono konsolę", 0x2: "odłączono konsolę",
    0x3: "ZDALNE POŁĄCZENIE z komputerem", 0x4: "zakończono zdalne połączenie",
    0x5: "zalogowano do Windows", 0x6: "wylogowano z Windows",
    0x7: "komputer zablokowany", 0x8: "komputer odblokowany",
}
BLOKADA, ODBLOKOWANIE = 0x7, 0x8


def sledz_sesje(okno_hwnd: int) -> bool:
    """Prosi Windows o powiadomienia o blokowaniu, odblokowaniu, logowaniu i połączeniach zdalnych."""
    if not na_windows() or not okno_hwnd:
        return False
    import ctypes
    from ctypes import wintypes
    try:
        rejestruj = ctypes.windll.wtsapi32.WTSRegisterSessionNotification
        rejestruj.argtypes = [wintypes.HWND, wintypes.DWORD]
        return bool(rejestruj(okno_hwnd, 0))  # NOTIFY_FOR_THIS_SESSION
    except (AttributeError, OSError):
        return False


def zdarzenie_sesji(wiadomosc_wskaznik: int) -> int | None:
    """Z komunikatu okna (nativeEvent) odczytuje zdarzenie sesji Windows albo None."""
    from ctypes import wintypes
    msg = wintypes.MSG.from_address(wiadomosc_wskaznik)
    return int(msg.wParam) if msg.message == WM_WTSSESSION_CHANGE else None


def nieudane_logowania(od) -> int | None:
    """Liczba nieudanych prób zalogowania lub odblokowania Windows od chwili `od` (zdarzenie 4625
    w dzienniku zabezpieczeń). Wymaga uprawnień administratora; None, gdy nie da się sprawdzić."""
    if not na_windows():
        return None
    import subprocess
    from datetime import timezone
    od_utc = od.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    zapytanie = f"*[System[(EventID=4625) and TimeCreated[@SystemTime>='{od_utc}']]]"
    try:
        wynik = subprocess.run(["wevtutil", "qe", "Security", f"/q:{zapytanie}", "/f:xml", "/c:200"],
                               capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    if wynik.returncode != 0:
        return None  # brak uprawnień do dziennika zabezpieczeń
    return wynik.stdout.count(b"<Event ")


# ---------------------------------------------------------------- tapeta pulpitu

SPI_GETDESKWALLPAPER = 0x0073
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE_SENDCHANGE = 0x01 | 0x02


def obecna_tapeta() -> str | None:
    if not na_windows():
        return None
    import ctypes
    bufor = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(bufor), bufor, 0):
        return bufor.value or None
    return None


def ustaw_tapete(sciezka: str) -> bool:
    if not na_windows():
        return False
    import ctypes
    return bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, str(sciezka),
                                                           SPIF_UPDATEINIFILE_SENDCHANGE))


def monitory_per_wallpaper(generuj) -> bool:
    """Ustawia OSOBNĄ tapetę na każdym monitorze (Windows 8+), dopasowaną do jego rozdzielczości i
    orientacji — dzięki temu pionowy monitor nie dostaje obciętej, poziomej tapety.

    `generuj(szer, wys)` ma zwrócić ścieżkę do pliku PNG w danym rozmiarze. Zwraca True, gdy się udało;
    False — gdy nie (wtedy program użyje zwykłej, jednej tapety dla wszystkich ekranów)."""
    if not na_windows():
        return False
    try:
        import ctypes
        from ctypes import POINTER, byref, c_uint, c_void_p, c_wchar_p
        from ctypes import wintypes

        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", c_uint), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8)]

            def __init__(self, tekst):
                super().__init__()
                ole32.CLSIDFromString(tekst, byref(self))

        CLSID = GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")
        IID = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
        wsk = c_void_p()
        if ole32.CoCreateInstance(byref(CLSID), None, 1, byref(IID), byref(wsk)):  # CLSCTX_INPROC_SERVER
            return False
        vtbl = ctypes.cast(wsk, POINTER(c_void_p))[0]
        tabela = ctypes.cast(vtbl, POINTER(c_void_p * 20)).contents

        def metoda(indeks, zwrot, *argi):
            return ctypes.WINFUNCTYPE(zwrot, c_void_p, *argi)(tabela[indeks])

        SetWallpaper = metoda(3, ctypes.c_long, c_wchar_p, c_wchar_p)
        GetMonitorDevicePathAt = metoda(5, ctypes.c_long, c_uint, POINTER(c_wchar_p))
        GetMonitorDevicePathCount = metoda(6, ctypes.c_long, POINTER(c_uint))
        GetMonitorRECT = metoda(7, ctypes.c_long, c_wchar_p, POINTER(wintypes.RECT))
        SetPosition = metoda(10, ctypes.c_long, ctypes.c_int)

        ile = c_uint(0)
        if GetMonitorDevicePathCount(wsk, byref(ile)) or ile.value == 0:
            return False
        SetPosition(wsk, 4)  # DWPOS_FILL — obraz jest już w proporcjach monitora, więc wypełnia bez zniekształceń
        udane = 0
        for i in range(ile.value):
            idm = c_wchar_p()
            if GetMonitorDevicePathAt(wsk, i, byref(idm)) or not idm.value:
                continue
            prost = wintypes.RECT()
            if GetMonitorRECT(wsk, idm.value, byref(prost)):
                ole32.CoTaskMemFree(idm)
                continue
            szer, wys = prost.right - prost.left, prost.bottom - prost.top
            try:
                plik = generuj(max(1, szer), max(1, wys))
                if plik and SetWallpaper(wsk, idm.value, str(plik)) == 0:
                    udane += 1
            except Exception:  # noqa: BLE001
                pass
            ole32.CoTaskMemFree(idm)
        return udane > 0
    except Exception:  # noqa: BLE001
        return False


def bezczynnosc_sekund() -> float | None:
    """Ile sekund minęło od ostatniego ruchu myszy lub klawisza w całym systemie (nie tylko w programie)."""
    if not na_windows():
        return None
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000
    except Exception:  # noqa: BLE001
        return None


def zablokuj_windows() -> bool:
    """Blokuje komputer (jak Win+L): dalej tylko hasło lub PIN Windows."""
    if not na_windows():
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.LockWorkStation())
    except Exception:  # noqa: BLE001
        return False


def dodaj_wyjatek_defendera(sciezki) -> bool | None:
    """Prosi Microsoft Defender, żeby NIE skanował wskazanych folderów Fakturnika (Add-MpPreference
    -ExclusionPath). Nie wyłącza ochrony w czasie rzeczywistym ani niczego innego — dodaje tylko wyjątek
    dla znanych, własnych folderów programu, żeby Defender nie blokował instalacji i uruchamiania.

    Uruchamia PowerShell z podniesieniem uprawnień (okno UAC — użytkownik musi kliknąć „Tak”).
    Zwraca True, gdy udało się uruchomić polecenie z podniesieniem; False, gdy użytkownik odmówił w UAC;
    None poza Windows lub przy błędzie. Dodanie wyjątku i tak wymaga uprawnień administratora."""
    if not na_windows():
        return None
    foldery = []
    for s in sciezki:
        s = str(s).strip()
        if s and s not in foldery:
            foldery.append(s)
    if not foldery:
        return None
    try:
        import ctypes
        # każdy folder w cudzysłowie pojedynczym (apostrofy w ścieżce podwajamy — zasada PowerShell)
        lista = ", ".join("'" + f.replace("'", "''") + "'" for f in foldery)
        polecenie = f"Add-MpPreference -ExclusionPath {lista}"
        parametry = f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{polecenie}"'
        # „runas” pokazuje okno UAC i uruchamia PowerShell jako administrator; 0 = okno ukryte
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", parametry, None, 0)
        return int(rc) > 32  # >32 = uruchomiono; <=32 (np. 5) = użytkownik odmówił w UAC
    except Exception:  # noqa: BLE001
        return None
