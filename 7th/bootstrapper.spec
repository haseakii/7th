# -*- mode: python ; coding: utf-8 -*-
# Bootstrapper spec — 打包为 e7.exe，引导安装 + 启动
# 用法: pyinstaller bootstrapper.spec

import sys

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'deploy',
        'deploy.installer',
        'deploy.config',
        'deploy.git',
        'deploy.pip',
        'deploy.atomic',
        'deploy.utils',
        'module.logger',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'cv2', 'numpy', 'PIL', 'rapidocr', 'cnocr', 'easyocr', 'paddleocr',
        'uiautomator2', 'adbutils',
        'pywebio', 'fastapi', 'starlette', 'uvicorn',
        'rich', 'scipy', 'matplotlib', 'tkinter', 'pandas',
        'tornado', 'websockets',
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
