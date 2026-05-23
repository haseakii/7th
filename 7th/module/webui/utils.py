"""
WebUI 工具函数 — Icon, TaskHandler, Switch, CSS 注入
"""

import threading
import time
from pathlib import Path
from queue import Queue
from typing import Callable, List, Optional

from pywebio.output import put_html
from pywebio.session import register_thread, run_js


class Icon:
    """SVG 图标集合，直接嵌入 HTML。"""

    ALAS = """<svg class="icon" viewBox="0 0 24 24" width="24" height="24">
        <path fill="currentColor" d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
    </svg>"""

    RUN = """<svg class="icon" viewBox="0 0 24 24" width="16" height="16">
        <circle cx="12" cy="12" r="8" fill="currentColor"/>
    </svg>"""

    STOP = """<svg class="icon" viewBox="0 0 24 24" width="16" height="16">
        <rect x="6" y="6" width="12" height="12" fill="currentColor"/>
    </svg>"""

    SETTING = """<svg class="icon" viewBox="0 0 24 24" width="16" height="16">
        <path fill="currentColor" d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z"/>
    </svg>"""

    OVERVIEW = """<svg class="icon" viewBox="0 0 24 24" width="16" height="16">
        <path fill="currentColor" d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
    </svg>"""


class Task:
    """周期性任务项。"""

    def __init__(self, func: Callable, interval: float, name: str = None):
        self.func = func
        self.interval = interval
        self.name = name or func.__name__
        self.next_run = time.time()


class TaskHandler:
    """后台周期性任务循环，支持多任务不同间隔。"""

    def __init__(self):
        self._tasks: List[Task] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add(self, func: Callable, interval: float = 1.0) -> None:
        """添加周期性任务。"""
        self._tasks.append(Task(func, interval))

    def start(self) -> None:
        """启动任务循环并注册到 PyWebIO 会话。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        register_thread(self._thread)
        self._thread.start()

    def stop(self) -> None:
        """停止任务循环并清空任务。"""
        self._running = False
        self._tasks.clear()

    def _loop(self) -> None:
        while self._running:
            now = time.time()
            for task in self._tasks:
                if not self._running:
                    return
                if now >= task.next_run:
                    try:
                        task.func()
                    except Exception:
                        pass
                    task.next_run = now + task.interval
            time.sleep(0.1)

    def remove_pending_task(self) -> None:
        """兼容 ALAS Frame 基类接口。"""
        pass


class Switch:
    """简单状态机。"""

    def __init__(self, state: int = 0):
        self.state = state

    def set(self, state: int) -> None:
        self.state = state

    def get(self) -> int:
        return self.state


CSS_DIR = Path(__file__).resolve().parent / "css"


def filepath_css(name: str) -> str:
    """返回 CSS 文件的绝对路径。"""
    return str(CSS_DIR / name)


def add_css(path: str) -> None:
    """从文件注入 CSS 到页面。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            css = f.read()
        put_html(f'<style>{css}</style>')
    except FileNotFoundError:
        pass
