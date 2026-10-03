"""Wbudowana przeglądarka w odizolowanej, bezpiecznej przestrzeni (do KSeF, e-Urzędu, CEIDG, banku).

Izolacja i ochrona (jak w przeglądarkach „bezpiecznej bankowości” programów antywirusowych):
  * osobny profil bez zapisu na dysku: ciasteczka, pamięć podręczna i historia żyją tylko w pamięci
    i znikają przy zamknięciu programu albo jego blokadzie; nic nie miesza się z inną przeglądarką,
  * tylko HTTPS: adresy http:// są podnoszone do https://, błędne certyfikaty są odrzucane bez wyjątków,
  * kamera, mikrofon, lokalizacja, powiadomienia, schowek i pełny ekran: zawsze zablokowane,
  * okienka wyskakujące otwierają się w tej samej karcie,
  * pliki wykonywalne (.exe, .msi, .bat, .js…) nie dają się pobrać; pobrane pliki dostają oznaczenie
    „pochodzi z internetu” (Zone.Identifier), więc antywirus (np. Norton) i SmartScreen je sprawdzają,
  * opcjonalnie tylko zaufane strony: gov.pl, zakładki i strony dopisane w Ustawieniach,
  * proces renderujący strony działa w piaskownicy Chromium (sandbox Windows).
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

ZAKLADKI = [
    ("KSeF", "https://ksef.podatki.gov.pl/"),
    ("e-Urząd Skarbowy", "https://www.podatki.gov.pl/e-urzad-skarbowy/"),
    ("Biała lista VAT", "https://www.podatki.gov.pl/wykaz-podatnikow-vat-wyszukiwarka"),
    ("CEIDG", "https://aplikacja.ceidg.gov.pl/ceidg/ceidg.public.ui/search.aspx"),
    ("REGON", "https://wyszukiwarkaregon.stat.gov.pl/"),
    ("ZUS PUE/eZUS", "https://www.zus.pl/portal/logowanie.npi"),
]
NIEBEZPIECZNE = {".exe", ".msi", ".msix", ".bat", ".cmd", ".com", ".scr", ".ps1", ".psm1", ".vbs", ".vbe", ".js",
                 ".jse", ".wsf", ".wsh", ".hta", ".jar", ".dll", ".sys", ".lnk", ".reg", ".cpl", ".msc", ".pif",
                 ".appx", ".appxbundle", ".application", ".iso", ".img", ".vhd", ".vhdx", ".chm", ".docm", ".xlsm",
                 ".pptm"}


def plik_niebezpieczny(nazwa: str) -> bool:
    nazwa = nazwa.lower().strip().rstrip(".")
    return any(nazwa.endswith(roz) for roz in NIEBEZPIECZNE)


def host_dozwolony(host: str, zaufane: list[str]) -> bool:
    """Tryb „tylko zaufane strony”: serwisy gov.pl, zakładki i domeny dopisane przez użytkownika (z poddomenami)."""
    host = (host or "").lower().rstrip(".")
    dozwolone = {urlparse(u).hostname for _, u in ZAKLADKI} | {z.strip().lower().lstrip("*.") for z in zaufane if z.strip()}
    return host.endswith(".gov.pl") or host == "gov.pl" or any(host == d or host.endswith("." + d) for d in dozwolone)


def adres_z_tekstu(tekst: str) -> QUrl:
    tekst = tekst.strip()
    if not tekst:
        return QUrl("about:blank")
    if " " in tekst or ("." not in tekst and not tekst.startswith(("http://", "https://"))):
        return QUrl(f"https://duckduckgo.com/?q={QUrl.toPercentEncoding(tekst).data().decode()}")
    if not tekst.startswith(("http://", "https://")):
        tekst = "https://" + tekst
    url = QUrl(tekst)
    if url.scheme() == "http":
        url.setScheme("https")
    return url


def oznacz_jako_z_internetu(sciezka: Path, adres: str = "") -> None:
    """Mark of the Web: Windows, SmartScreen i antywirus traktują plik jak pobrany z internetu."""
    if sys.platform != "win32":
        return
    try:
        with open(str(sciezka) + ":Zone.Identifier", "w", encoding="utf-8") as f:
            f.write(f"[ZoneTransfer]\r\nZoneId=3\r\nHostUrl={adres}\r\n")
    except OSError:
        pass


class Przegladarka(QWidget):
    pobrano = Signal(str)          # ścieżka pobranego (dozwolonego) pliku
    zablokowano = Signal(str)      # opis zablokowanej akcji (do powiadomienia)

    def __init__(self, ustawienia, katalog_pobranych: Path, przycisk, ikona, parent=None):
        super().__init__(parent)
        from PySide6.QtWebEngineCore import (
            QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor,
        )
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.ustawienia = ustawienia  # funkcja zwracająca bieżące ustawienia programu
        self.katalog_pobranych = katalog_pobranych

        class Straznik(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info):
                url = info.requestUrl()
                if url.scheme() == "http" and url.host() not in ("localhost", "127.0.0.1"):
                    https = QUrl(url)
                    https.setScheme("https")
                    info.redirect(https)

        okno = self

        class Strona(QWebEnginePage):
            def acceptNavigationRequest(self, url, typ, glowna_ramka):
                u = okno.ustawienia()
                if glowna_ramka and url.scheme() in ("http", "https") and u.get("przegladarka_tylko_zaufane") == "1" \
                        and not host_dozwolony(url.host(), u.get("przegladarka_zaufane", "").split(",")):
                    okno.zablokowano.emit(f"Strona {url.host()} nie jest na liście zaufanych (Ustawienia → Przeglądarka).")
                    return False
                if url.scheme() not in ("http", "https", "about", "data", "blob"):
                    okno.zablokowano.emit(f"Zablokowano otwarcie adresu typu „{url.scheme()}:”.")
                    return False
                return super().acceptNavigationRequest(url, typ, glowna_ramka)

            def createWindow(self, _typ):
                return self  # okienka wyskakujące w tej samej karcie

        # odizolowany profil bez nazwy = nic nie trafia na dysk (off-the-record)
        # rodzicem profilu jest aplikacja: profil musi żyć dłużej niż strony, które go używają
        from PySide6.QtWidgets import QApplication
        self.profil = QWebEngineProfile(QApplication.instance())
        self.profil.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profil.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.straznik = Straznik(self)
        self.profil.setUrlRequestInterceptor(self.straznik)
        self.profil.downloadRequested.connect(self._pobieranie)
        ust = self.profil.settings()
        A = QWebEngineSettings.WebAttribute
        for atrybut, wartosc in ((A.LocalContentCanAccessFileUrls, False), (A.LocalContentCanAccessRemoteUrls, False),
                                 (A.PluginsEnabled, False), (A.JavascriptCanOpenWindows, False),
                                 (A.JavascriptCanAccessClipboard, False), (A.AllowRunningInsecureContent, False),
                                 (A.AllowGeolocationOnInsecureOrigins, False), (A.FullScreenSupportEnabled, False),
                                 (A.ScreenCaptureEnabled, False), (A.DnsPrefetchEnabled, False),
                                 (A.WebRTCPublicInterfacesOnly, True), (A.PdfViewerEnabled, True)):
            ust.setAttribute(atrybut, wartosc)

        self.strona = Strona(self.profil, self)
        self.strona.certificateError.connect(lambda blad: (blad.rejectCertificate(),
                                                           self.zablokowano.emit("Niezaufany certyfikat strony: "
                                                                                 "połączenie przerwane.")))
        if hasattr(self.strona, "permissionRequested"):  # Qt 6.8+
            self.strona.permissionRequested.connect(lambda uprawnienie: uprawnienie.deny())
        else:
            self.strona.featurePermissionRequested.connect(
                lambda url, f: self.strona.setFeaturePermission(
                    url, f, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser))
        self.strona.fullScreenRequested.connect(lambda zadanie: zadanie.reject())

        self.widok = QWebEngineView(self)
        self.widok.setPage(self.strona)

        u = QVBoxLayout(self)
        u.setContentsMargins(0, 0, 0, 0)
        u.setSpacing(8)
        pasek = QHBoxLayout()
        pasek.setSpacing(6)
        for nazwa_ikony, podpowiedz, akcja in (("wstecz", "Wstecz", self.widok.back),
                                               ("dalej", "Dalej", self.widok.forward),
                                               ("odswiez", "Odśwież", self.widok.reload)):
            b = przycisk("", nazwa_ikony, "plaski", akcja)
            b.setToolTip(podpowiedz)
            pasek.addWidget(b)
        self.klodka = QLabel()
        pasek.addWidget(self.klodka)
        self.adres = QLineEdit(placeholderText="Adres strony albo szukane słowa")
        self.adres.returnPressed.connect(lambda: self.otworz(self.adres.text()))
        pasek.addWidget(self.adres, 1)
        b = przycisk("Wyczyść sesję", "kosz", "plaski", self.wyczysc)
        b.setToolTip("Usuwa ciasteczka, pamięć podręczną i historię tej przeglądarki")
        pasek.addWidget(b)
        u.addLayout(pasek)
        zakladki = QHBoxLayout()
        zakladki.setSpacing(4)
        for nazwa, adres in ZAKLADKI:
            zakladki.addWidget(przycisk(nazwa, styl="plaski", akcja=lambda _=False, a=adres: self.otworz(a)))
        zakladki.addStretch()
        u.addLayout(zakladki)
        u.addWidget(self.widok, 1)
        self.stan = QLabel("Odizolowana sesja: nic nie zapisuje się na dysku, tylko HTTPS, kamera i mikrofon "
                           "zablokowane, pliki wykonywalne nie do pobrania.", objectName="drobny")
        u.addWidget(self.stan)
        self._ikona = ikona
        self.widok.urlChanged.connect(self._zmiana_adresu)

    def _zmiana_adresu(self, url: QUrl):
        self.adres.setText(url.toString() if url.scheme() in ("http", "https") else "")
        bezpieczna = url.scheme() == "https"
        self.klodka.setPixmap(self._ikona("klodka" if bezpieczna else "klodka_otwarta",
                                          "#1e7f55" if bezpieczna else "#8a949d", 16))
        self.klodka.setToolTip("Połączenie szyfrowane (HTTPS)" if bezpieczna else "")

    def otworz(self, tekst: str):
        self.widok.setUrl(adres_z_tekstu(tekst))

    def wyczysc(self):
        """Koniec sesji: ciasteczka (logowania), pamięć podręczna i historia znikają."""
        self.profil.cookieStore().deleteAllCookies()
        self.profil.clearHttpCache()
        self.profil.clearAllVisitedLinks()
        self.widok.setUrl(QUrl("about:blank"))
        self.widok.history().clear()

    def _pobieranie(self, zadanie):
        nazwa = zadanie.downloadFileName()
        if plik_niebezpieczny(nazwa):
            zadanie.cancel()
            self.zablokowano.emit(f"Zablokowano pobieranie pliku „{nazwa}” (plik wykonywalny lub z makrami).")
            return
        self.katalog_pobranych.mkdir(parents=True, exist_ok=True)
        zadanie.setDownloadDirectory(str(self.katalog_pobranych))
        adres = zadanie.url().toString()

        def koniec():
            if zadanie.isFinished() and zadanie.state() == zadanie.DownloadState.DownloadCompleted:
                sciezka = Path(zadanie.downloadDirectory()) / zadanie.downloadFileName()
                oznacz_jako_z_internetu(sciezka, adres)
                self.pobrano.emit(str(sciezka))
        zadanie.isFinishedChanged.connect(koniec)
        zadanie.accept()


# ---------------------------------------------------------------- osobny proces przeglądarki

def polecenie_przegladarki(adres: str, tylko_zaufane: bool, zaufane: str, ochrona_ekranu: bool) -> list[str]:
    """Argumenty uruchomienia przeglądarki jako osobnego procesu Fakturnika."""
    argumenty = ["--przegladarka", adres or "about:blank", f"--zaufane={zaufane}"]
    if tylko_zaufane:
        argumenty.append("--tylko-zaufane")
    if ochrona_ekranu:
        argumenty.append("--ochrona-ekranu")
    return argumenty


def _ustawienia_z_argumentow(argumenty: list[str]) -> tuple[str, dict]:
    adres = ""
    if "--przegladarka" in argumenty:
        i = argumenty.index("--przegladarka")
        if i + 1 < len(argumenty) and not argumenty[i + 1].startswith("--"):
            adres = argumenty[i + 1]
    zaufane = next((a.split("=", 1)[1] for a in argumenty if a.startswith("--zaufane=")), "")
    return adres, {"przegladarka_tylko_zaufane": "1" if "--tylko-zaufane" in argumenty else "0",
                   "przegladarka_zaufane": zaufane}


def uruchom_przegladarke(argumenty: list[str]) -> int:
    """Osobny proces: przeglądarka nie ma dostępu do odszyfrowanych danych pacjentów z programu,
    a zablokowanie Fakturnika kończy ten proces razem z całą sesją (logowania znikają)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)  # wymóg QtWebEngine
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Fakturnik")
    app.setOrganizationName("Fakturnik")
    from . import ui, windows
    from .system import JednaKopia
    from .widzety import OknoPowiadomienia
    ui.zaladuj_czcionki()
    app.setStyle("Fusion")
    czcionka = QFont("Inter")
    czcionka.setPixelSize(13)
    app.setFont(czcionka)
    app.setStyleSheet(ui.STYL)
    app.setWindowIcon(QIcon(str(ui.ZASOBY / "ikona.png")))

    adres, ustawienia = _ustawienia_z_argumentow(argumenty)
    okno = QWidget()
    okno.setWindowTitle("Fakturnik: bezpieczna przeglądarka")
    okno.resize(1240, 860)
    okno.setStyleSheet(f"background: {ui.TLO};")
    u = QVBoxLayout(okno)
    u.setContentsMargins(18, 14, 18, 10)
    naglowek = QHBoxLayout()
    tarcza = QLabel()
    tarcza.setPixmap(ui.pixmapa("tarcza", ui.AKCENT, 20))
    naglowek.addWidget(tarcza)
    tytul = QLabel("Bezpieczna przeglądarka")
    tytul.setStyleSheet("font-size: 15px; font-weight: 650;")
    naglowek.addWidget(tytul)
    naglowek.addWidget(QLabel("odizolowany proces · tylko HTTPS · nic nie zapisuje się na dysku", objectName="drobny"))
    naglowek.addStretch()
    naglowek.addWidget(QLabel("by TeodorTeo.com", objectName="drobny"))
    u.addLayout(naglowek)
    przegladarka = Przegladarka(lambda: ustawienia, Path.home() / "Downloads" / "Fakturnik", ui.przycisk,
                                ui.pixmapa, okno)
    u.addWidget(przegladarka, 1)
    logo = ui.QPixmap(str(ui.ZASOBY / "ikona.png")).scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation)

    def powiadom(tytul_, tekst, typ="info", akcja=None):
        OknoPowiadomienia(tytul_, tekst, typ, akcja, 8000, logo).pokaz()

    def pobrano(sciezka: str):
        nazwa = Path(sciezka).name
        if Path(sciezka).suffix.lower() in (".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"):
            powiadom("Pobrano plik", f"{nazwa}\nKliknij, aby dodać go do zaszyfrowanych Plików Fakturnika.", "ok",
                     lambda: JednaKopia().wyslij_do_dzialajacej({"akcja": "dodaj", "pliki": [sciezka]}))
        else:
            powiadom("Pobrano plik", f"{nazwa} (folder Pobrane\\Fakturnik)", "ok")

    przegladarka.pobrano.connect(pobrano)
    przegladarka.zablokowano.connect(lambda tekst: powiadom("Zablokowano", tekst, "uwaga"))
    okno.show()
    if "--ochrona-ekranu" in argumenty:
        windows.ochrona_przed_przechwytywaniem(int(okno.winId()), True)
    przegladarka.otworz(adres)
    return app.exec()
