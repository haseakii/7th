"""
OCR 后端基类 — 定义 OCR 引擎的标准接口
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from module.logger import logger


@dataclass
class OcrRawResult:
    """OCR 后端的原始输出，经过统一格式转换后传给 OcrEngine 做后处理。"""
    text: str
    confidence: float
    box: List[Tuple[float, float]] = field(default_factory=list)


class BaseOcrBackend(ABC):
    """OCR 后端基类。所有 OCR 引擎继承此类并注册到 Registry。"""

    @abstractmethod
    def initialize(self) -> float:
        """加载模型。返回初始化耗时（秒）。"""
        raise NotImplementedError

    @abstractmethod
    def predict(self, image: np.ndarray) -> List[OcrRawResult]:
        """对图像执行 OCR，返回按从上到下、从左到右排序的识别结果。

        Args:
            image: BGR 格式 numpy 数组

        Returns:
            识别结果列表（未排序也可以，OcrEngine 会统一排序）
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """短标识符，例如 'rapidocr', 'easyocr', 'paddleocr'。"""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        """检查依赖是否可导入（不加载模型）。默认返回 True。"""
        return True
