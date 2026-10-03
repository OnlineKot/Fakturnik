"""Wygląd dokumentu (HTML dla QTextDocument) oraz drukowanie i zapis do PDF."""

import base64
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from datetime import date

from .baza import Dokument, podsumuj
from .walidacja import formatuj_konto
from .slownie import kwota_slownie


DOMYSLNE_LOGO = Path(__file__).parent / "zasoby" / "logo.png"
WYSOKOSC_LOGO = 85  # px na wydruku, ok. 2 cm


def logo_bajty(u: dict[str, str]) -> bytes | None:
    """Ustawienie "logo": "domyslne" = logo gabinetu dołączone do programu, "" = bez logo, inaczej base64."""
    wartosc = u.get("logo", "")
    if not wartosc:
        return None
    if wartosc == "domyslne":
        return DOMYSLNE_LOGO.read_bytes() if DOMYSLNE_LOGO.exists() else None
    try:
        return base64.b64decode(wartosc)
    except ValueError:
        return None


def zl(v: float) -> str:
    # twarda spacja: "1 500,00" nie łamie się w wąskiej kolumnie wydruku
    return f"{v:,.2f}".replace(",", "\u00a0").replace(".", ",")


def data_pl(iso: str) -> str:
    return ".".join(reversed(iso.split("-")))


def _wiersze(tekst: str) -> str:
    return "<br>".join(escape(w) for w in tekst.splitlines() if w.strip())


def _strona(dok: Dokument, u: dict[str, str], etykieta: str, nowa_strona: bool, logo: str) -> str:
    sprzedawca = [_wiersze(u["adres"])]
    if u["nip"]:
        sprzedawca.append(f"NIP: {escape(u['nip'])}")
    if u["regon"]:
        sprzedawca.append(f"REGON: {escape(u['regon'])}")

    nabywca = [f"<b>{escape(dok.nabywca)}</b>", _wiersze(dok.nabywca_adres)]
    if dok.nabywca_id:
        cyfry = "".join(c for c in dok.nabywca_id if c.isdigit())
        nabywca.append(("PESEL: " if len(cyfry) == 11 else "NIP: ") + escape(dok.nabywca_id))

    pozycje = "".join(
        f"<tr><td align='right'>{i}</td><td>{escape(p.nazwa)}</td>"
        f"<td align='right'>{p.ilosc:g}</td><td align='right' style='white-space:nowrap'>{zl(p.cena)}</td>"
        f"<td align='center'>zw</td><td align='right' style='white-space:nowrap'>{zl(p.wartosc)}</td></tr>"
        for i, p in enumerate(dok.pozycje, 1))

    platnosc = escape(dok.platnosc)
    if dok.platnosc == "przelew":
        if u["konto"]:
            platnosc += f"<br>Nr konta: {escape(formatuj_konto(u['konto']))}"
        if dok.nieoplacony and dok.termin_platnosci:
            platnosc += f"<br><b>Termin płatności: {data_pl(dok.termin_platnosci)}</b>"
        elif not dok.nieoplacony:
            platnosc += " (zapłacono)"
    else:
        platnosc += " (zapłacono)"

    podzial = "page-break-before: always;" if nowa_strona else ""
    anulowany = ""
    if dok.anulowano:
        powod = f": {escape(dok.powod_anulowania)}" if dok.powod_anulowania else ""
        anulowany = (f'<p style="font-size:13pt; font-weight:bold; color:#b00020; border:2px solid #b00020; '
                     f'padding:4px;">DOKUMENT ANULOWANY {data_pl(dok.anulowano)}{powod}</p>')
    return f"""
<div style="{podzial}">{anulowany}
<table width="100%" cellspacing="0" cellpadding="0"><tr>
  <td><span style="font-size:20pt; font-weight:bold;">{escape(dok.tytul)} nr {escape(dok.numer)}</span><br>
      <span style="font-size:9pt; letter-spacing:1px;">{etykieta.upper()}</span></td>
  <td align="right" valign="top" style="font-size:9.5pt;">{escape(u['miejsce'])}, {data_pl(dok.data_wystawienia)}<br>
      Data wykonania usługi: {data_pl(dok.data_uslugi)}</td>
</tr></table>
<br>
<table width="100%" cellspacing="0" cellpadding="6"><tr>
  <td width="50%" valign="top" style="border-top: 1.5px solid black;">
    <span style="font-size:8pt;">SPRZEDAWCA</span><br>
    <table width="100%" cellspacing="0" cellpadding="0"><tr>
      {f'<td valign="top" style="padding-right:10px;"><img src="data:image/png;base64,{logo}" height="{WYSOKOSC_LOGO}"></td>' if logo else ''}
      <td width="100%" valign="top"><span style="font-size:11.5pt; font-weight:bold;">{escape(u['nazwa'])}</span><br>
        {'<br>'.join(s for s in sprzedawca if s)}</td>
    </tr></table></td>
  <td width="50%" valign="top" style="border-top: 1.5px solid black;">
    <span style="font-size:8pt;">NABYWCA</span><br>{'<br>'.join(s for s in nabywca if s)}</td>
</tr></table>
<br>
<table width="100%" border="1" cellspacing="0" cellpadding="5" style="border-collapse:collapse; border-color:black;">
  <tr style="background:#e8e8e8; white-space:nowrap;"><th width="6%">Lp.</th><th>Nazwa usługi</th>
      <th width="8%">Ilość</th><th width="15%">Cena (zł)</th><th width="7%">VAT</th><th width="16%">Wartość (zł)</th></tr>
  {pozycje}
  <tr><td colspan="5" align="right"><b>Razem</b></td><td align="right"><b>{zl(dok.suma)}</b></td></tr>
</table>
<p style="font-size:12pt;"><b>Do zapłaty: {zl(dok.suma)} zł</b><br>
<span style="font-size:10.5pt;">Słownie: {kwota_slownie(dok.suma)}<br>Sposób płatności: {platnosc}</span></p>
<p style="font-size:8.5pt;">{escape(u['adnotacja'])}</p>
<br><br><br>
<table width="100%" style="font-size:8pt;"><tr>
  <td width="40%" align="center" style="border-top: 1px dotted black;">podpis osoby upoważnionej do odbioru</td>
  <td width="20%"></td>
  <td width="40%" align="center" style="border-top: 1px dotted black;">podpis osoby upoważnionej do wystawienia</td>
</tr></table>
</div>"""


