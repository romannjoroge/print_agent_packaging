# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for print_agent_service.exe (OPTIONAL).

With winservicetools, this exe is NOT needed — the service runs as
"pythonw.exe service.py" directly.  This spec is kept for optional
deployment scenarios where you want a standalone service exe.

Build with:
    pyinstaller build/service.spec
"""

import os
import sys

block_cipher = None

# Paths
spec_root = os.path.abspath(os.path.join(SPECPATH, '..'))
print_agent_root = os.path.abspath(os.path.join(spec_root, '..', 'print_agent'))

a = Analysis(
    [os.path.join(spec_root, 'service.py')],
    pathex=[spec_root, print_agent_root],
    binaries=[],
    datas=[],
    hiddenimports=[
        'print_agent',
        'print_agent.config',
        'print_agent.connections',
        'print_agent.connections.base',
        'print_agent.connections.network',
        'print_agent.connections.usb',
        'print_agent.connections.ipp',
        'print_agent.odoo_client',
        'print_agent.orchestrator',
        'print_agent.rendering',
        'yaml',
        'requests',
        'winservicetools',
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
    name='print_agent_service',
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
