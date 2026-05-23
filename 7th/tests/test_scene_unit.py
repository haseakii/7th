"""SceneManager 单元测试

测试策略：
- 优先级测试：mock 各 `_is_*` 方法，验证 detect() 按正确优先级返回
- 亮度分析测试：mock `crop()` 返回可控亮度的图像，验证秘密商店/大厅检测
- OCR 弹窗测试：mock `OCR.read()` 返回带"取消"的块，验证弹窗检测
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from shop.scene import Scene
from shop.scene_manager import SceneManager


def _img(mean_val, shape=(10, 10, 3)):
    """创建指定平均亮度的 BGR 图像。"""
    return np.full(shape, mean_val, dtype=np.uint8)


class TestSceneManagerBasics:
    """SceneManager 基础功能"""

    def test_init_default_ocr(self):
        """不传 ocr 参数时使用默认 OCR 类。"""
        sm = SceneManager()
        from shop.ocr_engine import OCR
        assert sm._ocr is OCR

    def test_ensure_returns_true_when_match(self):
        """ensure() 在场景匹配时返回 True。"""
        sm = SceneManager(ocr=MagicMock())
        sm.detect = MagicMock(return_value=Scene.SECRET_SHOP)
        assert sm.ensure(None, Scene.SECRET_SHOP) is True

    def test_ensure_returns_false_when_no_match(self):
        """ensure() 在场景不匹配时返回 False。"""
        sm = SceneManager(ocr=MagicMock())
        sm.detect = MagicMock(return_value=Scene.LOBBY)
        assert sm.ensure(None, Scene.SECRET_SHOP) is False

    def test_ensure_unknown(self):
        """ensure() 在未知场景时返回 False。"""
        sm = SceneManager(ocr=MagicMock())
        sm.detect = MagicMock(return_value=Scene.UNKNOWN)
        assert sm.ensure(None, Scene.SECRET_SHOP) is False


class TestSceneManagerDetectPriority:
    """detect() 优先级验证 — mock 各子检测方法"""

    def test_popup_highest_priority(self):
        """PURCHASE_POPUP 优先级最高，被优先返回。"""
        sm = SceneManager(ocr=MagicMock())
        sm._is_purchase_popup = MagicMock(return_value=True)
        sm._is_secret_shop = MagicMock(return_value=True)  # 也会匹配，但不应被调用
        scene = sm.detect(_img(0))
        assert scene == Scene.PURCHASE_POPUP
        sm._is_purchase_popup.assert_called_once()
        sm._is_secret_shop.assert_not_called()

    def test_secret_shop_second_priority(self):
        """无弹窗时返回 SECRET_SHOP。"""
        sm = SceneManager(ocr=MagicMock())
        sm._is_purchase_popup = MagicMock(return_value=False)
        sm._is_secret_shop = MagicMock(return_value=True)
        assert sm.detect(_img(0)) == Scene.SECRET_SHOP

    def test_lobby_third_priority(self):
        """无弹窗且不是商店时返回 LOBBY。"""
        sm = SceneManager(ocr=MagicMock())
        sm._is_purchase_popup = MagicMock(return_value=False)
        sm._is_secret_shop = MagicMock(return_value=False)
        sm._is_lobby = MagicMock(return_value=True)
        assert sm.detect(_img(0)) == Scene.LOBBY

    def test_unknown_fallback(self):
        """所有检测都不匹配时返回 UNKNOWN。"""
        sm = SceneManager(ocr=MagicMock())
        sm._is_purchase_popup = MagicMock(return_value=False)
        sm._is_secret_shop = MagicMock(return_value=False)
        sm._is_lobby = MagicMock(return_value=False)
        assert sm.detect(_img(0)) == Scene.UNKNOWN


class TestSceneManagerIsSecretShop:
    """_is_secret_shop 亮度分析"""

    @patch("shop.scene_manager.crop")
    def test_typical(self, mock_crop):
        """nav_top 暗, nav_mid 亮, content 暗 → 秘密商店。"""
        mock_crop.side_effect = [
            _img(53),   # nav_top < 80
            _img(177),  # nav_mid > 100
            _img(55),   # content < 100
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_secret_shop(_img(0)) is True

    @patch("shop.scene_manager.crop")
    def test_nav_top_too_bright(self, mock_crop):
        """nav_top > 80 → 提前返回 False。"""
        mock_crop.side_effect = [_img(100)]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_secret_shop(_img(0)) is False

    @patch("shop.scene_manager.crop")
    def test_nav_top_boundary(self, mock_crop):
        """nav_top == 80（边界值）— 不触发提前返回。"""
        mock_crop.side_effect = [
            _img(80),   # nav_top == 80, 继续
            _img(150),  # nav_mid > 100
            _img(60),   # content < 100
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_secret_shop(_img(0)) is True

    @patch("shop.scene_manager.crop")
    def test_nav_mid_dim(self, mock_crop):
        """nav_mid <= 100 → 不是秘密商店。"""
        mock_crop.side_effect = [
            _img(55),   # nav_top < 80
            _img(80),   # nav_mid <= 100
            _img(55),   # content < 100
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_secret_shop(_img(0)) is False

    @patch("shop.scene_manager.crop")
    def test_content_too_bright(self, mock_crop):
        """content >= 100 → 不是秘密商店。"""
        mock_crop.side_effect = [
            _img(55),   # nav_top < 80
            _img(150),  # nav_mid > 100
            _img(120),  # content >= 100
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_secret_shop(_img(0)) is False


class TestSceneManagerIsLobby:
    """_is_lobby 亮度分析"""

    @patch("shop.scene_manager.crop")
    def test_typical(self, mock_crop):
        """nav_top 亮, content 亮 → 大厅。"""
        mock_crop.side_effect = [
            _img(185),  # nav_top > 100
            _img(201),  # content > 100
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_lobby(_img(0)) is True

    @patch("shop.scene_manager.crop")
    def test_dark_nav(self, mock_crop):
        """导航栏暗 → 不是大厅。"""
        mock_crop.side_effect = [
            _img(55),   # nav_top <= 100
            _img(200),  # content 亮
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_lobby(_img(0)) is False

    @patch("shop.scene_manager.crop")
    def test_dark_content(self, mock_crop):
        """内容区暗 → 不是大厅。"""
        mock_crop.side_effect = [
            _img(150),  # nav_top > 100
            _img(50),   # content <= 100
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_lobby(_img(0)) is False

    @patch("shop.scene_manager.crop")
    def test_boundary_nav(self, mock_crop):
        """nav_top == 100（边界值）— nav_top 不满足 > 100。"""
        mock_crop.side_effect = [
            _img(100),  # nav_top == 100, 不 > 100
            _img(200),  # content 亮
        ]
        sm = SceneManager(ocr=MagicMock())
        assert sm._is_lobby(_img(0)) is False


class TestSceneManagerIsPurchasePopup:
    """_is_purchase_popup OCR 检测"""

    def test_found_cancel(self):
        """OCR 在取消区域检测到"取消"。"""
        sm = SceneManager(ocr=MagicMock())
        sm._ocr.read.return_value = [MagicMock(text="取消")]
        assert sm._is_purchase_popup(_img(0)) is True

    def test_found_cancel_with_extra_text(self):
        """OCR 结果包含"取消"和其他文字。"""
        sm = SceneManager(ocr=MagicMock())
        sm._ocr.read.return_value = [
            MagicMock(text="购买"),
            MagicMock(text="取消"),
        ]
        assert sm._is_purchase_popup(_img(0)) is True

    def test_not_found(self):
        """OCR 没检测到"取消"。"""
        sm = SceneManager(ocr=MagicMock())
        sm._ocr.read.return_value = [MagicMock(text="购买"), MagicMock(text="确认")]
        assert sm._is_purchase_popup(_img(0)) is False

    def test_empty_ocr_result(self):
        """OCR 返回空列表。"""
        sm = SceneManager(ocr=MagicMock())
        sm._ocr.read.return_value = []
        assert sm._is_purchase_popup(_img(0)) is False

    def test_no_blocks_at_all(self):
        """OCR 返回 None（极端情况）。"""
        sm = SceneManager(ocr=MagicMock())
        sm._ocr.read.return_value = None
        assert sm._is_purchase_popup(_img(0)) is False

    def test_uses_cancel_region(self):
        """验证 OCR 调用时使用了正确的弹窗取消区域。"""
        from shop.purchase import POPUP_CANCEL_REGION
        sm = SceneManager(ocr=MagicMock())
        sm._ocr.read.return_value = []
        sm._is_purchase_popup(_img(0))
        sm._ocr.read.assert_called_once()
        _, kwargs = sm._ocr.read.call_args
        assert kwargs.get("region") == POPUP_CANCEL_REGION
        assert kwargs.get("min_confidence") == 0.4
