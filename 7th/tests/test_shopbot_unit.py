"""
ShopBot 单元测试

覆盖需求:
- 7.1 主循环执行顺序（识别 → 购买 → 刷新）
- 7.3 异常恢复流程
- 7.4 连续恢复失败终止
- 6.1 刷新控制
- 6.3 天空石余量检查
- 6.4 最大刷新次数检查
- 7.2 运行统计汇总
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
    REFRESH_BTN,
    REFRESH_CONFIRM_BTN,
    REFRESH_SECOND_CONFIRM_BTN,
    SKYSTONE_AREA,
)
from shop.purchase import PurchaseResult


@pytest.fixture
def mock_config():
    """创建 mock ConfigManager"""
    config = MagicMock()
    app_cfg = MagicMock()
    app_cfg.device = MagicMock()
    app_cfg.device.serial = "127.0.0.1:5555"
    app_cfg.device.screenshot_method = "ADB"
    app_cfg.device.control_method = "ADB"
    app_cfg.shop = MagicMock()
    app_cfg.shop.skystone_threshold = 100
    app_cfg.shop.max_refresh_count = 200
    app_cfg.webui_port = 8080
    config.get.return_value = app_cfg
    config.get_buy_list.return_value = {
        "bookmarks": True,
        "mystic_medals": True,
        "equipment": False,
        "fodder": False,
    }
    return config


@pytest.fixture
def bot(mock_config):
    """创建 ShopBot 实例，替换内部组件为 mock"""
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
    """RunStatistics 数据类测试"""

    def test_default_values(self):
        """默认值全为 0"""
        stats = RunStatistics()
        assert stats.total_refreshes == 0
        assert stats.bookmarks_bought == 0
        assert stats.mystic_medals_bought == 0
        assert stats.equipment_bought == 0
        assert stats.skystone_spent == 0
        assert stats.skystone_remaining == 0

    def test_custom_values(self):
        """可以设置自定义值"""
        stats = RunStatistics(
            total_refreshes=50,
            bookmarks_bought=3,
            mystic_medals_bought=1,
            equipment_bought=2,
            skystone_spent=150,
            skystone_remaining=2850,
        )
        assert stats.total_refreshes == 50
        assert stats.bookmarks_bought == 3
        assert stats.mystic_medals_bought == 1
        assert stats.equipment_bought == 2
        assert stats.skystone_spent == 150
        assert stats.skystone_remaining == 2850


class TestShouldContinue:
    """停止条件测试 (需求 6.3, 6.4)"""

    def test_continue_when_resources_sufficient(self, bot):
        """资源充足且未达上限时继续"""
        assert bot.should_continue(500, 100, 10, 200) is True

    def test_stop_when_skystone_below_threshold(self, bot):
        """天空石低于阈值时停止"""
        assert bot.should_continue(50, 100, 10, 200) is False

    def test_stop_when_skystone_equals_threshold(self, bot):
        """天空石等于阈值时继续"""
        assert bot.should_continue(100, 100, 10, 200) is True

    def test_stop_when_refresh_count_reached(self, bot):
        """刷新次数达到上限时停止"""
        assert bot.should_continue(500, 100, 200, 200) is False

    def test_stop_when_refresh_count_exceeds(self, bot):
        """刷新次数超过上限时停止"""
        assert bot.should_continue(500, 100, 250, 200) is False

    def test_stop_both_conditions(self, bot):
        """两个条件同时满足时停止"""
        assert bot.should_continue(50, 100, 200, 200) is False

    def test_continue_at_zero_threshold(self, bot):
        """阈值为 0 时只要有天空石就继续"""
        assert bot.should_continue(1, 0, 0, 200) is True

    def test_stop_at_zero_skystone_with_zero_threshold(self, bot):
        """天空石为 0 且阈值为 0 时继续"""
        assert bot.should_continue(0, 0, 0, 200) is True


class TestUpdateStatistics:
    """运行统计更新测试 (需求 7.2)"""

    def test_update_bookmarks(self, bot):
        """成功购买书签时更新统计"""
        results = [PurchaseResult(item_type="bookmark", price=184000, success=True)]
        bot.update_statistics(results)
        assert bot.stats.bookmarks_bought == 1

    def test_update_mystic_medals(self, bot):
        """成功购买神秘奖章时更新统计"""
        results = [PurchaseResult(item_type="mystic_medal", price=280000, success=True)]
        bot.update_statistics(results)
        assert bot.stats.mystic_medals_bought == 1

    def test_update_equipment(self, bot):
        """成功购买装备时更新统计"""
        results = [PurchaseResult(item_type="equipment", price=250000, success=True)]
        bot.update_statistics(results)
        assert bot.stats.equipment_bought == 1

    def test_skip_failed_purchases(self, bot):
        """失败的购买不计入统计"""
        results = [
            PurchaseResult(item_type="bookmark", price=184000, success=False, reason="金币不足"),
        ]
        bot.update_statistics(results)
        assert bot.stats.bookmarks_bought == 0

    def test_multiple_results(self, bot):
        """多个购买结果正确累加"""
        results = [
            PurchaseResult(item_type="bookmark", price=184000, success=True),
            PurchaseResult(item_type="bookmark", price=184000, success=True),
            PurchaseResult(item_type="mystic_medal", price=280000, success=True),
            PurchaseResult(item_type="equipment", price=250000, success=False, reason="金币不足"),
        ]
        bot.update_statistics(results)
        assert bot.stats.bookmarks_bought == 2
        assert bot.stats.mystic_medals_bought == 1
        assert bot.stats.equipment_bought == 0

    def test_empty_results(self, bot):
        """空结果列表不改变统计"""
        bot.update_statistics([])
        assert bot.stats.bookmarks_bought == 0
        assert bot.stats.mystic_medals_bought == 0
        assert bot.stats.equipment_bought == 0


class TestGetStatistics:
    """获取统计测试"""

    def test_returns_copy(self, bot):
        """返回的是副本，修改不影响原始数据"""
        bot.stats.bookmarks_bought = 5
        stats = bot.get_statistics()
        stats.bookmarks_bought = 99
        assert bot.stats.bookmarks_bought == 5

    def test_reflects_current_state(self, bot):
        """返回当前状态"""
        bot.stats.total_refreshes = 10
        bot.stats.skystone_spent = 30
        stats = bot.get_statistics()
        assert stats.total_refreshes == 10
        assert stats.skystone_spent == 30


class TestStartStop:
    """启动/停止测试 (需求 9.8)"""

    def test_start_sets_running(self, bot):
        """start() 启动后 alive 为 True"""
        # Mock run_loop to just wait for stop
        def fake_loop():
            bot._stop_event.wait(timeout=5)
            bot._running = False

        with patch.object(bot, "run_loop", side_effect=fake_loop):
            bot.start()
            assert bot._running is True
            bot.stop()
            bot._thread.join(timeout=2)

    def test_stop_sets_event(self, bot):
        """stop() 设置停止事件"""
        bot.stop()
        assert bot._stop_event.is_set()

    def test_start_when_already_running(self, bot):
        """已运行时再次 start 不创建新线程"""
        bot._running = True
        original_thread = bot._thread
        bot.start()
        assert bot._thread is original_thread

    def test_alive_false_when_not_started(self, bot):
        """未启动时 alive 为 False"""
        assert bot.alive is False


class TestRunLoop:
    """主循环测试 (需求 7.1, 7.3, 7.4)"""

    @patch("shop_bot.time.sleep")
    def test_loop_order_recognize_purchase_refresh(self, mock_sleep, bot):
        """需求 7.1: 主循环按 识别→购买→刷新 顺序执行"""
        call_order = []

        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True
        bot.recognizer.recognize_shelf.side_effect = lambda: (
            call_order.append("recognize") or []
        )
        bot.purchase_engine.process_shelf.side_effect = lambda items: (
            call_order.append("purchase") or []
        )

        # should_continue returns False after first iteration
        with patch.object(bot, "check_resources", return_value=True), \
             patch.object(bot, "should_continue", return_value=False):
            bot.run_loop()

        assert call_order == ["recognize", "purchase"]

    @patch("shop_bot.time.sleep")
    def test_loop_with_refresh(self, mock_sleep, bot):
        """主循环包含刷新步骤"""
        call_order = []
        iteration = [0]

        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True
        bot.recognizer.recognize_shelf.side_effect = lambda: (
            call_order.append("recognize") or []
        )
        bot.purchase_engine.process_shelf.side_effect = lambda items: (
            call_order.append("purchase") or []
        )

        def fake_should_continue(*args):
            iteration[0] += 1
            return iteration[0] <= 1  # Continue for 1 iteration, then stop

        with patch.object(bot, "check_resources", return_value=True), \
             patch.object(bot, "should_continue", side_effect=fake_should_continue), \
             patch.object(bot, "refresh_shop", side_effect=lambda: (
                 call_order.append("refresh") or True
             )):
            bot.run_loop()

        assert call_order == ["recognize", "purchase", "refresh", "recognize", "purchase"]

    @patch("shop_bot.time.sleep")
    def test_error_recovery_on_exception(self, mock_sleep, bot):
        """需求 7.3: 异常时尝试恢复"""
        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True

        call_count = [0]

        def recognize_with_error():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("测试异常")
            return []

        bot.recognizer.recognize_shelf.side_effect = recognize_with_error
        bot.purchase_engine.process_shelf.return_value = []

        with patch.object(bot, "check_resources", return_value=True), \
             patch.object(bot, "should_continue", return_value=False), \
             patch.object(bot, "recover_from_error", return_value=True) as mock_recover:
            bot.run_loop()

        mock_recover.assert_called_once()

    @patch("shop_bot.time.sleep")
    def test_terminate_after_consecutive_failures(self, mock_sleep, bot):
        """需求 7.4: 连续 3 次恢复失败终止"""
        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True
        bot.recognizer.recognize_shelf.side_effect = RuntimeError("持续异常")

        with patch.object(bot, "recover_from_error", return_value=False) as mock_recover:
            bot.run_loop()

        assert mock_recover.call_count == MAX_CONSECUTIVE_ERRORS

    @patch("shop_bot.time.sleep")
    def test_device_connect_failure_stops(self, mock_sleep, bot):
        """设备连接失败时终止"""
        bot.device.connect.return_value = False
        bot.run_loop()
        assert bot._running is False

    @patch("shop_bot.time.sleep")
    def test_navigation_failure_stops(self, mock_sleep, bot):
        """导航失败时终止"""
        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = False
        bot.run_loop()
        assert bot._running is False

    @patch("shop_bot.time.sleep")
    def test_stop_event_exits_loop(self, mock_sleep, bot):
        """停止事件触发后退出循环"""
        bot.device.connect.return_value = True
        bot.navigator.navigate_to_secret_shop.return_value = True
        bot._stop_event.set()  # Pre-set stop event
        bot.recognizer.recognize_shelf.return_value = []
        bot.purchase_engine.process_shelf.return_value = []
        bot.run_loop()
        assert bot._running is False


class TestRefreshShop:
    """刷新货架测试 (需求 6.1, 6.2, 6.8)"""

    @patch("shop_bot.time.sleep")
    def test_successful_refresh(self, mock_sleep, bot):
        """成功刷新流程"""
        with patch.object(REFRESH_CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(REFRESH_SECOND_CONFIRM_BTN, "appear_on", return_value=False), \
             patch("shop_bot.Timer") as MockTimer:
            timer_instance = MagicMock()
            timer_instance.reached.return_value = False
            MockTimer.return_value = timer_instance
            # Make reached return True on second call to exit loop
            timer_instance.reached.side_effect = [False]

            result = bot.refresh_shop()
            assert result is True
            bot.device.click.assert_any_call(REFRESH_BTN)

    @patch("shop_bot.time.sleep")
    def test_refresh_with_second_confirm(self, mock_sleep, bot):
        """刷新时处理二次确认弹窗"""
        with patch.object(REFRESH_CONFIRM_BTN, "appear_on", return_value=True), \
             patch.object(REFRESH_SECOND_CONFIRM_BTN, "appear_on", return_value=True), \
             patch("shop_bot.Timer") as MockTimer:
            timer_instance = MagicMock()
            timer_instance.reached.side_effect = [False]
            MockTimer.return_value = timer_instance

            result = bot.refresh_shop()
            assert result is True

    @patch("shop_bot.time.sleep")
    def test_refresh_failure_after_retries(self, mock_sleep, bot):
        """刷新确认弹窗未出现，重试后失败"""
        with patch.object(REFRESH_CONFIRM_BTN, "appear_on", return_value=False), \
             patch("shop_bot.Timer") as MockTimer:
            timer_instance = MagicMock()
            timer_instance.reached.return_value = True
            MockTimer.return_value = timer_instance

            result = bot.refresh_shop()
            assert result is False


class TestRecoverFromError:
    """异常恢复测试"""

    def test_successful_recovery(self, bot):
        """恢复成功"""
        bot.navigator.navigate_to_secret_shop.return_value = True
        assert bot.recover_from_error() is True
        bot.device.save_error_screenshot.assert_called_once()

    def test_failed_recovery(self, bot):
        """恢复失败"""
        bot.navigator.navigate_to_secret_shop.return_value = False
        assert bot.recover_from_error() is False

    def test_recovery_exception(self, bot):
        """恢复过程中异常"""
        bot.device.save_error_screenshot.side_effect = RuntimeError("保存失败")
        assert bot.recover_from_error() is False


class TestConstants:
    """常量测试"""

    def test_button_instances_exist(self):
        """所有必要的 Button 实例都已定义"""
        assert REFRESH_BTN is not None
        assert REFRESH_CONFIRM_BTN is not None
        assert REFRESH_SECOND_CONFIRM_BTN is not None
        assert SKYSTONE_AREA is not None

    def test_max_consecutive_errors(self):
        """连续错误上限为 3"""
        assert MAX_CONSECUTIVE_ERRORS == 3

    def test_skystone_per_refresh(self):
        """每次刷新消耗 3 天空石"""
        assert SKYSTONE_PER_REFRESH == 3
