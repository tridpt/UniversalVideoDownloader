# -*- mode: python ; coding: utf-8 -*-
"""Cấu hình PyInstaller cho Universal Video Downloader.

Đóng gói thành 1 file .exe, nhúng kèm ffmpeg từ package static_ffmpeg.
Build: pyinstaller UniversalVideoDownloader.spec
"""

import os
import customtkinter
import static_ffmpeg

# Đường dẫn động (không hardcode theo máy)
ctk_path = os.path.dirname(customtkinter.__file__)
ffmpeg_bin = os.path.join(os.path.dirname(static_ffmpeg.__file__), 'bin', 'win32')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(os.path.join(ffmpeg_bin, '*.exe'), 'ffmpeg_bin')],
    datas=[(ctk_path, 'customtkinter')],
    hiddenimports=['plyer.platforms.win.notification'],
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
    name='UniversalVideoDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
