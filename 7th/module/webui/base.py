"""
Frame — ALAS 风格 4 区布局基类

提供 header / aside / menu / content 四区 HTML 布局，
以及 aside 按钮激活、menu 折叠/展开等交互方法。
"""

from pywebio.output import clear, put_html, put_scope, put_text, use_scope
from pywebio.session import defer_call, info, run_js

from module.webui.utils import Icon, TaskHandler


class Base:
    """WebUI 基类，管理会话生命周期。"""

    def __init__(self) -> None:
        self.alive = True
        self.visible = True
        self.is_mobile = info.user_agent.is_mobile
        self.task_handler = TaskHandler()
        defer_call(self.stop)

    def stop(self) -> None:
        self.alive = False
        self.task_handler.stop()


class Frame(Base):
    """4 区布局框架: header / aside / menu / content。"""

    def __init__(self) -> None:
        super().__init__()
        self.page = "Home"

    @staticmethod
    @use_scope("ROOT", clear=True)
    def _show() -> None:
        """渲染 4 区布局根容器。"""
        put_scope(
            "header",
            [
                put_html(Icon.ALAS).style("--header-icon--"),
                put_text("E7 Shop Bot").style("--header-text--"),
                put_scope("header_status"),
                put_scope("header_title"),
            ],
        )
        put_scope(
            "contents",
            [
                put_scope("aside"),
                put_scope("menu"),
                put_scope("content"),
            ],
        )

    @staticmethod
    @use_scope("header_title", clear=True)
    def set_title(text: str = ""):
        put_text(text)

    @staticmethod
    def collapse_menu() -> None:
        run_js(f"""
            $("#pywebio-scope-menu").addClass("container-menu-collapsed");
            $(".container-content-collapsed").removeClass("container-content-collapsed");
        """)

    @staticmethod
    def expand_menu() -> None:
        run_js(f"""
            $(".container-menu-collapsed").removeClass("container-menu-collapsed");
            $("#pywebio-scope-content").addClass("container-content-collapsed");
        """)

    @staticmethod
    def active_button(position: str, value: str) -> None:
        run_js(f"""
            $("button.btn-{position}").removeClass("btn-{position}-active");
            $("div[style*='--{position}-{value}--']>button").addClass("btn-{position}-active");
        """)
