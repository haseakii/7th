"""
SceneManager 场景管理器

在 ShopBot 主循环的关键节点检测当前游戏场景，发现异常（弹窗残留、被踢回大厅等）
时通知调用方处理。SceneManager 只负责检测和判断，不执行点击操作。

检测策略（优先级从高到低）：
1. PURCHASE_POPUP — OCR 检测弹窗区域的"取消"按钮
2. SECRET_SHOP — 左侧导航栏亮度分析（复用 navigator 阈值）
3. LOBBY — 导航栏+内容区亮度分析
4. UNKNOWN — 其他情况
"""

import numpy as np

from log import logger
from module.base.utils import crop
from shop.navigator import (
    CONTENT_BRIGHTNESS_THRESHOLD,
    LOBBY_NAV_MIN_BRIGHTNESS,
    SECRET_SHOP_SIDEBAR_THRESHOLD,
)
from shop.ocr_engine import OCR
from shop.purchase import POPUP_CANCEL_REGION
from shop.scene import Scene


class SceneManager:
    """场景管理器 — 检测当前游戏界面状态。"""

    def __init__(self, ocr=None):
        self._ocr = ocr or OCR

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def detect(self, image: np.ndarray) -> Scene:
        """分析单帧截图，返回当前场景。

        Args:
            image: BGR 格式截图。

        Returns:
            Scene 枚举值。
        """
        # 1. 购买弹窗检测（优先级最高，因为它叠加在 secret_shop 之上）
        if self._is_purchase_popup(image):
            return Scene.PURCHASE_POPUP

        # 2. 秘密商店
        if self._is_secret_shop(image):
            return Scene.SECRET_SHOP

        # 3. 大厅
        if self._is_lobby(image):
            return Scene.LOBBY

        return Scene.UNKNOWN

    def ensure(self, image: np.ndarray, target: Scene) -> bool:
        """检查当前场景是否为目标场景。

        Args:
            image: BGR 格式截图。
            target: 期望的场景。

        Returns:
            True 如果当前场景匹配目标场景。
        """
        return self.detect(image) == target

    # ------------------------------------------------------------------
    # 场景检测实现
    # ------------------------------------------------------------------

    def _is_purchase_popup(self, image: np.ndarray) -> bool:
        """轻量检测：弹窗取消区域 OCR 找"取消"关键词。

        只搜索 POPUP_CANCEL_REGION（约 340×110 像素），
        比全图或大面积 OCR 快得多。找到"取消"即认为弹窗存在。

        Args:
            image: BGR 格式截图。

        Returns:
            bool: 是否检测到购买弹窗。
        """
        blocks = self._ocr.read(
            image,
            region=POPUP_CANCEL_REGION,
            min_confidence=0.4,
        )
        return bool(blocks) and any("取消" in b.text for b in blocks)

    def _is_secret_shop(self, image: np.ndarray) -> bool:
        """通过多区域亮度特征检测是否在秘密商店。

        复用 navigator.py 中的阈值（实机截图校准）：
        - 左侧导航顶部暗 (<80)
        - 左侧导航中部按钮亮 (>100)
        - 内容区域暗 (<100)

        Args:
            image: BGR 格式截图。

        Returns:
            bool: 是否在秘密商店。
        """
        nav_top = crop(image, (80, 200, 160, 260))
        nav_top_bright = float(nav_top[:, :, :3].mean())

        if nav_top_bright > SECRET_SHOP_SIDEBAR_THRESHOLD:
            return False

        nav_mid = crop(image, (80, 300, 160, 400))
        nav_mid_bright = float(nav_mid[:, :, :3].mean())

        content = crop(image, (250, 150, 800, 520))
        content_bright = float(content[:, :, :3].mean())

        return (
            nav_mid_bright > LOBBY_NAV_MIN_BRIGHTNESS
            and content_bright < CONTENT_BRIGHTNESS_THRESHOLD
        )

    def _is_lobby(self, image: np.ndarray) -> bool:
        """通过多区域亮度特征检测是否在大厅。

        大厅特征：
        - 左侧导航顶部亮 (>100)
        - 内容区域亮 (>100)

        Args:
            image: BGR 格式截图。

        Returns:
            bool: 是否在大厅。
        """
        nav_top = crop(image, (80, 200, 160, 260))
        nav_top_bright = float(nav_top[:, :, :3].mean())

        content = crop(image, (250, 150, 800, 520))
        content_bright = float(content[:, :, :3].mean())

        return (
            nav_top_bright > LOBBY_NAV_MIN_BRIGHTNESS
            and content_bright > CONTENT_BRIGHTNESS_THRESHOLD
        )
