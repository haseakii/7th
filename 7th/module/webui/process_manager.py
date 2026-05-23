"""
ProcessManager — 后台任务子进程管理

管理 ShopBot 任务进程的启动、停止与状态查询。
"""

import queue
import threading
from multiprocessing import Process
from typing import Dict, Optional


class ProcessManager:
    """管理单个配置实例的任务进程。"""

    _instances: Dict[str, "ProcessManager"] = {}

    def __init__(self, config_name: str = "default"):
        self.config_name = config_name
        self._process: Optional[Process] = None
        self._state = 0  # 0=stopped, 1=running, 2=error
        self._log_queue: queue.Queue = queue.Queue()

    @classmethod
    def get_manager(cls, config_name: str) -> "ProcessManager":
        """获取或创建实例管理器。"""
        if config_name not in cls._instances:
            cls._instances[config_name] = cls(config_name)
        return cls._instances[config_name]

    @property
    def state(self) -> int:
        """返回进程状态: 0=stopped, 1=running, 2=error"""
        if self._process is not None and not self._process.is_alive():
            self._state = 0 if self._process.exitcode == 0 else 2
            self._process = None
        return self._state

    @property
    def alive(self) -> bool:
        return self.state == 1

    def start(self, func, ev: threading.Event = None) -> None:
        """启动后台任务进程。"""
        if self.alive:
            return
        self._process = Process(
            target=func,
            args=(self.config_name, ev),
            daemon=True,
        )
        self._process.start()
        self._state = 1

    def stop(self) -> None:
        """停止后台任务进程。"""
        if self._process is not None and self._process.is_alive():
            self._process.kill()
            self._process.join(timeout=3)
        self._process = None
        self._state = 0
