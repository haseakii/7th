"""
Unit tests for webui/widgets.py – reusable UI components.

Covers:
- put_resource_card: HTML generation for stat cards
- put_resource_cards: multi-card panel HTML
- BinarySwitchButton: render dispatches correct button state
- RichLog: scroll toggle state management and append gating
"""

import sys
import pathlib
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure 7th package root is on sys.path
_SEVENTH = str(pathlib.Path(__file__).resolve().parent.parent)
if _SEVENTH not in sys.path:
    sys.path.insert(0, _SEVENTH)


# ---------------------------------------------------------------------------
# put_resource_card tests
# ---------------------------------------------------------------------------

class TestPutResourceCard:
    def test_contains_label(self):
        from webui.widgets import put_resource_card
        html = put_resource_card("刷新次数", 42, "#89b4fa")
        assert "刷新次数" in html

    def test_contains_value(self):
        from webui.widgets import put_resource_card
        html = put_resource_card("书签", 7, "#a6e3a1")
        assert ">7<" in html

    def test_contains_color(self):
        from webui.widgets import put_resource_card
        html = put_resource_card("test", 0, "#f38ba8")
        assert "#f38ba8" in html

    def test_default_color(self):
        from webui.widgets import put_resource_card
        html = put_resource_card("test", 0)
        assert "#89b4fa" in html

    def test_string_value(self):
        from webui.widgets import put_resource_card
        html = put_resource_card("状态", "运行中", "#cba6f7")
        assert "运行中" in html

    def test_zero_value(self):
        from webui.widgets import put_resource_card
        html = put_resource_card("count", 0)
        assert ">0<" in html


class TestPutResourceCards:
    def test_wraps_in_flex_container(self):
        from webui.widgets import put_resource_cards
        html = put_resource_cards([("A", 1, "#fff"), ("B", 2, "#000")])
        assert "display:flex" in html
        assert "flex-wrap:wrap" in html

    def test_contains_all_cards(self):
        from webui.widgets import put_resource_cards
        cards = [
            ("刷新次数", 10, "#89b4fa"),
            ("书签购买", 3, "#a6e3a1"),
            ("天空石", 30, "#f38ba8"),
        ]
        html = put_resource_cards(cards)
        assert "刷新次数" in html
        assert "书签购买" in html
        assert "天空石" in html
        assert ">10<" in html
        assert ">3<" in html
        assert ">30<" in html

    def test_empty_cards(self):
        from webui.widgets import put_resource_cards
        html = put_resource_cards([])
        assert "display:flex" in html


# ---------------------------------------------------------------------------
# BinarySwitchButton tests
# ---------------------------------------------------------------------------

class TestBinarySwitchButton:
    def test_default_scope(self):
        from webui.widgets import BinarySwitchButton
        btn = BinarySwitchButton()
        assert btn.scope == "control-panel"

    def test_custom_scope(self):
        from webui.widgets import BinarySwitchButton
        btn = BinarySwitchButton(scope="my-scope")
        assert btn.scope == "my-scope"

    def test_render_running_shows_stop(self):
        from webui.widgets import BinarySwitchButton

        btn = BinarySwitchButton(scope="test-scope")
        callback = MagicMock()

        mock_use_scope = MagicMock()
        mock_use_scope.return_value.__enter__ = MagicMock()
        mock_use_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_put_buttons = MagicMock()
        mock_put_buttons.return_value.style = MagicMock()

        with patch("pywebio.output.use_scope", mock_use_scope), \
             patch("pywebio.output.put_buttons", mock_put_buttons):
            btn.render(is_running=True, onclick=callback)

        # Should render stop button
        args = mock_put_buttons.call_args
        buttons = args[0][0]
        assert buttons[0]["value"] == "stop"
        assert buttons[0]["color"] == "danger"
        assert "停止" in buttons[0]["label"]

    def test_render_stopped_shows_start(self):
        from webui.widgets import BinarySwitchButton

        btn = BinarySwitchButton(scope="test-scope")
        callback = MagicMock()

        mock_use_scope = MagicMock()
        mock_use_scope.return_value.__enter__ = MagicMock()
        mock_use_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_put_buttons = MagicMock()
        mock_put_buttons.return_value.style = MagicMock()

        with patch("pywebio.output.use_scope", mock_use_scope), \
             patch("pywebio.output.put_buttons", mock_put_buttons):
            btn.render(is_running=False, onclick=callback)

        args = mock_put_buttons.call_args
        buttons = args[0][0]
        assert buttons[0]["value"] == "start"
        assert buttons[0]["color"] == "success"
        assert "启动" in buttons[0]["label"]


