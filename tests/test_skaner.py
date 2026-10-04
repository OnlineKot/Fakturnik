import io
import os
import time
import zipfile

from fakturnik import skaner as s

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF"


def test_czyste_pliki():
    assert s.analiza("skan.pdf", PDF).stan == s.CZYSTY
    assert s.analiza("zdjecie.jpg", b"\xff\xd8\xff\xe0" + b"\0" * 20).stan == s.CZYSTY
    assert s.analiza("ok.webp", b"RIFF\0\0\0\0WEBPVP8 ").stan == s.CZYSTY


def test_program_udajacy_dokument():
    w = s.analiza("faktura.pdf.exe", b"MZ" + b"\0" * 60)
    assert w.stan == s.ZAGROZENIE and any("podwójne" in p for p in w.powody)
    assert s.analiza("faktura.pdf", b"MZ\x90\0").stan == s.ZAGROZENIE  # .pdf, ale w środku program
    assert s.analiza("rachunek‮fdp.exe", b"MZ").stan == s.ZAGROZENIE  # odwrócona nazwa


def test_pdf_z_aktywna_zawartoscia():
    assert s.analiza("a.pdf", PDF + b"/OpenAction << /S /JavaScript /JS (app.alert(1)) >>").stan == s.PODEJRZANY
    assert s.analiza("b.pdf", PDF + b"/Launch << /F (cmd.exe) >>").stan == s.ZAGROZENIE


def test_archiwa_i_makra():
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as z:
        z.writestr("dokumenty/faktura.pdf.js", "WScript.Echo(1)")
    assert s.analiza("paczka.zip", bufor.getvalue()).stan == s.ZAGROZENIE
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as z:
        z.writestr("word/vbaProject.bin", "x")
    assert s.analiza("umowa.docm", bufor.getvalue()).stan == s.PODEJRZANY
    assert s.analiza("niezgodny.png", PDF).stan == s.PODEJRZANY  # rozszerzenie nie pasuje do zawartości


def test_skanowanie_pliku_i_folderu_pobrane(tmp_path):
    (tmp_path / "skan.pdf").write_bytes(PDF)
    (tmp_path / "w_toku.crdownload").write_bytes(b"x")
    stary = tmp_path / "stary.pdf"
    stary.write_bytes(PDF)
    os.utime(stary, (time.time() - 3600, time.time() - 3600))
    w = s.skanuj(tmp_path / "skan.pdf")
    assert w.stan == s.CZYSTY and w.antywirus  # na Linuksie: „antywirus niedostępny (tylko własna analiza)”
    assert [p.name for p in s.nowe_pobrane(tmp_path, time.time() - 60)] == ["skan.pdf"]
