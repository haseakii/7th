"""
PurchaseEngine 单元测试（新版 - OCR 弹窗检测）
"""

import sys
import os
from unittest.mock import MagicMock, patch, call
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tasks.secret_shop.purchase import (
    PurchaseEngine,
    PurchaseResult,
    CONFIRM_BTN_POS,
    CANCEL_BTN_POS,
    POPUP_CONFIRM_REGION,
    POPUP_CANCEL_REGION,
    ITEM_TYPE_TO_CONFIG_KEY,
    PURCHASE_INTERVAL_MIN,
    PURCHASE_INTERVAL_MAX,
)
from module.vision.frame import FrameContext
from tasks.secret_shop.recognizer import ShopItem


@pytest.fixture
def mock_device():
    device = MagicMock()
    device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
    device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
    return device


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.buy_list = {
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
        currency="gold",
        price=184000,
        slot_index=0,
        position=(120, 160, 200, 240),
        confidence=0.92,
    )


@pytest.fixture
def sample_mystic():
    return ShopItem(
        item_type="mystic_medal",
        currency="gold",
        price=280000,
        slot_index=1,
        position=(120, 260, 200, 340),
        confidence=0.90,
    )


@pytest.fixture
def sample_equipment():
    return ShopItem(
        item_type="equipment",
        currency="gold",
        price=250000,
        slot_index=2,
        position=(120, 360, 200, 440),
        confidence=0.88,
    )


class TestShouldBuy:
    """购买决策测试 (需求 5.1)"""

    def test_buy_enabled_bookmark(self, engine, sample_bookmark):
        assert engine.should_buy(sample_bookmark) is True

    def test_buy_enabled_mystic(self, engine, sample_mystic):
        assert engine.should_buy(sample_mystic) is True

    def test_skip_disabled_equipment(self, engine, sample_equipment):
        assert engine.should_buy(sample_equipment) is False

    def test_never_buy_unknown(self, engine):
        unknown = ShopItem("unknown", "gold", 50000, 3, (120, 460, 200, 540), 0.30)
        assert engine.should_buy(unknown) is False

    def test_buy_when_all_disabled(self, mock_device, sample_bookmark):
        engine = PurchaseEngine(mock_device, buy_list={
            "bookmarks": False,
            "mystic_medals": False,
            "equipment": False,
            "fodder": False,
        })
        assert engine.should_buy(sample_bookmark) is False


class TestFrameContext:
    def test_capture_frame_wraps_legacy_screenshot(self, engine):
        frame = engine._capture_frame()

        assert isinstance(frame, FrameContext)
        assert frame.image.shape == (720, 1280, 3)

    def test_scan_popup_handles_missing_frame(self, engine):
        engine._ocr = MagicMock()

        state = engine._scan_popup(None)

        assert state.has_cancel is False
        engine._ocr.read.assert_not_called()


