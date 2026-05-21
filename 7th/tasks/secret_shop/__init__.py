"""
SecretShopTask - 秘密商店自动刷新购买任务

遵循 ALAS 任务规范，继承模块基类，封装 ShopBot 主循环。
"""

import threading
from typing import Optional

from log import logger
from module.base.base import ModuleBase
from shop.navigator import ShopNavigator
from shop.purchase import PurchaseEngine
from shop.recognizer import ItemRecognizer
from shop_bot import ShopBot, RunStatistics


class SecretShopTask(ModuleBase):
    """秘密商店刷新购买任务。

    封装 ShopBot 主循环，提供 ALAS 兼容的任务接口。
    """

    def __init__(self, config, device=None, task=None):
        super().__init__(config, device=device, task=task)
        self.config = config
        self.device = device
        self.bot: Optional[ShopBot] = None
        self._running = False
        self._stop_event = threading.Event()

    def run(self) -> None:
        """任务入口 — 运行商店自动刷新购买。"""
        logger.hr("SecretShopTask Run", level=0)

        # 用 E7Config 兼容 ConfigManager
        from config_manager import ConfigManager
        cfg_mgr = ConfigManager(config_path=self.config._config_path)
        cfg_mgr.load()

        self.bot = ShopBot(config=cfg_mgr)
        self.bot._stop_event = self._stop_event

        # 使用外部传入的 device（避免重复连接）
        self.bot.device = self.device

        self._running = True
        self.bot.run_loop()
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
    def stats(self) -> RunStatistics:
        if self.bot:
            return self.bot.get_statistics()
        return RunStatistics()
