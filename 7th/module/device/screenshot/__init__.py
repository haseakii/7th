"""
截图策略注册中心和工厂方法

提供 @register 装饰器、create() 工厂和 benchmark_all() 性能测试功能。
"""

import time
from typing import Dict, List, Optional, Type

from module.logger import logger
from module.device.screenshot.base import ScreenshotStrategy


# ── 注册中心 ──────────────────────────────────────────────────────────────────
_screenshot_registry: Dict[str, Type[ScreenshotStrategy]] = {}


def register(name: Optional[str] = None):
    """装饰器：将截图策略类注册到全局注册表。

    Args:
        name: 注册名，默认为类名转小写。
    """
    def decorator(cls: Type[ScreenshotStrategy]):
        key = name or cls.__name__.lower()
        _screenshot_registry[key] = cls
        return cls
    return decorator


# ── 工厂 ──────────────────────────────────────────────────────────────────────

def create(method: str, serial: str) -> ScreenshotStrategy:
    """创建截图策略实例。

    Args:
        method: 策略名（'auto' 表示快速选择第一个能用的，不跑 benchmark）
        serial: 设备序列号

    Returns:
        已初始化的策略实例
    """
    key = method.lower().strip()
    if key == "auto":
        return auto_select(serial)

    cls = _screenshot_registry.get(key)
    if cls is None:
        available = ", ".join(available_methods())
        logger.warning(
            f"未知截图方式 '{method}'，可用方式: {available}，使用默认 'adb'"
        )
        cls = _screenshot_registry.get("adb")
        if cls is None:
            raise RuntimeError("无可用截图策略（adb 策略也未注册）")

    instance = cls(serial)
    instance.initialize()
    return instance


def auto_select(serial: str) -> ScreenshotStrategy:
    """快速选择第一个能用的策略，不跑 benchmark。

    按注册顺序尝试各策略，返回第一个初始化成功的。
    完整的 benchmark 性能对比请在 WebUI 工具页执行。
    """
    logger.info("自动选择截图方式...")
    for name, cls in _screenshot_registry.items():
        instance = cls(serial)
        try:
            logger.info(f"尝试截图方式 '{name}'...")
            if instance.initialize():
                logger.info(f"选择截图方式: '{name}'")
                return instance
        except Exception as e:
            logger.debug(f"截图方式 '{name}' 初始化失败: {e}")
            continue

    logger.error("所有截图策略均不可用，使用 ADB 截图（兜底）")
    from module.device.screenshot.strategies import AdbScreenshot
    instance = AdbScreenshot(serial)
    instance.initialize()
    return instance


def benchmark_all(serial: str, iterations: int = 3) -> List[dict]:
    """对所有已注册策略跑 benchmark，返回排序后的结果。

    Args:
        serial: 设备序列号
        iterations: 每个策略测试次数

    Returns:
        按平均耗时排序的列表，每项含 name / avg_ms / success
    """
    results = []
    for name, cls in _screenshot_registry.items():
        instance = cls(serial)
        try:
            if not instance.initialize():
                results.append({"name": name, "avg_ms": None, "success": False, "note": "初始化失败"})
                continue
            avg = instance.benchmark(iterations=iterations)
            results.append({"name": name, "avg_ms": avg, "success": True, "note": ""})
        except Exception as e:
            logger.warning(f"截图方式 '{name}' benchmark 失败: {e}")
            results.append({"name": name, "avg_ms": None, "success": False, "note": str(e)[:60]})

    results.sort(key=lambda r: (not r["success"], r["avg_ms"] if r["avg_ms"] else float("inf")))
    return results


def available_methods() -> List[str]:
    """返回所有已注册的策略名 + 'auto'。"""
    return ["auto"] + sorted(_screenshot_registry.keys())


# ── 移除 fake PIL 模块，恢复真实 PIL ──────────────────────────────────────
# WebUI 启动时（app.py）会注入假 PIL 避免 pywebio 加载慢，
# 但 uiautomator2/adbutils 需要真实 PIL，在此全局恢复。
try:
    from module.webui.fake_pil_module import remove_fake_pil_module
    remove_fake_pil_module()
except ImportError:
    pass

# ── 导入具体策略触发注册 ──────────────────────────────────────────────────────
from module.device.screenshot.strategies import (  # noqa: F401,E402
    AdbScreenshot, AdbNcScreenshot, U2Screenshot,
    AScreenCapScreenshot, AScreenCapNcScreenshot,
    DroidCastScreenshot, DroidCastRawScreenshot,
    NemuIpcScreenshot, LdopenglScreenshot,
)
