"""
OCR 后端具体实现
"""

import time

import cv2
import numpy as np

from log import logger
from shop.ocr_backends.base import BaseOcrBackend, OcrRawResult
from shop.ocr_backends import register


@register("rapidocr")
class RapidOcrBackend(BaseOcrBackend):
    """RapidOCR 后端（ONNX Runtime），轻量快速。"""

    def __init__(self):
        self._reader = None

    def initialize(self) -> float:
        from rapidocr import RapidOCR
        t0 = time.perf_counter()
        self._reader = RapidOCR()
        return time.perf_counter() - t0

    @property
    def name(self) -> str:
        return "rapidocr"

    def predict(self, image: np.ndarray) -> list:
        output = self._reader(image)
        # rapidocr v3.x returns RapidOCROutput object with .boxes/.txts/.scores
        if hasattr(output, 'boxes'):
            boxes = output.boxes
            txts = output.txts
            scores = output.scores
            if boxes is None or txts is None:
                return []
            raw = list(zip(boxes, txts, scores))
        elif output:
            raw = output
        else:
            return []

        results = []
        for box, text, conf in raw:
            if box is None or (isinstance(box, (list, tuple)) and len(box) == 0):
                continue
            try:
                conf_f = float(conf) if conf is not None else 0.0
            except (ValueError, TypeError):
                conf_f = 0.0
            results.append(OcrRawResult(
                text=str(text),
                confidence=conf_f,
                box=[(float(p[0]), float(p[1])) for p in box],
            ))
        return results


@register("easyocr")
class EasyOcrBackend(BaseOcrBackend):
    """EasyOCR 后端（PyTorch），多语言支持，更适合复杂字体。"""

    def __init__(self):
        self._reader = None

    def initialize(self) -> float:
        import easyocr
        t0 = time.perf_counter()
        self._reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        return time.perf_counter() - t0

    @property
    def name(self) -> str:
        return "easyocr"

    @property
    def is_available(self) -> bool:
        try:
            import easyocr  # noqa: F401
            return True
        except ImportError:
            return False

    def predict(self, image: np.ndarray) -> list:
        # easyocr 需要 RGB 输入
        if image.shape[2] == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb = image
        raw = self._reader.readtext(rgb)
        results = []
        for bbox, text, conf in raw:
            if conf < 0.3:
                continue
            box = [(float(p[0]), float(p[1])) for p in bbox]
            results.append(OcrRawResult(
                text=str(text),
                confidence=float(conf),
                box=box,
            ))
        return results


@register("paddleocr")
class PaddleOcrBackend(BaseOcrBackend):
    """PaddleOCR 后端，中英文识别精度高。"""

    def __init__(self):
        self._reader = None

    def initialize(self) -> float:
        from paddleocr import PaddleOCR
        t0 = time.perf_counter()
        self._reader = PaddleOCR(
            use_angle_cls=False, lang='ch', show_log=False, use_gpu=False,
        )
        return time.perf_counter() - t0

    @property
    def name(self) -> str:
        return "paddleocr"

    @property
    def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR  # noqa: F401
            return True
        except ImportError:
            return False

    def predict(self, image: np.ndarray) -> list:
        raw = self._reader.ocr(image, cls=False)
        results = []
        if not raw or not raw[0]:
            return results
        for line in raw[0]:
            bbox, (text, conf) = line
            if conf < 0.3:
                continue
            box = [(float(p[0]), float(p[1])) for p in bbox]
            results.append(OcrRawResult(
                text=str(text),
                confidence=float(conf),
                box=box,
            ))
        return results
