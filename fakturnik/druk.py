"""Wygląd dokumentu (HTML dla QTextDocument) oraz drukowanie i zapis do PDF."""

import base64
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from datetime import date, datetime

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
        if len(cyfry) != 11:
            nabywca.append("NIP: " + escape(dok.nabywca_id))
        elif u.get("druk_pesel") == "1":  # PESEL nie jest wymagany na rachunku (minimalizacja danych)
            nabywca.append("PESEL: " + escape(dok.nabywca_id))

    platnosc = escape(dok.platnosc)
    if dok.platnosc == "przelew":
        if dok.termin_platnosci:
            platnosc += f", termin: {data_pl(dok.termin_platnosci)}"
        if u["konto"]:
            platnosc += f"<br>Nr konta: {escape(formatuj_konto(u['konto']))}"
    elif not dok.jest_korekta:
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
  <td><span style="font-size:{15 if dok.jest_korekta else 20}pt; font-weight:bold;">{escape(dok.nazwa_druku)} nr {escape(dok.numer)}</span><br>
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
{_tresc(dok, platnosc, u)}
<p style="font-size:8.5pt;">{escape(u['adnotacja'])}</p>
{f'<p style="font-size:8.5pt;">Wystawił(a): {escape(dok.wystawil)}</p>' if dok.wystawil and dok.wystawil != "Właścicielka" and u.get("druk_wystawil", "1") == "1" else ""}
{'<br>' if dok.jest_korekta else '<br><br><br>'}
<table width="100%" style="font-size:8pt;"><tr>
  <td width="40%" align="center" style="border-top: 1px dotted black;">podpis osoby upoważnionej do odbioru</td>
  <td width="20%"></td>
  <td width="40%" align="center" style="border-top: 1px dotted black;">podpis osoby upoważnionej do wystawienia</td>
</tr></table>
{_stopka_wydruku(u)}
</div>"""


def _tabela_pozycji(pozycje: list, podpis: str = "Razem") -> str:
    wiersze = "".join(
        f"<tr><td align='right'>{i}</td><td>{escape(p.nazwa)}</td><td align='center'>{escape(p.jm)}</td>"
        f"<td align='right'>{p.ilosc:g}</td><td align='right' style='white-space:nowrap'>{zl(p.cena)}</td>"
        f"<td align='center'>zw</td><td align='right' style='white-space:nowrap'>{zl(p.wartosc)}</td></tr>"
        for i, p in enumerate(pozycje, 1))
    suma = round(sum(p.wartosc for p in pozycje), 2)
    return f"""<table width="100%" border="1" cellspacing="0" cellpadding="5" style="border-collapse:collapse; border-color:black;">
  <tr style="background:#e8e8e8; white-space:nowrap;"><th width="6%">Lp.</th><th>Nazwa usługi</th><th width="7%">J.m.</th>
      <th width="8%">Ilość</th><th width="14%">Cena jedn. (zł)</th><th width="7%">VAT</th><th width="15%">Wartość (zł)</th></tr>
  {wiersze or '<tr><td colspan="7" align="center">brak pozycji</td></tr>'}
  <tr><td colspan="6" align="right"><b>{podpis}</b></td><td align="right"><b>{zl(suma)}</b></td></tr>
</table>"""


def _podsumowanie_stawek(netto: float) -> str:
    """Zestawienie według stawki VAT (dla faktur): usługi zwolnione, więc VAT 0 i brutto = netto."""
    return f"""<table align="right" border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse; border-color:black; font-size:9pt; margin-top:6px;">
  <tr style="background:#e8e8e8;"><th>Stawka VAT</th><th>Wartość netto (zł)</th><th>Kwota VAT (zł)</th><th>Wartość brutto (zł)</th></tr>
  <tr><td align="center">zw</td><td align="right">{zl(netto)}</td><td align="right">0,00</td><td align="right">{zl(netto)}</td></tr>
</table><br clear="all">"""


def tekst_qr_przelewu(dok: Dokument, u: dict[str, str]) -> str | None:
    """Treść kodu QR do przelewu według rekomendacji Związku Banków Polskich (aplikacje polskich banków):
    NIP|PL|rachunek|kwota w groszach (6 cyfr)|odbiorca (do 20 znaków)|tytuł (do 32 znaków)|||"""
    konto = "".join(c for c in u.get("konto", "") if c.isdigit())
    if dok.platnosc != "przelew" or len(konto) != 26 or dok.suma <= 0:
        return None
    nip = "".join(c for c in u.get("nip", "") if c.isdigit())
    grosze = round(dok.suma * 100)
    kwota = f"{grosze:06d}" if grosze <= 999999 else ""  # większych kwot standard nie mieści: wpisze się ręcznie
    return "|".join([nip if len(nip) == 10 else "", "PL", konto, kwota, _ascii(u.get("nazwa", ""))[:20].strip(),
                     _ascii(f"{dok.nazwa_druku} {dok.numer}")[:32].strip(), "", "", ""])


def _ascii(tekst: str) -> str:
    """Bez polskich znaków i separatora pól (nie każda aplikacja bankowa je przyjmuje)."""
    zamiana = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ|", "acelnoszzACELNOSZZ/")
    return " ".join(tekst.translate(zamiana).split())


def _kod_qr(tresc: str) -> str:
    import segno
    return segno.make(tresc, error="m", micro=False).png_data_uri(scale=3, border=1)


def _tresc(dok: Dokument, platnosc: str, u: dict[str, str] | None = None) -> str:
    if not dok.jest_korekta:
        stawki = _podsumowanie_stawek(dok.suma) if dok.tytul == "Faktura" else ""
        kwota = f"""<p style="font-size:12pt;"><b>Do zapłaty: {zl(dok.suma)} zł</b><br>
