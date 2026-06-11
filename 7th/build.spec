# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for E7 Shop Bot
# 用法: pip install pyinstaller && pyinstaller build.spec

import os
import sys

block_cipher = None
ROOT = os.path.abspath('.')

a = Analysis(
    ['gui.py'],
    pathex=[ROOT],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('config/*.json', 'config'),
        ('module/config/argument', 'module/config/argument'),
        ('module/config/i18n', 'module/config/i18n'),
    ],
    hiddenimports=[
        # WebUI
        'pywebio',
        'pywebio.platform.fastapi',
        'pywebio.output',
        'pywebio.input',
        'pywebio.pin',
        'pywebio.session',
        # ASGI 服务
        'uvicorn',
        'fastapi',
        'starlette',
        'starlette.websockets',
        # 框架
        'rich',
        'rich.highlighter',
        'rich.theme',
        'yaml',
        'inflection',
        # 图像处理
        'cv2',
        'numpy',
        'PIL',
        # OCR
        'rapidocr',
        'cnocr',
        # 设备控制
        'uiautomator2',
        'adbutils',
        # E7 模块
        'module.config',
        'module.config.argument',
        'module.config.i18n',
        'module.webui',
        'module.device',
        'module.device.screenshot',
        'module.device.control',
        'module.ocr',
        'module.submodule',
        'module.logger',
        'tasks.secret_shop',
        'tasks.secret_shop.ocr_backends',
        'deploy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'tkinter', 'pandas',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    ],
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
