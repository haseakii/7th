"""
DeviceController 设备控制器

合并 ADB 连接、截图、点击控制。
从 Alas 的 connection_attr、screenshot、control 模块精简复用。
支持 ADB 和 uiautomator2 两种截图/控制方式。
"""

import os
import subprocess
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from log import logger, save_error_screenshot
from module.base.utils import random_rectangle_point


# ---- 自动查找 adb 可执行文件 ----
def _find_adb() -> str:
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


ADB_EXECUTABLE = _find_adb()


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
        self._u2_device = None

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
                    # 如果使用 uiautomator2，初始化 u2 设备
                    if self.screenshot_method == "uiautomator2" or self.control_method == "uiautomator2":
                        self._init_u2()
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

    def _init_u2(self) -> None:
        """初始化 uiautomator2 设备连接"""
        try:
            import uiautomator2 as u2
            self._u2_device = u2.connect(self.serial)
            logger.info(f"uiautomator2 连接成功: {self.serial}")
        except Exception as e:
            logger.error(f"uiautomator2 初始化失败: {e}")
            raise

    def screenshot(self) -> np.ndarray:
        """截取 1280x720 截图。

        Returns:
            np.ndarray: BGR 格式的截图数组
        """
        if self.screenshot_method == "uiautomator2":
            image = self._screenshot_u2()
        else:
            image = self._screenshot_adb()

        # 确保分辨率为 1280x720（横向）
        h, w = image.shape[:2]
        if h == self.SCREENSHOT_WIDTH and w == self.SCREENSHOT_HEIGHT:
            # 截图方向为纵向（720x1280），旋转至横向（1280x720）
            # ADB screencap 返回物理帧缓冲，部分模拟器/设备在横屏游戏中仍输出纵向
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif w != self.SCREENSHOT_WIDTH or h != self.SCREENSHOT_HEIGHT:
            image = cv2.resize(image, (self.SCREENSHOT_WIDTH, self.SCREENSHOT_HEIGHT))

        self.image = image
        return image

    def _screenshot_adb(self) -> np.ndarray:
        """通过 ADB screencap 截图。

        Returns:
            np.ndarray: BGR 格式的截图
        """
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"ADB 截图失败: {result.stderr.decode(errors='ignore')}")

        # 将 PNG 字节解码为 numpy 数组
        nparr = np.frombuffer(result.stdout, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("ADB 截图解码失败: 返回数据无法解析为图像")
        return image

    def _screenshot_u2(self) -> np.ndarray:
        """通过 uiautomator2 截图。

        Returns:
            np.ndarray: BGR 格式的截图
        """
        if self._u2_device is None:
            raise RuntimeError("uiautomator2 设备未初始化，请先调用 connect()")

        pil_image = self._u2_device.screenshot()
        # PIL Image (RGB) → numpy (RGB) → BGR
        image = np.array(pil_image)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image

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
        """直接点击指定坐标（供 OCR 方案使用）。

        Args:
            x: 屏幕 x 坐标
            y: 屏幕 y 坐标
        """
        logger.info(f"点击坐标 ({x}, {y})")
        self._click_xy(x, y)

    def _click_xy(self, x: int, y: int) -> None:
        if self.control_method == "uiautomator2":
            self._click_u2(x, y)
        else:
            self._click_adb(x, y)

    def _click_adb(self, x: int, y: int) -> None:
        """通过 ADB input tap 点击。"""
        subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "shell", "input", "tap", str(x), str(y)],
            capture_output=True, timeout=10
        )

    def _click_u2(self, x: int, y: int) -> None:
        """通过 uiautomator2 点击。"""
        if self._u2_device is None:
            raise RuntimeError("uiautomator2 设备未初始化，请先调用 connect()")
        self._u2_device.click(x, y)

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

        if self.control_method == "uiautomator2":
            self._swipe_u2(sx, sy, ex, ey, duration)
        else:
            self._swipe_adb(sx, sy, ex, ey, duration)

    def _swipe_adb(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        """通过 ADB input swipe 滑动。"""
        duration_ms = int(duration * 1000)
        subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "shell", "input", "swipe",
             str(sx), str(sy), str(ex), str(ey), str(duration_ms)],
            capture_output=True, timeout=10
        )

    def _swipe_u2(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        """通过 uiautomator2 滑动。"""
        if self._u2_device is None:
            raise RuntimeError("uiautomator2 设备未初始化，请先调用 connect()")
        self._u2_device.swipe(sx, sy, ex, ey, duration=duration)

    def save_error_screenshot(self, name: str = "") -> str:
        """保存错误截图到 screenshots/error/ 目录。

        Args:
            name: 可选的截图名称前缀

        Returns:
            str: 保存的文件路径，如果没有可用截图则返回空字符串
        """
        if self.image is None:
            logger.warning("无可用截图，跳过错误截图保存")
            return ""
        return save_error_screenshot(self.image, name=name)
