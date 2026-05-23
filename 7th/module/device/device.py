"""
DeviceController 设备控制器

合并 ADB 连接、截图、点击控制。
截图/控制方法采用策略模式，由 screenshot/control 子系统负责创建和初始化。
"""

import os
import subprocess
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from log import logger, save_error_screenshot
from module.base.utils import random_rectangle_point
from module.device.adb_utils import ADB_EXECUTABLE


class DeviceController:
    """合并 ADB 连接、截图、点击控制的设备控制器"""

    # 目标截图分辨率
    SCREENSHOT_WIDTH = 1280
    SCREENSHOT_HEIGHT = 720

    def __init__(self, config):
        """支持 E7Config 和 DeviceConfig 两种配置对象。"""
        self.serial: str = getattr(config, 'serial', None) or getattr(config, 'device_serial', '127.0.0.1:16384')
        self.screenshot_method: str = getattr(config, 'screenshot_method', None) or getattr(config, 'device_screenshot_method', 'ADB')
        self.control_method: str = getattr(config, 'control_method', None) or getattr(config, 'device_control_method', 'ADB')
        self.image: Optional[np.ndarray] = None

        # 策略实例（懒初始化，首次 screenshot/click 时创建）
        self._screenshot_strategy = None
        self._control_strategy = None

    # ── 策略懒初始化 ──────────────────────────────────────────────────────────

    def _ensure_screenshot(self):
        """确保截图策略已初始化。"""
        if self._screenshot_strategy is not None:
            return
        from module.device.screenshot import create as create_screenshot
        method = self.screenshot_method
        logger.info(f"初始化截图策略: '{method}'")
        self._screenshot_strategy = create_screenshot(method, self.serial)

    def _ensure_control(self):
        """确保控制策略已初始化。"""
        if self._control_strategy is not None:
            return
        from module.device.control import create as create_control
        method = self.control_method
        logger.info(f"初始化控制策略: '{method}'")
        self._control_strategy = create_control(method, self.serial)

    # ── ADB 连接 ────────────────────────────────────────────────────────────

    def connect(self, max_retries: int = 3, retry_delay: float = 5.0) -> bool:
        """连接 ADB 设备，失败重试。

        Args:
            max_retries: 最大重试次数，默认 3 次
            retry_delay: 重试间隔秒数，默认 5.0 秒

        Returns:
            bool: 连接是否成功
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"正在连接设备 {self.serial}（第 {attempt}/{max_retries} 次）")
                result = subprocess.run(
                [ADB_EXECUTABLE, "connect", self.serial],
                    capture_output=True, text=True, timeout=10
                )
                output = result.stdout.strip()

                if "connected" in output or "already" in output:
                    logger.info(f"设备连接成功: {self.serial}")
                    return True
                else:
                    logger.warning(f"连接输出异常: {output}")
                    raise ConnectionError(output)

            except Exception as e:
                logger.error(f"连接失败（第 {attempt}/{max_retries} 次）: {e}")
                if attempt < max_retries:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)

        logger.error(f"设备连接失败，已重试 {max_retries} 次: {self.serial}")
        return False

    # ── 截图 ──────────────────────────────────────────────────────────────────

    def screenshot(self) -> np.ndarray:
        """截取 1280x720 截图。

        Returns:
            np.ndarray: BGR 格式的截图数组
        """
        self._ensure_screenshot()
        image = self._screenshot_strategy.screenshot()

        # 确保分辨率为 1280x720（横向）
        h, w = image.shape[:2]
        if h == self.SCREENSHOT_WIDTH and w == self.SCREENSHOT_HEIGHT:
            # 截图方向为纵向（720x1280），旋转至横向（1280x720）
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif w != self.SCREENSHOT_WIDTH or h != self.SCREENSHOT_HEIGHT:
            image = cv2.resize(image, (self.SCREENSHOT_WIDTH, self.SCREENSHOT_HEIGHT))

        self.image = image
        return image

    # ── 向后兼容的旧截图方法（供子类重写或外部直接调用） ──────────────────

    def _screenshot_adb(self) -> np.ndarray:
        """通过 ADB screencap 截图（向后兼容包装）。"""
        self._ensure_screenshot()
        from module.device.screenshot.strategies import AdbScreenshot
        if isinstance(self._screenshot_strategy, AdbScreenshot):
            return self._screenshot_strategy.screenshot()
        # 如果不是 ADB 策略，临时创建 ADB 实例
        tmp = AdbScreenshot(self.serial)
        tmp.initialize()
        return tmp.screenshot()

    def _screenshot_u2(self) -> np.ndarray:
        """通过 uiautomator2 截图（向后兼容包装）。"""
        self._ensure_screenshot()
        from module.device.screenshot.strategies import U2Screenshot
        if isinstance(self._screenshot_strategy, U2Screenshot):
            return self._screenshot_strategy.screenshot()
        tmp = U2Screenshot(self.serial)
        tmp.initialize()
        return tmp.screenshot()

    # ── 点击 ──────────────────────────────────────────────────────────────────

    def click(self, button) -> None:
        """点击按钮区域（带随机偏移）。

        Args:
            button: Button 实例，需有 button 属性返回 (x1, y1, x2, y2) 区域
        """
        x, y = random_rectangle_point(button.button)
        x, y = int(x), int(y)
        logger.info(f"点击 ({x}, {y}) @ {button}")
        self._click_xy(x, y)

    def click_position(self, x: int, y: int) -> None:
        """直接点击指定坐标（供 OCR 方案使用）。"""
        logger.info(f"点击坐标 ({x}, {y})")
        self._click_xy(x, y)

    def _click_xy(self, x: int, y: int) -> None:
        self._ensure_control()
        self._control_strategy.click(x, y)

    def _click_adb(self, x: int, y: int) -> None:
        """通过 ADB input tap 点击（向后兼容包装）。"""
        self._ensure_control()
        from module.device.control.strategies import AdbControl
        if isinstance(self._control_strategy, AdbControl):
            self._control_strategy.click(x, y)
            return
        tmp = AdbControl(self.serial)
        tmp.initialize()
        tmp.click(x, y)

    def _click_u2(self, x: int, y: int) -> None:
        """通过 uiautomator2 点击（向后兼容包装）。"""
        self._ensure_control()
        from module.device.control.strategies import U2Control
        if isinstance(self._control_strategy, U2Control):
            self._control_strategy.click(x, y)
            return
        tmp = U2Control(self.serial)
        tmp.initialize()
        tmp.click(x, y)

    # ── 滑动 ──────────────────────────────────────────────────────────────────

    def swipe(self, start: Tuple[int, int], end: Tuple[int, int], duration: float = 0.3) -> None:
        """从 start 滑动到 end。

        Args:
            start: 起始坐标 (x, y)
            end: 结束坐标 (x, y)
            duration: 滑动持续时间（秒）
        """
        sx, sy = int(start[0]), int(start[1])
        ex, ey = int(end[0]), int(end[1])
        logger.info(f"滑动 ({sx}, {sy}) -> ({ex}, {ey}), 时长 {duration}s")
        self._ensure_control()
        self._control_strategy.swipe(sx, sy, ex, ey, duration)

    def _swipe_adb(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        """通过 ADB input swipe 滑动（向后兼容包装）。"""
        self._ensure_control()
        from module.device.control.strategies import AdbControl
        if isinstance(self._control_strategy, AdbControl):
            self._control_strategy.swipe(sx, sy, ex, ey, duration)
            return
        tmp = AdbControl(self.serial)
        tmp.initialize()
        tmp.swipe(sx, sy, ex, ey, duration)

    def _swipe_u2(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        """通过 uiautomator2 滑动（向后兼容包装）。"""
        self._ensure_control()
        from module.device.control.strategies import U2Control
        if isinstance(self._control_strategy, U2Control):
            self._control_strategy.swipe(sx, sy, ex, ey, duration)
            return
        tmp = U2Control(self.serial)
        tmp.initialize()
        tmp.swipe(sx, sy, ex, ey, duration)

    # ── 工具方法 ──────────────────────────────────────────────────────────────

    def save_error_screenshot(self, name: str = "") -> str:
        """保存错误截图到 screenshots/error/ 目录。"""
        if self.image is None:
            logger.warning("无可用截图，跳过错误截图保存")
            return ""
        return save_error_screenshot(self.image, name=name)