<span style="font-size:10.5pt;">Słownie: {kwota_slownie(dok.suma)}<br>Sposób płatności: {platnosc}</span></p>"""
        qr = tekst_qr_przelewu(dok, u) if u and u.get("druk_qr", "1") == "1" else None
        if qr:
            kwota = f"""<table width="100%" cellspacing="0" cellpadding="0"><tr><td valign="top">{kwota}</td>
<td width="120" align="center" valign="top" style="font-size:7.5pt; color:#444444;">
<img src="{_kod_qr(qr)}" width="96" height="96"><br>Zapłać kodem QR<br>w aplikacji banku</td></tr></table>"""
        return f"""{_tabela_pozycji(dok.pozycje)}
{stawki}
{kwota}"""
    roznica = dok.suma
    if roznica < 0:
        wynik = f"Do zwrotu nabywcy: {zl(-roznica)} zł"
    elif roznica > 0:
        wynik = f"Do zapłaty (dopłata): {zl(roznica)} zł"
    else:
        wynik = "Kwota bez zmian (korekta danych)"
    return f"""<p style="font-size:10pt;">Dotyczy faktury nr <b>{escape(dok.korekta_do)}</b>
z dnia {data_pl(dok.korekta_data) if dok.korekta_data else '—'}<br>
Przyczyna korekty: <b>{escape(dok.powod_korekty) or '—'}</b></p>
<p style="font-size:9pt; margin-bottom:2px;"><b>PRZED KOREKTĄ</b></p>
{_tabela_pozycji(dok.pozycje_przed, "Razem przed korektą")}
<p style="font-size:9pt; margin-bottom:2px;"><b>PO KOREKCIE</b></p>
{_tabela_pozycji(dok.pozycje, "Razem po korekcie")}
<table align="right" border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse; border-color:black; font-size:9pt; margin-top:6px;">
  <tr style="background:#e8e8e8;"><th>Stawka VAT</th><th>Netto przed</th><th>Netto po</th><th>Różnica netto</th><th>Różnica VAT</th></tr>
  <tr><td align="center">zw</td><td align="right">{zl(dok.suma_przed)}</td><td align="right">{zl(dok.suma_po)}</td>
      <td align="right">{zl(roznica)}</td><td align="right">0,00</td></tr>
</table><br clear="all">
<p style="font-size:12pt;"><b>{wynik}</b><br>
<span style="font-size:10.5pt;">Słownie: {kwota_slownie(abs(roznica))}<br>Sposób rozliczenia: {platnosc}</span></p>"""


def _stopka_wydruku(u: dict[str, str]) -> str:
    if u.get("druk_data_wydruku") != "1":
        return ""
    return (f'<p style="font-size:7.5pt; color:#666666; margin-top:18px;">'
            f'Wydrukowano {datetime.now():%d.%m.%Y, %H:%M}</p>')


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
      {f"Wygenerowano {datetime.now():%d.%m.%Y, %H:%M}" if u.get("druk_data_wygenerowania", "1") == "1" else ""}</td>
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


def html_zamkniecia_dnia(dokumenty: list[Dokument], u: dict[str, str], dzien: date) -> str:
    """Raport na koniec dnia: utarg według sposobu płatności (gotówka do przeliczenia w kasie) i lista dokumentów."""
    pods = podsumuj(dokumenty)
    kolejnosc = ["gotówka", "karta", "przelew"]
    sposoby = kolejnosc + sorted(k for k in pods.wg_platnosci if k not in kolejnosc)
    kafelki = "".join(
        f"<td width='{100 // len(sposoby)}%' align='center' style='border:1px solid #bbbbbb; padding:10px;'>"
        f"<span style='font-size:9pt; color:#555555;'>{escape(k.upper())}</span><br>"
        f"<span style='font-size:17pt; font-weight:bold;'>{zl(pods.wg_platnosci.get(k, 0))}</span>"
        f"<span style='font-size:10pt;'> zł</span><br><span style='font-size:8pt; color:#555555;'>"
        f"{sum(1 for d in dokumenty if d.wazny and d.platnosc == k)} dok.</span></td>"
        for k in sposoby)
    szary = ' style="color:#888888;"'
    wiersze = "".join(
        f"<tr{szary if d.anulowano else ''}><td>{escape(d.numer)}</td>"
        f"<td>{escape(d.nazwa_druku)}</td><td>{escape(d.nabywca)}</td><td>{escape(d.platnosc)}</td>"
        f"<td align='right'>{'anulowany' if d.anulowano else zl(d.suma)}</td></tr>"
        for d in sorted(dokumenty, key=lambda d: (d.numer, d.id or 0)))
    return f"""<html><body style='font-family: Inter, Arial; font-size:9.5pt;'>