def html_dokumentu(dok: Dokument, u: dict[str, str], z_kopia: bool = False, duplikat: bool = False) -> str:
    """Dokument do druku. `duplikat` = ponowny wydruk wystawionego wcześniej dokumentu."""
    obraz = logo_bajty(u)
    logo = base64.b64encode(obraz).decode("ascii") if obraz else ""
    pierwsza = f"duplikat z dnia {data_pl(date.today().isoformat())}" if duplikat else "oryginał"
    strony = [_strona(dok, u, pierwsza, False, logo)]
    if z_kopia:
        strony.append(_strona(dok, u, "kopia", True, logo))
    return f"<html><body style='font-family: Inter, Arial; font-size:10pt;'>{''.join(strony)}</body></html>"


def html_zestawienia(dokumenty: list[Dokument], u: dict[str, str], okres: str, filtr: str = "") -> str:
    """Zestawienie dokumentów (np. za miesiąc) do druku lub PDF, np. dla księgowej."""
    pods = podsumuj(dokumenty)
    wiersze = []
    for i, d in enumerate(sorted(dokumenty, key=lambda d: (d.data_wystawienia, d.id or 0)), 1):
        styl = ' style="color:#888888;"' if d.anulowano else ""
        kwota = "anulowany" if d.anulowano else zl(d.suma)
        wiersze.append(
            f"<tr{styl}><td align='right'>{i}</td><td>{escape(d.numer)}</td><td>{data_pl(d.data_wystawienia)}</td>"
            f"<td>{escape(d.nabywca)}</td><td>{escape(d.platnosc)}</td><td align='right'>{kwota}</td></tr>")
    platnosci = "".join(f"<tr><td>{escape(k)}</td><td align='right'>{zl(v)} zł</td></tr>"
                        for k, v in sorted(pods.wg_platnosci.items()))
    anul = f"<br>Anulowane (nie wliczone): {pods.anulowanych}" if pods.anulowanych else ""
    return f"""<html><body style='font-family: Inter, Arial; font-size:9.5pt;'>
<table width="100%" cellspacing="0" cellpadding="0"><tr>
  <td width="55%"><span style="font-size:16pt; font-weight:bold;">Zestawienie dokumentów</span><br>
      <span style="font-size:11pt;">{escape(okres)}</span>
      {f'<br><span style="font-size:9pt;">Filtr: {escape(filtr)}</span>' if filtr else ''}</td>
  <td align="right" valign="top" style="font-size:9pt;"><b>{escape(u['nazwa'])}</b><br>
      {('NIP: ' + escape(u['nip']) + '<br>') if u['nip'] else ''}
      Wygenerowano {data_pl(date.today().isoformat())}</td>
</tr></table>
<br>
<table width="100%" border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse; border-color:black;">
  <tr style="background:#e8e8e8;"><th>Lp.</th><th>Numer</th><th>Data</th><th width="38%">Nabywca</th>
      <th>Płatność</th><th>Kwota (zł)</th></tr>
  {''.join(wiersze) or '<tr><td colspan="6" align="center">Brak dokumentów</td></tr>'}
  <tr><td colspan="5" align="right"><b>Razem ({pods.liczba} dok.)</b></td>
      <td align="right"><b>{zl(pods.suma)}</b></td></tr>
</table>
<br>
<table cellspacing="0" cellpadding="3" style="font-size:10pt;">
  <tr><td colspan="2"><b>Według sposobu płatności</b></td></tr>
  {platnosci or '<tr><td>brak</td><td></td></tr>'}
</table>
<p style="font-size:10pt;">Suma: <b>{zl(pods.suma)} zł</b>{anul}</p>
</body></html>"""


