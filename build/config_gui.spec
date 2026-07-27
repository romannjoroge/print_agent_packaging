# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for print_agent_config.exe.

Build with:
    pyinstaller build/config_gui.spec

Launches the tkinter-based configuration GUI.
"""

import os
import sys

block_cipher = None

# Paths
spec_root = os.path.abspath(os.path.join(SPECPATH, '..'))
print_agent_root = os.path.abspath(os.path.join(spec_root, '..', 'print_agent'))

a = Analysis(
    [os.path.join(spec_root, 'config_gui.py')],
    pathex=[spec_root, print_agent_root],
    binaries=[],
    datas=[],
    hiddenimports=[
        'print_agent',
        'print_agent.config',
        'print_agent.odoo_client',
        'config_manager',
        'yaml',
        'requests',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='print_agent_config',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed app, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
