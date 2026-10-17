# -*- mode: python ; coding: utf-8 -*-
# Empacotamento do DinoTube para Windows. Uso (na raiz do projeto): pyinstaller DinoTube.spec --noconfirm
# Gera dist/DinoTube/DinoTube.exe (pasta única: abre mais rápido e não extrai nada a cada execução).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH)
FFMPEG_DIR = ROOT / "third_party" / "ffmpeg"

# Só o ffmpeg e o ffprobe entram no pacote (o ffplay nunca é usado). LICENSE e README acompanham os binários (GPL).
datas = [
    (str(FFMPEG_DIR / "bin" / "ffmpeg.exe"), "third_party/ffmpeg/bin"),
    (str(FFMPEG_DIR / "bin" / "ffprobe.exe"), "third_party/ffmpeg/bin"),
    (str(FFMPEG_DIR / "LICENSE"), "third_party/ffmpeg"),
    (str(FFMPEG_DIR / "README.txt"), "third_party/ffmpeg"),
]
# A versão dos provedores aparece em Configurações; ela vem dos metadados dos pacotes.
for package in ("yt-dlp", "pytubefix"):
    datas += copy_metadata(package)
datas += collect_data_files("pytubefix")

hiddenimports = collect_submodules("yt_dlp") + collect_submodules("pytubefix")

# Módulos do Qt que o aplicativo não usa: deixam o pacote bem menor.
excludes = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtDesigner",
    "PySide6.QtGraphs", "PySide6.QtQuick3D", "PySide6.QtRemoteObjects", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "tkinter", "pytest", "pytestqt",
]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DinoTube",
    icon=str(ROOT / "packaging" / "dinotube.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX em binários do Qt/ffmpeg costuma disparar antivírus e quebrar DLLs
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="DinoTube")
