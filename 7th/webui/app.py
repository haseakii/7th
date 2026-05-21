"""
Web UI 主应用

基于 PyWebIO + tornado 的浏览器管理界面。
参考 Alas 的 scope 布局方式：用 put_scope 创建 aside / content 区域，
通过 CSS 选择器 #pywebio-scope-{name} 控制布局。
"""

import logging
import os
import base64
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from log import logger

if TYPE_CHECKING:
    from shop_bot import RunStatistics

PAGE_OVERVIEW = "overview"
PAGE_SHOP_CONFIG = "shop_config"
PAGE_DEVICE_CONFIG = "device_config"
PAGE_TEMPLATES = "templates"

NAV_ITEMS = [
    ("📊 总览", PAGE_OVERVIEW),
    ("🛒 商店配置", PAGE_SHOP_CONFIG),
    ("📱 设备配置", PAGE_DEVICE_CONFIG),
    ("🖼 模板管理", PAGE_TEMPLATES),
]

# ── CSS ──────────────────────────────────────────────────────────────
# 利用 PyWebIO 自动生成的 #pywebio-scope-xxx 选择器做布局
_CSS = """
<style>
/* === reset === */
body { margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont,
       "Segoe UI", Roboto, "Helvetica Neue", sans-serif; }
footer, .pywebio-footer { display:none !important; }
#output-container, .webio-outputarea {
    max-width:100% !important; padding:0 !important; }
.pywebio { padding:0; min-height:unset; }

/* === root grid: full viewport === */
#pywebio-scope-root {
    height: 100vh;
    display: flex;
}

/* === aside (sidebar) === */
#pywebio-scope-aside {
    width: 200px;
    min-width: 200px;
    background: #181825;
    border-right: 1px solid #313244;
    padding: 0;
    overflow-y: auto;
    flex-shrink: 0;
}
#pywebio-scope-aside .btn {
    display: block; width:100%; text-align:left; border:none; border-radius:0;
    background: transparent; color:#a6adc8; padding:10px 20px;
    font-size:14px; transition: all .15s;
}
#pywebio-scope-aside .btn:hover { background:#313244; color:#cdd6f4; }
#pywebio-scope-aside .btn.btn-aside-active {
    background:#313244; color:#89b4fa; font-weight:bold;
    border-left:3px solid #89b4fa;
}

/* === content === */
#pywebio-scope-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px 32px;
    background: #1e1e2e;
    color: #cdd6f4;
}

/* === stat cards === */
.stat-cards { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:16px; }
.stat-card { flex:1; min-width:130px; background:#313244; border-radius:8px;
             padding:14px 16px; text-align:center; }
.stat-card .lbl { font-size:12px; color:#a6adc8; }
.stat-card .val { font-size:24px; font-weight:bold; margin-top:4px; }

/* === group header === */
.ghdr { margin:18px 0 8px; font-size:16px; font-weight:bold;
        border-bottom:1px solid #45475a; padding-bottom:4px; color:#cdd6f4; }

/* === log area === */
#pywebio-scope-log-lines {
    background:#11111b; border-radius:8px; padding:10px;
    height:350px; overflow-y:auto;
    font-family: Menlo, Consolas, "Courier New", monospace;
    font-size:12px; color:#cdd6f4;
}

/* === form dark theme === */
.form-control, .form-select, .custom-select, select.form-control {
    background:#313244 !important; color:#cdd6f4 !important;
    border-color:#45475a !important; border-radius:4px !important; }
.form-control:focus, .form-select:focus {
    border-color:#89b4fa !important;
    box-shadow:0 0 0 .2rem rgba(137,180,250,.25) !important; }
label, .form-check-label { color:#cdd6f4 !important; }
.form-check-input:checked {
    background-color:#89b4fa !important; border-color:#89b4fa !important; }
.btn { border-radius:6px !important; }

/* === sidebar title === */
.sb-title { color:#89b4fa; font-size:18px; font-weight:bold;
            padding:14px 20px; border-bottom:1px solid #313244; }

/* === warning banner === */
.warn-banner { background:#f38ba8; color:#1e1e2e; padding:8px 14px;
               border-radius:6px; margin-bottom:12px; font-weight:bold; }

/* === template cards === */
.tpl-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
            gap:16px; margin-top:12px; }
.tpl-card { background:#313244; border-radius:8px; padding:16px; }
.tpl-card .tpl-name { font-size:15px; font-weight:bold; color:#89b4fa; margin-bottom:8px; }
.tpl-card img { max-width:100%; border-radius:4px; background:#11111b;
                min-height:60px; object-fit:contain; }
.tpl-card .tpl-info { font-size:12px; color:#a6adc8; margin-top:6px; }
.tpl-card .tpl-coords { font-family:monospace; font-size:11px; color:#f9e2af;
                         background:#1e1e2e; padding:4px 8px; border-radius:4px;
                         margin-top:4px; word-break:break-all; }
.tpl-upload-zone { border:2px dashed #45475a; border-radius:8px; padding:20px;
                   text-align:center; color:#a6adc8; margin-top:12px; }
</style>
"""


