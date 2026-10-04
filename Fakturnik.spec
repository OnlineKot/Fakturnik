# Budowanie Fakturnik.exe (PyInstaller). Uruchamiane w GitHub Actions:  pyinstaller --noconfirm Fakturnik.spec
#
# Plik .spec zamiast samych opcji wiersza poleceń, żeby pominąć części Qt, których program nie używa,
# a które PyInstaller dołącza „na wszelki wypadek” (program jest dzięki temu wyraźnie mniejszy i szybciej startuje):
#  * klawiatura ekranowa Qt (ciągnie za sobą cały silnik Qt Quick/QML),
#  * programowy OpenGL (opengl32sw.dll, ok. 20 MB) — okna programu go nie potrzebują,
#  * tłumaczenia Qt na wszystkie języki (zostaje polski i angielski),
#  * wtyczki sieciowe Qt (TLS, informacje o sieci): połączenia z internetem robi Python, nie Qt.
import os
import re

WYKLUCZONE_MODULY = [
    "tkinter", "unittest", "pydoc_data",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQml", "PySide6.QtOpenGLWidgets",
    "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.Qt3DCore",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSerialPort",
    "PySide6.QtWebSockets", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtTextToSpeech",
]

_ZBEDNE = re.compile(
    r"(opengl32sw\.dll"
    r"|Qt6(Quick|Qml|VirtualKeyboard|QmlModels|QmlMeta|QmlWorkerScript|WebEngine|WebChannel)[A-Za-z]*\.(dll|so[.\d]*)"
    r"|libQt6(Quick|Qml|VirtualKeyboard|QmlModels|QmlMeta|QmlWorkerScript)[A-Za-z]*\.so[.\d]*"
    r"|plugins[\\/](platforminputcontexts|networkinformation|tls|generic|qmltooling|egldeviceintegrations)[\\/]"
    r"|[\\/]qml[\\/])",
    re.IGNORECASE)
_TLUMACZENIE = re.compile(r"translations[\\/](\w+?)_([a-z]{2})(_[A-Z]{2})?\.qm$")


def potrzebny(sciezka: str) -> bool:
    if _ZBEDNE.search(sciezka):
        return False
    m = _TLUMACZENIE.search(sciezka)
    return not m or m.group(2) in ("pl", "en")


a = Analysis(
    ["main.py"],
    datas=[("fakturnik/zasoby", "fakturnik/zasoby")],
    excludes=WYKLUCZONE_MODULY,
    noarchive=False,
)
przed = len(a.binaries) + len(a.datas)
a.binaries = [x for x in a.binaries if potrzebny(x[0])]
a.datas = [x for x in a.datas if potrzebny(x[0])]
print(f"Fakturnik.spec: skipped {przed - len(a.binaries) - len(a.datas)} unused Qt files")  # bez polskich liter: konsola Windows (cp1252)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Fakturnik",
    console=False,
    upx=False,
    icon="fakturnik/zasoby/ikona.ico",
    version="wersja_exe.txt" if os.path.exists("wersja_exe.txt") else None,
    runtime_tmpdir=None,
)
