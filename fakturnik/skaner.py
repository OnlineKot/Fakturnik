"""Skaner plików: przed dodaniem do zaszyfrowanych Plików i w folderze Pobrane.

Dwa poziomy sprawdzania:
  1. Własna analiza (działa zawsze, bez internetu): prawdziwy typ pliku po jego zawartości (a nie po
     rozszerzeniu), programy udające dokumenty („faktura.pdf.exe”, plik .pdf, który jest programem),
     aktywna zawartość w PDF (JavaScript, uruchamianie programów, załączone pliki), makra w dokumentach
     Office i niebezpieczne pliki ukryte w archiwach ZIP.
  2. Antywirus zainstalowany w Windows: przez AMSI (Windows Antimalware Scan Interface — działa z Microsoft
     Defender i z innymi antywirusami, które go obsługują), a gdy AMSI jest niedostępne, przez
     Microsoft Defender (MpCmdRun). Plik nie jest nigdzie wysyłany.

Wynik: „czysty”, „podejrzany” (można dodać po potwierdzeniu) albo „zagrożenie” (plik jest odrzucany).
"""

import io
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

CZYSTY, PODEJRZANY, ZAGROZENIE = "czysty", "podejrzany", "zagrożenie"
MAKS_SKAN = 200 * 1024 * 1024
NIEBEZPIECZNE = {".exe", ".msi", ".msix", ".msp", ".bat", ".cmd", ".com", ".scr", ".ps1", ".psm1", ".vbs", ".vbe",
                 ".js", ".jse", ".wsf", ".wsh", ".hta", ".jar", ".dll", ".sys", ".lnk", ".reg", ".cpl", ".msc",
                 ".pif", ".appx", ".appxbundle", ".application", ".appinstaller", ".iso", ".img", ".vhd", ".vhdx",
                 ".chm", ".url", ".website", ".rdp", ".xll", ".library-ms", ".settingcontent-ms", ".py", ".pyw"}
MAKRA = {".docm", ".xlsm", ".pptm", ".dotm", ".xlam", ".ppam"}
POBIERANE_W_TOKU = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}

