"""
UI 组件

BinarySwitchButton（启停双态切换）、RichLog（实时日志）、
资源卡片等可复用 Web UI 组件。

这些组件是对 PyWebIO 原语的薄封装，从 app.py 中的内联实现
提取为独立的可复用函数/类。
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Resource Card
# ---------------------------------------------------------------------------

def put_resource_card(label: str, value, color: str = "#89b4fa") -> str:
    """生成单个资源统计卡片的 HTML 字符串。

    参考 Alas 的 ``put_resource_card`` 模式，返回一个带标签和数值的
    卡片 HTML 片段，可嵌入 flex 容器中水平排列。

    Args:
        label: 卡片标签文字（如 "刷新次数"）
        value: 显示的数值（会被转为字符串）
        color: 数值文字的 CSS 颜色，默认蓝色

    Returns:
        HTML 字符串，一个圆角卡片 div。
    """
    return (
        f'<div style="flex:1;min-width:120px;background:#313244;'
        f'border-radius:8px;padding:14px 16px;text-align:center;'
        f'margin:0 6px;">'
        f'<div style="font-size:12px;color:#a6adc8;">{label}</div>'
        f'<div style="font-size:24px;font-weight:bold;color:{color};'
        f'margin-top:4px;">{value}</div></div>'
    )


def put_resource_cards(cards: list[tuple[str, object, str]]) -> str:
    """生成水平排列的资源卡片面板 HTML。

    Args:
        cards: 列表，每项为 ``(label, value, color)`` 三元组。

    Returns:
        包含所有卡片的 flex 容器 HTML 字符串。
    """
    inner = "".join(put_resource_card(l, v, c) for l, v, c in cards)
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">'
        f'{inner}</div>'
    )


# ---------------------------------------------------------------------------
# BinarySwitchButton
# ---------------------------------------------------------------------------

class BinarySwitchButton:
    """启动/停止双态切换按钮组件。

    参考 Alas 的 BinarySwitchButton 模式：
    - 运行中 → 红色 "⏹ 停止" 按钮
    - 已停止 → 绿色 "▶ 启动" 按钮

    使用方式::

        btn = BinarySwitchButton(scope="control-panel")
        btn.render(is_running=False, onclick=my_callback)
    """

    def __init__(self, scope: str = "control-panel"):
        """
        Args:
            scope: PyWebIO scope 名称，按钮将渲染到此 scope 中。
        """
        self.scope = scope

    def render(self, is_running: bool, onclick: Callable[[str], None]) -> None:
        """渲染按钮到指定 scope。

        Args:
            is_running: 当前是否运行中。
            onclick: 点击回调，接收 ``"start"`` 或 ``"stop"`` 字符串。
        """
        from pywebio.output import put_buttons, use_scope

        with use_scope(self.scope, clear=True):
            if is_running:
                put_buttons(
                    [{"label": "⏹ 停止", "value": "stop", "color": "danger"}],
                    onclick=onclick,
                ).style("margin:10px 0;")
            else:
                put_buttons(
                    [{"label": "▶ 启动", "value": "start", "color": "success"}],
                    onclick=onclick,
                ).style("margin:10px 0;")


# ---------------------------------------------------------------------------
# RichLog
# ---------------------------------------------------------------------------

class RichLog:
    """实时滚动日志组件，支持 ScrollON/ScrollOFF 切换。

    参考 Alas 的 RichLog 组件模式：
    - 可滚动的日志区域
    - ScrollON/ScrollOFF 切换按钮控制自动滚动

    使用方式::

        rich_log = RichLog(scope_toggle="log-scroll-toggle",
                           scope_lines="log-lines")
        rich_log.render_toggle()
        rich_log.append_line("hello world")
    """

    def __init__(
        self,
        scope_toggle: str = "log-scroll-toggle",
        scope_lines: str = "log-lines",
    ):
        """
        Args:
            scope_toggle: 滚动切换按钮的 scope 名称。
            scope_lines: 日志行输出的 scope 名称。
        """
        self.scope_toggle = scope_toggle
        self.scope_lines = scope_lines
        self.scroll_enabled: bool = True

    def render_toggle(self) -> None:
        """渲染 ScrollON/ScrollOFF 切换按钮。"""
        from pywebio.output import put_buttons, use_scope

        label = "ScrollON" if self.scroll_enabled else "ScrollOFF"
        color = "success" if self.scroll_enabled else "secondary"
        with use_scope(self.scope_toggle, clear=True):
            put_buttons(
                [{"label": label, "value": "toggle", "color": color}],
                onclick=lambda _: self.toggle_scroll(),
            ).style("margin:4px 0;")

    def toggle_scroll(self) -> None:
        """切换自动滚动状态并重新渲染按钮。"""
        self.scroll_enabled = not self.scroll_enabled
        self.render_toggle()

    def append_line(self, text: str) -> None:
        """向日志区域追加一行文本。

        仅在 ``scroll_enabled`` 为 True 时渲染。

        Args:
            text: 要追加的日志文本。
        """
        if not self.scroll_enabled:
            return
        from pywebio.output import put_text, use_scope

        with use_scope(self.scope_lines):
            put_text(text).style(
                "font-family:monospace;font-size:12px;"
                "margin:1px 0;padding:0;color:#cdd6f4;"
            )
