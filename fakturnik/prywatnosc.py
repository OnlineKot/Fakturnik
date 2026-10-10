"""Prywatność Windows: wyłączanie analityki (telemetrii), Copilota, Recall, reklam i historii aktywności.

W gabinecie na ekranie są dane pacjentów, więc lepiej, żeby Windows nie wysyłał ich do analizy
ani nie robił zrzutów ekranu (Recall). Program ustawia standardowe zasady grupy (te same, które
administrator ustawia w gpedit.msc), więc wszystko da się cofnąć przyciskiem „Przywróć”.

* Ustawienia użytkownika (HKCU) program zmienia sam.
* Ustawienia całego komputera (HKLM) i usługa telemetrii wymagają administratora: program uruchamia
  się wtedy na chwilę z prośbą o zgodę (Fakturnik.exe --prywatnosc).

Sam Fakturnik nie ma żadnej analityki ani telemetrii: łączy się tylko z GitHubem (aktualizacje)
i, na żądanie, z białą listą VAT Ministerstwa Finansów (sprawdzenie NIP).
"""

import subprocess
import sys
from dataclasses import dataclass

HKCU, HKLM = "HKCU", "HKLM"


@dataclass(frozen=True)
class Wpis:
    grupa: str
    galaz: str
    klucz: str
    nazwa: str
    wartosc: int


GRUPY = {
    "copilot": "Copilot (asystent AI Windows i Edge)",
    "recall": "Recall (zrzuty ekranu analizowane przez AI)",
    "telemetria": "Analityka i dane diagnostyczne",
    "reklamy": "Reklamy, sugestie i spersonalizowane treści",
    "aktywnosc": "Historia aktywności i pisania",
}

