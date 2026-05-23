"""
ConfigWatcher — 配置文件变更监听

检测 JSON 配置文件的外部修改并自动重载。
"""

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from log import logger
from module.config.config_updater import filepath_config


class ConfigWatcher:
    """配置文件变更监听器。

    在独立线程中轮询文件的 mtime，检测外部修改。
    """

    config_name: str = ''
    _watcher_thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = threading.Event()
    _last_mtime: float = 0
    _on_change: Optional[Callable] = None

    def start_watcher(self, on_change: Optional[Callable] = None) -> None:
        """启动文件变更监听线程。"""
        if self._watcher_thread and self._watcher_thread.is_alive():
            return

        self._on_change = on_change
        self._stop_event.clear()
        self._last_mtime = self._get_mtime()
        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            name='ConfigWatcher',
            daemon=True,
        )
        self._watcher_thread.start()
        logger.debug('ConfigWatcher 已启动')

    def stop_watcher(self) -> None:
        """停止文件变更监听。"""
        self._stop_event.set()
        logger.debug('ConfigWatcher 已停止')

    def _get_mtime(self) -> float:
        path = filepath_config(self.config_name)
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            mtime = self._get_mtime()
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                logger.info('检测到配置文件变更，重载中...')
                if self._on_change:
                    self._on_change()
            time.sleep(2)
