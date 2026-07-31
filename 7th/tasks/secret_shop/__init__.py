"""
SecretShopTask - 秘密商店自动刷新购买任务

遵循 ALAS 任务规范，继承模块基类，封装 ShopBot 主循环。
"""

import threading

from module.logger import logger
from module.base.base import ModuleBase


class SecretShopTask(ModuleBase):
    """秘密商店刷新购买任务。

    封装 ShopBot 主循环，提供 ALAS 兼容的任务接口。
    """

    def __init__(self, config, device=None, task=None):
        super().__init__(config, device=device, task=task)
        self.config = config
        self.device = device
        self.bot = None  # ShopBot 实例，延迟初始化
        self._running = False
        self._stop_event = threading.Event()

    def run(self) -> None:
        """任务入口 — 运行商店自动刷新购买。"""
        logger.hr("SecretShopTask Run", level=0)

        # 延迟导入避免循环依赖：shop_bot → tasks.secret_shop → shop_bot
        from shop_bot import ShopBot

        self.bot = ShopBot(config=self.config, device=self.device)
        self.bot._stop_event = self._stop_event

        self._running = True
        try:
            self.bot.run_loop()
        finally:
            self._running = False

    def stop(self) -> None:
        """停止任务。"""
        logger.info("SecretShopTask 停止")
        self._stop_event.set()
        if self.bot:
            self.bot.stop()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def stats(self):
        """返回运行统计。"""
        if self.bot:
            return self.bot.get_statistics()
        from shop_bot import RunStatistics
        return RunStatistics()
