# Feature: auto-shop-refresh, Property 6: 停止条件正确性
"""
属性测试：停止条件正确性

生成随机天空石余量/阈值/刷新次数组合，验证 ShopBot.should_continue() 的继续/停止决策。

**Validates: Requirements 6.3, 6.4**
"""

import sys
import os
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shop_bot import ShopBot


def _make_bot():
    """创建 ShopBot 实例，mock 所有外部依赖。"""
    config = MagicMock()
    app_cfg = MagicMock()
    app_cfg.device = MagicMock()
    app_cfg.device.serial = "127.0.0.1:5555"
    app_cfg.device.screenshot_method = "ADB"
    app_cfg.device.control_method = "ADB"
    app_cfg.shop = MagicMock()
    app_cfg.shop.skystone_threshold = 100
    app_cfg.shop.max_refresh_count = 200
    config.get.return_value = app_cfg

    with patch("shop_bot.DeviceController"), \
         patch("shop_bot.ShopNavigator"), \
         patch("shop_bot.ItemRecognizer"), \
         patch("shop_bot.PurchaseEngine"):
        return ShopBot(config)


# **Validates: Requirements 6.3, 6.4**
@given(
    skystone_remaining=st.integers(min_value=0, max_value=100000),
    skystone_threshold=st.integers(min_value=0, max_value=100000),
    refresh_count=st.integers(min_value=0, max_value=10000),
    max_refresh_count=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=100)
def test_should_continue_stop_condition_correctness(
    skystone_remaining,
    skystone_threshold,
    refresh_count,
    max_refresh_count,
):
    """Property 6: 停止条件正确性

    当天空石余量 < 阈值 或 刷新次数 >= 最大刷新次数时返回 False，否则返回 True。
    """
    bot = _make_bot()
    result = bot.should_continue(
        skystone_remaining, skystone_threshold, refresh_count, max_refresh_count
    )

    should_stop = (
        skystone_remaining < skystone_threshold
        or refresh_count >= max_refresh_count
    )

    if should_stop:
        assert result is False, (
            f"Expected False (stop) but got True: "
            f"skystone_remaining={skystone_remaining}, skystone_threshold={skystone_threshold}, "
            f"refresh_count={refresh_count}, max_refresh_count={max_refresh_count}"
        )
    else:
        assert result is True, (
            f"Expected True (continue) but got False: "
            f"skystone_remaining={skystone_remaining}, skystone_threshold={skystone_threshold}, "
            f"refresh_count={refresh_count}, max_refresh_count={max_refresh_count}"
        )


# Feature: auto-shop-refresh, Property 7: 运行统计汇总正确性
"""
属性测试：运行统计汇总正确性

生成随机 PurchaseResult 序列（随机 item_type、price、success、reason），
调用 ShopBot.update_statistics(results) 后验证统计汇总数值：
- bookmarks_bought 等于成功购买 bookmark 的数量
- mystic_medals_bought 等于成功购买 mystic_medal 的数量
- equipment_bought 等于成功购买 equipment 的数量
- 失败的购买不计入统计

**Validates: Requirements 7.2**
"""

from shop.purchase import PurchaseResult as _PurchaseResult  # noqa: E402

# Strategies for generating random PurchaseResult sequences
_item_types = st.sampled_from(["bookmark", "mystic_medal", "equipment", "fodder", "unknown"])
_purchase_result_strategy = st.builds(
    _PurchaseResult,
    item_type=_item_types,
    price=st.integers(min_value=0, max_value=500000),
    success=st.booleans(),
    reason=st.text(min_size=0, max_size=20),
)
_purchase_results_strategy = st.lists(_purchase_result_strategy, min_size=0, max_size=50)


# **Validates: Requirements 7.2**
@given(results=_purchase_results_strategy)
@settings(max_examples=100)
def test_update_statistics_correctness(results):
    """Property 7: 运行统计汇总正确性

    对任意 PurchaseResult 序列，update_statistics 后：
    - bookmarks_bought == 成功购买 bookmark 的数量
    - mystic_medals_bought == 成功购买 mystic_medal 的数量
    - equipment_bought == 成功购买 equipment 的数量
    - 失败的购买不计入统计
    """
    bot = _make_bot()

    # 确保统计从零开始
    assert bot.stats.bookmarks_bought == 0
    assert bot.stats.mystic_medals_bought == 0
    assert bot.stats.equipment_bought == 0

    bot.update_statistics(results)

    expected_bookmarks = sum(
        1 for r in results if r.item_type == "bookmark" and r.success
    )
    expected_mystic_medals = sum(
        1 for r in results if r.item_type == "mystic_medal" and r.success
    )
    expected_equipment = sum(
        1 for r in results if r.item_type == "equipment" and r.success
    )

    assert bot.stats.bookmarks_bought == expected_bookmarks, (
        f"bookmarks_bought: expected {expected_bookmarks}, got {bot.stats.bookmarks_bought}"
    )
    assert bot.stats.mystic_medals_bought == expected_mystic_medals, (
        f"mystic_medals_bought: expected {expected_mystic_medals}, got {bot.stats.mystic_medals_bought}"
    )
    assert bot.stats.equipment_bought == expected_equipment, (
        f"equipment_bought: expected {expected_equipment}, got {bot.stats.equipment_bought}"
    )


