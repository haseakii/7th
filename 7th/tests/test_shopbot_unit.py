"""
ShopBot 单元测试（新版 - OCR 检测 + 固定坐标）
"""

import sys
import os
import threading
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shop_bot import (
    ShopBot,
    RunStatistics,
    MAX_CONSECUTIVE_ERRORS,
    SKYSTONE_PER_REFRESH,
    REFRESH_BTN_REGION,
    REFRESH_CONFIRM_BTN_POS,
    SKYSTONE_REGION,
)
from tasks.secret_shop.purchase import PurchaseResult


@pytest.fixture
def mock_config():
    config = MagicMock()
    app_cfg = MagicMock()
    app_cfg.device = MagicMock()
    app_cfg.device.serial = "127.0.0.1:5555"
    app_cfg.device.screenshot_method = "ADB"
    app_cfg.device.control_method = "ADB"
    app_cfg.shop = MagicMock()
    app_cfg.shop.skystone_threshold = 100
    app_cfg.shop.max_refresh_count = 200
    app_cfg.shop.max_bookmarks = 0
    app_cfg.shop.max_mystic_medals = 0
    app_cfg.shop.max_skystone_spend = 0
    app_cfg.webui_port = 8080
    config.get.return_value = app_cfg
    config.get_buy_list.return_value = {
        "bookmarks": True, "mystic_medals": True,
        "equipment": False, "fodder": False,
    }
    return config


@pytest.fixture
def bot(mock_config):
    with patch("shop_bot.DeviceController") as MockDevice, \
         patch("shop_bot.ShopNavigator") as MockNav, \
         patch("shop_bot.ItemRecognizer") as MockRec, \
         patch("shop_bot.PurchaseEngine") as MockPur:
        mock_device = MagicMock()
        mock_device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        mock_device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
        MockDevice.return_value = mock_device

        b = ShopBot(mock_config)
        b.device = mock_device
        b.navigator = MockNav.return_value
        b.recognizer = MockRec.return_value
        b.purchase_engine = MockPur.return_value
        return b


class TestRunStatistics:
    def test_default_values(self):
        stats = RunStatistics()
        assert stats.total_refreshes == 0
        assert stats.bookmarks_bought == 0
        assert stats.mystic_medals_bought == 0
        assert stats.equipment_bought == 0
        assert stats.skystone_spent == 0
        assert stats.skystone_remaining == 0

    def test_custom_values(self):
        stats = RunStatistics(total_refreshes=50, bookmarks_bought=3,
                              mystic_medals_bought=1, equipment_bought=2,
                              skystone_spent=150, skystone_remaining=2850)
        assert stats.total_refreshes == 50
        assert stats.bookmarks_bought == 3
        assert stats.mystic_medals_bought == 1
        assert stats.equipment_bought == 2
        assert stats.skystone_spent == 150
        assert stats.skystone_remaining == 2850


class TestShouldContinue:
    def test_continue_when_resources_sufficient(self, bot):
        assert bot.should_continue(500, 100, 10, 200) is True

    def test_stop_when_skystone_below_threshold(self, bot):
        assert bot.should_continue(50, 100, 10, 200) is False

    def test_stop_when_refresh_count_reached(self, bot):
        assert bot.should_continue(500, 100, 200, 200) is False

    def test_stop_when_refresh_count_exceeds(self, bot):
        assert bot.should_continue(500, 100, 250, 200) is False

    def test_continue_at_zero_threshold(self, bot):
        assert bot.should_continue(1, 0, 0, 200) is True


