# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.build_main import Analysis
from PyInstaller.building.api import PYZ, EXE
from PyInstaller.utils.hooks import collect_submodules

# 收集 fontTools 所有子模块
hidden_imports = collect_submodules('fontTools')
hidden_imports += collect_submodules('lxml')
hidden_imports += collect_submodules('defcon')
hidden_imports += [
    'config',
    'config.loader',
    'converter',
    'converter.base',
    'converter.orchestrator',
    'converter.ttc',
    'converter.ttf',
    'utils',
    'utils.font',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
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
    name='font-replace',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
