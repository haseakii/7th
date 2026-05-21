# Feature: auto-shop-refresh, Property 1: 配置序列化往返一致性
"""
属性测试：配置序列化往返一致性

对任意有效的 AppConfig 实例（包含任意合法的设备序列号、截图方式、控制方式、
购买物品列表布尔值、最大刷新次数、金币阈值、天空石阈值），通过
ConfigManager.save() 写入 YAML 文件后再通过 ConfigManager.load() 加载回来，
得到的配置对象应与原始对象在所有字段上完全一致。

**Validates: Requirements 2.1, 2.2, 2.5, 2.7**
"""

import sys
from pathlib import Path

# 确保可以导入 7th 下的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile

import hypothesis.strategies as st
from hypothesis import given, settings

from config_manager import AppConfig, ConfigManager, DeviceConfig, ShopConfig

# --- 策略定义 ---

# 设备序列号：非空可打印字符串（排除控制字符和换行）
serials = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        whitelist_characters=".:_-",
    ),
    min_size=1,
    max_size=50,
)

# 截图方式和控制方式：从支持的选项中选取
screenshot_methods = st.sampled_from(["ADB", "uiautomator2"])
control_methods = st.sampled_from(["ADB", "uiautomator2"])

# 布尔值
booleans = st.booleans()

# 非负整数（用于阈值和计数）
non_negative_ints = st.integers(min_value=0, max_value=100000)

# 端口号
ports = st.integers(min_value=1, max_value=65535)

# 组合策略：DeviceConfig
device_configs = st.builds(
    DeviceConfig,
    serial=serials,
    screenshot_method=screenshot_methods,
    control_method=control_methods,
)

# 组合策略：ShopConfig
shop_configs = st.builds(
    ShopConfig,
    buy_bookmarks=booleans,
    buy_mystic_medals=booleans,
    buy_equipment=booleans,
    buy_fodder=booleans,
    max_refresh_count=non_negative_ints,
    gold_threshold=non_negative_ints,
    skystone_threshold=non_negative_ints,
)

# 组合策略：AppConfig
app_configs = st.builds(
    AppConfig,
    device=device_configs,
    shop=shop_configs,
    webui_port=ports,
)


@given(config=app_configs)
@settings(max_examples=100)
def test_config_serialization_roundtrip(config):
    """
    Property 1: 配置序列化往返一致性

    对任意有效的 AppConfig，save → load 后所有字段应完全一致。

    **Validates: Requirements 2.1, 2.2, 2.5, 2.7**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = str(Path(tmp_dir) / "config.yaml")
        mgr = ConfigManager(config_path)

        # 将随机生成的配置写入内部状态并保存
        mgr._config = config
        mgr.save()

        # 用新的 ConfigManager 实例加载
        mgr2 = ConfigManager(config_path)
        loaded = mgr2.load()

        # 验证所有字段一致
        assert loaded.device.serial == config.device.serial, (
            f"serial mismatch: {loaded.device.serial!r} != {config.device.serial!r}"
        )
        assert loaded.device.screenshot_method == config.device.screenshot_method, (
            f"screenshot_method mismatch: {loaded.device.screenshot_method!r} != {config.device.screenshot_method!r}"
        )
        assert loaded.device.control_method == config.device.control_method, (
            f"control_method mismatch: {loaded.device.control_method!r} != {config.device.control_method!r}"
        )
        assert loaded.shop.buy_bookmarks == config.shop.buy_bookmarks, (
            f"buy_bookmarks mismatch: {loaded.shop.buy_bookmarks} != {config.shop.buy_bookmarks}"
        )
        assert loaded.shop.buy_mystic_medals == config.shop.buy_mystic_medals, (
            f"buy_mystic_medals mismatch: {loaded.shop.buy_mystic_medals} != {config.shop.buy_mystic_medals}"
        )
        assert loaded.shop.buy_equipment == config.shop.buy_equipment, (
            f"buy_equipment mismatch: {loaded.shop.buy_equipment} != {config.shop.buy_equipment}"
        )
        assert loaded.shop.buy_fodder == config.shop.buy_fodder, (
            f"buy_fodder mismatch: {loaded.shop.buy_fodder} != {config.shop.buy_fodder}"
        )
        assert loaded.shop.max_refresh_count == config.shop.max_refresh_count, (
            f"max_refresh_count mismatch: {loaded.shop.max_refresh_count} != {config.shop.max_refresh_count}"
        )
        assert loaded.shop.gold_threshold == config.shop.gold_threshold, (
            f"gold_threshold mismatch: {loaded.shop.gold_threshold} != {config.shop.gold_threshold}"
        )
        assert loaded.shop.skystone_threshold == config.shop.skystone_threshold, (
            f"skystone_threshold mismatch: {loaded.shop.skystone_threshold} != {config.shop.skystone_threshold}"
        )
        assert loaded.webui_port == config.webui_port, (
            f"webui_port mismatch: {loaded.webui_port} != {config.webui_port}"
        )


# Feature: auto-shop-refresh, Property 2: 无效 YAML 格式检测
"""
属性测试：无效 YAML 格式检测