<table width="100%" cellspacing="0" cellpadding="0"><tr>
  <td><span style="font-size:18pt; font-weight:bold;">Zamknięcie dnia</span><br>
      <span style="font-size:11pt;">{DNI_TYGODNIA[dzien.weekday()]}, {data_pl(dzien.isoformat())}</span></td>
  <td align="right" valign="top" style="font-size:9pt;"><b>{escape(u['nazwa'])}</b><br>
      {f"Wygenerowano {datetime.now():%d.%m.%Y, %H:%M}" if u.get("druk_data_wygenerowania", "1") == "1" else ""}</td>
</tr></table>
<br>
<table width="100%" cellspacing="6" cellpadding="0"><tr>{kafelki}</tr></table>
<p style="font-size:13pt;"><b>Razem: {zl(pods.suma)} zł</b> &nbsp; <span style="font-size:10pt;">
({pods.liczba} dok.{f", anulowane: {pods.anulowanych}" if pods.anulowanych else ""})</span></p>
<table width="100%" border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse; border-color:black;">
  <tr style="background:#e8e8e8;"><th>Numer</th><th>Dokument</th><th width="40%">Nabywca</th><th>Płatność</th>
      <th>Kwota (zł)</th></tr>
  {wiersze or '<tr><td colspan="5" align="center">Dziś nie wystawiono dokumentów</td></tr>'}
</table>
<br><br>
<table width="100%" style="font-size:9.5pt;"><tr>
  <td width="28%">Gotówka w kasie (przeliczona):</td>
  <td width="17%" style="border-bottom: 1px dotted black;">&nbsp;</td>
  <td width="10%"></td>
  <td width="45%" align="center" style="border-top: 1px dotted black;">podpis</td>
</tr></table>
</body></html>"""


DNI_TYGODNIA = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]


def html_danych_osoby(nazwa: str, identyfikator: str, adres: str, dokumenty: list[Dokument],
                      u: dict[str, str]) -> str:
    """Informacja o przetwarzanych danych jednej osoby (art. 15 RODO): dane i lista jej dokumentów."""
    wiersze = "".join(
        f"<tr><td>{escape(d.numer)}</td><td>{escape(d.tytul)}</td><td>{data_pl(d.data_wystawienia)}</td>"
        f"<td>{escape(', '.join(p.nazwa for p in d.pozycje))}</td>"
        f"<td align='right'>{'anulowany' if d.anulowano else zl(d.suma)}</td></tr>"
        for d in sorted(dokumenty, key=lambda d: (d.data_wystawienia, d.id or 0)))
    return f"""<html><body style='font-family: Inter, Arial; font-size:9.5pt;'>
<p style="font-size:15pt; font-weight:bold;">Informacja o przetwarzanych danych osobowych</p>
<p>Administrator danych: <b>{escape(u['nazwa'])}</b><br>{_wiersze(u['adres'])}</p>
<p><b>Dane osoby</b><br>Imię i nazwisko / nazwa: {escape(nazwa)}<br>
PESEL / NIP: {escape(identyfikator) or '—'}<br>Adres: {escape(adres.replace(chr(10), ', ')) or '—'}</p>
<p><b>Cel i podstawa:</b> wystawianie i przechowywanie rachunków oraz faktur – obowiązek prawny
(art. 6 ust. 1 lit. c RODO, przepisy podatkowe i o rachunkowości).<br>
<b>Okres przechowywania:</b> {escape(u.get('rodo_lat', '5'))} lat po końcu roku wystawienia dokumentu,
potem dane osobowe są usuwane.<br>
<b>Odbiorcy:</b> biuro rachunkowe i organy podatkowe – tylko w zakresie wymaganym przepisami.<br>
Przysługuje Pani/Panu prawo dostępu do danych, ich sprostowania, ograniczenia przetwarzania
oraz skargi do Prezesa UODO.</p>
<p><b>Dokumenty ({len(dokumenty)})</b></p>
<table width="100%" border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse; border-color:black;">
  <tr style="background:#e8e8e8;"><th>Numer</th><th>Rodzaj</th><th>Data</th><th width="45%">Usługi</th>
      <th>Kwota (zł)</th></tr>
  {wiersze or '<tr><td colspan="5" align="center">Brak dokumentów</td></tr>'}
</table>
<p style="font-size:8pt; color:#666666;">Sporządzono {date.today():%d.%m.%Y}</p>
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
