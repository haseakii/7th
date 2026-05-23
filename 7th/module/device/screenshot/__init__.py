"""
截图策略注册中心和工厂方法

提供 @register 装饰器、create() 工厂和 auto_select() 自动选择功能。
"""

import time
from typing import Dict, List, Optional, Type

from log import logger
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
        method: 策略名（'auto' 表示自动选择最佳策略）
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
            raise RuntimeError("无可用截图策略（ad裸策略也未注册）")

    instance = cls(serial)
    instance.initialize()
    return instance


def auto_select(serial: str) -> ScreenshotStrategy:
    """自动测试所有已注册策略，选最快的。

    遍历注册表中的策略，对每个策略尝试 initialize() 和 benchmark(3)，
    选择平均耗时最短的策略。初始化失败的策略会被跳过并记录警告。

    Args:
        serial: 设备序列号

    Returns:
        经 benchmark 测试的最快策略实例
    """
    logger.info("===== 截图策略自动检测 =====")
    results: List[tuple] = []  # (name, avg_ms, instance)

    for name, cls in _screenshot_registry.items():
        instance = cls(serial)
        try:
            logger.info(f"测试截图方式 '{name}'...")
            if not instance.initialize():
                logger.warning(f"  '{name}' 初始化失败，跳过")
                continue
            avg_ms = instance.benchmark(iterations=3)
            logger.info(f"  '{name}' 平均 {avg_ms:.1f}ms")
            results.append((avg_ms, instance))
        except Exception as e:
            logger.warning(f"  '{name}' 测试失败: {e}，跳过")

    if not results:
        logger.error("所有截图策略均不可用，使用 ADB 截图（兜底）")
        from module.device.screenshot.strategies import AdbScreenshot
        instance = AdbScreenshot(serial)
        instance.initialize()
        return instance

    results.sort(key=lambda x: x[0])
    best = results[0][1]
    logger.info(
        f"选择截图方式 '{best.name}' ({results[0][0]:.1f}ms)，"
        + (f"比 '{results[-1][1].name}' 快 {results[-1][0] / results[0][0]:.1f}x"
           if len(results) > 1 else "")
    )
    return best


def available_methods() -> List[str]:
    """返回所有已注册的策略名 + 'auto'。"""
    return ["auto"] + sorted(_screenshot_registry.keys())


# ── 导入具体策略触发注册 ──────────────────────────────────────────────────────
from module.device.screenshot.strategies import AdbScreenshot, AdbRawScreenshot, U2Screenshot  # noqa: F401,E402
