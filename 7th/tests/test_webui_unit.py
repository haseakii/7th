"""
Unit tests for webui/app.py – ShopBotGUI

Covers:
- Instantiation with ConfigManager and ShopBot
- Navigation between pages
- Startup failure graceful degradation (Requirement 9.13)
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy dependencies so we can import ShopBotGUI without a real device
# ---------------------------------------------------------------------------

# Ensure the 7th package root is on sys.path
import pathlib
_SEVENTH = str(pathlib.Path(__file__).resolve().parent.parent)
if _SEVENTH not in sys.path:
    sys.path.insert(0, _SEVENTH)


def _make_mock_config():
    """Create a mock ConfigManager."""
    from config_manager import AppConfig
    cfg = AppConfig()
    mock = MagicMock()
    mock.get.return_value = cfg
    return mock


def _make_mock_bot():
    """Create a mock ShopBot."""
    mock = MagicMock()
    mock.alive = False
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestShopBotGUIInit:
    def test_init_stores_references(self):
        from webui.app import ShopBotGUI, PAGE_OVERVIEW
        config = _make_mock_config()
        bot = _make_mock_bot()
        gui = ShopBotGUI(config, bot)

        assert gui.config is config
        assert gui.bot is bot
        assert gui._current_page == PAGE_OVERVIEW

    def test_nav_items_contains_three_pages(self):
        from webui.app import NAV_ITEMS
        assert len(NAV_ITEMS) == 4
        labels = [label for label, _ in NAV_ITEMS]
        assert any("总览" in l for l in labels)
        assert any("商店配置" in l for l in labels)
        assert any("设备配置" in l for l in labels)


class TestStartServerDegradation:
    """Requirement 9.13: Web UI startup failure degrades to no-UI mode."""

    def test_start_server_logs_warning_on_os_error(self):
        """If the port is in use (OSError), start_server should log a warning
        and return without raising."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())

        # Patch tornado_start to raise OSError (port in use)
        with patch("webui.app.logger") as mock_logger:
            with patch.dict("sys.modules", {
                "pywebio.platform.tornado": MagicMock(
                    start_server=MagicMock(side_effect=OSError("Address already in use"))
                ),
            }):
                # Should NOT raise
                gui.start_server(port=8080)

            # Should have logged a warning
            mock_logger.warning.assert_called()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "启动失败" in warning_msg or "8080" in warning_msg

    def test_start_server_logs_warning_on_generic_exception(self):
        """Any unexpected exception during startup should be caught and logged."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())

        with patch("webui.app.logger") as mock_logger:
            with patch.dict("sys.modules", {
                "pywebio.platform.tornado": MagicMock(
                    start_server=MagicMock(side_effect=RuntimeError("unexpected"))
                ),
            }):
                gui.start_server(port=9999)

            mock_logger.warning.assert_called()

    def test_start_server_handles_missing_pywebio(self):
        """If pywebio is not installed, start_server should log and return."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())

        # Temporarily make pywebio.platform.tornado un-importable
        with patch("webui.app.logger") as mock_logger:
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if "pywebio.platform.tornado" in name:
                    raise ImportError("No module named 'pywebio'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                gui.start_server(port=8080)

            mock_logger.warning.assert_called()


class TestNavigateTo:
    """Test that _navigate_to dispatches to the correct render method."""

    def test_navigate_to_overview(self):
        from webui.app import ShopBotGUI, PAGE_OVERVIEW

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui.render_overview = MagicMock()
        gui.render_shop_config = MagicMock()
        gui.render_device_config = MagicMock()

        # Mock pywebio.output.clear since it requires a session
        with patch("webui.app.ShopBotGUI._navigate_to") as _:
            pass

        # Direct call to verify dispatch logic
        with patch("pywebio.output.clear"):
            gui._navigate_to(PAGE_OVERVIEW)

        assert gui._current_page == PAGE_OVERVIEW
        gui.render_overview.assert_called_once()
        gui.render_shop_config.assert_not_called()
        gui.render_device_config.assert_not_called()

    def test_navigate_to_shop_config(self):
        from webui.app import ShopBotGUI, PAGE_SHOP_CONFIG

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui.render_overview = MagicMock()
        gui.render_shop_config = MagicMock()
        gui.render_device_config = MagicMock()

        with patch("pywebio.output.clear"):
            gui._navigate_to(PAGE_SHOP_CONFIG)

        assert gui._current_page == PAGE_SHOP_CONFIG
        gui.render_shop_config.assert_called_once()

    def test_navigate_to_device_config(self):
        from webui.app import ShopBotGUI, PAGE_DEVICE_CONFIG

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui.render_overview = MagicMock()
        gui.render_shop_config = MagicMock()
        gui.render_device_config = MagicMock()

        with patch("pywebio.output.clear"):
            gui._navigate_to(PAGE_DEVICE_CONFIG)

        assert gui._current_page == PAGE_DEVICE_CONFIG
        gui.render_device_config.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for Task 13.2: Overview page implementation
# ---------------------------------------------------------------------------

class TestBuildStatsHtml:
    """Test _build_stats_html produces correct card HTML."""

    def test_contains_all_five_stat_labels(self):
        from webui.app import ShopBotGUI
        from shop_bot import RunStatistics

        stats = RunStatistics(
            total_refreshes=10,
            bookmarks_bought=3,
            mystic_medals_bought=1,
            skystone_spent=30,
            skystone_remaining=2970,
        )
        html = ShopBotGUI._build_stats_html(stats)

        assert "刷新次数" in html
        assert "书签购买" in html
        assert "神秘奖章" in html
        assert "天空石消耗" in html
        assert "天空石余量" in html

    def test_contains_stat_values(self):
        from webui.app import ShopBotGUI
        from shop_bot import RunStatistics

        stats = RunStatistics(
            total_refreshes=42,
            bookmarks_bought=7,
            mystic_medals_bought=2,
            skystone_spent=126,
            skystone_remaining=1874,
        )
        html = ShopBotGUI._build_stats_html(stats)

        assert ">42<" in html
        assert ">7<" in html
        assert ">2<" in html
        assert ">126<" in html
        assert ">1874<" in html

    def test_zero_stats(self):
        from webui.app import ShopBotGUI
        from shop_bot import RunStatistics

        stats = RunStatistics()
        html = ShopBotGUI._build_stats_html(stats)

        # All values should be 0
        assert html.count(">0<") == 5


class TestStartStopHandler:
    """Test _on_start_stop calls bot.start() or bot.stop()."""

    def test_start_action_calls_bot_start(self):
        from webui.app import ShopBotGUI

        bot = _make_mock_bot()
        gui = ShopBotGUI(_make_mock_config(), bot)
        gui._refresh_control_button = MagicMock()

        gui._on_start_stop("start")

        bot.start.assert_called_once()
        bot.stop.assert_not_called()

    def test_stop_action_calls_bot_stop(self):
        from webui.app import ShopBotGUI

        bot = _make_mock_bot()
        gui = ShopBotGUI(_make_mock_config(), bot)
        gui._refresh_control_button = MagicMock()

        gui._on_start_stop("stop")

        bot.stop.assert_called_once()
        bot.start.assert_not_called()


class TestStopOverviewUpdates:
    """Test stop_overview_updates sets the flag."""

    def test_sets_overview_active_false(self):
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._overview_active = True
        gui.stop_overview_updates()

        assert gui._overview_active is False


class TestScrollToggle:
    """Test _toggle_scroll flips the scroll state."""

    def test_toggle_from_on_to_off(self):
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._scroll_enabled = True
        gui._render_scroll_toggle = MagicMock()

        gui._toggle_scroll()

        assert gui._scroll_enabled is False
        gui._render_scroll_toggle.assert_called_once()

    def test_toggle_from_off_to_on(self):
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._scroll_enabled = False
        gui._render_scroll_toggle = MagicMock()

        gui._toggle_scroll()

        assert gui._scroll_enabled is True
        gui._render_scroll_toggle.assert_called_once()


class TestWebUILogHandler:
    """Test _WebUILogHandler buffers and drains log records."""

    def test_emit_and_drain(self):
        import logging
        from webui.app import _WebUILogHandler, ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        handler = _WebUILogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        handler.emit(record)

        lines = handler.drain()
        assert lines == ["hello world"]

    def test_drain_clears_buffer(self):
        import logging
        from webui.app import _WebUILogHandler, ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        handler = _WebUILogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="line1", args=(), exc_info=None,
        )
        handler.emit(record)
        handler.drain()

        # Second drain should be empty
        assert handler.drain() == []

    def test_multiple_records(self):
        import logging
        from webui.app import _WebUILogHandler, ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        handler = _WebUILogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        for msg in ["a", "b", "c"]:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=msg, args=(), exc_info=None,
            )
            handler.emit(record)

        lines = handler.drain()
        assert lines == ["a", "b", "c"]


