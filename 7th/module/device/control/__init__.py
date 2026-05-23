"""
控制策略注册中心和工厂方法

提供 @register 装饰器和 create() 工厂。
控制不做 auto-benchmark，而是按优先级尝试第一个能用的。
"""

from typing import Dict, List, Optional, Type

from log import logger
from module.device.control.base import ControlStrategy


# ── 注册中心 ──────────────────────────────────────────────────────────────────
_control_registry: Dict[str, Type[ControlStrategy]] = {}


def register(name: Optional[str] = None):
    """装饰器：将控制策略类注册到全局注册表。"""
    def decorator(cls: Type[ControlStrategy]):
        key = name or cls.__name__.lower()
        _control_registry[key] = cls
        return cls
    return decorator


# ── 工厂 ──────────────────────────────────────────────────────────────────────

def create(method: str, serial: str) -> ControlStrategy:
    """创建控制策略实例。

    Args:
        method: 策略名（'auto' 表示自动选择第一个能用的）
        serial: 设备序列号

    Returns:
        已初始化的策略实例
    """
    key = method.lower().strip()
    if key == "auto":
        return auto_select(serial)

    cls = _control_registry.get(key)
    if cls is None:
        available = ", ".join(available_methods())
        logger.warning(
            f"未知控制方式 '{method}'，可用方式: {available}，使用默认 'adb'"
        )
        cls = _control_registry.get("adb")
        if cls is None:
            raise RuntimeError("无可用控制策略（adb 策略也未注册）")

    instance = cls(serial)
    instance.initialize()
    return instance


def auto_select(serial: str) -> ControlStrategy:
    """按优先级尝试各控制策略，返回第一个能用的。

    优先级：adb（无额外依赖） > uiautomator2
    """
    logger.info("自动检测控制方式...")
    for name, cls in _control_registry.items():
        try:
            instance = cls(serial)
            if instance.initialize():
                logger.info(f"选择控制方式: '{name}'")
                return instance
        except Exception as e:
            logger.debug(f"控制方式 '{name}' 初始化失败: {e}")
            continue

    # 兜底：用 ADB 控制
    logger.warning("所有控制策略均不可用，使用 ADB 控制（兜底）")
    from module.device.control.strategies import AdbControl
    instance = AdbControl(serial)
    instance.initialize()
    return instance


def available_methods() -> List[str]:
    """返回所有已注册的策略名 + 'auto'。"""
    return ["auto"] + sorted(_control_registry.keys())


# ── 导入具体策略触发注册 ──────────────────────────────────────────────────────
from module.device.control.strategies import AdbControl, U2Control  # noqa: F401,E402
