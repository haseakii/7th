"""
OCR 后端注册中心和工厂方法

提供 @register 装饰器和 create() 工厂。
OCR 不做 auto-benchmark（准确率比速度更重要），由用户手动选择。
"""

import time
from typing import Dict, List, Optional, Type

from log import logger
from tasks.secret_shop.ocr_backends.base import BaseOcrBackend


# ── 注册中心 ──────────────────────────────────────────────────────────────────
_ocr_registry: Dict[str, Type[BaseOcrBackend]] = {}


def register(name: Optional[str] = None):
    """装饰器：将 OCR 后端类注册到全局注册表。"""
    def decorator(cls: Type[BaseOcrBackend]):
        key = name or cls.__name__.lower()
        _ocr_registry[key] = cls
        return cls
    return decorator


# ── 工厂 ──────────────────────────────────────────────────────────────────────

def create(method: str) -> BaseOcrBackend:
    """创建 OCR 后端实例。

    Args:
        method: 后端名

    Returns:
        已初始化的 OCR 后端实例
    """
    key = method.lower().strip()

    cls = _ocr_registry.get(key)
    if cls is None:
        available = ", ".join(available_methods())
        logger.warning(
            f"未知 OCR 后端 '{method}'，可用后端: {available}，使用默认 'rapidocr'"
        )
        cls = _ocr_registry.get("rapidocr")
        if cls is None:
            raise RuntimeError("无可用 OCR 后端（rapidocr 也未注册）")

    instance = cls()
    t0 = time.time()
    init_time = instance.initialize()
    logger.info(f"OCR 后端 '{key}' 就绪（初始化耗时 {init_time:.1f}s）")
    return instance


def available_methods() -> List[str]:
    """返回所有可用的后端名（is_available=True 的）。"""
    result: List[str] = []
    for key, cls in _ocr_registry.items():
        try:
            if cls().is_available:
                result.append(key)
        except Exception:
            result.append(key)
    return result


# ── 导入具体后端触发注册 ──────────────────────────────────────────────────────
from tasks.secret_shop.ocr_backends.backends import (  # noqa: F401,E402
    RapidOcrBackend,
    EasyOcrBackend,
    PaddleOcrBackend,
)
