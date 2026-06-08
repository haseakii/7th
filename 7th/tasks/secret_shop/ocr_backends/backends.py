"""
OCR 后端具体实现
"""

import os
import time

import cv2
import numpy as np

from module.logger import logger
from module.device.alas_paths import CNOCR_MODEL_DIR
from tasks.secret_shop.ocr_backends.base import BaseOcrBackend, OcrRawResult
from tasks.secret_shop.ocr_backends import register


@register("rapidocr")
class RapidOcrBackend(BaseOcrBackend):
    """RapidOCR 后端（ONNX Runtime），轻量快速。"""

    def __init__(self):
        self._reader = None

    def initialize(self) -> float:
        from rapidocr import RapidOCR
        t0 = time.perf_counter()
        # ONNX Runtime 内存优化：
        # - intra_op_num_threads=2: 限制线程工作缓冲区
        # - enable_cpu_mem_arena: 启用内存池减少碎片化
        params = {
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
            "EngineConfig.onnxruntime.enable_cpu_mem_arena": True,
            "EngineConfig.onnxruntime.cpu_ep_cfg.arena_extend_strategy": "kSameAsRequested",
        }
        self._reader = RapidOCR(params=params)
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


@register("alas")
class AlasOcrBackend(BaseOcrBackend):
    """ALAS 原生 OCR 后端（cnocr densenet-lite-gru），轻量游戏界面专用。

    复用 ALAS `bin/cnocr_models/cnocr/` 模型文件。
    适合英文/数字识别；中文识别使用 cnocr 通用模型（含 6426 字符）。
    """

    def __init__(self):
        self._reader = None
        self._model_name = None

    def initialize(self) -> float:
        from cnocr import CnOcr
        t0 = time.perf_counter()

        model_dir = CNOCR_MODEL_DIR if os.path.isdir(CNOCR_MODEL_DIR) else None
        if model_dir is None:
            logger.warning(f"ALAS OCR 模型目录不存在: {CNOCR_MODEL_DIR}，回退到 cnocr 内置模型")

        self._reader = CnOcr(
            model_name='densenet-lite-gru',
            model_epoch=39,
            root=model_dir or None,
            name='cnocr',
        )
        self._model_name = 'alas_cnocr'
        return time.perf_counter() - t0

    @property
    def name(self) -> str:
        return "alas"

    @property
    def is_available(self) -> bool:
        try:
            from cnocr import CnOcr  # noqa: F401
            return True
        except ImportError:
            return False

    def predict(self, image: np.ndarray) -> list:
        # CnOcr 需要 RGB 输入
        if image.shape[2] == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb = image
        raw = self._reader.ocr(rgb)
        results = []
        if not raw:
            return results
        for item in raw:
            text = item['text'] if isinstance(item, dict) else item[0]
            score = item.get('score', 0) if isinstance(item, dict) else item[1]
            position = item.get('position', []) if isinstance(item, dict) else item[2]
            if score is not None and score < 0.3:
                continue
            box = [(float(p[0]), float(p[1])) for p in (position or [])]
            results.append(OcrRawResult(
                text=str(text),
                confidence=float(score) if score is not None else 0.0,
                box=box,
            ))
        return results
