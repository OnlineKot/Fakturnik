from fakturnik.przegladarka import (
    _ustawienia_z_argumentow, adres_z_tekstu, host_dozwolony, plik_niebezpieczny, polecenie_przegladarki,
)


def test_blokada_plikow_wykonywalnych():
    for zly in ("instalator.exe", "FAKTURA.PDF.exe", "skrypt.js", "x.bat", "makro.docm", "obraz.iso", "a.exe.",
                "skrot.url", "polaczenie.rdp", "strona.html", "obraz.svg", "skrypt.py", "dodatek.xll", "bez"):
        assert plik_niebezpieczny(zly), zly
    for dobry in ("faktura.pdf", "skan.jpg", "jpk.xml", "wyciag.csv", "dokumenty.zip"):
        assert not plik_niebezpieczny(dobry), dobry


def test_tylko_zaufane_strony():
    assert host_dozwolony("ksef.podatki.gov.pl", [])
    assert host_dozwolony("www.biznes.gov.pl", [])
    assert host_dozwolony("online.mbank.pl", ["mbank.pl"])
    assert not host_dozwolony("mbank.pl.oszust.com", ["mbank.pl"])
    assert not host_dozwolony("gov.pl.oszust.com", [])
    assert not host_dozwolony("example.com", [])


def test_adresy_tylko_https():
    assert adres_z_tekstu("http://bank.pl").scheme() == "https"
    assert adres_z_tekstu("bank.pl").toString() == "https://bank.pl"
    assert "duckduckgo.com" in adres_z_tekstu("biała lista vat").toString()


def test_argumenty_procesu_przegladarki():
    argumenty = polecenie_przegladarki("https://ksef.podatki.gov.pl/", True, "mbank.pl,ing.pl", False)
    adres, ustawienia = _ustawienia_z_argumentow(argumenty)
    assert adres == "https://ksef.podatki.gov.pl/"
    assert ustawienia == {"przegladarka_tylko_zaufane": "1", "przegladarka_zaufane": "mbank.pl,ing.pl"}
