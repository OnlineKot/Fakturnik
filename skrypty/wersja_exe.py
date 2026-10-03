"""Tworzy plik z metadanymi .exe (wydawca, nazwa, wersja) dla PyInstallera.

Opis i wersja w pliku .exe ułatwiają antywirusom (np. Nortonowi) rozpoznanie programu.
Użycie: python skrypty/wersja_exe.py 1.0.15 > wersja_exe.txt
"""

import sys

wersja = sys.argv[1]
nazwa = sys.argv[2] if len(sys.argv) > 2 else "Fakturnik"
opis = sys.argv[3] if len(sys.argv) > 3 else "Fakturnik - rachunki i faktury dla gabinetu"
czesci = tuple(int(x) for x in wersja.split(".")[:3]) + (0,)
print(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={czesci}, prodvers={czesci}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041504B0', [
      StringStruct('CompanyName', 'TeodorTeo.com'),
      StringStruct('FileDescription', '{opis}'),
      StringStruct('FileVersion', '{wersja}'),
      StringStruct('InternalName', '{nazwa}'),
      StringStruct('LegalCopyright', 'TeodorTeo.com'),
      StringStruct('OriginalFilename', '{nazwa}.exe'),
      StringStruct('ProductName', 'Fakturnik'),
      StringStruct('ProductVersion', '{wersja}')])]),
    VarFileInfo([VarStruct('Translation', [0x0415, 1200])])
  ]
)""")
