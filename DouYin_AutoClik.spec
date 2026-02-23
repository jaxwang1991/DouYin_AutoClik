# -*- mode: python ; coding: utf-8 -*-

import os

a = Analysis(
    ['gui.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        # Playwright data will be copied by build.bat after packaging
    ],
    hiddenimports=[
        'playwright.sync',
        'soundcard',
        'soundfile',
        'numpy',
        'openai',
        'dashscope',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'scipy',
        'IPython',
        'pydoc',
    ],
    noarchive=True,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DouYin_AutoClik',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DouYin_AutoClik',
)