_SYGNATURY = [
    (b"%PDF", "pdf"), (b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"), (b"GIF87a", "gif"), (b"GIF89a", "gif"),
    (b"BM", "bmp"), (b"II*\x00", "tif"), (b"MM\x00*", "tif"), (b"MZ", "exe"), (b"PK\x03\x04", "zip"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"), (b"7z\xbc\xaf\x27\x1c", "7z"), (b"Rar!", "rar"),
    (b"\x7fELF", "exe"), (b"#!", "skrypt"),
]
_ZGODNE = {"pdf": {"pdf"}, "jpg": {"jpg", "jpeg"}, "png": {"png"}, "gif": {"gif"}, "bmp": {"bmp"},
           "tif": {"tif", "tiff"}, "webp": {"webp"}, "zip": {"zip", "docx", "xlsx", "pptx", "odt", "ods", "odp",
                                                             "docm", "xlsm", "pptm", "epub"},
           "ole": {"doc", "xls", "ppt", "msg"}}
_PDF_GROZNE = [(rb"/Launch", "uruchamianie programów"), (rb"/EmbeddedFile", "załączone pliki"),
               (rb"/RichMedia", "osadzone multimedia (Flash)")]
_PDF_PODEJRZANE = [(rb"/JavaScript", "kod JavaScript"), (rb"/JS\b", "kod JavaScript"),
                   (rb"/OpenAction", "akcja przy otwarciu"), (rb"/AA\b", "akcje automatyczne"),
                   (rb"/XFA", "formularz XFA"), (rb"/SubmitForm", "wysyłanie danych formularza"),
                   (rb"/ImportData", "import danych")]


@dataclass
class Wynik:
    plik: str
    stan: str = CZYSTY
    powody: list[str] = field(default_factory=list)
    antywirus: str = ""

    def podnies(self, stan: str, powod: str):
        if (stan, self.stan) in ((ZAGROZENIE, CZYSTY), (ZAGROZENIE, PODEJRZANY), (PODEJRZANY, CZYSTY)):
            self.stan = stan
        if powod not in self.powody:
            self.powody.append(powod)

    @property
    def opis(self) -> str:
        tekst = {CZYSTY: "Bez zastrzeżeń", PODEJRZANY: "Podejrzany", ZAGROZENIE: "ZAGROŻENIE"}[self.stan]
        return tekst + (": " + "; ".join(self.powody) if self.powody else "")


def typ_z_zawartosci(dane: bytes) -> str | None:
    if dane[:4] == b"RIFF" and dane[8:12] == b"WEBP":
        return "webp"
    for sygnatura, typ in _SYGNATURY:
        if dane.startswith(sygnatura):
            return typ
    return None


def _rozszerzenia(nazwa: str) -> list[str]:
    return [("." + r).lower() for r in nazwa.strip().rstrip(". ").split(".")[1:]]


def analiza(nazwa: str, dane: bytes) -> Wynik:
    """Własna analiza pliku (bez antywirusa)."""
    w = Wynik(nazwa)
    rozsz = _rozszerzenia(nazwa)
    ostatnie = rozsz[-1] if rozsz else ""
    if ostatnie in NIEBEZPIECZNE:
        w.podnies(ZAGROZENIE, f"plik wykonywalny lub skrypt ({ostatnie})")
        if len(rozsz) > 1 and rozsz[-2] in {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".txt"}:
            w.podnies(ZAGROZENIE, "podwójne rozszerzenie (program udaje dokument)")
    if ostatnie in MAKRA:
        w.podnies(PODEJRZANY, "dokument Office z makrami")
    if re.search("[\u202e\u202d\u200f\u200e]", nazwa):
        w.podnies(ZAGROZENIE, "ukryte znaki odwracające nazwę pliku")
    typ = typ_z_zawartosci(dane)
    if typ in ("exe", "skrypt"):
        w.podnies(ZAGROZENIE, "zawartość to program, nie dokument")
    elif typ and ostatnie and ostatnie.lstrip(".") not in _ZGODNE.get(typ, {typ}) and ostatnie not in NIEBEZPIECZNE:
        w.podnies(PODEJRZANY, f"rozszerzenie {ostatnie} nie pasuje do zawartości ({typ})")
    if typ == "pdf":
        for wzorzec, opis in _PDF_GROZNE:
            if re.search(wzorzec, dane):
                w.podnies(ZAGROZENIE if opis != "załączone pliki" else PODEJRZANY, f"PDF zawiera: {opis}")
        for wzorzec, opis in _PDF_PODEJRZANE:
            if re.search(wzorzec, dane):
                w.podnies(PODEJRZANY, f"PDF zawiera: {opis}")
    elif typ == "zip":
        try:
            with zipfile.ZipFile(io.BytesIO(dane)) as z:
                for wpis in z.namelist()[:5000]:
                    r = _rozszerzenia(Path(wpis).name)
                    if r and r[-1] in NIEBEZPIECZNE:
                        w.podnies(ZAGROZENIE, f"archiwum zawiera program lub skrypt ({Path(wpis).name})")
                    if wpis.lower().endswith("vbaproject.bin"):
                        w.podnies(PODEJRZANY, "dokument zawiera makra")
                    if r and r[-1] in MAKRA:
                        w.podnies(PODEJRZANY, f"archiwum zawiera dokument z makrami ({Path(wpis).name})")
        except (zipfile.BadZipFile, RuntimeError, ValueError):
            w.podnies(PODEJRZANY, "uszkodzone lub zaszyfrowane archiwum (nie da się sprawdzić)")
    elif typ == "ole" and re.search(rb"VBA|_VBA_PROJECT|Macros", dane):
        w.podnies(PODEJRZANY, "dokument zawiera makra")
    return w


# ---------- antywirus Windows ----------
def skan_amsi(dane: bytes, nazwa: str) -> str | None:
    """AMSI: CZYSTY / ZAGROZENIE albo None, gdy niedostępne."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        amsi = ctypes.WinDLL("amsi.dll")
        amsi.AmsiInitialize.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
        amsi.AmsiOpenSession.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        amsi.AmsiScanBuffer.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG, wintypes.LPCWSTR,
                                        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        amsi.AmsiCloseSession.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        amsi.AmsiUninitialize.argtypes = [ctypes.c_void_p]
        kontekst, sesja, wynik = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_int(0)
        if amsi.AmsiInitialize("Fakturnik", ctypes.byref(kontekst)) != 0:
            return None
        try:
            if amsi.AmsiOpenSession(kontekst, ctypes.byref(sesja)) != 0:
                return None
            bufor = ctypes.create_string_buffer(dane, len(dane))
            kod = amsi.AmsiScanBuffer(kontekst, bufor, len(dane), nazwa, sesja, ctypes.byref(wynik))
            amsi.AmsiCloseSession(kontekst, sesja)
            if kod != 0:
                return None
            return ZAGROZENIE if wynik.value >= 32768 else CZYSTY  # AMSI_RESULT_DETECTED
        finally:
            amsi.AmsiUninitialize(kontekst)
    except Exception:  # noqa: BLE001 - brak AMSI, wyłączony antywirus itp.
        return None


def _mpcmdrun() -> Path | None:
    for katalog in (os.environ.get("ProgramFiles", r"C:\Program Files") + r"\Windows Defender",):
        p = Path(katalog) / "MpCmdRun.exe"
        if p.is_file():
            return p
    return None


def skan_defender(sciezka: Path) -> str | None:
    """Microsoft Defender z wiersza poleceń (bez usuwania pliku): CZYSTY / ZAGROZENIE albo None."""
    if sys.platform != "win32" or not (mp := _mpcmdrun()):
        return None
    try:
        kod = subprocess.run([str(mp), "-Scan", "-ScanType", "3", "-File", str(sciezka), "-DisableRemediation"],
                             capture_output=True, timeout=120, creationflags=0x08000000).returncode
    except (OSError, subprocess.TimeoutExpired):
        return None
    return {0: CZYSTY, 2: ZAGROZENIE}.get(kod)


def skanuj(sciezka: Path | str) -> Wynik:
    sciezka = Path(sciezka)
    try:
        rozmiar = sciezka.stat().st_size
        with open(sciezka, "rb") as f:
            dane = f.read(MAKS_SKAN)
    except OSError as e:
        return Wynik(sciezka.name, PODEJRZANY, [f"nie da się odczytać pliku ({e.strerror or e})"])
    w = analiza(sciezka.name, dane)
    if rozmiar > MAKS_SKAN:
        w.podnies(PODEJRZANY, "plik zbyt duży, sprawdzono tylko początek")
    av = skan_amsi(dane, sciezka.name)
    w.antywirus = "antywirus Windows (AMSI)" if av else ""
    if av is None:
        av = skan_defender(sciezka)
        w.antywirus = "Microsoft Defender" if av else "antywirus niedostępny (tylko własna analiza)"
    if av == ZAGROZENIE:
        w.podnies(ZAGROZENIE, f"wykryte przez: {w.antywirus}")
    return w


def nowe_pobrane(katalog: Path, od: float, limit: int = 50) -> list[Path]:
    """Pliki w folderze Pobrane zmienione po czasie `od` (bez plików, które jeszcze się pobierają)."""
    wynik = []
    try:
        for p in katalog.iterdir():
            try:
                if p.is_file() and p.suffix.lower() not in POBIERANE_W_TOKU and p.stat().st_mtime > od \
                        and not p.name.startswith("~$"):
                    wynik.append(p)
            except OSError:
                continue
    except OSError:
        return []
    return sorted(wynik, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
