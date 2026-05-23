"""Price recognition using whole-price-image template matching.

ALAS cnocr models were trained on Azur Lane fonts and cannot read Epic Seven's
font reliably (both azur_lane digits model and cnocr full Chinese model fail).
Instead, we match the entire price region image against stored templates.

The price text is at x=1071-1104 (~33px wide), cyan-colored, in the upper
portion of each item row. Each unique price produces a distinct pixel pattern.
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple

from log import logger

# Price region (absolute x coordinates in 1280x720 screenshot)
# Full price area = coin icon + price digits
PRICE_X1 = 1071
PRICE_X2 = 1125
PRICE_Y_FRACTION = 0.45  # Use top 45% of row height for price text

# Template matching threshold
MATCH_THRESHOLD = 0.85

_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "e7", "prices",
)


class PriceReader:
    """Recognize item prices via whole-price-image template matching."""

    def __init__(self, template_dir: str = _TEMPLATE_DIR):
        self.template_dir = template_dir
        self.templates: Dict[int, List[np.ndarray]] = {}
        os.makedirs(template_dir, exist_ok=True)
        self._load_templates()

    def _load_templates(self) -> None:
        """Load stored price templates from disk.

        Templates are named price_XXXXX_N.png where XXXXX is the price value
        and N is a sample index for multiple examples of the same price.
        """
        self.templates.clear()
        if not os.path.isdir(self.template_dir):
            return
        for fname in os.listdir(self.template_dir):
            if not fname.startswith("price_") or not fname.endswith(".png"):
                continue
            try:
                # Parse: price_14900_0.png -> 14900
                parts = fname[len("price_"):-len(".png")].split("_")
                price_value = int(parts[0])
                path = os.path.join(self.template_dir, fname)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates.setdefault(price_value, []).append(img)
            except (ValueError, IndexError):
                logger.warning(f"无效模板文件名: {fname}")

        total = sum(len(v) for v in self.templates.values())
        if total > 0:
            logger.info(f"已加载 {len(self.templates)} 种价格, 共 {total} 个模板")

    def _preprocess(self, price_img: np.ndarray) -> np.ndarray:
        """Preprocess price image for template matching.

        Converts to grayscale, applies binary threshold to isolate cyan text,
        and normalizes to a standard height.

        Args:
            price_img: BGR or grayscale price region image

        Returns:
            Preprocessed binary image (white text on black background)
        """
        if price_img.ndim == 3:
            gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = price_img.copy()

        # OTSU binary inverse: text becomes white, background black
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Standardize height to 36px for consistent comparison
        target_h = 36
        h, w = binary.shape[:2]
        if h != target_h:
            scale = target_h / h
            new_w = int(w * scale)
            binary = cv2.resize(binary, (new_w, target_h), interpolation=cv2.INTER_CUBIC)
            _, binary = cv2.threshold(binary, 127, 255, cv2.THRESH_BINARY)

        return binary

    def extract_price_region(self, image: np.ndarray, y1: int, y2: int) -> np.ndarray:
        """Extract the price region from an item row.

        Args:
            image: Full screenshot (BGR)
            y1: Row top y coordinate
            y2: Row bottom y coordinate

        Returns:
            Price region image (BGR)
        """
        upper_h = int((y2 - y1) * PRICE_Y_FRACTION)
        return image[y1:y1 + upper_h, PRICE_X1:PRICE_X2]

    def recognize(self, price_img: np.ndarray) -> Tuple[int, float]:
        """Recognize price from image using template matching.

        Args:
            price_img: Price region image (BGR or grayscale)

        Returns:
            (price_value, confidence) — (0, 0.0) if no match found
        """
        if price_img is None or price_img.size == 0:
            return 0, 0.0

        processed = self._preprocess(price_img)

        best_price = 0
        best_score = 0.0

        for price_value, template_list in self.templates.items():
            for template in template_list:
                # Ensure same dimensions for matching
                th, tw = template.shape[:2]
                ph, pw = processed.shape[:2]

                if th != ph or tw != pw:
                    # Resize template to match processed image
                    tmpl = cv2.resize(template, (pw, ph), interpolation=cv2.INTER_CUBIC)
                    _, tmpl = cv2.threshold(tmpl, 127, 255, cv2.THRESH_BINARY)
                else:
                    tmpl = template

                score = cv2.matchTemplate(processed, tmpl, cv2.TM_CCOEFF_NORMED)[0][0]

                if score > best_score:
                    best_score = score
                    best_price = price_value

        if best_score >= MATCH_THRESHOLD:
            return best_price, best_score
        return 0, best_score

    def save_template(self, price_img: np.ndarray, price_value: int) -> str:
        """Save a new price template for future matching.

        Args:
            price_img: Price region image
            price_value: The actual price value (user-provided)

        Returns:
            Path to the saved template file
        """
        processed = self._preprocess(price_img)

        # Find next available index for this price
        existing = len(self.templates.get(price_value, []))
        fname = f"price_{price_value}_{existing}.png"
        path = os.path.join(self.template_dir, fname)

        cv2.imwrite(path, processed)
        self.templates.setdefault(price_value, []).append(processed)

        logger.info(f"保存价格模板: {fname}")
        return path

    def save_unknown(self, price_img: np.ndarray) -> str:
        """Save an unknown price image for later labeling.

        Args:
            price_img: Price region image

        Returns:
            Path to the saved file
        """
        os.makedirs(self.template_dir, exist_ok=True)

        # Find next unknown index
        existing = [f for f in os.listdir(self.template_dir) if f.startswith("unknown_")]
        idx = len(existing)
        fname = f"unknown_{idx:04d}.png"
        path = os.path.join(self.template_dir, fname)

        processed = self._preprocess(price_img)
        cv2.imwrite(path, processed)

        logger.info(f"保存未知价格图片: {fname}")
        return path

    @property
    def has_templates(self) -> bool:
        """Whether any price templates are loaded."""
        return len(self.templates) > 0
