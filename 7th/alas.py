"""
E7AutoScript — 第七史诗 ALAS 风格主调度器

管理配置初始化、设备连接、任务调度与生命周期。
遵循 ALAS 的 AzurLaneAutoScript 设计模式。

异常链:
  TaskEnd → 正常结束
  GameStuckError → 重启
  ScriptError → 请求人工介入
"""

import threading
from typing import Optional

from log import logger
from module.config.config import E7Config
from module.device.device import DeviceController


class TaskEnd(Exception):
    """任务正常结束。"""
    pass


class GameStuckError(Exception):
    """游戏卡死，需要重启。"""
    pass


class ScriptError(Exception):
    """脚本错误，需要人工介入。"""
    pass


class E7AutoScript:
    """主调度器，管理设备与任务生命周期。"""

    stop_event: threading.Event = None

    def __init__(self, config_name: str = "default", config_path: Optional[str] = None):
        logger.hr("E7AutoScript Start", level=0)
        self.config_name = config_name
        self.config_path = config_path
        self.config: Optional[E7Config] = None
        self.device: Optional[DeviceController] = None
        self._stop_event = threading.Event()

    def init(self) -> bool:
        """初始化配置和设备连接。"""
        try:
            self.config = E7Config(config_name=self.config_name, config_path=self.config_path)
            logger.info("配置加载成功")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return False
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return False

        try:
            self.device = DeviceController(self.config)
            if not self.device.connect():
                logger.error("设备连接失败")
                return False
        except Exception as e:
            logger.error(f"设备连接异常: {e}")
            return False

        logger.info("E7AutoScript 初始化完成")
        return True

    def run_secret_shop(self) -> None:
        """运行秘密商店刷新购买任务。

        异常处理链：
        - TaskEnd → 正常结束
        - GameStuckError → 尝试重启
        - ScriptError → 请求人工介入
        - 其他异常 → 日志记录后抛出
        """
        try:
            # 延迟导入任务模块
            from tasks.secret_shop import SecretShopTask

            task = SecretShopTask(config=self.config, device=self.device)
            task._stop_event = self._stop_event
            task.run()

        except TaskEnd:
            logger.info("秘密商店任务正常结束")
        except GameStuckError:
            logger.warning("游戏可能卡死，尝试重启设备连接")
            self._restart_device()
        except ScriptError as e:
            logger.error(f"脚本错误，需要人工介入: {e}")
            raise
        except Exception as e:
            logger.error(f"任务运行异常: {e}")
            raise

    def _restart_device(self) -> bool:
        """重启设备连接。"""
        logger.info("正在重启设备连接...")
        if self.device:
            self.device.disconnect()
        if self.device:
            return self.device.connect()
        return False

    def stop(self) -> None:
        """停止所有任务。"""
        logger.info("E7AutoScript 收到停止请求")
        self._stop_event.set()

    @property
    def running(self) -> bool:
        return hasattr(self, '_task_thread') and self._task_thread and self._task_thread.is_alive()


if __name__ == "__main__":
    alas = E7AutoScript()
    if alas.init():
        alas.run_secret_shop()
