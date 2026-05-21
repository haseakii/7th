"""
DeviceController 单元测试

覆盖需求: 1.1 (ADB 连接), 1.2 (连接重试), 1.3 (重试失败终止),
          1.4 (截图 1280x720), 1.5 (ADB/u2 截图方式)
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config_manager import DeviceConfig
from module.device.device import DeviceController


class TestDeviceControllerInit:
    """测试 DeviceController 初始化"""

    def test_init_with_default_config(self):
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.serial == "127.0.0.1:5555"
        assert dc.screenshot_method == "ADB"
        assert dc.control_method == "ADB"
        assert dc.image is None
        assert dc._u2_device is None

    def test_init_with_custom_config(self):
        config = DeviceConfig(
            serial="192.168.1.100:5555",
            screenshot_method="uiautomator2",
            control_method="uiautomator2"
        )
        dc = DeviceController(config)
        assert dc.serial == "192.168.1.100:5555"
        assert dc.screenshot_method == "uiautomator2"
        assert dc.control_method == "uiautomator2"


class TestConnect:
    """测试设备连接"""

    @patch("module.device.device.subprocess.run")
    def test_connect_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="connected to 127.0.0.1:5555", returncode=0)
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.connect() is True

    @patch("module.device.device.subprocess.run")
    def test_connect_already_connected(self, mock_run):
        mock_run.return_value = MagicMock(stdout="already connected to 127.0.0.1:5555", returncode=0)
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.connect() is True

    @patch("module.device.device.time.sleep")
    @patch("module.device.device.subprocess.run")
    def test_connect_retry_then_success(self, mock_run, mock_sleep):
        """第一次失败，第二次成功"""
        mock_run.side_effect = [
            MagicMock(stdout="failed to connect", returncode=1),
            MagicMock(stdout="connected to 127.0.0.1:5555", returncode=0),
        ]
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.connect(max_retries=3, retry_delay=1.0) is True
        mock_sleep.assert_called_once_with(1.0)

    @patch("module.device.device.time.sleep")
    @patch("module.device.device.subprocess.run")
    def test_connect_all_retries_fail(self, mock_run, mock_sleep):
        """所有重试都失败，返回 False"""
        mock_run.return_value = MagicMock(stdout="failed", returncode=1)
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.connect(max_retries=3, retry_delay=0.1) is False
        # 应该重试 2 次（第 1 次失败后 sleep，第 2 次失败后 sleep，第 3 次失败不 sleep）
        assert mock_sleep.call_count == 2

    @patch("module.device.device.time.sleep")
    @patch("module.device.device.subprocess.run")
    def test_connect_exception_triggers_retry(self, mock_run, mock_sleep):
        """subprocess 抛异常也应触发重试"""
        mock_run.side_effect = [
            Exception("adb not found"),
            MagicMock(stdout="connected to 127.0.0.1:5555", returncode=0),
        ]
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.connect(max_retries=2, retry_delay=0.1) is True


class TestScreenshot:
    """测试截图功能"""

    @patch("module.device.device.subprocess.run")
    def test_screenshot_adb_stores_image(self, mock_run):
        """ADB 截图应存储到 self.image"""
        # 创建一个假的 PNG 图像
        fake_image = np.zeros((720, 1280, 3), dtype=np.uint8)
        _, png_data = cv2.imencode(".png", fake_image)

        mock_run.return_value = MagicMock(
            stdout=png_data.tobytes(), returncode=0
        )
        config = DeviceConfig()
        dc = DeviceController(config)
        result = dc.screenshot()

        assert result is not None
        assert result.shape == (720, 1280, 3)
        assert dc.image is not None

    @patch("module.device.device.subprocess.run")
    def test_screenshot_adb_resizes_to_1280x720(self, mock_run):
        """非标准分辨率应被 resize 到 1280x720"""
        fake_image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        _, png_data = cv2.imencode(".png", fake_image)

        mock_run.return_value = MagicMock(
            stdout=png_data.tobytes(), returncode=0
        )
        config = DeviceConfig()
        dc = DeviceController(config)
        result = dc.screenshot()

        assert result.shape == (720, 1280, 3)

    @patch("module.device.device.subprocess.run")
    def test_screenshot_adb_failure_raises(self, mock_run):
        """ADB 截图失败应抛出 RuntimeError"""
        mock_run.return_value = MagicMock(
            stdout=b"", returncode=1,
            stderr=b"error: device not found"
        )
        config = DeviceConfig()
        dc = DeviceController(config)
        with pytest.raises(RuntimeError):
            dc.screenshot()

    def test_screenshot_u2_without_init_raises(self):
        """未初始化 u2 设备时截图应抛出 RuntimeError"""
        config = DeviceConfig(screenshot_method="uiautomator2")
        dc = DeviceController(config)
        with pytest.raises(RuntimeError, match="uiautomator2 设备未初始化"):
            dc.screenshot()


class TestClick:
    """测试点击功能"""

    @patch("module.device.device.subprocess.run")
    def test_click_adb_calls_input_tap(self, mock_run):
        """ADB 点击应调用 adb shell input tap"""
        config = DeviceConfig()
        dc = DeviceController(config)
        button = MagicMock()
        button.button = (100, 200, 300, 400)
        button.__str__ = lambda self: "TEST_BTN"

        dc.click(button)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "input" in args
        assert "tap" in args

    def test_click_u2_without_init_raises(self):
        """未初始化 u2 设备时点击应抛出 RuntimeError"""
        config = DeviceConfig(control_method="uiautomator2")
        dc = DeviceController(config)
        button = MagicMock()
        button.button = (100, 200, 300, 400)

        with pytest.raises(RuntimeError, match="uiautomator2 设备未初始化"):
            dc.click(button)


class TestSwipe:
    """测试滑动功能"""

    @patch("module.device.device.subprocess.run")
    def test_swipe_adb_calls_input_swipe(self, mock_run):
        """ADB 滑动应调用 adb shell input swipe"""
        config = DeviceConfig()
        dc = DeviceController(config)
        dc.swipe((100, 200), (300, 400), duration=0.5)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "input" in args
        assert "swipe" in args
        # 验证 duration 转换为毫秒
        assert "500" in args

    def test_swipe_u2_without_init_raises(self):
        """未初始化 u2 设备时滑动应抛出 RuntimeError"""
        config = DeviceConfig(control_method="uiautomator2")
        dc = DeviceController(config)

        with pytest.raises(RuntimeError, match="uiautomator2 设备未初始化"):
            dc.swipe((100, 200), (300, 400))


class TestSaveErrorScreenshot:
    """测试错误截图保存"""

    def test_save_error_screenshot_no_image(self):
        """没有截图时应返回空字符串"""
        config = DeviceConfig()
        dc = DeviceController(config)
        assert dc.image is None
        result = dc.save_error_screenshot("test")
        assert result == ""

    def test_save_error_screenshot_with_image(self, tmp_path):
        """有截图时应保存并返回路径"""
        import log
        original_dir = log._SCREENSHOT_DIR
        log._SCREENSHOT_DIR = tmp_path

        try:
            config = DeviceConfig()
            dc = DeviceController(config)
            dc.image = np.zeros((720, 1280, 3), dtype=np.uint8)
            result = dc.save_error_screenshot("device_error")
            assert result != ""
            assert "device_error" in result
            assert result.endswith(".png")
        finally:
            log._SCREENSHOT_DIR = original_dir
