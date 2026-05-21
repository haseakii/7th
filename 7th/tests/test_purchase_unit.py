"""
PurchaseEngine 单元测试

覆盖需求:
- 5.1 购买决策与配置匹配
- 5.2 点击物品并确认购买
- 5.3 自动点击确认按钮
- 5.4 购买确认弹窗重试
- 5.5 金币不足跳过
- 5.7 购买失败记录原因
- 5.8 购买间隔 0.5-1.0 秒
- 5.9 记录购买日志
"""

import sys
import os
from unittest.mock import MagicMock, patch, call
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shop.purchase import (
    PurchaseEngine,
    PurchaseResult,
    CONFIRM_BTN,
    SECOND_CONFIRM_BTN,
    INSUFFICIENT_GOLD_INDICATOR,
    ITEM_TYPE_TO_CONFIG_KEY,
    PURCHASE_INTERVAL_MIN,
    PURCHASE_INTERVAL_MAX,
)
from shop.recognizer import ShopItem


@pytest.fixture
def mock_device():
    """创建 mock DeviceController"""
    device = MagicMock()
    device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
    device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
    return device


@pytest.fixture
def mock_config():
    """创建 mock ConfigManager，默认购买书签和神秘奖章"""
    config = MagicMock()
    config.get_buy_list.return_value = {
        "bookmarks": True,
        "mystic_medals": True,
        "equipment": False,
        "fodder": False,
    }
    return config


@pytest.fixture
def engine(mock_device, mock_config):
    return PurchaseEngine(mock_device, mock_config)


@pytest.fixture
def sample_bookmark():
    return ShopItem(
        item_type="bookmark",
        price=184000,
        slot_index=0,
        position=(120, 160, 200, 240),
        confidence=0.92,
    )


@pytest.fixture
def sample_mystic():
    return ShopItem(
        item_type="mystic_medal",
        price=280000,
        slot_index=1,
        position=(120, 260, 200, 340),
        confidence=0.90,
    )


@pytest.fixture
def sample_equipment():
    return ShopItem(
        item_type="equipment",
        price=250000,
        slot_index=2,
        position=(120, 360, 200, 440),
        confidence=0.88,
    )


@pytest.fixture
def sample_unknown():
    return ShopItem(
        item_type="unknown",
        price=50000,
        slot_index=3,
        position=(120, 460, 200, 540),
        confidence=0.30,
    )


class TestShouldBuy:
    """购买决策测试 (需求 5.1)"""

    def test_buy_enabled_bookmark(self, engine, sample_bookmark):
        """配置启用书签时应购买"""
        assert engine.should_buy(sample_bookmark) is True

    def test_buy_enabled_mystic(self, engine, sample_mystic):
        """配置启用神秘奖章时应购买"""
        assert engine.should_buy(sample_mystic) is True

    def test_skip_disabled_equipment(self, engine, sample_equipment):
        """配置禁用装备时不购买"""
        assert engine.should_buy(sample_equipment) is False

    def test_never_buy_unknown(self, engine, sample_unknown):
        """unknown 类型永远不购买"""
        assert engine.should_buy(sample_unknown) is False

    def test_buy_when_all_disabled(self, engine, mock_config, sample_bookmark):
        """所有物品禁用时不购买"""
        mock_config.get_buy_list.return_value = {
            "bookmarks": False,
            "mystic_medals": False,
            "equipment": False,
            "fodder": False,
        }
        assert engine.should_buy(sample_bookmark) is False

    def test_unknown_always_false_even_if_config_missing(self, engine, sample_unknown, mock_config):
        """unknown 类型即使配置中有也不购买"""
        mock_config.get_buy_list.return_value = {"unknown": True}
        assert engine.should_buy(sample_unknown) is False


