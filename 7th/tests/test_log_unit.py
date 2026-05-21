"""
日志模块单元测试

覆盖需求: 8.1 (双输出), 8.2 (格式), 8.3 (级别), 8.4 (文件路径), 8.5 (错误截图)
"""

import logging
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# 确保可以导入 7th 下的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from log import ShopBotFormatter, save_error_screenshot, _LOG_DIR, _SCREENSHOT_DIR


class TestShopBotFormatter:
    """测试自定义日志格式器"""

    def setup_method(self):
        self.formatter = ShopBotFormatter()

    def test_format_contains_timestamp(self):
        record = logging.LogRecord(
            name="ShopBot", level=logging.INFO, pathname="", lineno=0,
            msg="测试消息", args=(), exc_info=None
        )
        result = self.formatter.format(record)
        # 验证时间戳格式 [YYYY-MM-DD HH:MM:SS]
        assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", result)

    def test_format_contains_level(self):
        record = logging.LogRecord(
            name="ShopBot", level=logging.WARNING, pathname="", lineno=0,
            msg="警告", args=(), exc_info=None
        )
        result = self.formatter.format(record)
        assert "[WARNING]" in result

    def test_format_contains_module_name(self):
        record = logging.LogRecord(
            name="Navigator", level=logging.INFO, pathname="", lineno=0,
            msg="导航中", args=(), exc_info=None
        )
        result = self.formatter.format(record)
        assert "[Navigator]" in result

    def test_format_contains_message(self):
        record = logging.LogRecord(
            name="ShopBot", level=logging.INFO, pathname="", lineno=0,
            msg="第 15 轮刷新", args=(), exc_info=None
        )
        result = self.formatter.format(record)
        assert "第 15 轮刷新" in result

    def test_format_full_pattern(self):
        """验证完整格式: [timestamp] [level] [module] message"""
        record = logging.LogRecord(
            name="ShopBot", level=logging.INFO, pathname="", lineno=0,
            msg="第 15 轮刷新", args=(), exc_info=None
        )
        result = self.formatter.format(record)
        pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[INFO\] \[ShopBot\] 第 15 轮刷新"
        assert re.match(pattern, result)

    def test_all_log_levels(self):
        """验证 DEBUG, INFO, WARNING, ERROR 四个级别"""
        for level, name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
        ]:
            record = logging.LogRecord(
                name="Test", level=level, pathname="", lineno=0,
                msg="msg", args=(), exc_info=None
            )
            result = self.formatter.format(record)
            assert f"[{name}]" in result


class TestLogger:
    """测试 logger 实例配置"""

    def test_logger_has_handlers(self):
        from log import logger
        assert len(logger.handlers) >= 2

    def test_logger_has_console_handler(self):
        from log import logger
        console_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(console_handlers) >= 1

    def test_logger_has_file_handler(self):
        from log import logger
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) >= 1

    def test_logger_level_is_debug(self):
        from log import logger
        assert logger.level == logging.DEBUG

    def test_log_file_path_contains_date(self):
        from log import logger
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) >= 1
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in file_handlers[0].baseFilename


class TestSaveErrorScreenshot:
    """测试错误截图保存"""

    def test_save_screenshot_creates_file(self, tmp_path):
        """验证截图文件被创建"""
        import log
        original_dir = log._SCREENSHOT_DIR
        log._SCREENSHOT_DIR = tmp_path

        try:
            image = np.zeros((720, 1280, 3), dtype=np.uint8)
            result = save_error_screenshot(image)
            assert result != ""
            assert os.path.exists(result)
        finally:
            log._SCREENSHOT_DIR = original_dir

    def test_save_screenshot_with_name(self, tmp_path):
        """验证带名称前缀的截图"""
        import log
        original_dir = log._SCREENSHOT_DIR
        log._SCREENSHOT_DIR = tmp_path

        try:
            image = np.zeros((720, 1280, 3), dtype=np.uint8)
            result = save_error_screenshot(image, name="test_error")
            assert "test_error" in result
            assert result.endswith(".png")
        finally:
            log._SCREENSHOT_DIR = original_dir

    def test_save_screenshot_invalid_image(self, tmp_path):
        """验证无效图像类型返回空字符串"""
        import log
        original_dir = log._SCREENSHOT_DIR
        log._SCREENSHOT_DIR = tmp_path

        try:
            result = save_error_screenshot("not_an_image")
            assert result == ""
        finally:
            log._SCREENSHOT_DIR = original_dir

    def test_save_screenshot_png_format(self, tmp_path):
        """验证保存为 PNG 格式"""
        import log
        original_dir = log._SCREENSHOT_DIR
        log._SCREENSHOT_DIR = tmp_path

        try:
            image = np.zeros((100, 100, 3), dtype=np.uint8)
            result = save_error_screenshot(image)
            assert result.endswith(".png")
        finally:
            log._SCREENSHOT_DIR = original_dir
