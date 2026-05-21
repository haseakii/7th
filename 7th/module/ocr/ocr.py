"""
OCR 识别（基于 ALAS cnocr 方案）

使用本地 cnocr 模型进行 OCR，支持数字识别（价格）、通用文字识别。
模型文件位于 ./bin/cnocr_models/ 下。
"""

from typing import Union

import numpy as np

from module.base.button import Button
from module.base.utils import crop, extract_letters
from module.logger import logger
from module.ocr.models import OCR_MODEL


class Ocr:
    """Base OCR class. Crops image areas, preprocesses, and runs OCR.

    The pipeline:
        1. Crop the button area from the screenshot
        2. Pre-process: extract letter pixels (binarize by color)
        3. Call cnocr model
        4. Post-process the recognized text

    Attributes:
        SHOW_LOG: Whether to log OCR results.
    """

    SHOW_LOG = True

    def __init__(self, buttons, lang='azur_lane', letter=(255, 255, 255),
                 threshold=128, alphabet=None, name=None):
        self.buttons = buttons if isinstance(buttons, (list, tuple)) else [buttons]
        self.lang = lang
        self.letter = letter
        self.threshold = threshold
        self.alphabet = alphabet
        self.name = name or str(buttons)

    def ocr(self, image):
        if not isinstance(image, np.ndarray):
            return []

        result_list = []
        for button in self.buttons:
            im = crop(image, button.area)
            im = extract_letters(im, letter=self.letter, threshold=self.threshold)
            if im is not None:
                res = self._recognize(im)
                result_list.append(res)
            else:
                result_list.append([])

        if len(self.buttons) == 1:
            result_list = result_list[0]

        if self.SHOW_LOG:
            logger.info(f'OCR [{self.name}]: {result_list}')
        return result_list

    def _recognize(self, im):
        model = getattr(OCR_MODEL, self.lang)
        result = model.atomic_ocr_for_single_lines(
            [im], cand_alphabet=self.alphabet
        )
        return result[0] if result else []


class Digit(Ocr):
    """数字 OCR，用于识别价格。"""

    def __init__(self, buttons, lang='azur_lane', letter=(255, 255, 255),
                 threshold=128, alphabet=None, name=None):
        super().__init__(
            buttons,
            lang=lang,
            letter=letter,
            threshold=threshold,
            alphabet=alphabet or '0123456789',
            name=name or 'Digit',
        )

    def ocr(self, image) -> Union[int, list]:
        result = super().ocr(image)
        if isinstance(result, list) and len(result) == 0:
            return 0 if len(self.buttons) == 1 else [0] * len(self.buttons)

        def to_digit(text_list):
            if not text_list:
                return 0
            text = ''.join(str(c) for c in text_list)
            # Replace common OCR errors
            text = text.replace('O', '0').replace('o', '0')
            text = text.replace('I', '1').replace('l', '1')
            text = text.replace('S', '5').replace('B', '8')
            text = text.replace('Z', '2').replace('T', '7')
            try:
                return int(text)
            except ValueError:
                return 0

        if isinstance(result, list) and len(result) == len(self.buttons):
            return [to_digit(r) for r in result]
        return to_digit(result)
