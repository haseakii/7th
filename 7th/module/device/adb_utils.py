"""
ADB 工具函数 — 从 device.py 提取的共享模块
提供 ADB 可执行文件路径查找和执行函数，供 DeviceController 和截图/控制策略共用。
"""

import os
import subprocess


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


# ── ADB 执行函数 ──────────────────────────────────────────────────────────


def adb_cmd(serial: str, *args, timeout: int = 30) -> subprocess.CompletedProcess:
    """执行 adb 命令，返回 CompletedProcess。"""
    cmd = [ADB_EXECUTABLE, "-s", serial] + list(args)
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def adb_shell(serial: str, cmd: list, timeout: int = 30) -> bytes:
    """执行 adb shell 命令，返回 stdout bytes。失败抛 RuntimeError。"""
    result = adb_cmd(serial, "shell", *cmd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"ADB shell 失败: {result.stderr.decode(errors='ignore')[:200]}"
        )
    return result.stdout


def adb_shell_stream(serial: str, cmd: list, timeout: int = 30) -> bytes:
    """执行 adb exec-out 命令，返回二进制 stdout。"""
    result = subprocess.run(
        [ADB_EXECUTABLE, "-s", serial, "exec-out"] + cmd,
        capture_output=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ADB exec-out 失败: {result.stderr.decode(errors='ignore')[:200]}"
        )
    return result.stdout


def adb_push(serial: str, local: str, remote: str, timeout: int = 30):
    """推送文件到设备。"""
    result = adb_cmd(serial, "push", local, remote, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"ADB push 失败: {result.stderr.decode(errors='ignore')[:200]}"
        )


def adb_forward(serial: str, local: str, remote: str, timeout: int = 10) -> int:
    """建立 ADB 端口转发，返回本地端口号。"""
    import socket as _sock

    if local.startswith('tcp:'):
        port = int(local[4:])
    else:
        with _sock.socket() as s:
            s.bind(('', 0))
            port = s.getsockname()[1]
        local = f'tcp:{port}'

    result = adb_cmd(serial, "forward", local, remote, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"ADB forward 失败: {result.stderr.decode(errors='ignore')[:200]}"
        )
    return port
