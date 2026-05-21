"""
Button 模板匹配（精简版）

从 Alas 精简复用，保留 appear_on、match、match_luma 方法。
移除 ButtonGrid、split_server、GIF 支持、Resource 基类。
"""

import os

import cv2
import numpy as np

from module.base.decorator import cached_property
from module.base.utils import (
    area_offset,
    color_similar,
    crop,
    get_color,
    load_image,
    rgb2luma,
)


class Button:
    """简化版 Button，用于模板匹配和颜色检测。"""

    def __init__(self, area, color, button, file=None, name=None):
        """Initialize a Button instance.

        Args:
            area (tuple): Area that the button would appear on the image.
                (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y)
            color (tuple): Color we expect the area would be. (r, g, b)
            button (tuple): Area to be clicked if button appears on the image.
                (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y)
            file (str): Path to the template image file.
            name (str): Name of the button.
        """
        self.raw_area = area
        self.raw_color = color
        self.raw_button = button
        self.raw_file = file
        self.raw_name = name

        self._button_offset = None
        self._match_init = False
        self._match_luma_init = False
        self.image = None
        self.image_luma = None

    @cached_property
    def area(self):
        return self.raw_area

    @cached_property
    def color(self):
        return self.raw_color

    @cached_property
    def _button(self):
        return self.raw_button

    @cached_property
    def file(self):
        return self.raw_file

    @cached_property
    def name(self):
        if self.raw_name:
            return self.raw_name
        elif self.file:
            return os.path.splitext(os.path.split(self.file)[1])[0]
        else:
            return 'BUTTON'

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.name)

    def __bool__(self):
        return True

    @property
    def button(self):
        if self._button_offset is None:
            return self._button
        else:
            return self._button_offset

    def appear_on(self, image, threshold=10):
        """Check if the button appears on the image by color similarity.

        Args:
            image (np.ndarray): Screenshot.
            threshold (int): Default to 10.

        Returns:
            bool: True if button appears on screenshot.
        """
        return color_similar(
            color1=get_color(image, self.area),
            color2=self.color,
            threshold=threshold
        )

    def load_color(self, image):
        """Load color from the specific area of the given image.

        Args:
            image (np.ndarray): Screenshot.

        Returns:
            tuple: Color (r, g, b).
        """
        self.__dict__['color'] = get_color(image, self.area)
        self.image = crop(image, self.area)
        return self.color

    def ensure_template(self):
        """Load asset template image for template matching."""
        if not self._match_init:
            self.image = load_image(self.file, self.area)
            self._match_init = True

    def ensure_luma_template(self):
        """Load luma (Y channel) version of template for luma matching."""
        if not self._match_luma_init:
            self.image_luma = rgb2luma(self.image)
            self._match_luma_init = True

    def _parse_offset(self, offset):
        """Parse offset parameter into a numpy array.

        Args:
            offset (int, tuple): Detection area offset.

        Returns:
            np.ndarray
        """
        if isinstance(offset, tuple):
            if len(offset) == 2:
                return np.array((-offset[0], -offset[1], offset[0], offset[1]))
            else:
                return np.array(offset)
        else:
            return np.array((-3, -offset, 3, offset))

    def match(self, image, offset=30, similarity=0.85):
        """Detect button by template matching.

        Args:
            image (np.ndarray): Screenshot.
            offset (int, tuple): Detection area offset.
            similarity (float): 0-1. Similarity threshold.

        Returns:
            bool
        """
        self.ensure_template()
        offset = self._parse_offset(offset)
        image = crop(image, offset + self.area, copy=False)

        res = cv2.matchTemplate(self.image, image, cv2.TM_CCOEFF_NORMED)
        _, sim, _, point = cv2.minMaxLoc(res)
        self._button_offset = area_offset(self._button, offset[:2] + np.array(point))
        return sim > similarity

    def match_luma(self, image, offset=30, similarity=0.85):
        """Detect button by template matching under Y channel (Luminance).

        Args:
            image (np.ndarray): Screenshot.
            offset (int, tuple): Detection area offset.
            similarity (float): 0-1. Similarity threshold.

        Returns:
            bool
        """
        self.ensure_template()
        self.ensure_luma_template()
        offset = self._parse_offset(offset)
        image = crop(image, offset + self.area, copy=False)

        image_luma = rgb2luma(image)
        res = cv2.matchTemplate(self.image_luma, image_luma, cv2.TM_CCOEFF_NORMED)
        _, sim, _, point = cv2.minMaxLoc(res)
        self._button_offset = area_offset(self._button, offset[:2] + np.array(point))
        return sim > similarity
