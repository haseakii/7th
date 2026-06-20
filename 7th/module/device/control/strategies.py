"""
控制策略具体实现 — 含 ALAS 完整底层方法
"""

import os
import subprocess
import time

from module.logger import logger
from module.device.adb_utils import ADB_EXECUTABLE, adb_shell, adb_push
from module.device.alas_paths import ALAS_BIN, MAATOUCH_BIN, HERMIT_APK
from module.device.control.base import ControlStrategy
from module.device.control import register


# ── ADB 控制 ────────────────────────────────────────────────────────────────

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
            raise RuntimeError(f"ADB 点击失败: {result.stderr.decode(errors='ignore')[:200]}")

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        duration_ms = int(duration * 1000)
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "shell", "input", "swipe",
             str(sx), str(sy), str(ex), str(ey), str(duration_ms)],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"ADB 滑动失败: {result.stderr.decode(errors='ignore')[:200]}")


# ── uiautomator2 控制 ───────────────────────────────────────────────────────

@register("uiautomator2")
class U2Control(ControlStrategy):
    """通过 uiautomator2 进行控制。"""

    def __init__(self, serial: str):
        self.serial = serial
        self._u2 = None

    def initialize(self) -> bool:
        try:
            import uiautomator2 as u2
        except ImportError as e:
            logger.warning(f"uiautomator2 导入失败: {e}")
            return False

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


# ── minitouch ───────────────────────────────────────────────────────────────

@register("minitouch")
class MinitouchControl(ControlStrategy):
    """minitouch — 多点触控工具。需要自行编译推送到设备。"""

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        # minitouch 需要自行编译，ALAS bin 目录不包含
        logger.info("minitouch: 未找到二进制文件，不可用")
        return False

    @property
    def name(self) -> str:
        return "minitouch"

    def click(self, x: int, y: int) -> None:
        raise NotImplementedError("minitouch 待实现")

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        raise NotImplementedError("minitouch 待实现")


# ── Hermit ──────────────────────────────────────────────────────────────────

@register("hermit")
class HermitControl(ControlStrategy):
    """Hermit — 轻量触控工具，类似 minitouch 但更简单。"""

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        bin_path = os.path.join(ALAS_BIN, 'hermit', 'hermit')
        if not os.path.isfile(bin_path):
            logger.warning("Hermit 二进制不存在")
            return False
        logger.info("Hermit 可用（需要 ADB forward + socket 连接）")
        return False  # TODO: 完整实现

    @property
    def name(self) -> str:
        return "hermit"

    def click(self, x: int, y: int) -> None:
        raise NotImplementedError("Hermit 待实现")

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        raise NotImplementedError("Hermit 待实现")


# ── MaaTouch ────────────────────────────────────────────────────────────────

@register("maatouch")
class MaaTouchControl(ControlStrategy):
    """MaaTouch — ALAS 在 minitouch 基础上改进的多点触控工具。"""

    REMOTE_PATH = "/data/local/tmp/maatouch"

    def __init__(self, serial: str):
        self.serial = serial
        self._available = False

    def initialize(self) -> bool:
        bin_path = os.path.join(ALAS_BIN, 'MaaTouch', 'maatouch')
        if not os.path.isfile(bin_path):
            # 尝试 arm64 版本
            bin_path = os.path.join(ALAS_BIN, 'MaaTouch', 'maatouch_arm64')
            if not os.path.isfile(bin_path):
                logger.warning("MaaTouch 二进制不存在")
                return False
        try:
            adb_push(self.serial, bin_path, self.REMOTE_PATH)
            adb_shell(self.serial, ["chmod", "0777", self.REMOTE_PATH])
            self._available = True
            logger.info("MaaTouch 就绪")
            return True
        except Exception as e:
            logger.warning(f"MaaTouch 初始化失败: {e}")
            return False

    @property
    def name(self) -> str:
        return "maatouch"

    def click(self, x: int, y: int) -> None:
        adb_shell(self.serial, [self.REMOTE_PATH, "tap", str(x), str(y)])

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        adb_shell(self.serial, [self.REMOTE_PATH, "swipe", str(sx), str(sy), str(ex), str(ey)])
