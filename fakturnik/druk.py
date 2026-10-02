"""Wygląd dokumentu (HTML dla QTextDocument) oraz drukowanie i zapis do PDF."""

import base64
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from .baza import Dokument
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
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


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
        f"<td align='right'>{p.ilosc:g}</td><td align='right'>{zl(p.cena)}</td>"
        f"<td align='center'>zw</td><td align='right'>{zl(p.wartosc)}</td></tr>"
        for i, p in enumerate(dok.pozycje, 1))

    platnosc = escape(dok.platnosc)
    if dok.platnosc == "przelew" and u["konto"]:
        platnosc += f", nr konta: {escape(u['konto'])}"
    elif dok.platnosc != "przelew":
        platnosc += " (zapłacono)"

    podzial = "page-break-before: always;" if nowa_strona else ""
    return f"""
<div style="{podzial}">
<table width="100%" cellspacing="0" cellpadding="0"><tr>
  <td><span style="font-size:20pt; font-weight:bold;">{escape(u['tytul'])} nr {escape(dok.numer)}</span><br>
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
  <tr style="background:#e8e8e8;"><th>Lp.</th><th width="50%">Nazwa usługi</th><th>Ilość</th>
      <th>Cena (zł)</th><th>VAT</th><th>Wartość (zł)</th></tr>
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


def html_dokumentu(dok: Dokument, u: dict[str, str], z_kopia: bool = False) -> str:
    obraz = logo_bajty(u)
    logo = base64.b64encode(obraz).decode("ascii") if obraz else ""
    strony = [_strona(dok, u, "oryginał", False, logo)]
    if z_kopia:
        strony.append(_strona(dok, u, "kopia", True, logo))
    return f"<html><body style='font-family: Arial; font-size:10pt;'>{''.join(strony)}</body></html>"


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
