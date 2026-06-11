"""
ALAS 路径常量 — 共享给截图/控制/OCR 策略使用。

统一管理 ALAS 子模块的二进制和模型文件路径，
避免在各策略文件中硬编码重复路径。
"""

import os


def _project_root() -> str:
    """返回 7th 项目根目录。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _alas_root() -> str:
    """返回 ALAS 源码根目录。"""
    return os.path.join(_project_root(), 'AzurLaneAutoScript')


# ALAS bin 目录（二进制/APK 文件）
ALAS_BIN = os.path.join(_alas_root(), 'bin')

# aScreenCap 截图工具
ASCREENCAP_DIR = os.path.join(ALAS_BIN, 'ascreencap')

# DroidCast APK
DROIDCAST_APK = os.path.join(ALAS_BIN, 'DroidCast', 'DroidCast_raw-release-1.0.apk')

# MaaTouch 触控工具
MAATOUCH_BIN = os.path.join(ALAS_BIN, 'MaaTouch', 'maatouch')

# Hermit APK
HERMIT_APK = os.path.join(ALAS_BIN, 'hermit', 'hermit.apk')

# CNOCR 模型目录
CNOCR_MODELS_DIR = os.path.join(_alas_root(), 'bin', 'cnocr_models')
CNOCR_MODEL_DIR = os.path.join(CNOCR_MODELS_DIR, 'cnocr')
