"""
截图策略具体实现
"""

import subprocess

import cv2
import numpy as np

from log import logger
from module.device.adb_utils import ADB_EXECUTABLE
from module.device.screenshot.base import ScreenshotStrategy
from module.device.screenshot import register


@register("adb")
class AdbScreenshot(ScreenshotStrategy):
    """ADB screencap -p（PNG 编码），兼容所有设备。"""

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "adb"

    def screenshot(self) -> np.ndarray:
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ADB 截图失败: {result.stderr.decode(errors='ignore')[:200]}"
            )
        nparr = np.frombuffer(result.stdout, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("ADB 截图解码失败")
        return image


@register("adb_raw")
class AdbRawScreenshot(ScreenshotStrategy):
    """ADB raw framebuffer（无 PNG 编解码）。

    跳过 PNG 编码/解码过程，直接解析 raw RGBA framebuffer，
    通常比 ADB screencap -p 快 2-3 倍。
    raw 格式：12 字节头部 (w,h,stride) + RGBA_8888 像素数据。
    """

    TARGET_WIDTH = 1280
    TARGET_HEIGHT = 720

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "adb_raw"

    def screenshot(self) -> np.ndarray:
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "exec-out", "screencap"],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ADB raw 截图失败: {result.stderr.decode(errors='ignore')[:200]}"
            )

        data = result.stdout
        # 跳过 12 字节头部
        pixels = np.frombuffer(data[12:], dtype=np.uint8)

        try:
            # 尝试按目标分辨率 reshape
            img = pixels.reshape(self.TARGET_HEIGHT, self.TARGET_WIDTH, 4)  # RGBA
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        except ValueError:
            # 如果分辨率不符，回退到 PNG 解码
            logger.debug("adb_raw reshape 失败，回退到 imdecode")
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise RuntimeError("ADB raw 截图回退解码失败")
        return img


@register("uiautomator2")
class U2Screenshot(ScreenshotStrategy):
    """uiautomator2 截图。需要设备端 u2 server。"""

    def __init__(self, serial: str):
        self.serial = serial
        self._u2 = None

    def initialize(self) -> bool:
        import uiautomator2 as u2
        self._u2 = u2.connect(self.serial)
        if self._u2 is None:
            raise RuntimeError("uiautomator2 连接返回 None")
        logger.info(f"uiautomator2 连接成功: {self.serial}")
        return True

    @property
    def name(self) -> str:
        return "uiautomator2"

    def screenshot(self) -> np.ndarray:
        if self._u2 is None:
            raise RuntimeError("uiautomator2 未初始化")
        pil_img = self._u2.screenshot()
        img = np.array(pil_img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img