class TestNavigateStopsOverview:
    """Test that navigating away from overview stops background threads."""

    def test_navigate_away_calls_stop_overview(self):
        from webui.app import ShopBotGUI, PAGE_OVERVIEW, PAGE_SHOP_CONFIG

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._current_page = PAGE_OVERVIEW
        gui._overview_active = True
        gui.render_shop_config = MagicMock()

        with patch("pywebio.output.clear"):
            gui._navigate_to(PAGE_SHOP_CONFIG)

        assert gui._overview_active is False


# ---------------------------------------------------------------------------
# Tests for Task 13.4: Config pages implementation
# ---------------------------------------------------------------------------

class TestRenderShopConfig:
    """Test render_shop_config uses pin inputs and persists via ConfigManager."""

    def test_shop_config_calls_pin_inputs(self):
        """render_shop_config should use pywebio.pin for reactive inputs."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_checkbox") as mock_checkbox, \
             patch("pywebio.pin.put_input") as mock_input, \
             patch("pywebio.pin.pin_on_change"):
            gui.render_shop_config()

        # Should create checkbox for buy items
        mock_checkbox.assert_called_once()
        call_kwargs = mock_checkbox.call_args
        assert call_kwargs[0][0] == "shop_buy_items"

        # Should create 6 number inputs (max_refresh, gold_threshold, skystone_threshold,
        # max_bookmarks, max_mystic_medals, max_skystone_spend)
        assert mock_input.call_count == 6

    def test_shop_config_initial_checked_values(self):
        """Checkbox initial values should match config."""
        from webui.app import ShopBotGUI
        from config_manager import AppConfig, ShopConfig

        cfg = AppConfig(shop=ShopConfig(
            buy_bookmarks=True,
            buy_mystic_medals=False,
            buy_equipment=True,
            buy_fodder=False,
        ))
        mock_config = MagicMock()
        mock_config.get.return_value = cfg

        gui = ShopBotGUI(mock_config, _make_mock_bot())

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_checkbox") as mock_checkbox, \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.pin_on_change"):
            gui.render_shop_config()

        call_kwargs = mock_checkbox.call_args
        initial_value = call_kwargs[1]["value"] if "value" in (call_kwargs[1] or {}) else call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
        # The value kwarg should contain only checked items
        assert "buy_bookmarks" in initial_value
        assert "buy_mystic_medals" not in initial_value
        assert "buy_equipment" in initial_value
        assert "buy_fodder" not in initial_value

    def test_shop_config_buy_items_change_persists(self):
        """Changing buy items checkbox should call config.update for each item."""
        from webui.app import ShopBotGUI

        mock_config = _make_mock_config()
        gui = ShopBotGUI(mock_config, _make_mock_bot())

        captured_callbacks = {}

        def capture_pin_on_change(name, onchange=None):
            captured_callbacks[name] = onchange

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_checkbox"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.pin_on_change", side_effect=capture_pin_on_change):
            gui.render_shop_config()

        # Simulate checking only bookmarks and equipment
        cb = captured_callbacks["shop_buy_items"]
        cb(["buy_bookmarks", "buy_equipment"])

        # Should have called update for all 4 items
        calls = mock_config.update.call_args_list
        update_map = {c[0][1]: c[0][2] for c in calls if c[0][0] == "shop"}
        assert update_map["buy_bookmarks"] is True
        assert update_map["buy_mystic_medals"] is False
        assert update_map["buy_equipment"] is True
        assert update_map["buy_fodder"] is False

    def test_shop_config_max_refresh_change_persists(self):
        """Changing max_refresh_count should call config.update."""
        from webui.app import ShopBotGUI

        mock_config = _make_mock_config()
        gui = ShopBotGUI(mock_config, _make_mock_bot())

        captured_callbacks = {}

        def capture_pin_on_change(name, onchange=None):
            captured_callbacks[name] = onchange

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_checkbox"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.pin_on_change", side_effect=capture_pin_on_change):
            gui.render_shop_config()

        captured_callbacks["shop_max_refresh_count"](150)
        mock_config.update.assert_any_call("shop", "max_refresh_count", 150)

    def test_shop_config_threshold_changes_persist(self):
        """Changing gold/skystone thresholds should call config.update."""
        from webui.app import ShopBotGUI

        mock_config = _make_mock_config()
        gui = ShopBotGUI(mock_config, _make_mock_bot())

        captured_callbacks = {}

        def capture_pin_on_change(name, onchange=None):
            captured_callbacks[name] = onchange

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_checkbox"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.pin_on_change", side_effect=capture_pin_on_change):
            gui.render_shop_config()

        captured_callbacks["shop_gold_threshold"](50000)
        mock_config.update.assert_any_call("shop", "gold_threshold", 50000)

        captured_callbacks["shop_skystone_threshold"](100)
        mock_config.update.assert_any_call("shop", "skystone_threshold", 100)


class TestRenderDeviceConfig:
    """Test render_device_config with running/stopped states."""

    def test_device_config_shows_inputs(self):
        """Device config should show serial input and two selects."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_input") as mock_input, \
             patch("pywebio.pin.put_select") as mock_select, \
             patch("pywebio.pin.pin_on_change"):
            gui.render_device_config()

        # 1 text input (serial)
        mock_input.assert_called_once()
        assert mock_input.call_args[0][0] == "device_serial"

        # 2 selects (screenshot_method, control_method)
        assert mock_select.call_count == 2

    def test_device_config_running_shows_warning(self):
        """When bot is running, should show warning HTML."""
        from webui.app import ShopBotGUI

        bot = _make_mock_bot()
        bot.alive = True
        gui = ShopBotGUI(_make_mock_config(), bot)

        html_calls = []

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html", side_effect=lambda h: html_calls.append(h)), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.put_select"), \
             patch("pywebio.pin.pin_on_change"):
            gui.render_device_config()

        # Should contain a warning about running state
        warning_found = any("运行中" in h for h in html_calls)
        assert warning_found, "Expected running state warning HTML"

    def test_device_config_running_disables_serial(self):
        """When bot is running, serial input should be readonly."""
        from webui.app import ShopBotGUI

        bot = _make_mock_bot()
        bot.alive = True
        gui = ShopBotGUI(_make_mock_config(), bot)

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_input") as mock_input, \
             patch("pywebio.pin.put_select"), \
             patch("pywebio.pin.pin_on_change"):
            gui.render_device_config()

        # Serial input should have readonly=True
        call_kwargs = mock_input.call_args[1] if mock_input.call_args[1] else {}
        assert call_kwargs.get("readonly") is True

    def test_device_config_running_no_pin_on_change(self):
        """When bot is running, pin_on_change should NOT be registered."""
        from webui.app import ShopBotGUI

        bot = _make_mock_bot()
        bot.alive = True
        gui = ShopBotGUI(_make_mock_config(), bot)

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.put_select"), \
             patch("pywebio.pin.pin_on_change") as mock_pin_change:
            gui.render_device_config()

        # No pin_on_change should be registered when running
        mock_pin_change.assert_not_called()

    def test_device_config_stopped_registers_callbacks(self):
        """When bot is stopped, pin_on_change should be registered for all 3 inputs."""
        from webui.app import ShopBotGUI

        bot = _make_mock_bot()
        bot.alive = False
        gui = ShopBotGUI(_make_mock_config(), bot)

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.put_select"), \
             patch("pywebio.pin.pin_on_change") as mock_pin_change:
            gui.render_device_config()

        # Should register 3 callbacks: serial, screenshot_method, control_method
        assert mock_pin_change.call_count == 3

    def test_device_config_change_persists(self):
        """Changing device config values should call config.update."""
        from webui.app import ShopBotGUI

        mock_config = _make_mock_config()
        bot = _make_mock_bot()
        bot.alive = False
        gui = ShopBotGUI(mock_config, bot)

        captured_callbacks = {}

        def capture_pin_on_change(name, onchange=None):
            captured_callbacks[name] = onchange

        with patch("pywebio.output.use_scope"), \
             patch("pywebio.output.put_html"), \
             patch("pywebio.output.put_text"), \
             patch("pywebio.output.put_buttons"), \
             patch("pywebio.pin.put_input"), \
             patch("pywebio.pin.put_select"), \
             patch("pywebio.pin.pin_on_change", side_effect=capture_pin_on_change):
            gui.render_device_config()

        captured_callbacks["device_serial"]("192.168.1.100:5555")
        mock_config.update.assert_any_call("device", "serial", "192.168.1.100:5555")

        captured_callbacks["device_screenshot_method"]("uiautomator2")
        mock_config.update.assert_any_call("device", "screenshot_method", "uiautomator2")

        captured_callbacks["device_control_method"]("uiautomator2")
        mock_config.update.assert_any_call("device", "control_method", "uiautomator2")


