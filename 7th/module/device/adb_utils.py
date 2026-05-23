"""
ADB 工具函数 — 从 device.py 提取的共享模块
提供 ADB 可执行文件路径查找功能，供 DeviceController 和截图/控制策略共用。
"""

import os


def find_adb() -> str:
    """自动查找 adb 可执行文件。"""
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    candidates = [
        os.path.join(project_root, "adb", "adb.exe"),
        os.path.join(project_root, "adb.exe"),
        os.path.join(project_root, "platform-tools", "adb.exe"),
        os.path.join(project_root, "adb", "adb"),
        os.path.join(project_root, "adb"),
        # Android SDK 平台工具默认安装路径
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        # MuMu Player 12 （网易 MuMu 模拟器）
        r"C:\Program Files\Netease\MuMu Player 12-1\shell\adb.exe",
        r"C:\Program Files\Netease\MuMu Player 12\shell\adb.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return "adb"


ADB_EXECUTABLE = find_adb()