_POL = r"Software\Policies\Microsoft"
WPISY = [
    # Copilot
    Wpis("copilot", HKCU, _POL + r"\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1),
    Wpis("copilot", HKCU, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowCopilotButton", 0),
    Wpis("copilot", HKLM, _POL + r"\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1),
    Wpis("copilot", HKLM, _POL + r"\Edge", "HubsSidebarEnabled", 0),
    Wpis("copilot", HKLM, _POL + r"\Edge", "CopilotCDPPageContext", 0),
    Wpis("copilot", HKLM, _POL + r"\Edge", "CopilotPageContext", 0),
    # Recall
    Wpis("recall", HKCU, _POL + r"\Windows\WindowsAI", "DisableAIDataAnalysis", 1),
    Wpis("recall", HKLM, _POL + r"\Windows\WindowsAI", "DisableAIDataAnalysis", 1),
    Wpis("recall", HKLM, _POL + r"\Windows\WindowsAI", "AllowRecallEnablement", 0),
    Wpis("recall", HKLM, _POL + r"\Windows\WindowsAI", "TurnOffSavingSnapshots", 1),
    # telemetria i analityka
    Wpis("telemetria", HKCU, r"Software\Microsoft\Windows\CurrentVersion\Privacy",
         "TailoredExperiencesWithDiagnosticDataEnabled", 0),
    Wpis("telemetria", HKCU, r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", 0),
    Wpis("telemetria", HKLM, _POL + r"\Windows\DataCollection", "AllowTelemetry", 0),
    Wpis("telemetria", HKLM, _POL + r"\Windows\DataCollection", "DoNotShowFeedbackNotifications", 1),
    Wpis("telemetria", HKLM, _POL + r"\Windows\DataCollection", "DisableOneSettingsDownloads", 1),
    Wpis("telemetria", HKLM, _POL + r"\Windows\AppCompat", "AITEnable", 0),
    Wpis("telemetria", HKLM, _POL + r"\Edge", "DiagnosticData", 0),
    Wpis("telemetria", HKLM, _POL + r"\Edge", "PersonalizationReportingEnabled", 0),
    # reklamy i sugestie
    Wpis("reklamy", HKCU, r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0),
    Wpis("reklamy", HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SubscribedContent-338388Enabled", 0),
    Wpis("reklamy", HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SubscribedContent-338389Enabled", 0),
    Wpis("reklamy", HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SubscribedContent-353694Enabled", 0),
    Wpis("reklamy", HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SilentInstalledAppsEnabled", 0),
    Wpis("reklamy", HKCU, r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SystemPaneSuggestionsEnabled", 0),
    Wpis("reklamy", HKLM, _POL + r"\Windows\AdvertisingInfo", "DisabledByGroupPolicy", 1),
    Wpis("reklamy", HKLM, _POL + r"\Windows\CloudContent", "DisableWindowsConsumerFeatures", 1),
    Wpis("reklamy", HKLM, _POL + r"\Windows\CloudContent", "DisableTailoredExperiencesWithDiagnosticData", 1),
    # historia aktywności i pisania
    Wpis("aktywnosc", HKCU, r"Software\Microsoft\InputPersonalization", "RestrictImplicitTextCollection", 1),
    Wpis("aktywnosc", HKCU, r"Software\Microsoft\InputPersonalization", "RestrictImplicitInkCollection", 1),
    Wpis("aktywnosc", HKCU, r"Software\Microsoft\InputPersonalization\TrainedDataStore", "HarvestContacts", 0),
    Wpis("aktywnosc", HKLM, _POL + r"\Windows\System", "EnableActivityFeed", 0),
    Wpis("aktywnosc", HKLM, _POL + r"\Windows\System", "PublishUserActivities", 0),
    Wpis("aktywnosc", HKLM, _POL + r"\Windows\System", "UploadUserActivities", 0),
]

# usługi telemetrii (wyłączane razem z ustawieniami komputera; „Przywróć” włącza je z powrotem)
USLUGI = {"DiagTrack": "auto", "dmwappushservice": "demand"}


class Rejestr:
    """Cienka warstwa nad winreg (w testach podmieniana słownikiem)."""

    def __init__(self):
        import winreg
        self.w = winreg
        self.galezie = {HKCU: winreg.HKEY_CURRENT_USER, HKLM: winreg.HKEY_LOCAL_MACHINE}

    def czytaj(self, galaz: str, klucz: str, nazwa: str):
        try:
            with self.w.OpenKey(self.galezie[galaz], klucz, 0, self.w.KEY_READ | self.w.KEY_WOW64_64KEY) as k:
                return self.w.QueryValueEx(k, nazwa)[0]
        except OSError:
            return None

    def zapisz(self, galaz: str, klucz: str, nazwa: str, wartosc: int) -> None:
        with self.w.CreateKeyEx(self.galezie[galaz], klucz, 0, self.w.KEY_WRITE | self.w.KEY_WOW64_64KEY) as k:
            self.w.SetValueEx(k, nazwa, 0, self.w.REG_DWORD, int(wartosc))

    def usun(self, galaz: str, klucz: str, nazwa: str) -> None:
        try:
            with self.w.OpenKey(self.galezie[galaz], klucz, 0, self.w.KEY_WRITE | self.w.KEY_WOW64_64KEY) as k:
                self.w.DeleteValue(k, nazwa)
        except FileNotFoundError:
            pass


def dostepne() -> bool:
    return sys.platform == "win32"


def stan(rejestr=None) -> dict[str, dict]:
    """Dla każdej grupy: ile ustawień jest już wyłączonych (dla użytkownika i dla komputera)."""
    rejestr = rejestr or Rejestr()
    wynik = {g: {"nazwa": n, "ustawione": 0, "wszystkie": 0, "brak_admin": 0} for g, n in GRUPY.items()}
    for w in WPISY:
        g = wynik[w.grupa]
        g["wszystkie"] += 1
        try:
            ok = rejestr.czytaj(w.galaz, w.klucz, w.nazwa) == w.wartosc
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            g["ustawione"] += 1
        elif w.galaz == HKLM:
            g["brak_admin"] += 1
    for g in wynik.values():
        g["wylaczone"] = g["ustawione"] == g["wszystkie"]
    return wynik


def zastosuj(galezie: set[str], rejestr=None) -> list[str]:
    """Ustawia wpisy w podanych gałęziach; zwraca listę błędów (pusta = wszystko się udało)."""
    rejestr = rejestr or Rejestr()
    bledy = []
    for w in WPISY:
        if w.galaz in galezie:
            try:
                rejestr.zapisz(w.galaz, w.klucz, w.nazwa, w.wartosc)
            except OSError as e:
                bledy.append(f"{w.galaz}\\{w.klucz}\\{w.nazwa}: {e}")
    return bledy


def przywroc(galezie: set[str], rejestr=None) -> list[str]:
    """Usuwa ustawione przez program wartości: Windows wraca do swoich ustawień domyślnych."""
    rejestr = rejestr or Rejestr()
    bledy = []
    for w in WPISY:
        if w.galaz in galezie:
            try:
                rejestr.usun(w.galaz, w.klucz, w.nazwa)
            except OSError as e:
                bledy.append(f"{w.galaz}\\{w.klucz}\\{w.nazwa}: {e}")
    return bledy


def _sc(*argumenty: str) -> int:
    try:
        return subprocess.run(["sc.exe", *argumenty], capture_output=True, timeout=30,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
    except (OSError, subprocess.TimeoutExpired):
        return -1


def uslugi_telemetrii(wylacz: bool) -> None:
    for nazwa, domyslny in USLUGI.items():
        if wylacz:
            _sc("stop", nazwa)
            _sc("config", nazwa, "start=", "disabled")
        else:
            _sc("config", nazwa, "start=", domyslny)


def usun_aplikacje_copilot() -> bool:
    """Odinstalowuje aplikację Copilot dla bieżącego użytkownika (Microsoft Store, da się zainstalować ponownie)."""
    if not dostepne():
        return False
    polecenie = "Get-AppxPackage -Name 'Microsoft.Copilot' | Remove-AppxPackage -ErrorAction SilentlyContinue"
    try:
        return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", polecenie],
                              capture_output=True, timeout=120,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def tryb_administratora(argumenty: list[str]) -> int:
    """Fakturnik.exe --prywatnosc [wylacz|przywroc]: ustawienia całego komputera (uruchamiane z UAC)."""
    przywracanie = "przywroc" in argumenty
    if przywracanie:
        bledy = przywroc({HKLM})
        uslugi_telemetrii(False)
    else:
        bledy = zastosuj({HKLM})
        uslugi_telemetrii(True)
    return 1 if bledy else 0
