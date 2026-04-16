# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Windrose Mod Deployer."""

import os
import sys
from pathlib import Path

block_cipher = None

# Locate customtkinter for data bundling
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)

# Try to locate tkdnd for drag-and-drop support
tkdnd_datas = []
try:
    import tkinterdnd2
    tkdnd_path = os.path.dirname(tkinterdnd2.__file__)
    tkdnd_datas.append((tkdnd_path, 'tkinterdnd2'))
except ImportError:
    pass

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter'),
        ('assets/icon.ico', 'assets'),
        ('assets/icon_256.png', 'assets'),
    ] + tkdnd_datas,
    hiddenimports=[
        'customtkinter',
        'py7zr',
        'rarfile',
        'paramiko',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Windrose Mod Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Windrose Mod Manager',
)
