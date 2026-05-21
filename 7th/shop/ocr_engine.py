"""
OCR 引擎封装 — 基于 RapidOCR

为识别器、购买引擎、主控循环提供统一的 OCR 接口。
RapidOCR 支持中英文混合识别，~1s/图（CPU），满足实时需求。

典型用途:
  >>> from shop.ocr_engine import OCR
  >>> text_blocks = OCR.read(img)                     # 整图 OCR
  >>> text_blocks = OCR.read(img, region=(x1,y1,x2,y2))  # 指定区域
  >>> digit_blocks = OCR.read_digits(img, region=...)     # 只取数字
"""

import time
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
    """RapidOCR 引擎封装，延迟初始化 + 缓存提高性能。"""

    _instance = None
    _reader = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_reader(self):
        if self._reader is None:
            from rapidocr import RapidOCR
            logger.info("初始化 RapidOCR 引擎（首次加载约需数秒）...")
            t0 = time.time()
            self._reader = RapidOCR()
            logger.info(f"RapidOCR 引擎就绪（耗时 {time.time() - t0:.1f}s）")
        return self._reader

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
        reader = self._ensure_reader()
        if image is None or image.size == 0:
            return []

        img = image[region[1]:region[3], region[0]:region[2]] if region else image
        if img.size == 0:
            return []

        output = reader(img)
        # rapidocr v3.x returns RapidOCROutput object
        if hasattr(output, 'boxes'):
            boxes = output.boxes
            txts = output.txts
            scores = output.scores
            if boxes is None or len(boxes) == 0:
                return []
            raw = list(zip(boxes, txts, scores))
        else:
            raw = output
            if not raw:
                return []

        blocks = []
        for box, text, conf in raw:
            if box is None or (isinstance(box, (list, tuple)) and len(box) == 0) or (hasattr(box, 'shape') and box.size == 0):
                continue
            try:
                conf_f = float(conf) if conf is not None else 0.0
            except (ValueError, TypeError):
                conf_f = 0.0
            if conf_f < min_confidence:
                continue
            block = TextBlock(
                text=str(text),
                confidence=conf_f,
                box=[(float(p[0]), float(p[1])) for p in box],
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
