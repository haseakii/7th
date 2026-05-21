"""
ShopNavigator 单元测试

覆盖需求:
- 3.1 截图并判断当前界面状态（秘密商店、大厅、未知）
- 3.2 从大厅导航至秘密商店
- 3.3 已在秘密商店时跳过导航
- 3.4 弹窗关闭和重试
- 3.5 导航超时处理
- 3.6 场景检测亮度阈值（基于实际游戏截图校准 2026-05-07）
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shop.navigator import (
    ShopNavigator,
    LOBBY_BTN,
    SECRET_SHOP_ENTRANCE_BTN,
    POPUP_CLOSE_BTN,
    SECRET_SHOP_SIDEBAR,
    COLOR_THRESHOLD,
    SECRET_SHOP_SIDEBAR_THRESHOLD,
    CONTENT_BRIGHTNESS_THRESHOLD,
    LOBBY_NAV_MIN_BRIGHTNESS,
)


@pytest.fixture
def mock_device():
    """创建 mock DeviceController"""
    device = MagicMock()
    device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
    return device


@pytest.fixture
def navigator(mock_device):
    return ShopNavigator(mock_device)


def _make_scene_image(
    nav_top_bright: float = 0,
    nav_mid_bright: float = 0,
    content_bright: float = 0,
) -> np.ndarray:
    """创建指定区域亮度的场景图像。

    nav_top:     (80,200)-(160,260) — 左侧导航顶部
    nav_mid:     (80,300)-(160,480) — 左侧导航中部按钮区
    content:     (250,150)-(800,520) — 内容区域（物品槽位区）
    """
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    img[200:260, 80:160] = int(nav_top_bright)
    img[300:480, 80:160] = int(nav_mid_bright)
    img[150:520, 250:800] = int(content_bright)
    return img


class TestDetectCurrentScene:
    """场景检测测试"""

    def test_detect_secret_shop(self, navigator, mock_device):
        """需求 3.1: 秘密商店特征：导航顶暗+导航中亮+内容区暗"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=50, nav_mid_bright=180, content_bright=50
        )
        assert navigator.detect_current_scene() == "secret_shop"

    def test_detect_lobby(self, navigator, mock_device):
        """需求 3.1: 大厅特征：导航顶亮+内容区亮"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=150, nav_mid_bright=0, content_bright=180
        )
        assert navigator.detect_current_scene() == "lobby"

    def test_detect_unknown_when_no_match(self, navigator, mock_device):
        """无法识别时返回 'unknown'"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=50, nav_mid_bright=50, content_bright=50
        )
        assert navigator.detect_current_scene() == "unknown"

    def test_secret_shop_has_priority(self, navigator, mock_device):
        """秘密商店检测优先于大厅检测（排除 nav_top_dark 但其他区域亮的情况）"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=50, nav_mid_bright=180, content_bright=180
        )
        # nav_top=50(<80) 满足 secret_shop, 但 content=180(>100) 不满足 content<100
        # 所以应该是 unknown 而非 secret_shop
        assert navigator.detect_current_scene() == "unknown"


class TestIsSecretShop:
    """_is_secret_shop 检测测试"""

    def test_shop_conditions_met(self, navigator, mock_device):
        """导航顶暗+导航中亮+内容区暗 返回 True"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=40, nav_mid_bright=150, content_bright=60
        )
        assert navigator._is_secret_shop(mock_device.screenshot()) is True

    def test_nav_top_too_bright_not_shop(self, navigator, mock_device):
        """导航顶部太亮（>80）返回 False"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=120, nav_mid_bright=150, content_bright=60
        )
        assert navigator._is_secret_shop(mock_device.screenshot()) is False

    def test_nav_mid_too_dim_not_shop(self, navigator, mock_device):
        """导航中部不够亮（<=100）返回 False"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=50, nav_mid_bright=50, content_bright=60
        )
        assert navigator._is_secret_shop(mock_device.screenshot()) is False

    def test_content_too_bright_not_shop(self, navigator, mock_device):
        """内容区太亮（>100）返回 False"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=50, nav_mid_bright=150, content_bright=180
        )
        assert navigator._is_secret_shop(mock_device.screenshot()) is False

    def test_threshold_constant(self):
        """秘密商店导航顶部亮度阈值为 80"""
        assert SECRET_SHOP_SIDEBAR_THRESHOLD == 80


class TestIsLobby:
    """_is_lobby 检测测试"""

    def test_lobby_conditions_met(self, navigator, mock_device):
        """导航顶亮+内容区亮 返回 True"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=150, nav_mid_bright=0, content_bright=180
        )
        assert navigator._is_lobby(mock_device.screenshot()) is True

    def test_nav_top_too_dim(self, navigator, mock_device):
        """导航顶部亮度 <= 100 返回 False"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=50, nav_mid_bright=0, content_bright=180
        )
        assert navigator._is_lobby(mock_device.screenshot()) is False

    def test_content_too_dim(self, navigator, mock_device):
        """内容区亮度 <= 100 返回 False"""
        mock_device.screenshot.return_value = _make_scene_image(
            nav_top_bright=150, nav_mid_bright=0, content_bright=50
        )
        assert navigator._is_lobby(mock_device.screenshot()) is False

    def test_lobby_thresholds(self):
        """大厅亮度阈值配置正确"""
        assert LOBBY_NAV_MIN_BRIGHTNESS == 100
        assert CONTENT_BRIGHTNESS_THRESHOLD == 100


class TestNavigateToSecretShop:
    """导航至秘密商店测试"""

    def test_already_at_secret_shop(self, navigator, mock_device):
        """需求 3.3: 已在秘密商店时跳过导航直接返回 True"""
        with patch.object(navigator, "detect_current_scene", return_value="secret_shop"):
            assert navigator.navigate_to_secret_shop() is True
        mock_device.click.assert_not_called()

    @patch("shop.navigator.time.sleep")
    def test_navigate_from_lobby(self, mock_sleep, navigator, mock_device):
        """需求 3.2: 从大厅点击秘密商店入口按钮"""
        scenes = iter(["lobby", "secret_shop"])
        with patch.object(navigator, "detect_current_scene", side_effect=scenes):
            result = navigator.navigate_to_secret_shop()
            assert result is True
            mock_device.click.assert_called_once_with(SECRET_SHOP_ENTRANCE_BTN)

    @patch("shop.navigator.time.sleep")
    def test_navigation_timeout(self, mock_sleep, navigator, mock_device):
        """需求 3.5: 导航超时返回 False"""
        with patch.object(navigator, "detect_current_scene", return_value="unknown"), \
             patch.object(navigator, "handle_popup", return_value=False):
            result = navigator.navigate_to_secret_shop(timeout=0.01)
            assert result is False

    @patch("shop.navigator.time.sleep")
    def test_popup_handling_during_navigation(self, mock_sleep, navigator, mock_device):
        """需求 3.4: 导航中遇到弹窗时关闭并继续"""
        call_count = 0

        def scene_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return "unknown"
            return "secret_shop"

        with patch.object(navigator, "detect_current_scene", side_effect=scene_side_effect), \
             patch.object(navigator, "handle_popup", return_value=True):
            result = navigator.navigate_to_secret_shop()
            assert result is True


class TestHandlePopup:
    """弹窗处理测试"""

    def test_popup_detected_and_closed(self, navigator, mock_device):
        """检测到弹窗时点击关闭并返回 True"""
        with patch.object(POPUP_CLOSE_BTN, "appear_on", return_value=True):
            assert navigator.handle_popup() is True
            mock_device.click.assert_called_once_with(POPUP_CLOSE_BTN)

    def test_no_popup(self, navigator, mock_device):
        """没有弹窗时返回 False"""
        with patch.object(POPUP_CLOSE_BTN, "appear_on", return_value=False):
            assert navigator.handle_popup() is False
            mock_device.click.assert_not_called()


class TestConstants:
    """常量和配置测试"""

    def test_color_threshold(self):
        """弹窗检测颜色阈值为 50"""
        assert COLOR_THRESHOLD == 50

    def test_button_instances_exist(self):
        """所有必要的 Button 实例都已定义"""
        assert LOBBY_BTN is not None
        assert SECRET_SHOP_ENTRANCE_BTN is not None
        assert POPUP_CLOSE_BTN is not None
        assert SECRET_SHOP_SIDEBAR is not None
