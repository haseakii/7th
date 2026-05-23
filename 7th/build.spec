# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for ShopBot
# 用法: pyinstaller build.spec

import os
import sys

block_cipher = None
ROOT = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('module/config/argument', 'module/config/argument'),
        ('module/webui/css', 'module/webui/css'),
    ],
    hiddenimports=[
        'pywebio',
        'pywebio.platform.tornado',
        'pywebio.platform.fastapi',
        'pywebio.output',
        'pywebio.input',
        'pywebio.pin',
        'pywebio.session',
        'tornado',
        'tornado.web',
        'tornado.ioloop',
        'tornado.websocket',
        'uvicorn',
        'fastapi',
        'yaml',
        'cv2',
        'numpy',
        'PIL',
        # ALAS 风格模块
        'module.config',
        'module.config.argument',
        'module.webui',
        'module.base',
        'tasks.secret_shop',
        'deploy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'scipy', 'pandas'],
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
    name='E7ShopBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='E7ShopBot',
)