class _TestThemeToggle_removed:
    """Test dark/light theme toggle."""

    def test_default_theme_is_dark(self):
        """Default theme should be dark."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        # _dark_theme defaults to True (via getattr fallback)
        assert getattr(gui, "_dark_theme", True) is True

    def test_toggle_theme_switches_to_light(self):
        """Toggling from dark should switch to light."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._dark_theme = True

        with patch("pywebio.output.put_html"):
            gui._toggle_theme()

        assert gui._dark_theme is False

    def test_toggle_theme_switches_back_to_dark(self):
        """Toggling from light should switch back to dark."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._dark_theme = False

        with patch("pywebio.output.put_html"):
            gui._toggle_theme()

        assert gui._dark_theme is True

    def test_toggle_theme_injects_css(self):
        """Toggling theme should inject CSS via put_html."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())
        gui._dark_theme = True

        with patch("pywebio.output.put_html") as mock_html:
            gui._toggle_theme()

        # Should inject light theme CSS (since we toggled from dark)
        mock_html.assert_called_once()
        css = mock_html.call_args[0][0]
        assert "#ffffff" in css  # light background

    def test_render_theme_toggle_shows_button(self):
        """_render_theme_toggle should render a toggle button."""
        from webui.app import ShopBotGUI

        gui = ShopBotGUI(_make_mock_config(), _make_mock_bot())

        with patch("pywebio.output.put_buttons") as mock_buttons:
            gui._render_theme_toggle()

        mock_buttons.assert_called_once()
        btn_config = mock_buttons.call_args[0][0][0]
        assert btn_config["value"] == "toggle_theme"