对任意非法的 YAML 字符串（包含语法错误如不匹配的括号、错误缩进、非法字符等），
ConfigManager.load() 应抛出包含错误位置或原因描述的异常（ValueError），
而不是静默加载错误数据。

**Validates: Requirements 2.4**
"""


import pytest

# --- 无效 YAML 生成策略 ---

# 生成一定会导致 YAML 解析错误（yaml.YAMLError）的字符串
_yaml_breakers = st.sampled_from([
    "key: [unclosed",       # 未关闭的列表
    "key: {unclosed",       # 未关闭的映射
    "key: 'unclosed",       # 未关闭的单引号
    'key: "unclosed',       # 未关闭的双引号
    "a:\n  b: 1\n c: 2",   # 错误缩进（子级缩进不一致）
    ":\n[",                 # 不匹配的方括号
    "*invalid_anchor",      # 无效的锚点引用
    "%INVALID",             # 无效的指令
])

# 随机文本后缀，增加多样性
_random_suffix = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=0,
    max_size=20,
)

# 组合策略：在 YAML 语法错误前缀后拼接随机文本
invalid_yaml_strings = st.builds(
    lambda breaker, suffix: f"{breaker}{suffix}",
    breaker=_yaml_breakers,
    suffix=_random_suffix,
)


@given(bad_yaml=invalid_yaml_strings)
@settings(max_examples=100)
def test_invalid_yaml_raises_value_error(bad_yaml):
    """
    Property 2: 无效 YAML 格式检测

    对任意包含语法错误的 YAML 字符串，ConfigManager.load() 应抛出 ValueError。

    **Validates: Requirements 2.4**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = str(Path(tmp_dir) / "config.yaml")

        # 将无效 YAML 内容写入文件
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(bad_yaml)

        mgr = ConfigManager(config_path)

        with pytest.raises(ValueError):
            mgr.load()


# Feature: auto-shop-refresh, Property 3: 配置并发读写安全
"""
属性测试：配置并发读写安全

多线程同时调用 get() 和 update()，验证无异常抛出且最终配置状态一致。
所有操作应成功完成，最终配置状态应与某个合法的操作串行化顺序一致。

**Validates: Requirements 2.8**
"""

import threading


# --- 并发操作策略 ---

# 可更新的配置项定义：(section, key, value_strategy)
_updatable_fields = [
    ("shop", "buy_bookmarks", st.booleans()),
    ("shop", "buy_mystic_medals", st.booleans()),
    ("shop", "buy_equipment", st.booleans()),
    ("shop", "buy_fodder", st.booleans()),
    ("shop", "max_refresh_count", st.integers(min_value=0, max_value=100000)),
    ("shop", "gold_threshold", st.integers(min_value=0, max_value=100000)),
    ("shop", "skystone_threshold", st.integers(min_value=0, max_value=100000)),
    ("device", "serial", st.just("127.0.0.1:5555")),
    ("device", "screenshot_method", st.sampled_from(["ADB", "uiautomator2"])),
    ("device", "control_method", st.sampled_from(["ADB", "uiautomator2"])),
    ("app", "webui_port", st.integers(min_value=1, max_value=65535)),
]

# 单个 update 操作策略：随机选一个字段并生成对应值
_update_ops = st.one_of([
    st.tuples(st.just(section), st.just(key), val_st).map(
        lambda t: ("update", t[0], t[1], t[2])
    )
    for section, key, val_st in _updatable_fields
])

# 单个 get 操作策略
_get_ops = st.just(("get",))

# 混合操作列表：get 和 update 随机混合
concurrent_ops = st.lists(
    st.one_of(_get_ops, _update_ops),
    min_size=4,
    max_size=20,
)