class TestBuyItem:
    """购买流程测试 (需求 5.2, 5.3, 5.4, 5.5)"""

    @patch("shop.purchase.time.sleep")
    def test_successful_purchase(self, mock_sleep, engine, mock_device, sample_bookmark):
        """成功购买流程：点击 → 确认 → 验证"""
        with patch.object(CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(SECOND_CONFIRM_BTN, "appear_on", return_value=False), \
             patch.object(INSUFFICIENT_GOLD_INDICATOR, "appear_on", return_value=False):
            result = engine.buy_item(sample_bookmark)
            assert result.success is True
            assert result.item_type == "bookmark"
            assert result.price == 184000
            assert result.reason == ""

    @patch("shop.purchase.time.sleep")
    def test_purchase_with_second_confirm(self, mock_sleep, engine, mock_device, sample_bookmark):
        """需求 5.4: 二次确认弹窗自动处理"""
        with patch.object(CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(SECOND_CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(INSUFFICIENT_GOLD_INDICATOR, "appear_on", return_value=False):
            result = engine.buy_item(sample_bookmark)
            assert result.success is True
            # 应该点击了物品 + 确认 + 二次确认 = 至少 3 次 click
            assert mock_device.click.call_count >= 3

    @patch("shop.purchase.time.sleep")
    def test_insufficient_gold_skips(self, mock_sleep, engine, mock_device, sample_bookmark):
        """需求 5.5: 金币不足时跳过并记录原因"""
        with patch.object(CONFIRM_BTN, "appear_on", return_value=False), \
             patch.object(INSUFFICIENT_GOLD_INDICATOR, "appear_on", return_value=True):
            result = engine.buy_item(sample_bookmark)
            assert result.success is False
            assert "金币不足" in result.reason

    @patch("shop.purchase.time.sleep")
    def test_confirm_popup_not_appearing_retries(self, mock_sleep, engine, mock_device, sample_bookmark):
        """需求 5.4: 确认弹窗未出现时重试"""
        # 模拟 Timer.reached 快速超时，然后重试也失败
        with patch.object(CONFIRM_BTN, "appear_on", return_value=False), \
             patch.object(SECOND_CONFIRM_BTN, "appear_on", return_value=False), \
             patch.object(INSUFFICIENT_GOLD_INDICATOR, "appear_on", return_value=False), \
             patch("shop.purchase.Timer") as MockTimer:
            timer_instance = MagicMock()
            timer_instance.reached.return_value = True
            MockTimer.return_value = timer_instance
            result = engine.buy_item(sample_bookmark)
            assert result.success is False
            assert "弹窗未出现" in result.reason


class TestHandleConfirmPopup:
    """确认弹窗处理测试"""

    @patch("shop.purchase.time.sleep")
    def test_first_confirm_only(self, mock_sleep, engine, mock_device):
        """只有第一次确认弹窗"""
        with patch.object(CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(SECOND_CONFIRM_BTN, "appear_on", return_value=False):
            assert engine.handle_confirm_popup() is True
            mock_device.click.assert_called_once_with(CONFIRM_BTN)

    @patch("shop.purchase.time.sleep")
    def test_both_confirms(self, mock_sleep, engine, mock_device):
        """两次确认弹窗都出现"""
        with patch.object(CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(SECOND_CONFIRM_BTN, "appear_on", return_value=True):
            assert engine.handle_confirm_popup() is True
            assert mock_device.click.call_count == 2

    def test_no_popup(self, engine, mock_device):
        """没有弹窗时返回 False"""
        with patch.object(CONFIRM_BTN, "appear_on", return_value=False):
            assert engine.handle_confirm_popup() is False
            mock_device.click.assert_not_called()

    def test_no_image(self, engine, mock_device):
        """没有截图时返回 False"""
        mock_device.image = None
        assert engine.handle_confirm_popup() is False


class TestProcessShelf:
    """货架处理测试 (需求 5.8, 5.9)"""

    @patch("shop.purchase.time.sleep")
    @patch("shop.purchase.random.uniform", return_value=0.75)
    def test_process_buys_matching_items(self, mock_uniform, mock_sleep, engine, sample_bookmark, sample_equipment):
        """只购买配置中启用的物品"""
        with patch.object(engine, "buy_item") as mock_buy:
            mock_buy.return_value = PurchaseResult(
                item_type="bookmark", price=184000, success=True
            )
            results = engine.process_shelf([sample_bookmark, sample_equipment])
            # 只有 bookmark 应该被购买（equipment 禁用）
            assert len(results) == 1
            assert results[0].item_type == "bookmark"
            mock_buy.assert_called_once_with(sample_bookmark)

    @patch("shop.purchase.time.sleep")
    @patch("shop.purchase.random.uniform", return_value=0.75)
    def test_purchase_interval(self, mock_uniform, mock_sleep, engine, sample_bookmark, sample_mystic):
        """需求 5.8: 购买间隔 0.5-1.0 秒"""
        with patch.object(engine, "buy_item") as mock_buy:
            mock_buy.return_value = PurchaseResult(
                item_type="bookmark", price=184000, success=True
            )
            engine.process_shelf([sample_bookmark, sample_mystic])
            # random.uniform 应该被调用来生成间隔
            mock_uniform.assert_called_with(PURCHASE_INTERVAL_MIN, PURCHASE_INTERVAL_MAX)

    @patch("shop.purchase.time.sleep")
    @patch("shop.purchase.random.uniform", return_value=0.75)
    def test_process_empty_shelf(self, mock_uniform, mock_sleep, engine):
        """空货架返回空结果"""
        results = engine.process_shelf([])
        assert results == []

    @patch("shop.purchase.time.sleep")
    @patch("shop.purchase.random.uniform", return_value=0.75)
    def test_process_all_unknown_items(self, mock_uniform, mock_sleep, engine, sample_unknown):
        """所有物品都是 unknown 时不购买"""
        with patch.object(engine, "buy_item") as mock_buy:
            results = engine.process_shelf([sample_unknown])
            assert results == []
            mock_buy.assert_not_called()


class TestPurchaseResult:
    """PurchaseResult 数据类测试"""

    def test_default_reason(self):
        """默认 reason 为空字符串"""
        result = PurchaseResult(item_type="bookmark", price=184000, success=True)
        assert result.reason == ""

    def test_with_reason(self):
        """可以设置失败原因"""
        result = PurchaseResult(
            item_type="bookmark", price=184000, success=False, reason="金币不足"
        )
        assert result.reason == "金币不足"


class TestConstants:
    """常量和配置测试"""

    def test_item_type_mapping_covers_all_types(self):
        """物品类型映射覆盖所有可购买类型"""
        assert "bookmark" in ITEM_TYPE_TO_CONFIG_KEY
        assert "mystic_medal" in ITEM_TYPE_TO_CONFIG_KEY
        assert "equipment" in ITEM_TYPE_TO_CONFIG_KEY
        assert "fodder" in ITEM_TYPE_TO_CONFIG_KEY

    def test_unknown_not_in_mapping(self):
        """unknown 不在映射中"""
        assert "unknown" not in ITEM_TYPE_TO_CONFIG_KEY

    def test_button_instances_exist(self):
        """所有必要的 Button 实例都已定义"""
        assert CONFIRM_BTN is not None
        assert SECOND_CONFIRM_BTN is not None
        assert INSUFFICIENT_GOLD_INDICATOR is not None

    def test_purchase_interval_range(self):
        """购买间隔范围正确"""
        assert PURCHASE_INTERVAL_MIN == 0.5
        assert PURCHASE_INTERVAL_MAX == 1.0
        assert PURCHASE_INTERVAL_MIN < PURCHASE_INTERVAL_MAX
