# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('playwright/driver/package/_internal', 'playwright/driver/package/_internal'),
    ],
    hiddenimports=['playwright.sync', 'soundcard', 'soundfile', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DouYin_AutoClik',
           debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
           upx_exclude=[], runtime_tmpdir=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True,
               upx_exclude=[], name='DouYin_AutoClik')
