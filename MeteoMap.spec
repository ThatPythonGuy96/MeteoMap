# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('icons/', 'icons/'),
    ('meteomap.ico', '.'),
]
binaries = []
hiddenimports = []

for pkg in ['rasterio', 'fiona', 'pyproj', 'geopandas']:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ['MeteoMap.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MeteoMap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, #change to True
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, #change to False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['meteomap.ico'],
)
