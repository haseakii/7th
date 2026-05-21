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
        # 打包 assets 目录（模板图片）
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'pywebio',
        'pywebio.platform.tornado',
        'pywebio.output',
        'pywebio.input',
        'pywebio.pin',
        'pywebio.session',
        'tornado',
        'tornado.web',
        'tornado.ioloop',
        'tornado.websocket',
        'yaml',
        'cv2',
        'numpy',
        'PIL',
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
    name='ShopBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台窗口，方便看日志
    icon=None,     # 可以换成自定义 ico 图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ShopBot',
)
