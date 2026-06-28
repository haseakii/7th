"""Scene detection for SecretShop task."""

import numpy as np

from module.base.utils import crop
from module.vision.frame import FrameContext, get_frame_image
from module.vision.profile import SECRET_SHOP_PROFILE
from tasks.secret_shop.ocr_engine import OCR
from tasks.secret_shop.purchase import POPUP_CANCEL_REGION
from tasks.secret_shop.scene import Scene

CONTENT_BRIGHTNESS_THRESHOLD = SECRET_SHOP_PROFILE.content_brightness_threshold
LOBBY_NAV_MIN_BRIGHTNESS = SECRET_SHOP_PROFILE.lobby_nav_min_brightness
SECRET_SHOP_SIDEBAR_THRESHOLD = SECRET_SHOP_PROFILE.secret_shop_sidebar_threshold


class SceneManager:
    """Detect the current game scene from a screenshot or FrameContext."""

    def __init__(self, ocr=None):
        self._ocr = ocr or OCR

    def detect(self, image: np.ndarray) -> Scene:
        """Analyze one frame and return the current scene."""
        frame = image if isinstance(image, FrameContext) else None
        if frame is not None and frame.scene is not None:
            return frame.scene

        if self._is_purchase_popup(image):
            scene = Scene.PURCHASE_POPUP
        elif self._is_secret_shop(image):
            scene = Scene.SECRET_SHOP
        elif self._is_lobby(image):
            scene = Scene.LOBBY
        else:
            scene = Scene.UNKNOWN

        if frame is not None:
            frame.scene = scene
        return scene

    def ensure(self, image: np.ndarray, target: Scene) -> bool:
        return self.detect(image) == target

    def _is_purchase_popup(self, image: np.ndarray) -> bool:
        source = get_frame_image(image)
        cancel_area = crop(source, POPUP_CANCEL_REGION)
        brightness = float(cancel_area.mean())
        if brightness > 120:
            return False

        blocks = self._ocr.read(
            image,
            region=POPUP_CANCEL_REGION,
            min_confidence=0.4,
        )
        return bool(blocks) and any("取消" in b.text or "鍙栨秷" in b.text for b in blocks)

    def _is_secret_shop(self, image: np.ndarray) -> bool:
        source = get_frame_image(image)
        nav_top = crop(source, SECRET_SHOP_PROFILE.nav_top_region)
        nav_top_bright = float(nav_top[:, :, :3].mean())
        if nav_top_bright > SECRET_SHOP_SIDEBAR_THRESHOLD:
            return False

        nav_mid = crop(source, SECRET_SHOP_PROFILE.nav_mid_region)
        nav_mid_bright = float(nav_mid[:, :, :3].mean())

        content = crop(source, SECRET_SHOP_PROFILE.content_region)
        content_bright = float(content[:, :, :3].mean())

        return (
            nav_mid_bright > LOBBY_NAV_MIN_BRIGHTNESS
            and content_bright < CONTENT_BRIGHTNESS_THRESHOLD
        )

    def _is_lobby(self, image: np.ndarray) -> bool:
        source = get_frame_image(image)
        nav_top = crop(source, SECRET_SHOP_PROFILE.nav_top_region)
        nav_top_bright = float(nav_top[:, :, :3].mean())

        content = crop(source, SECRET_SHOP_PROFILE.content_region)
        content_bright = float(content[:, :, :3].mean())

        return (
            nav_top_bright > LOBBY_NAV_MIN_BRIGHTNESS
            and content_bright > CONTENT_BRIGHTNESS_THRESHOLD
        )