class ShopBotGUI:
    """PyWebIO Web UI — 参考 Alas 的 scope 布局。"""

    def __init__(self, config, bot):
        self.config = config
        self.bot = bot
        self._current_page = PAGE_OVERVIEW
        self._overview_active = False
        self._scroll_enabled = True

    def start_server(self, port: int = 8080) -> None:
        try:
            from pywebio.platform.tornado import start_server as tornado_start
        except ImportError:
            logger.warning("pywebio 未安装，无法启动 Web UI")
            return
        logger.info(f"正在启动 Web UI，监听 localhost:{port} ...")
        try:
            tornado_start(self._main_page, port=port, host="localhost",
                          debug=False, auto_open_webbrowser=False)
        except OSError as e:
            logger.warning(f"Web UI 启动失败（端口 {port} 可能被占用）: {e}")
        except Exception as e:
            logger.warning(f"Web UI 启动失败: {e}")

    # ── layout ───────────────────────────────────────────────────────
    def _main_page(self) -> None:
        from pywebio.output import put_html, put_scope, use_scope
        from pywebio.session import set_env

        set_env(title="ShopBot 管理界面", output_animation=False)
        put_html(_CSS)

        # Alas 风格: root 包含 aside + content
        # PyWebIO 会自动生成 #pywebio-scope-root, #pywebio-scope-aside, #pywebio-scope-content
        put_scope("root", [
            put_scope("aside"),
            put_scope("content"),
        ])

        self._render_sidebar()
        self._navigate_to(PAGE_OVERVIEW)

    def _render_sidebar(self) -> None:
        from pywebio.output import put_html, put_buttons, use_scope
        from pywebio.session import run_js

        with use_scope("aside", clear=True):
            put_html('<div class="sb-title">🤖 ShopBot</div>')
            for label, pid in NAV_ITEMS:
                put_buttons(
                    [{"label": label, "value": pid, "color": "secondary"}],
                    onclick=[lambda p=pid: self._navigate_to(p)],
                )

    def _navigate_to(self, page_id: str) -> None:
        from pywebio.output import clear
        from pywebio.session import run_js

        if self._current_page == PAGE_OVERVIEW and page_id != PAGE_OVERVIEW:
            self.stop_overview_updates()

        self._current_page = page_id
        clear("content")

        # 高亮当前侧边栏按钮
        run_js("""
            document.querySelectorAll('#pywebio-scope-aside .btn')
                .forEach(b => b.classList.remove('btn-aside-active'));
        """)

        if page_id == PAGE_OVERVIEW:
            self.render_overview()
        elif page_id == PAGE_SHOP_CONFIG:
            self.render_shop_config()
        elif page_id == PAGE_DEVICE_CONFIG:
            self.render_device_config()
        elif page_id == PAGE_TEMPLATES:
            self.render_template_manager()

    # ── overview ─────────────────────────────────────────────────────
    def render_overview(self) -> None:
        from pywebio.output import (put_html, put_scope, put_buttons,
                                     put_text, use_scope)
        from pywebio.session import register_thread

        with use_scope("content"):
            put_html('<h2 style="margin-top:0;color:#cdd6f4;">📊 总览</h2>')
            put_scope("stats-panel")
            self._refresh_stats_panel()
            put_scope("control-panel")
            self._refresh_control_button()
            put_html('<div class="ghdr">📜 实时日志</div>')
            put_scope("log-scroll-toggle")
            self._scroll_enabled = True
            self._render_scroll_toggle()
            put_scope("log-lines")

        self._overview_active = True
        for fn in (self._stats_updater, self._control_updater, self._log_updater):
            t = threading.Thread(target=fn, daemon=True)
            register_thread(t)
            t.start()

    @staticmethod
    def _build_stats_html(stats) -> str:
        cards = [
            ("刷新次数", stats.total_refreshes, "#89b4fa"),
            ("书签购买", stats.bookmarks_bought, "#a6e3a1"),
            ("神秘奖章", stats.mystic_medals_bought, "#cba6f7"),
            ("天空石消耗", stats.skystone_spent, "#f38ba8"),
            ("天空石余量", stats.skystone_remaining, "#f9e2af"),
        ]
        parts = []
        for lbl, val, clr in cards:
            parts.append(
                f'<div class="stat-card"><div class="lbl">{lbl}</div>'
                f'<div class="val" style="color:{clr};">{val}</div></div>')
        return f'<div class="stat-cards">{"".join(parts)}</div>'

    def _refresh_stats_panel(self) -> None:
        from pywebio.output import put_html, use_scope
        stats = self.bot.get_statistics()
        with use_scope("stats-panel", clear=True):
            put_html(self._build_stats_html(stats))

    def _stats_updater(self) -> None:
        while self._overview_active:
            time.sleep(10)
            if not self._overview_active or self._current_page != PAGE_OVERVIEW:
                break
            try: self._refresh_stats_panel()
            except Exception: break

    def _on_start_stop(self, action: str) -> None:
        if action == "start": self.bot.start()
        else: self.bot.stop()
        time.sleep(0.3)
        self._refresh_control_button()

    def _refresh_control_button(self) -> None:
        from pywebio.output import put_buttons, use_scope
        running = self.bot.alive
        with use_scope("control-panel", clear=True):
            if running:
                put_buttons([{"label": "⏹ 停止", "value": "stop", "color": "danger"}],
                            onclick=self._on_start_stop).style("margin:10px 0;")
            else:
                put_buttons([{"label": "▶ 启动", "value": "start", "color": "success"}],
                            onclick=self._on_start_stop).style("margin:10px 0;")

    def _control_updater(self) -> None:
        last = None
        while self._overview_active:
            time.sleep(1)
            if not self._overview_active or self._current_page != PAGE_OVERVIEW:
                break
            try:
                cur = self.bot.alive
                if cur != last:
                    self._refresh_control_button()
                    last = cur
            except Exception: break

    def _render_scroll_toggle(self) -> None:
        from pywebio.output import put_buttons, use_scope
        lbl = "ScrollON" if self._scroll_enabled else "ScrollOFF"
        clr = "success" if self._scroll_enabled else "secondary"
        with use_scope("log-scroll-toggle", clear=True):
            put_buttons([{"label": lbl, "value": "t", "color": clr}],
                        onclick=lambda _: self._toggle_scroll()).style("margin:4px 0;")

    def _toggle_scroll(self) -> None:
        self._scroll_enabled = not self._scroll_enabled
        self._render_scroll_toggle()

    def _log_updater(self) -> None:
        from pywebio.output import put_text, use_scope
        from pywebio.session import run_js

        handler = _WebUILogHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s",
                                                datefmt="%H:%M:%S"))
        target = logging.getLogger("ShopBot")
        target.addHandler(handler)
        try:
            while self._overview_active:
                time.sleep(0.5)
                if self._current_page != PAGE_OVERVIEW:
                    break
                lines = handler.drain()
                if not lines or not self._scroll_enabled:
                    continue
                try:
                    with use_scope("log-lines"):
                        for line in lines:
                            put_text(line).style("margin:1px 0;")
                    run_js("""
                        var el = document.getElementById('pywebio-scope-log-lines');
                        if (el) el.scrollTop = el.scrollHeight;
                    """)
                except Exception:
                    break
        finally:
            target.removeHandler(handler)

    def stop_overview_updates(self) -> None:
        self._overview_active = False

    # ── shop config ─────────────────────────────────────────────────
    def render_shop_config(self) -> None:
        from pywebio.output import put_html, use_scope
        from pywebio.pin import pin_on_change, put_checkbox, put_input

        cfg = self.config.get()
        shop = cfg.shop

        with use_scope("content"):
            put_html('<h2 style="margin-top:0;color:#cdd6f4;">🛒 商店配置</h2>')

            put_html('<div class="ghdr">购买物品</div>')
            buy_opts = [
                {"label": "召唤书签 (Bookmarks)", "value": "buy_bookmarks"},
                {"label": "神秘奖章 (Mystic Medals)", "value": "buy_mystic_medals"},
                {"label": "装备 (Equipment)", "value": "buy_equipment"},
                {"label": "狗粮 (Fodder)", "value": "buy_fodder"},
            ]
            checked = [o["value"] for o in buy_opts if getattr(shop, o["value"], False)]
            put_checkbox("shop_buy_items", options=buy_opts, value=checked)
            def _on_buy(val):
                for o in buy_opts:
                    self.config.update("shop", o["value"], o["value"] in val)
            pin_on_change("shop_buy_items", onchange=_on_buy)

            put_html('<div class="ghdr">刷新参数</div>')
            put_input("shop_max_refresh_count", type="number",
                      label="最大刷新次数", value=shop.max_refresh_count)
            def _on_max(val):
                try: self.config.update("shop", "max_refresh_count", int(val))
                except (ValueError, TypeError): pass
            pin_on_change("shop_max_refresh_count", onchange=_on_max)

            put_html('<div class="ghdr">阈值设置</div>')
            put_input("shop_gold_threshold", type="number",
                      label="金币下限阈值", value=shop.gold_threshold)
            put_input("shop_skystone_threshold", type="number",
                      label="天空石下限阈值", value=shop.skystone_threshold)
            def _on_gold(val):
                try: self.config.update("shop", "gold_threshold", int(val))
                except (ValueError, TypeError): pass
            def _on_sky(val):
                try: self.config.update("shop", "skystone_threshold", int(val))
                except (ValueError, TypeError): pass
            pin_on_change("shop_gold_threshold", onchange=_on_gold)
            pin_on_change("shop_skystone_threshold", onchange=_on_sky)

            put_html('<div class="ghdr">停止条件（0=不限）</div>')
            put_input("shop_max_bookmarks", type="number",
                      label="购买书签上限", value=shop.max_bookmarks)
            put_input("shop_max_mystic_medals", type="number",
                      label="购买神秘奖章上限", value=shop.max_mystic_medals)
            put_input("shop_max_skystone_spend", type="number",
                      label="刷新消耗天空石上限", value=shop.max_skystone_spend)
            def _on_max_bm(val):
                try: self.config.update("shop", "max_bookmarks", int(val))
                except (ValueError, TypeError): pass
            def _on_max_mm(val):
                try: self.config.update("shop", "max_mystic_medals", int(val))
                except (ValueError, TypeError): pass
            def _on_max_ss(val):
                try: self.config.update("shop", "max_skystone_spend", int(val))
                except (ValueError, TypeError): pass
            pin_on_change("shop_max_bookmarks", onchange=_on_max_bm)
            pin_on_change("shop_max_mystic_medals", onchange=_on_max_mm)
            pin_on_change("shop_max_skystone_spend", onchange=_on_max_ss)

    # ── device config ────────────────────────────────────────────────
    def render_device_config(self) -> None:
        from pywebio.output import put_html, use_scope
        from pywebio.pin import pin_on_change, put_input, put_select

        cfg = self.config.get()
        dev = cfg.device
        running = self.bot.alive

        with use_scope("content"):
            put_html('<h2 style="margin-top:0;color:#cdd6f4;">📱 设备配置</h2>')

            if running:
                put_html('<div class="warn-banner">'
                         '⚠ 运行中，设备配置不可修改。请先停止运行再修改。</div>')

            put_html('<div class="ghdr">设备连接</div>')
            put_input("device_serial", label="模拟器序列号",
                      value=dev.serial, readonly=running)
            put_select("device_screenshot_method", label="截图方式",
                       options=["ADB", "uiautomator2"], value=dev.screenshot_method)
            put_select("device_control_method", label="控制方式",
                       options=["ADB", "uiautomator2"], value=dev.control_method)

            if not running:
                def _s(val):
                    if not self.bot.alive:
                        self.config.update("device", "serial", str(val))
                def _ss(val):
                    if not self.bot.alive:
                        self.config.update("device", "screenshot_method", str(val))
                def _sc(val):
                    if not self.bot.alive:
                        self.config.update("device", "control_method", str(val))
                pin_on_change("device_serial", onchange=_s)
                pin_on_change("device_screenshot_method", onchange=_ss)
                pin_on_change("device_control_method", onchange=_sc)

    # ── template manager ────────────────────────────────────────────
    # 所有模板定义：name, label, description, default file path
    TEMPLATE_DEFS = [
        ("bookmark",        "召唤书签",   "Covenant Bookmarks 图标模板"),
        ("mystic_medal",    "神秘奖章",   "Mystic Medals 图标模板"),
        ("equipment",       "装备",       "Equipment 图标模板"),
        ("fodder",          "狗粮",       "Fodder 图标模板"),
        ("lobby",           "大厅标识",   "游戏大厅界面标识"),
        ("shop_tab",        "商店标签",   "商店主界面标签"),
        ("secret_shop",     "秘密商店标签", "秘密商店标签按钮"),
        ("secret_shop_indicator", "秘密商店标识", "秘密商店界面标识"),
        ("refresh_btn",     "刷新按钮",   "秘密商店刷新按钮"),
        ("confirm_btn",     "确认按钮",   "购买/刷新确认弹窗按钮"),
        ("second_confirm_btn", "二次确认", "二次确认弹窗按钮"),
        ("popup_close",     "弹窗关闭",   "意外弹窗关闭按钮"),
        ("insufficient_gold", "金币不足", "金币不足提示"),
        ("skystone_area",   "天空石区域", "天空石数值 OCR 区域"),
    ]

    def _get_assets_dir(self) -> Path:
        """返回 assets/e7/ 目录的绝对路径，兼容 PyInstaller 打包。"""
        import sys
        if getattr(sys, 'frozen', False):
            # 打包后：exe 同级目录下的 assets/e7/
            base = Path(sys.executable).resolve().parent
        else:
            base = Path(__file__).resolve().parent.parent
        return base / "assets" / "e7"

    def _img_to_data_uri(self, filepath: Path) -> str:
        """将图片文件转为 base64 data URI，用于在 HTML 中内联显示。"""
        try:
            data = filepath.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            suffix = filepath.suffix.lower()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "bmp": "image/bmp"}.get(suffix.lstrip("."), "image/png")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return ""

    def render_template_manager(self) -> None:
        from pywebio.output import put_html, put_buttons, put_scope, use_scope
        from pywebio.input import file_upload

        assets_dir = self._get_assets_dir()
        assets_dir.mkdir(parents=True, exist_ok=True)

        with use_scope("content"):
            put_html('<h2 style="margin-top:0;color:#cdd6f4;">🖼 模板管理</h2>')
            put_html('<p style="color:#a6adc8;margin-bottom:4px;">'
                     '上传或替换物品/按钮的截图模板。模板用于模板匹配识别游戏界面元素。<br>'
                     '建议从 1280×720 分辨率的游戏截图中裁剪。</p>')

            # 上传按钮
            put_buttons(
                [{"label": "📤 上传模板图片", "value": "upload", "color": "primary"}],
                onclick=[lambda: self._handle_template_upload()],
            ).style("margin-bottom:16px;")

            # 模板卡片网格
            put_scope("tpl-grid-scope")
            self._refresh_template_grid()

    def _refresh_template_grid(self) -> None:
        from pywebio.output import put_html, use_scope

        assets_dir = self._get_assets_dir()
        cards_html = []

        for tpl_name, tpl_label, tpl_desc in self.TEMPLATE_DEFS:
            # 查找已有的模板文件
            img_html = '<div style="color:#585b70;font-size:12px;padding:20px 0;text-align:center;">未上传</div>'
            file_info = "无文件"
            for ext in ("png", "jpg", "jpeg", "bmp"):
                fpath = assets_dir / f"{tpl_name}.{ext}"
                if fpath.exists():
                    data_uri = self._img_to_data_uri(fpath)
                    if data_uri:
                        img_html = f'<img src="{data_uri}" alt="{tpl_name}" style="max-height:120px;">'
                    size_kb = fpath.stat().st_size / 1024
                    file_info = f"{fpath.name} ({size_kb:.1f} KB)"
                    break

            cards_html.append(
                f'<div class="tpl-card">'
                f'<div class="tpl-name">{tpl_label}</div>'
                f'{img_html}'
                f'<div class="tpl-info">{tpl_desc}</div>'
                f'<div class="tpl-info">文件: {file_info}</div>'
                f'</div>'
            )

        grid = f'<div class="tpl-grid">{"".join(cards_html)}</div>'
        with use_scope("tpl-grid-scope", clear=True):
            put_html(grid)

    def _handle_template_upload(self) -> None:
        from pywebio.input import file_upload, select, input as pywebio_input
        from pywebio.output import put_html, put_text, toast, use_scope

        assets_dir = self._get_assets_dir()

        # 选择要上传的模板类型
        options = [f"{label} ({name})" for name, label, _ in self.TEMPLATE_DEFS]
        choice = select("选择模板类型", options=options)
        idx = options.index(choice)
        tpl_name = self.TEMPLATE_DEFS[idx][0]

        # 上传文件
        uploaded = file_upload(
            "上传模板图片",
            accept="image/*",
            help_text="支持 PNG/JPG/BMP，建议从 1280×720 截图中裁剪",
        )

        if uploaded:
            # 确定保存路径
            original_name = uploaded["filename"]
            ext = Path(original_name).suffix.lower() or ".png"
            save_path = assets_dir / f"{tpl_name}{ext}"

            # 删除同名不同扩展名的旧文件
            for old_ext in ("png", "jpg", "jpeg", "bmp"):
                old_file = assets_dir / f"{tpl_name}.{old_ext}"
                if old_file.exists() and old_file != save_path:
                    old_file.unlink()

            # 保存新文件
            save_path.write_bytes(uploaded["content"])
            logger.info(f"模板已保存: {save_path}")
            toast(f"✅ {self.TEMPLATE_DEFS[idx][1]} 模板已保存", color="success")

            # 刷新卡片网格
            self._refresh_template_grid()


# ── log handler ──────────────────────────────────────────────────────
class _WebUILogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self._buffer: list[str] = []
        self._lock = threading.Lock()

    def emit(self, record):
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(msg)
        except Exception:
            self.handleError(record)

    def drain(self) -> list[str]:
        with self._lock:
            lines = self._buffer[:]
            self._buffer.clear()
        return lines