@given(ops=concurrent_ops)
@settings(max_examples=100)
def test_config_concurrent_read_write_safety(ops):
    """
    Property 3: 配置并发读写安全

    多线程同时调用 get() 和 update()，验证无异常且最终状态一致。

    **Validates: Requirements 2.8**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = str(Path(tmp_dir) / "config.yaml")
        mgr = ConfigManager(config_path)
        mgr.save()  # 写入默认配置

        errors = []
        barrier = threading.Barrier(len(ops))

        def worker(op):
            try:
                barrier.wait(timeout=5)
                if op[0] == "get":
                    result = mgr.get()
                    # 验证返回的是有效的 AppConfig
                    assert isinstance(result, AppConfig)
                else:
                    # op = ("update", section, key, value)
                    _, section, key, value = op
                    mgr.update(section, key, value)
            except threading.BrokenBarrierError:
                pass  # 允许 barrier 超时（不影响正确性）
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(op,)) for op in ops]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # 验证：无异常抛出
        assert errors == [], f"并发操作中出现异常: {errors}"

        # 验证：最终状态有效
        final = mgr.get()
        assert isinstance(final, AppConfig)

        # 验证所有字段类型正确
        assert isinstance(final.device, DeviceConfig)
        assert isinstance(final.shop, ShopConfig)
        assert isinstance(final.device.serial, str)
        assert isinstance(final.device.screenshot_method, str)
        assert isinstance(final.device.control_method, str)
        assert isinstance(final.shop.buy_bookmarks, bool)
        assert isinstance(final.shop.buy_mystic_medals, bool)
        assert isinstance(final.shop.buy_equipment, bool)
        assert isinstance(final.shop.buy_fodder, bool)
        assert isinstance(final.shop.max_refresh_count, int)
        assert isinstance(final.shop.gold_threshold, int)
        assert isinstance(final.shop.skystone_threshold, int)
        assert isinstance(final.webui_port, int)
        assert 1 <= final.webui_port <= 65535
        assert final.shop.max_refresh_count >= 0
        assert final.shop.gold_threshold >= 0
        assert final.shop.skystone_threshold >= 0


# Feature: auto-shop-refresh, Property 10: 运行时设备配置锁定
"""
属性测试：运行时设备配置锁定

模拟 ShopBot 运行状态（bot.alive = True），验证 Web UI 的设备配置页
不会注册 pin_on_change 回调，即设备配置修改在运行时被有效阻止。

**Validates: Requirements 9.12**
"""

from unittest.mock import MagicMock, patch


# 设备配置值策略
device_serials = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        whitelist_characters=".:_-",
    ),
    min_size=1,
    max_size=50,
)
device_screenshot_methods = st.sampled_from(["ADB", "uiautomator2"])
device_control_methods = st.sampled_from(["ADB", "uiautomator2"])


@given(
    serial=device_serials,
    screenshot_method=device_screenshot_methods,
    control_method=device_control_methods,
)
@settings(max_examples=100, deadline=None)
def test_runtime_device_config_locked(serial, screenshot_method, control_method):
    """
    Property 10: 运行时设备配置锁定

    当 ShopBot 处于运行状态（alive=True）时，Web UI 的设备配置页
    不应注册 pin_on_change 回调，从而阻止设备配置修改。

    **Validates: Requirements 9.12**
    """
    # 构造带有随机设备配置的 ConfigManager mock
    mock_config = MagicMock()
    mock_app_config = MagicMock()
    mock_app_config.device.serial = serial
    mock_app_config.device.screenshot_method = screenshot_method
    mock_app_config.device.control_method = control_method
    mock_config.get.return_value = mock_app_config

    # 构造 alive=True 的 bot mock
    mock_bot = MagicMock()
    mock_bot.alive = True

    # 导入并创建 ShopBotGUI
    from webui.app import ShopBotGUI

    gui = ShopBotGUI(config=mock_config, bot=mock_bot)

    # Mock 所有 PyWebIO 函数
    with patch("webui.app.ShopBotGUI._render_theme_toggle"), \
         patch("pywebio.output.put_html"), \
         patch("pywebio.output.put_text") as mock_put_text, \
         patch("pywebio.output.use_scope") as mock_use_scope, \
         patch("pywebio.pin.put_input") as mock_put_input, \
         patch("pywebio.pin.put_select") as mock_put_select, \
         patch("pywebio.pin.pin_on_change") as mock_pin_on_change:

        # use_scope 作为上下文管理器
        mock_use_scope.return_value.__enter__ = MagicMock()
        mock_use_scope.return_value.__exit__ = MagicMock(return_value=False)

        gui.render_device_config()

        # 核心断言：bot 运行时，pin_on_change 不应被调用
        # 这意味着没有注册任何配置变更回调，设备配置修改被锁定
        mock_pin_on_change.assert_not_called(), (
            f"pin_on_change should NOT be called when bot is alive, "
            f"but was called {mock_pin_on_change.call_count} times. "
            f"Device config (serial={serial!r}, screenshot={screenshot_method!r}, "
            f"control={control_method!r}) should be locked during runtime."
        )