def dokument_tekstowy(html: str) -> QTextDocument:
    doc = QTextDocument()
    doc.setHtml(html)
    return doc


def przygotuj_drukarke(u: dict[str, str], pdf: str | None = None) -> QPrinter:
    drukarka = QPrinter(QPrinter.PrinterMode.HighResolution)
    if pdf:
        drukarka.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        drukarka.setOutputFileName(pdf)
    elif u.get("drukarka"):
        info = QPrinterInfo.printerInfo(u["drukarka"])
        if not info.isNull():
            drukarka.setPrinterName(info.printerName())
    drukarka.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                       QPageLayout.Orientation.Portrait,
                                       QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter))
    return drukarka


def drukuj(html: str, drukarka: QPrinter) -> None:
    dokument_tekstowy(html).print_(drukarka)


def dostepne_drukarki() -> list[str]:
    return QPrinterInfo.availablePrinterNames()


# ---------- drukowanie wrzuconych plików (PDF, zdjęcia) ----------

def strony_pliku(tresc: bytes, typ: str, dpi: int = 200) -> list:
    """Zamienia plik na listę obrazów stron (QImage) do druku lub podglądu."""
    from PySide6.QtGui import QImage
    if typ != "pdf":
        obraz = QImage.fromData(tresc)
        if obraz.isNull():
            raise ValueError("Nie udało się odczytać obrazu.")
        return [obraz]
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
    from PySide6.QtPdf import QPdfDocument
    bufor = QBuffer()
    bufor.setData(QByteArray(tresc))
    bufor.open(QIODevice.OpenModeFlag.ReadOnly)
    pdf = QPdfDocument()
    pdf.load(bufor)
    if pdf.status() != QPdfDocument.Status.Ready:
        raise ValueError("Nie udało się otworzyć pliku PDF.")
    strony = []
    for i in range(pdf.pageCount()):
        rozmiar = pdf.pagePointSize(i)  # w punktach (1/72 cala)
        piksele = QSize(max(1, int(rozmiar.width() * dpi / 72)), max(1, int(rozmiar.height() * dpi / 72)))
        strony.append(pdf.render(i, piksele))
    return strony


def drukuj_plik(tresc: bytes, typ: str, drukarka: QPrinter) -> None:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QPainter
    strony = strony_pliku(tresc, typ)
    malarz = QPainter()
    if not malarz.begin(drukarka):
        raise RuntimeError("Nie udało się rozpocząć drukowania.")
    try:
        for i, obraz in enumerate(strony):
            if i:
                drukarka.newPage()
            obszar = drukarka.pageRect(QPrinter.Unit.DevicePixel).toRect()
            obszar.moveTo(0, 0)
            dopasowany = obraz.size().scaled(obszar.size(), Qt.AspectRatioMode.KeepAspectRatio)
            cel = QRect(0, 0, dopasowany.width(), dopasowany.height())
            cel.moveCenter(obszar.center())
            malarz.drawImage(cel, obraz)
    finally:
        malarz.end()
