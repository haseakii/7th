"""
E7 OCR 引擎 — RapidOCR 封装，提供 ALAS 兼容接口

保留 RapidOCR 的全部功能（物品识别已验证可用），
同时提供与 ALAS cnocr Ocr/Digit 类兼容的接口。
"""

import time
from typing import List, Optional, Tuple

import numpy as np

from module.logger import logger
from tasks.secret_shop.ocr_engine import OcrEngine, TextBlock


# 复用 RapidOCR 引擎单例
_rapid_ocr = OcrEngine()


class E7Ocr:
    """E7 OCR 引擎，基于 RapidOCR。

    提供与 ALAS Ocr 类相似的高层接口，
    但后端使用 RapidOCR（已验证中英文混合识别效果好）。
    """

    SHOW_LOG = True

    def __init__(self, buttons, lang='e7', letter=None, threshold=128, alphabet=None, name=None):
        self.name = name or str(buttons)
        self._buttons = buttons
        self.letter = letter
        self.threshold = threshold
        self.alphabet = alphabet

    @property
    def buttons(self):
        buttons = self._buttons
        if not isinstance(buttons, list):
            buttons = [buttons]
        return [b.area if hasattr(b, 'area') else b for b in buttons]

    @buttons.setter
    def buttons(self, value):
        self._buttons = value

    def ocr(self, image, direct_ocr=False):
        """执行 OCR 识别。

        Args:
            image: np.ndarray 截图
            direct_ocr: 是否跳过裁剪（内部使用）

        Returns:
            list[str]: 识别文本列表
        """
        results = []
        for area in self.buttons:
            blocks = _rapid_ocr.read(image, region=area, min_confidence=0.3)
            text = ''.join(b.text for b in blocks)
            results.append(text)

        if len(self.buttons) == 1:
            results = results[0]

        if self.SHOW_LOG:
            logger.info(f'{self.name}: {results}')

        return results


class E7Digit(E7Ocr):
    """数字 OCR，继承 E7Ocr，返回 int。"""

    def __init__(self, buttons, lang='e7', letter=None, threshold=128,
                 alphabet='0123456789', name=None):
        super().__init__(buttons, lang=lang, letter=letter,
                         threshold=threshold, alphabet=alphabet, name=name)

    def ocr(self, image, direct_ocr=False):
        result = super().ocr(image, direct_ocr=direct_ocr)
        if isinstance(result, list):
            return [int(r) if r.strip().isdigit() else 0 for r in result]
        return int(result) if isinstance(result, str) and result.strip().isdigit() else 0