# Feature: auto-shop-refresh, Property 9: 安全停止不中断购买
"""
属性测试：安全停止不中断购买

模拟购买操作耗时，在 run_loop 执行过程中调用 stop()，
验证当前 process_shelf 调用完整完成（所有物品都被处理）后主循环才退出。

**Validates: Requirements 9.8**
"""

import threading  # noqa: E402
import time as _time  # noqa: E402

from shop.recognizer import ShopItem  # noqa: E402


def _make_shop_items(n: int):
    """生成 n 个需要购买的 ShopItem。"""
    return [
        ShopItem(
            item_type="bookmark",
            currency="gold",
            price=184000,
            slot_index=i,
            position=(100 * i, 200, 100 * i + 80, 350),
            confidence=0.95,
        )
        for i in range(n)
    ]


# **Validates: Requirements 9.8**
@given(
    num_items=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=50, deadline=None)
def test_safe_stop_does_not_interrupt_purchase(num_items):
    """Property 9: 安全停止不中断购买

    模拟 process_shelf 处理多个物品（每个耗时一小段时间），
    在处理过程中调用 stop()，验证：
    1. process_shelf 完整处理了所有物品（不被中断）
    2. 主循环在当前迭代结束后退出
    """
    bot = _make_bot()

    # Track which items were processed by process_shelf
    processed_items = []
    shelf_call_count = 0

    items = _make_shop_items(num_items)

    original_process_shelf = None

    def mock_process_shelf(item_list):
        """模拟耗时的购买操作，逐个处理物品并记录。"""
        nonlocal shelf_call_count
        shelf_call_count += 1
        results = []
        for item in item_list:
            # Simulate purchase taking some time
            _time.sleep(0.01)
            processed_items.append(item.slot_index)
            results.append(_PurchaseResult(
                item_type=item.item_type,
                price=item.price,
                success=True,
                reason="",
            ))
        return results

    # Mock dependencies so run_loop can execute
    bot.device.connect = MagicMock(return_value=True)
    bot.navigator.navigate_to_secret_shop = MagicMock(return_value=True)
    bot.recognizer.recognize_shelf = MagicMock(return_value=items)
    bot.recognizer.recognize_visible_items = MagicMock(return_value=items)
    bot.purchase_engine.process_shelf = MagicMock(side_effect=mock_process_shelf)

    # Skip calibration and scroll-to-top to avoid race with delayed stop
    bot._calibrate_before_loop = MagicMock()
    bot._scroll_to_top = MagicMock()

    # Skip scene validation to focus on stop-not-interrupting behavior
    bot._ensure_secret_shop = MagicMock(return_value=True)

    # Make check_resources / should_continue always want to continue
    bot.check_resources = MagicMock(return_value=True)
    bot.refresh_shop = MagicMock(return_value=True)

    cfg = bot.config.get()
    cfg.shop.skystone_threshold = 0
    cfg.shop.max_refresh_count = 9999

    # Schedule stop() to fire after a short delay (while process_shelf is running)
    stop_fired = threading.Event()

    def delayed_stop():
        # Wait a tiny bit so run_loop enters process_shelf
        _time.sleep(0.005)
        bot.stop()
        stop_fired.set()

    stop_thread = threading.Thread(target=delayed_stop, daemon=True)
    stop_thread.start()

    # Run the loop directly (not in a separate thread, so we can assert after)
    bot._stop_event.clear()
    bot._running = True
    bot.run_loop()

    stop_thread.join(timeout=2.0)

    # Key assertion: all items in the first shelf were fully processed
    # process_shelf was called at least once
    assert shelf_call_count >= 1, "process_shelf should have been called at least once"

    # The first call should have processed ALL items (not interrupted mid-way)
    expected_slots = list(range(num_items))
    first_batch = processed_items[:num_items]
    assert first_batch == expected_slots, (
        f"Expected all {num_items} items processed in first batch, "
        f"got {first_batch}"
    )

    # Bot should have stopped (not running anymore)
    assert bot._running is False, "Bot should have stopped after run_loop exits"
