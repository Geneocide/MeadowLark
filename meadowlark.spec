# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

a = Analysis(
    ["meadowlark.pyw"],
    pathex=[],
    binaries=[
        (".venv/Scripts/deno.exe", "."),
    ],
    datas=copy_metadata("meadowlark") + [
        ("resources", "resources"),
    ],
    hiddenimports=[
        *collect_submodules("yt_dlp"),
        "keyring.backends.Windows",
        "wakepy._implementations",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MeadowLark",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon="resources/icons/meadowlark.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MeadowLark",
)
