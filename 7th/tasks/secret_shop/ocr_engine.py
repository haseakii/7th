"""
OCR 引擎封装 — 支持多种后端

为识别器、购买引擎、主控循环提供统一的 OCR 接口。
默认使用 RapidOCR，可通过 set_backend() 切换到其他后端。

典型用途:
  >>> from shop.ocr_engine import OCR
  >>> text_blocks = OCR.read(img)                     # 整图 OCR
  >>> text_blocks = OCR.read(img, region=(x1,y1,x2,y2))  # 指定区域
  >>> digit_blocks = OCR.read_digits(img, region=...)     # 只取数字
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from log import logger


@dataclass
class TextBlock:
    """OCR 识别结果中的一个文字块。

    Attributes:
        text: 识别出的文本
        confidence: 置信度 (0-1)
        box: 四边形顶点 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        cx: 中心 x 坐标（排序用）
        cy: 中心 y 坐标（排序用）
    """
    text: str
    confidence: float
    box: List[Tuple[float, float]]
    cx: float = 0.0
    cy: float = 0.0

    def __post_init__(self):
        if self.box:
            xs = [p[0] for p in self.box]
            ys = [p[1] for p in self.box]
            self.cx = sum(xs) / len(xs)
            self.cy = sum(ys) / len(ys)


class OcrEngine:
    """OCR 引擎封装，支持多后端切换，延迟初始化提高性能。"""

    _instance = None
    _backend = None
    _backend_name = "rapidocr"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_backend(cls, name: str) -> None:
        """切换到指定 OCR 后端。

        Args:
            name: 后端名（rapidocr, easyocr, paddleocr 等）
        """
        if name != cls._backend_name:
            cls._backend = None  # 强制重新初始化
            cls._backend_name = name
            logger.info(f"OCR 后端已切换为: '{name}'（下次 OCR 调用时生效）")

    def _ensure_backend(self):
        """确保 OCR 后端已加载。"""
        if self._backend is not None:
            return self._backend
        from tasks.secret_shop.ocr_backends import create as create_backend
        logger.info(f"初始化 OCR 后端: '{self._backend_name}'")
        self._backend = create_backend(self._backend_name)
        return self._backend

    def read(
        self,
        image: np.ndarray,
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.4,
    ) -> List[TextBlock]:
        """对截图（或指定区域）执行 OCR，返回文字块列表。

        Args:
            image: BGR 截图
            region: 可选裁剪区域 (x1, y1, x2, y2)
            min_confidence: 最低置信度阈值

        Returns:
            按从上到下、从左到右排序的文字块列表
        """
        backend = self._ensure_backend()
        if image is None or image.size == 0:
            return []

        img = image[region[1]:region[3], region[0]:region[2]] if region else image
        if img.size == 0:
            return []

        raw_results = backend.predict(img)
        blocks = []
        for raw in raw_results:
            if raw.confidence < min_confidence:
                continue
            block = TextBlock(
                text=raw.text,
                confidence=raw.confidence,
                box=raw.box,
            )
            if region:
                block.cx += region[0]
                block.cy += region[1]
            blocks.append(block)

        blocks.sort(key=lambda b: (round(b.cy / 20), b.cx))
        return blocks

    def read_texts(
        self,
        image: np.ndarray,
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.4,
    ) -> List[str]:
        """仅返回文本列表，适合快速判断。"""
        return [b.text for b in self.read(image, region, min_confidence)]

    def read_digits(
        self,
        image: np.ndarray,
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.3,
    ) -> List[TextBlock]:
        """仅保留纯数字/标点结果（过滤非数字文本）。"""
        blocks = self.read(image, region, min_confidence)
        return [b for b in blocks if self._is_numeric_text(b.text)]

    def find_text(
        self,
        image: np.ndarray,
        target: str,
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.4,
    ) -> Optional[TextBlock]:
        """在截图中搜索指定文本，返回第一个匹配项。"""
        for block in self.read(image, region, min_confidence):
            if target in block.text:
                return block
        return None

    def find_any_text(
        self,
        image: np.ndarray,
        targets: List[str],
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.4,
    ) -> Optional[TextBlock]:
        """搜索多个目标文本，返回第一个匹配项。"""
        for block in self.read(image, region, min_confidence):
            for target in targets:
                if target in block.text:
                    return block
        return None

    @staticmethod
    def _is_numeric_text(text: str) -> bool:
        cleaned = text.replace(",", "").replace(".", "").replace(" ", "")
        return cleaned.isdigit() and len(cleaned) > 0

    def read_number(
        self,
        image: np.ndarray,
        region: Optional[Tuple[int, int, int, int]] = None,
        min_confidence: float = 0.3,
    ) -> Tuple[Optional[int], float]:
        """从区域读取一个数字值，返回 (数值, 置信度)。

        合并同一行上相近的数字块（OCR 可能将 "25,260" 拆成 "25"+"260"），
        取合并后最长的完整数字。
        无有效数字时返回 (None, 0.0)。
        """
        digits = self.read_digits(image, region, min_confidence)
        if not digits:
            return None, 0.0

        # 按 y 坐标分组（同一行差距 < 10px）
        rows: List[List[TextBlock]] = []
        for d in sorted(digits, key=lambda b: b.cy):
            if not rows or abs(d.cy - rows[-1][0].cy) > 10:
                rows.append([d])
            else:
                rows[-1].append(d)

        # 对每行按 x 排序，合并相邻块（间距 < 30px）
        best_value: Optional[int] = None
        best_conf = 0.0
        for row in rows:
            row.sort(key=lambda b: b.cx)
            merged = ""
            conf_sum = 0.0
            prev_bx2 = 0
            for b in row:
                bx2 = b.box[1][0] if b.box else b.cx + 20
                if merged and (b.cx - prev_bx2) > 30:
                    # 间距过大，不合并，尝试当前已合并结果
                    pass
                merged += b.text.replace(",", "").replace(" ", "")
                conf_sum += b.confidence
                prev_bx2 = bx2

            if merged and merged.isdigit():
                avg_conf = conf_sum / len(row)
                val = int(merged)
                if avg_conf > best_conf:
                    best_value = val
                    best_conf = avg_conf

        if best_value is not None:
            return best_value, best_conf
        return None, 0.0


# 模块级单例（方便直接导入使用）
OCR = OcrEngine()
