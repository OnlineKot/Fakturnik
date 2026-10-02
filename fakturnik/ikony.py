"""Liniowe ikony interfejsu (rysunki w stylu Lucide, licencja ISC), malowane z SVG w dowolnym kolorze."""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PLIK = '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>'

KSZTALTY = {
    "nowy": _PLIK + '<path d="M9 15h6"/><path d="M12 18v-6"/>',
    "historia": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>'
                '<path d="M12 7v5l4 2"/>',
    "ustawienia": '<path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/><path d="M8 12H3"/>'
                  '<path d="M21 20h-5"/><path d="M12 20H3"/><path d="M14 2v4"/><path d="M8 10v4"/>'
                  '<path d="M16 18v4"/>',
    "klodka": '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "klodka_otwarta": '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    "drukarka": '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
                '<path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    "podglad": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "pdf": _PLIK + '<path d="M12 18v-6"/><path d="m9 15 3 3 3-3"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "kosz": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
            '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "szukaj": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "odswiez": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
               '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "klucz": '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    "archiwum": '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/>'
                '<path d="M10 12h4"/>',
    "przywroc": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "arkusz": _PLIK + '<path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/>',
    "lista": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/>'
             '<path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "kopiuj": '<rect width="14" height="14" x="8" y="8" rx="2"/>'
              '<path d="M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"/>',
    "obraz": '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/>'
             '<path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    "pobierz": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "tarcza": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1'
              'c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "ok": '<path d="M20 6 9 17l-5-5"/>',
    "uwaga": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
             '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "zamknij": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}

SZARY = "#6e6e73"
CIEMNY = "#1d1d1f"


def pixmapa(nazwa: str, kolor: str = SZARY, rozmiar: int = 18, grubosc: float = 1.75) -> QPixmap:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{kolor}" '
           f'stroke-width="{grubosc}" stroke-linecap="round" stroke-linejoin="round">{KSZTALTY[nazwa]}</svg>')
    skala = 3  # ostre także na ekranach z powiększeniem 150–300%
    pix = QPixmap(rozmiar * skala, rozmiar * skala)
    pix.fill(Qt.GlobalColor.transparent)
    malarz = QPainter(pix)
    malarz.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(malarz, QRectF(0, 0, pix.width(), pix.height()))
    malarz.end()
    pix.setDevicePixelRatio(skala)
    return pix


def ikona(nazwa: str, kolor: str = SZARY, aktywny: str | None = None, rozmiar: int = 18) -> QIcon:
    """Ikona; `aktywny` to kolor dla stanu zaznaczonego (np. wybrana pozycja menu)."""
    ic = QIcon()
    ic.addPixmap(pixmapa(nazwa, kolor, rozmiar), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmapa(nazwa, "#b0b0b5", rozmiar), QIcon.Mode.Disabled, QIcon.State.Off)
    if aktywny:
        ic.addPixmap(pixmapa(nazwa, aktywny, rozmiar), QIcon.Mode.Normal, QIcon.State.On)
    return ic
