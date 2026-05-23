"""
Updater — 基于 Git 的自动更新

定时检查远程更新，执行 git pull + pip install 并重启。
"""

import threading
import time
from typing import Optional

from deploy.git import GitManager
from deploy.pip import PipManager
from log import logger


class Updater:
    """自动更新管理器。

    在后台线程中定期检查远程更新，
    检测到更新后执行 git pull + pip install。
    """

    def __init__(self, config_path: Optional[str] = None):
        self.git = GitManager(config_path)
        self.pip = PipManager(config_path)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._update_available = False
        self._latest_commit = ""

    @property
    def update_available(self) -> bool:
        return self._update_available

    def start(self, interval: int = 300) -> None:
        """启动定时检查线程。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._check_loop,
            args=(interval,),
            daemon=True,
        )
        self._thread.start()
        logger.info(f"更新检查已启动（间隔 {interval}s）")

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("更新检查已停止")

    def _check_loop(self, interval: int) -> None:
        while not self._stop_event.is_set():
            try:
                self.check()
            except Exception as e:
                logger.warning(f"更新检查异常: {e}")
            time.sleep(interval)

    def check(self) -> bool:
        """检查远程是否有更新。"""
        if not self.git.fetch():
            return False
        has_update = self.git.has_update()
        if has_update:
            self._latest_commit = self.git.remote_commit()
            self._update_available = True
            logger.info(f"发现新版本: {self._latest_commit[:8]}")
        return has_update

    def run_update(self) -> bool:
        """执行更新：git pull → pip install。"""
        logger.hr("开始更新", level=1)

        if not self.git.pull():
            logger.error("Git pull 失败")
            return False

        self.pip.install()
        self._update_available = False
        logger.info("更新完成，请重启程序")
        return True


# 模块级单例
updater = Updater()
