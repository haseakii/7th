"""
E7GUI — 第七史诗 ALAS 风格 Web 管理界面

由 args.json + menu.json 驱动配置页面渲染，
提供 4 区布局（header/aside/menu/content）和任务启停控制。
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List

from pywebio import config as webconfig
from pywebio.output import (
    put_button,
    put_buttons,
    put_collapse,
    put_html,
    put_scope,
    put_text,
    use_scope,
)
from pywebio.pin import pin
from pywebio.session import register_thread, run_js, set_env

from log import logger
from module.config.config import E7Config
from module.config.deep import deep_iter
from module.webui.base import Frame
from module.webui.setting import State as AppState
from module.webui.utils import add_css, filepath_css
from module.webui.widgets import put_output


class _WebUILogHandler(logging.Handler):
    """线程安全日志缓冲区，供 UI 轮询刷新。"""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        ))
        self._buffer: List[str] = []
        self._lock = threading.Lock()

    def emit(self, record):
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(msg)
        except Exception:
            self.handleError(record)

    def drain(self) -> List[str]:
        with self._lock:
            lines = self._buffer[:]
            self._buffer.clear()
        return lines


class E7GUI(Frame):
    """E7 Shop Bot 管理界面。"""

    theme = "dark"

    def __init__(self) -> None:
        super().__init__()
        self.config_name = "default"
        self.config = E7Config(config_name=self.config_name)

        # 加载菜单和参数定义
        args_path = Path(__file__).resolve().parent.parent / "config" / "argument"
        with open(args_path / "menu.json", encoding="utf-8") as f:
            self.MENU: Dict = json.load(f)
        with open(args_path / "args.json", encoding="utf-8") as f:
            self.ARGS: Dict = json.load(f)

        self.rendered_cache = []

        # 运行状态（使用 State 单例，页面刷新后不丢失）
        self._bot = AppState.bot
        self._scroll_enabled = True
        self._last_stats = AppState.last_stats

    def initial(self) -> None:
        """初始化页面：布局渲染 → CSS → 菜单构建。"""
        self._show()
        add_css(filepath_css("dark.css"))
        self.set_aside()
        self.set_menu()

    # ── Aside ──────────────────────────────────────────────────────

    @use_scope("aside", clear=True)
    def set_aside(self) -> None:
        """渲染侧边栏导航。"""
        put_html(
            '<div class="aside-title">E7 Shop Bot</div>'
        )

        # 总览
        put_buttons(
            [
                {"label": "📊 总览", "value": "overview", "color": "aside"},
            ],
            onclick=[self.set_overview],
        )

        # 配置实例
        put_scope("aside_instance", [put_scope("inst-default")])
        self._render_aside_instance("default")

    @use_scope("aside_instance")
    def _render_aside_instance(self, name: str) -> None:
        """渲染单个配置实例按钮。"""
        with use_scope(f"inst-{name}", clear=True):
            put_buttons(
                [
                    {"label": name, "value": name, "color": "aside"},
                ],
                onclick=self.set_menu,
            )

    # ── Menu ───────────────────────────────────────────────────────

    @use_scope("menu", clear=True)
    def set_menu(self, task: str = "") -> None:
        """根据 menu.json 渲染可折叠任务菜单。"""
        self.init_aside(name=task or "default")
        self.task_handler.stop()
        self.stop_overview_updates()

        # 总览按钮
        put_buttons(
            [
                {"label": "📊 总览", "value": "overview", "color": "menu"},
            ],
            onclick=[self.set_overview],
        ).style("--menu-overview--")

        # 可折叠任务区
        for menu_key, menu_data in self.MENU.items():
            if menu_data.get("menu") != "collapse":
                continue
            tasks = menu_data.get("tasks", [])
            content = []
            for t in tasks:
                parts = t.split(".")
                label = parts[-1] if len(parts) >= 2 else t
                content.append(
                    put_buttons(
                        [{"label": label, "value": t, "color": "menu"}],
                        onclick=self.set_group,
                    ).style(f"--menu-{t}--")
                )
            put_collapse(
                title=put_text(menu_key).style("text-transform: none; font-weight: 600;"),
                content=content,
            )

        # 默认选中总览
        self.set_overview()

    # ── Group (配置表单) ───────────────────────────────────────────
    # ALAS 风格：pin 命名 {task}_{group}_{arg}

    @use_scope("content", clear=True)
    def set_group(self, task: str) -> None:
        """根据 args.json 渲染配置表单。"""
        self.stop_overview_updates()
        self.init_menu(name=task)
        self.set_title(task)

        put_scope("_groups", [put_scope("groups")])

        task_data = self.ARGS.get(task, {})
        for group, arg_dict in deep_iter(task_data, depth=1):
            if not isinstance(arg_dict, dict):
                continue
            self._render_group(group, arg_dict, task)

        # 加载已保存的配置值
        self._load_config_to_pin(task)

        # 保存 / 重置按钮
        put_scope("form_actions")
        with use_scope("form_actions"):
            put_button("💾 保存配置", onclick=self._save_config, color="success")
            put_text(" ").style("display:inline; margin:0 8px;")
            put_button("↻ 重置默认", onclick=lambda: self.set_group(task), color="warning").style("margin-left: 8px;")

    @use_scope("groups")
    def _render_group(self, group, arg_dict, task) -> None:
        """渲染单个配置分组（ALAS 风格）。"""
        group_name = group[0]

        output_list = []
        for arg, arg_data in deep_iter(arg_dict, depth=1):
            if not isinstance(arg_data, dict) or "type" not in arg_data:
                continue
            if arg[0] == "_info":
                continue

            kwargs = dict(arg_data)
            arg_name = arg[0]
            kwargs["widget_type"] = kwargs.pop("type")
            kwargs["name"] = f"{task}_{group_name}_{arg_name}"
            kwargs["title"] = arg_data.get("display", arg_name)
            kwargs["value"] = arg_data.get("value", "")
            kwargs["options"] = kwargs.pop("option", [])

            o = put_output(kwargs)
            if o is not None:
                o.spec["scope"] = f"#pywebio-scope-group_{group_name}"
                output_list.append(o)

        if not output_list:
            return

        group_info = arg_dict.get("_info", {})
        group_display = group_info.get("name", group_name)
        with use_scope(f"group_{group_name}"):
            put_text(group_display)
            for output in output_list:
                output.show()

    # ── 配置持久化 ──────────────────────────────────────────────────

    def _save_config(self) -> None:
        """将当前 pin 值保存到 config JSON。"""
        try:
            for task_name in ("SecretShop", "Device", "Webui"):
                task_data = self.ARGS.get(task_name, {})
                for group_name, group_data in deep_iter(task_data, depth=1):
                    if not isinstance(group_data, dict):
                        continue
                    for arg_name, arg_def in deep_iter(group_data, depth=1):
                        if not isinstance(arg_def, dict) or "type" not in arg_def:
                            continue
                        pin_name = f"{task_name}_{group_name[0]}_{arg_name[0]}"
                        path = f"{task_name}.{group_name[0]}.{arg_name[0]}"
                        raw = pin[pin_name]
                        # 类型转换
                        if arg_def["type"] == "checkbox":
                            value = bool(raw)
                        elif arg_def["type"] == "input":
                            if isinstance(raw, str):
                                try:
                                    value = int(raw) if raw.isdigit() else float(raw)
                                except (ValueError, TypeError):
                                    value = raw
                            else:
                                value = raw
                        else:
                            value = raw
                        self.config.set(path, value)
            self.config.update()
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def _load_config_to_pin(self, task: str) -> None:
        """从已保存的 JSON 配置加载值到 pin。"""
        task_data = self.ARGS.get(task, {})
        for group_name, group_data in deep_iter(task_data, depth=1):
            if not isinstance(group_data, dict):
                continue
            for arg_name, arg_def in deep_iter(group_data, depth=1):
                if not isinstance(arg_def, dict) or "type" not in arg_def:
                    continue
                path = f"{task}.{group_name[0]}.{arg_name[0]}"
                saved = self.config.get(path)
                if saved is not None:
                    pin_name = f"{task}_{group_name[0]}_{arg_name[0]}"
                    try:
                        pin[pin_name] = saved
                    except Exception:
                        pass

    # ── Overview (总览) ────────────────────────────────────────────

    def stop_overview_updates(self) -> None:
        """停止所有后台更新线程。"""
        AppState.overview_active = False

    # ── 日志滚动切换 ──────────────────────────────────────────────────

    def _render_scroll_toggle(self) -> None:
        """渲染日志自动滚动切换按钮。"""
        from pywebio.output import put_buttons, use_scope
        lbl = "⏷ 自动滚动: 开" if self._scroll_enabled else "⏷ 自动滚动: 关"
        clr = "success" if self._scroll_enabled else "secondary"
        with use_scope("log_scroll_toggle", clear=True):
            put_buttons(
                [{"label": lbl, "value": "toggle", "color": clr}],
                onclick=lambda _: self._toggle_scroll(),
            ).style("margin: 4px 0;")

    def _toggle_scroll(self) -> None:
        """切换自动滚动。"""
        self._scroll_enabled = not self._scroll_enabled
        self._render_scroll_toggle()

    @use_scope("content", clear=True)
    def set_overview(self) -> None:
        """渲染总览仪表盘。"""
        self.stop_overview_updates()
        self.init_menu(name="overview")
        self.page = "overview"
        AppState.overview_active = True

        # 顶部区域：标题 + 启停按钮
        put_scope("scheduler_bar")
        with use_scope("scheduler_bar"):
            put_scope("scheduler_bar_left", [
                put_text("控制面板").style("font-size: 1.25rem; margin: auto .5rem auto;"),
            ])
            put_scope("controls", [
                put_button("▶ 启动", onclick=self._on_start, color="success"),
                put_button("⏹ 停止", onclick=self._on_stop, color="danger").style("margin-left: 8px;"),
                put_button("⏻ 停止服务", onclick=self._on_shutdown_server, color="secondary").style("margin-left: 8px;"),
            ])

        # 状态卡片（使用持久化的 last_stats，避免刷新归零）
        stats = self._last_stats
        put_scope("status_cards")
        with use_scope("status_cards"):
            put_html(
                '<div class="status-grid">'
                '<div class="status-card">'
                '<div class="status-value" id="stat-runs">%s</div>'
                '<div class="status-label">刷新次数</div></div>'
                '<div class="status-card">'
                '<div class="status-value" id="stat-bookmarks">%s</div>'
                '<div class="status-label">书签获得</div></div>'
                '<div class="status-card">'
                '<div class="status-value" id="stat-medals">%s</div>'
                '<div class="status-label">神秘奖章</div></div>'
                '<div class="status-card">'
                '<div class="status-value" id="stat-skystone">%s</div>'
                '<div class="status-label">天空石剩余</div></div>'
                "</div>" % (
                    stats["total_refreshes"],
                    stats["bookmarks_bought"],
                    stats["mystic_medals_bought"],
                    stats["skystone_remaining"],
                )
            )

        # 日志区域 — 使用纯 HTML div 而非 put_scope，完全控制尺寸与滚动
        put_scope("log_bar")
        with use_scope("log_bar"):
            put_text("日志").style("font-size: 1.25rem; margin: auto .5rem auto;")

        put_scope("log_scroll_toggle")
        self._render_scroll_toggle()

        put_html(
            '<div id="log-lines" style="'
            'background:#11111b;border-radius:8px;padding:8px 12px;'
            'height:350px;max-height:350px;overflow-y:auto;overflow-x:hidden;'
            'font-family:Menlo,Consolas,Courier New,monospace;font-size:12px;'
            'color:#cdd6f4;margin-top:8px;line-height:1.5;white-space:nowrap;'
            '">&nbsp;</div>'
        )

        # 每个 updater 运行在独立的已注册线程中（v1.1 已验证的方式）
        for fn in (self._stats_updater, self._log_updater):
            t = threading.Thread(target=fn, daemon=True)
            register_thread(t)
            t.start()

    # ── 控制回调 ───────────────────────────────────────────────────

    def _on_start(self) -> None:
        """启动 ShopBot 后台任务。"""
        if self._bot and self._bot.alive:
            logger.info("ShopBot 已在运行")
            return

        from shop_bot import ShopBot
        self._bot = ShopBot(config=self.config)
        self._bot._stop_event.clear()
        self._bot.start()
        AppState.bot = self._bot
        logger.info("▶ ShopBot 已启动")

    def _on_stop(self) -> None:
        """停止 ShopBot 后台任务。"""
        if self._bot and self._bot.alive:
            self._bot.stop()
            AppState.bot = None
            logger.info("⏹ ShopBot 已停止")

    def _on_shutdown_server(self) -> None:
        """停止整个 Web 服务。"""
        from pywebio.session import run_js
        logger.info("正在停止 Web 服务...")
        run_js("fetch('/api/shutdown', {method:'POST'})")

    # ── 后台刷新线程（v1.1 已验证模式） ──────────────────────────

    def _stats_updater(self) -> None:
        """独立线程：轮询更新状态卡片。"""
        while AppState.overview_active:
            time.sleep(2)
            if not AppState.overview_active:
                break
            try:
                bot = AppState.bot or self._bot
                if bot and bot.alive:
                    stats = bot.get_statistics()
                    if stats:
                        AppState.last_stats.update(
                            total_refreshes=stats.total_refreshes,
                            bookmarks_bought=stats.bookmarks_bought,
                            mystic_medals_bought=stats.mystic_medals_bought,
                            skystone_remaining=stats.skystone_remaining,
                        )
                        run_js(
                            "document.getElementById('stat-runs').textContent = v;",
                            v=str(stats.total_refreshes),
                        )
                        run_js(
                            "document.getElementById('stat-bookmarks').textContent = v;",
                            v=str(stats.bookmarks_bought),
                        )
                        run_js(
                            "document.getElementById('stat-medals').textContent = v;",
                            v=str(stats.mystic_medals_bought),
                        )
                        run_js(
                            "document.getElementById('stat-skystone').textContent = v;",
                            v=str(stats.skystone_remaining),
                        )
            except Exception:
                pass

    def _log_updater(self) -> None:
        """独立线程：轮询日志缓冲区，通过 run_js 直接追加 DOM。"""
        handler = _WebUILogHandler()
        handler.setLevel(logging.DEBUG)
        target = logging.getLogger("ShopBot")
        target.addHandler(handler)
        MAX_LINES = 500
        try:
            while AppState.overview_active:
                time.sleep(0.4)
                if not AppState.overview_active:
                    break
                lines = handler.drain()
                if not lines:
                    continue
                if not self._scroll_enabled:
                    continue
                try:
                    safe = []
                    for l in lines:
                        l = (l.replace("&", "&amp;")
                              .replace("<", "&lt;")
                              .replace(">", "&gt;")
                              .replace('"', "&quot;")
                              .replace("'", "&#39;"))
                        safe.append(l)
                    html = "".join(f'<div class="ll">{l}</div>' for l in safe)
                    run_js(
                        """var c=$("#log-lines");
                           c.append(v);
                           var max=500;
                           var n=c.children().length;
                           if(n>max)c.children(":lt("+(n-max)+")").remove();
                           c.scrollTop(c.prop("scrollHeight"));""",
                        v=html,
                    )
                except Exception:
                    pass
        finally:
            target.removeHandler(handler)


# ── 页面入口 ──────────────────────────────────────────────────────
def app():
    """PyWebIO 页面入口。"""
    webconfig(title="E7 Shop Bot", theme="dark")
    set_env(output_max_width="100%")
    gui = E7GUI()
    gui.initial()