class TestBuyItem:
    """购买流程测试 (新版 OCR 检测)"""

    @patch("tasks.secret_shop.purchase.time.sleep")
    def test_successful_purchase(self, mock_sleep, engine, mock_device, sample_bookmark):
        """成功购买：OCR 检测弹窗 → 固定坐标确认"""
        from tasks.secret_shop.purchase import _PopupState
        no_popup = _PopupState()
        popup = _PopupState(has_cancel=True, has_buy_or_confirm=True)

        with patch.object(engine, "_scan_popup") as mock_scan:
            # while loop → no popup → popup detected; retry check → no; verify → closed
            mock_scan.side_effect = [no_popup, popup, no_popup, no_popup]
            result = engine.buy_item(sample_bookmark)
            assert result.success is True
            assert result.item_type == "bookmark"

    @patch("tasks.secret_shop.purchase.time.sleep")
    def test_buy_item_scans_frame_context(self, mock_sleep, engine, sample_bookmark):
        """鍐呴儴鎴浘搴旇灏佽涓?FrameContext 锛屼究浜?OCR 缂撳瓨銆?"""
        from tasks.secret_shop.purchase import _PopupState
        no_popup = _PopupState()
        popup = _PopupState(has_cancel=True, has_buy_or_confirm=True)

        with patch.object(engine, "_scan_popup") as mock_scan:
            mock_scan.side_effect = [popup, no_popup, no_popup]
            result = engine.buy_item(sample_bookmark)

        assert result.success is True
        assert isinstance(mock_scan.call_args_list[0].args[0], FrameContext)

    @patch("tasks.secret_shop.purchase.time.sleep")
    def test_purchase_with_second_confirm(self, mock_sleep, engine, mock_device, sample_bookmark):
        """二次确认弹窗"""
        from tasks.secret_shop.purchase import _PopupState
        no_popup = _PopupState()
        popup = _PopupState(has_cancel=True, has_buy_or_confirm=True)

        with patch.object(engine, "_scan_popup") as mock_scan:
            # while → popup; retry check → popup (second); verify → closed
            mock_scan.side_effect = [popup, popup, no_popup]
            result = engine.buy_item(sample_bookmark)
            assert result.success is True
            assert mock_device.click_position.call_count >= 2

    @patch("tasks.secret_shop.purchase.time.sleep")
    def test_insufficient_gold_skips(self, mock_sleep, engine, mock_device, sample_bookmark):
        """金币不足跳过"""
        from tasks.secret_shop.purchase import _PopupState

        with patch.object(engine, "_scan_popup") as mock_scan, \
             patch.object(engine, "_close_popup"):
            mock_scan.return_value = _PopupState(insufficient_gold=True)
            result = engine.buy_item(sample_bookmark)
            assert result.success is False
            assert "金币不足" in result.reason

    @patch("tasks.secret_shop.purchase.time.sleep")
    def test_confirm_popup_not_appearing_retries(self, mock_sleep, engine, mock_device, sample_bookmark):
        """确认弹窗未出现时重试"""
        from tasks.secret_shop.purchase import _PopupState

        with patch.object(engine, "_scan_popup") as mock_scan:
            mock_scan.return_value = _PopupState()
            result = engine.buy_item(sample_bookmark)
            assert result.success is False
            assert "弹窗未出现" in result.reason


class TestProcessShelf:
    """货架处理测试"""

    @patch("tasks.secret_shop.purchase.time.sleep")
    @patch("tasks.secret_shop.purchase.random.uniform", return_value=0.75)
    def test_process_buys_matching_items(self, mock_uniform, mock_sleep, engine, sample_bookmark):
        with patch.object(engine, "buy_item") as mock_buy:
            mock_buy.return_value = PurchaseResult("bookmark", 184000, True)
            results = engine.process_shelf([sample_bookmark])
            assert len(results) == 1
            assert results[0].item_type == "bookmark"

    @patch("tasks.secret_shop.purchase.time.sleep")
    @patch("tasks.secret_shop.purchase.random.uniform", return_value=0.75)
    def test_purchase_interval(self, mock_uniform, mock_sleep, engine, sample_bookmark, sample_mystic):
        with patch.object(engine, "buy_item") as mock_buy:
            mock_buy.return_value = PurchaseResult("bookmark", 184000, True)
            engine.process_shelf([sample_bookmark, sample_mystic])
            mock_uniform.assert_called_with(PURCHASE_INTERVAL_MIN, PURCHASE_INTERVAL_MAX)

    @patch("tasks.secret_shop.purchase.time.sleep")
    @patch("tasks.secret_shop.purchase.random.uniform", return_value=0.75)
    def test_process_empty_shelf(self, mock_uniform, mock_sleep, engine):
        results = engine.process_shelf([])
        assert results == []


class TestConstants:
    def test_item_type_mapping_covers_all_types(self):
        assert "bookmark" in ITEM_TYPE_TO_CONFIG_KEY
        assert "mystic_medal" in ITEM_TYPE_TO_CONFIG_KEY
        assert "equipment" in ITEM_TYPE_TO_CONFIG_KEY
        assert "fodder" in ITEM_TYPE_TO_CONFIG_KEY

    def test_confirm_btn_pos_defined(self):
        assert CONFIRM_BTN_POS == (818, 508)
        assert CANCEL_BTN_POS == (482, 508)

    def test_purchase_interval_range(self):
        assert PURCHASE_INTERVAL_MIN == 0.5
        assert PURCHASE_INTERVAL_MAX == 1.0
