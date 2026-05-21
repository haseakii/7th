"""
E7AutoScript - 第七史诗 ALAS 风格主调度器

管理配置初始化、设备连接、任务调度与生命周期。
遵循 ALAS 的 AzurLaneAutoScript 设计模式。
"""

import threading
from typing import Optional

from log import logger
from module.config.config import E7Config
from module.device.device import DeviceController


class E7AutoScript:
    """主调度器，管理设备与任务生命周期。"""

    stop_event: threading.Event = None

    def __init__(self, config_name: str = "config.yaml"):
        logger.hr("E7AutoScript Start", level=0)
        self.config_name = config_name
        self.config: Optional[E7Config] = None
        self.device: Optional[DeviceController] = None

    def init(self) -> bool:
        """初始化配置和设备连接。"""
        try:
            self.config = E7Config(config_path=self.config_name)
            logger.info("配置加载成功")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return False

        self.device = DeviceController(self.config)
        if not self.device.connect():
            logger.error("设备连接失败")
            return False

        logger.info("E7AutoScript 初始化完成")
        return True

    def run_secret_shop(self) -> None:
        """运行秘密商店刷新购买任务。"""
        from tasks.secret_shop import SecretShopTask
        task = SecretShopTask(config=self.config, device=self.device)
        task.run()

    def stop(self) -> None:
        """停止所有任务。"""
        logger.info("E7AutoScript 收到停止请求")
        if self.stop_event is not None:
            self.stop_event.set()

    @property
    def running(self) -> bool:
        return hasattr(self, '_task_thread') and self._task_thread and self._task_thread.is_alive()


if __name__ == "__main__":
    alas = E7AutoScript()
    if alas.init():
        alas.run_secret_shop()