class TestUpdateStatistics:
    def test_update_bookmarks(self, bot):
        results = [PurchaseResult("bookmark", 184000, True)]
        bot.update_statistics(results)
        assert bot.stats.bookmarks_bought == 1

    def test_update_mystic_medals(self, bot):
        results = [PurchaseResult("mystic_medal", 280000, True)]
        bot.update_statistics(results)
        assert bot.stats.mystic_medals_bought == 1

    def test_update_equipment(self, bot):
        results = [PurchaseResult("equipment", 250000, True)]
        bot.update_statistics(results)
        assert bot.stats.equipment_bought == 1

    def test_skip_failed_purchases(self, bot):
        results = [PurchaseResult("bookmark", 184000, False, "金币不足")]
        bot.update_statistics(results)
        assert bot.stats.bookmarks_bought == 0

    def test_multiple_results(self, bot):
        results = [
            PurchaseResult("bookmark", 184000, True),
            PurchaseResult("bookmark", 184000, True),
            PurchaseResult("mystic_medal", 280000, True),
            PurchaseResult("equipment", 250000, False, "金币不足"),
        ]
        bot.update_statistics(results)
        assert bot.stats.bookmarks_bought == 2
        assert bot.stats.mystic_medals_bought == 1
        assert bot.stats.equipment_bought == 0


class TestStartStop:
    def test_stop_sets_event(self, bot):
        bot.stop()
        assert bot._stop_event.is_set()

    def test_start_when_already_running(self, bot):
        bot._running = True
        original_thread = bot._thread
        bot.start()
        assert bot._thread is original_thread

    def test_alive_false_when_not_started(self, bot):
        assert bot.alive is False


class TestRunLoop:
    @patch("shop_bot.time.sleep")
    def test_loop_order_recognize_purchase(self, mock_sleep, bot):
        call_order = []
        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True
        bot.recognizer.recognize_visible_items.side_effect = lambda: (
            call_order.append("recognize") or []
        )
        bot.purchase_engine.process_shelf.side_effect = lambda items: (
            call_order.append("purchase") or []
        )
        def mock_scroll_down():
            bot.recognizer.recognize_visible_items()
            bot.purchase_engine.process_shelf([])
            return []
        with patch.object(bot, "_calibrate_before_loop"), \
             patch.object(bot, "_scroll_to_top"), \
             patch.object(bot, "_scroll_down_and_buy", side_effect=mock_scroll_down), \
             patch.object(bot, "check_resources", return_value=True), \
             patch.object(bot, "should_continue", return_value=False):
            bot.run_loop()
        assert call_order == ["recognize", "purchase"]

    @patch("shop_bot.time.sleep")
    def test_stop_event_exits_loop(self, mock_sleep, bot):
        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True
        bot._stop_event.set()
        bot.recognizer.recognize_visible_items.return_value = []
        bot.purchase_engine.process_shelf.return_value = []
        bot.run_loop()
        assert bot._running is False


class TestRefreshShop:
    @patch("shop_bot.time.sleep")
    def test_successful_refresh(self, mock_sleep, bot):
        """使用缓存位置刷新"""
        bot._refresh_btn_pos = (748, 460)
        result = bot.refresh_shop()
        assert result is True

    @patch("shop_bot.time.sleep")
    def test_refresh_uses_cached_position(self, mock_sleep, bot):
        bot._refresh_btn_pos = (748, 460)
        bot.refresh_shop()
        bot.device.click_position.assert_any_call(748, 460)

    @patch("shop_bot.time.sleep")
    def test_refresh_failure_after_retries(self, mock_sleep, bot):
        bot._refresh_btn_pos = None
        with patch.object(bot, "_find_refresh_button", return_value=None):
            result = bot.refresh_shop()
            assert result is False


class TestRecoverFromError:
    def test_successful_recovery(self, bot):
        bot.navigator.navigate_to_secret_shop.return_value = True
        assert bot.recover_from_error() is True
        bot.device.save_error_screenshot.assert_called_once()

    def test_failed_recovery(self, bot):
        bot.navigator.navigate_to_secret_shop.return_value = False
        assert bot.recover_from_error() is False

    def test_recovery_exception(self, bot):
        bot.device.save_error_screenshot.side_effect = RuntimeError("保存失败")
        assert bot.recover_from_error() is False


class TestConstants:
    def test_constants_defined(self):
        assert MAX_CONSECUTIVE_ERRORS == 3
        assert SKYSTONE_PER_REFRESH == 3
        assert REFRESH_BTN_REGION == (50, 620, 400, 718)
        assert REFRESH_CONFIRM_BTN_POS == (748, 460)
        assert SKYSTONE_REGION == (860, 0, 990, 55)
