"""
E7 Updater 存根 — ALAS 的 Git 更新检查器，E7 不需要。

保留以兼容 WebUI import。提供所有 WebUI 调用的方法存根。
"""

import datetime
import threading
import time
from typing import Generator, List, Tuple

from module.logger import logger
from module.webui.utils import TaskHandler


class Updater:
    """E7 更新器存根。"""

    def __init__(self, file=None):
        self.state = 0
        self.event: threading.Event = None
        self.delay = 0

        # 兼容属性
        self.Branch = 'main'
        self.Repository = ''

    @staticmethod
    def _noop_gen():
        yield
        while True:
            yield

    def check_update(self):
        return self._noop_gen()

    def schedule_update(self):
        return self._noop_gen()

    def run_update(self):
        """运行更新（E7 存根）。"""
        pass

    def cancel(self):
        """取消更新（E7 存根）。"""
        pass

    def get_commit(self, branch: str = 'HEAD', short_sha1: bool = True, n: int = 1) -> list:
        """
        获取提交信息（E7 存根，返回空数据）。

        Returns:
            list of tuples: (sha1, author, time, message) 或 [(sha1, author, time, message)]
        """
        if n == 1:
            return ['—', '—', '—', '—']
        return [('—', '—', '—', '—')] * n


updater = Updater()
