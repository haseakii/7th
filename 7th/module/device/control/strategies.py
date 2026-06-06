"""
控制策略具体实现
"""

import subprocess

from log import logger
from module.device.adb_utils import ADB_EXECUTABLE
from module.device.control.base import ControlStrategy
from module.device.control import register


@register("adb")
class AdbControl(ControlStrategy):
    """通过 ADB shell input tap/swipe 进行控制。"""

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "adb"

    def click(self, x: int, y: int) -> None:
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "shell", "input", "tap",
             str(x), str(y)],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ADB 点击失败: {result.stderr.decode(errors='ignore')[:200]}"
            )

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        duration_ms = int(duration * 1000)
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "shell", "input", "swipe",
             str(sx), str(sy), str(ex), str(ey), str(duration_ms)],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ADB 滑动失败: {result.stderr.decode(errors='ignore')[:200]}"
            )


@register("uiautomator2")
class U2Control(ControlStrategy):
    """通过 uiautomator2 进行控制。"""

    def __init__(self, serial: str):
        self.serial = serial
        self._u2 = None

    def initialize(self) -> bool:
        import uiautomator2 as u2
        self._u2 = u2.connect(self.serial)
        if self._u2 is None:
            raise RuntimeError("uiautomator2 连接返回 None")
        logger.info(f"uiautomator2 控制连接成功: {self.serial}")
        return True

    @property
    def name(self) -> str:
        return "uiautomator2"

    def click(self, x: int, y: int) -> None:
        if self._u2 is None:
            raise RuntimeError("uiautomator2 未初始化")
        self._u2.click(x, y)

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        if self._u2 is None:
            raise RuntimeError("uiautomator2 未初始化")
        self._u2.swipe(sx, sy, ex, ey, duration=duration)
