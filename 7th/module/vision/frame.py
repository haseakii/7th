"""Per-screenshot context shared by scene detection and OCR."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import numpy as np

Region = Optional[Tuple[int, int, int, int]]
OcrCacheKey = Tuple[Region, float, str]


@dataclass
class FrameContext:
    image: np.ndarray
    created_at: datetime = field(default_factory=datetime.now)
    scene: Any = None
    ocr_cache: Dict[OcrCacheKey, Any] = field(default_factory=dict)

    def ocr_key(self, region: Region = None, min_confidence: float = 0.4, mode: str = "text") -> OcrCacheKey:
        normalized_region = tuple(region) if region is not None else None
        return normalized_region, float(min_confidence), mode


def get_frame_image(frame_or_image):
    """Return the BGR image from either a FrameContext or a raw ndarray."""
    if isinstance(frame_or_image, FrameContext):
        return frame_or_image.image
    return frame_or_image


def capture_device_frame(device):
    """Capture a FrameContext from a device-like object.

    Prefer a device-provided ``capture_frame`` implementation when available;
    otherwise fall back to ``screenshot`` for legacy mocks/controllers.
    """
    capture_frame = getattr(type(device), "capture_frame", None)
    if callable(capture_frame):
        return device.capture_frame()

    image = device.screenshot()
    if image is None:
        return None
    return FrameContext(image=image)
