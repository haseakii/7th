"""
日志模块

独立的 logger 模块，支持控制台 + 文件双输出。
日志格式：[时间戳] [级别] [模块] 消息
日志文件保存到 logs/YYYY-MM-DD.log
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# 项目根目录（7th/）— 兼容 PyInstaller 打包后的路径
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后，exe 所在目录
    _BASE_DIR = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path(__file__).resolve().parent
_LOG_DIR = _BASE_DIR / "logs"
_SCREENSHOT_DIR = _BASE_DIR / "screenshots" / "error"


class ShopBotFormatter(logging.Formatter):
    """自定义日志格式器: [时间戳] [级别] [模块] 消息"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        module = record.name
        message = record.getMessage()
        return f"[{timestamp}] [{level}] [{module}] {message}"


def _get_daily_file_handler() -> logging.FileHandler:
    """创建按日期命名的文件 handler"""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    handler = logging.FileHandler(str(log_file), encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ShopBotFormatter())
    return handler


def _get_console_handler() -> logging.StreamHandler:
    """创建控制台 handler"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(ShopBotFormatter())
    return handler


def _setup_logger(name: str = "ShopBot") -> logging.Logger:
    """初始化并返回 logger 实例"""
    _logger = logging.getLogger(name)
    _logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if not _logger.handlers:
        _logger.addHandler(_get_console_handler())
        _logger.addHandler(_get_daily_file_handler())

    _logger.propagate = False
    return _logger


def save_error_screenshot(image: np.ndarray, name: str = "") -> str:
    """
    保存错误截图到 screenshots/error/ 目录。

    Args:
        image: numpy array 格式的截图 (BGR 或 RGB)
        name: 可选的截图名称前缀

    Returns:
        str: 保存的文件路径
    """
    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}.png" if name else f"{timestamp}.png"
    filepath = _SCREENSHOT_DIR / filename

    if isinstance(image, np.ndarray):
        cv2.imwrite(str(filepath), image)
    else:
        logger.warning(f"无法保存截图: 无效的图像类型 {type(image)}")
        return ""

    logger.info(f"错误截图已保存: {filepath}")
    return str(filepath)


class AlasCompatibleLogger:
    """ALAS 兼容包装，在标准 logging.Logger 上添加 hr() 等方法。"""

    def __init__(self, logger_inst):
        self._logger = logger_inst

    def __getattr__(self, name):
        return getattr(self._logger, name)

    def hr(self, title="", level=1):
        """打印分隔线，ALAS 风格。"""
        if level == 0:
            self._logger.info(f"{'=' * 15} {title} {'=' * 15}")
        elif level == 1:
            self._logger.info(f"{'-' * 10} {title} {'-' * 10}")
        elif level == 2:
            self._logger.info(f"{'~' * 5} {title} {'~' * 5}")
        else:
            self._logger.info(f"{'*' * 5} {title} {'*' * 5}")


# 模块级 logger 实例
_logger_inst = _setup_logger()
logger = AlasCompatibleLogger(_logger_inst)