# ---------------------------------------------------------------------------
# RichLog tests
# ---------------------------------------------------------------------------

class TestRichLog:
    def test_default_scopes(self):
        from webui.widgets import RichLog
        rl = RichLog()
        assert rl.scope_toggle == "log-scroll-toggle"
        assert rl.scope_lines == "log-lines"
        assert rl.scroll_enabled is True

    def test_custom_scopes(self):
        from webui.widgets import RichLog
        rl = RichLog(scope_toggle="t", scope_lines="l")
        assert rl.scope_toggle == "t"
        assert rl.scope_lines == "l"

    def test_toggle_scroll_flips_state(self):
        from webui.widgets import RichLog
        rl = RichLog()
        rl.render_toggle = MagicMock()  # avoid PyWebIO calls

        assert rl.scroll_enabled is True
        rl.toggle_scroll()
        assert rl.scroll_enabled is False
        rl.toggle_scroll()
        assert rl.scroll_enabled is True

    def test_toggle_scroll_calls_render(self):
        from webui.widgets import RichLog
        rl = RichLog()
        rl.render_toggle = MagicMock()

        rl.toggle_scroll()
        rl.render_toggle.assert_called_once()

    def test_append_line_skipped_when_scroll_off(self):
        from webui.widgets import RichLog
        rl = RichLog()
        rl.scroll_enabled = False

        # Should not attempt any PyWebIO calls
        with patch("pywebio.output.use_scope") as mock_scope, \
             patch("pywebio.output.put_text") as mock_text:
            rl.append_line("test line")
            mock_scope.assert_not_called()
            mock_text.assert_not_called()

    def test_append_line_renders_when_scroll_on(self):
        from webui.widgets import RichLog
        rl = RichLog()
        rl.scroll_enabled = True

        mock_use_scope = MagicMock()
        mock_use_scope.return_value.__enter__ = MagicMock()
        mock_use_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_put_text = MagicMock()
        mock_put_text.return_value.style = MagicMock()

        with patch("pywebio.output.use_scope", mock_use_scope), \
             patch("pywebio.output.put_text", mock_put_text):
            rl.append_line("hello")

        mock_put_text.assert_called_once_with("hello")

    def test_render_toggle_shows_scroll_on(self):
        from webui.widgets import RichLog
        rl = RichLog()
        rl.scroll_enabled = True

        mock_use_scope = MagicMock()
        mock_use_scope.return_value.__enter__ = MagicMock()
        mock_use_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_put_buttons = MagicMock()
        mock_put_buttons.return_value.style = MagicMock()

        with patch("pywebio.output.use_scope", mock_use_scope), \
             patch("pywebio.output.put_buttons", mock_put_buttons):
            rl.render_toggle()

        args = mock_put_buttons.call_args
        buttons = args[0][0]
        assert buttons[0]["label"] == "ScrollON"
        assert buttons[0]["color"] == "success"

    def test_render_toggle_shows_scroll_off(self):
        from webui.widgets import RichLog
        rl = RichLog()
        rl.scroll_enabled = False

        mock_use_scope = MagicMock()
        mock_use_scope.return_value.__enter__ = MagicMock()
        mock_use_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_put_buttons = MagicMock()
        mock_put_buttons.return_value.style = MagicMock()

        with patch("pywebio.output.use_scope", mock_use_scope), \
             patch("pywebio.output.put_buttons", mock_put_buttons):
            rl.render_toggle()

        args = mock_put_buttons.call_args
        buttons = args[0][0]
        assert buttons[0]["label"] == "ScrollOFF"
        assert buttons[0]["color"] == "secondary"
