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
from datetime import datetime
from typing import Optional

import inflection

from module.config.config import E7Config, TaskEnd
from module.device.device import DeviceController
from module.exception import GameStuckError, ScriptError, RequestHumanTakeover
from module.logger import logger
from module.task.registry import get_task


class E7AutoScript:
    """主调度器，管理设备与任务生命周期。"""

    stop_event: threading.Event = None

    def __init__(self, config_name: str = "default", config: Optional[E7Config] = None):
        logger.hr("E7AutoScript Start", level=0)
        self.config_name = config_name
        self._config = config
        self._device: Optional[DeviceController] = None
        self._stop_event = threading.Event()
        self.failure_record = {}

    @property
    def config(self) -> E7Config:
        if self._config is None:
            self._config = E7Config(config_name=self.config_name)
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    @property
    def device(self) -> Optional[DeviceController]:
        return self._device

    def init(self) -> bool:
        """初始化配置和设备连接。"""
        try:
            _ = self.config
            logger.info("配置加载成功")
        except RequestHumanTakeover:
            logger.critical("无可用任务，请至少启用一个任务")
            return False
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return False

        try:
            self._device = DeviceController(self.config)
            if not self._device.connect():
                logger.error("设备连接失败")
                return False
        except Exception as e:
            logger.error(f"设备连接异常: {e}")
            return False

        logger.info("E7AutoScript 初始化完成")
        return True

    def loop(self):
        """ALAS 风格调度主循环。

        每轮循环：
          1. config.load() — 从磁盘重新读取 JSON
          2. get_next() — 从 JSON 发现下一个任务
          3. run(command) — 派发到对应方法
          4. task_delay() — 任务结束后更新 NextRun
          5. device.config = config — 保持设备引用最新
        """
        logger.info(f"启动调度循环: {self.config_name}")

        # 初始读取配置
        self.config.load()

        while not self._stop_event.is_set():
            # ── 获取下一个任务 ──
            try:
                task = self.config.get_next()
            except RequestHumanTakeover:
                logger.warning("没有启用的任务，调度器保持运行并等待配置变更")
                if self._stop_event.wait(10):
                    break
                self.config.load()
                continue

            # ── 如果任务调度时间在未来，等待（最多 60s 轮询 stop_event） ──
            now = datetime.now()
            if isinstance(task.next_run, datetime) and task.next_run > now:
                remaining = int((task.next_run - now).total_seconds())
                logger.info(f"等待 {remaining}s 至 `{task.command}` 调度时间")
                while remaining > 0:
                    chunk = min(remaining, 60)
                    if self._stop_event.wait(chunk):
                        break
                    remaining -= chunk
                if self._stop_event.is_set():
                    break
                continue

            # ── 执行任务 ──
            command = task.command
            self._device.config = self.config
            self.config.task = task
            logger.hr(inflection.underscore(command), level=0)
            success = self.run(command)

            # ── 任务完成后更新调度时间 ──
            self.config.task_delay(success=success, task=task.command)

            # ── 失败计数 ──
            failed = self.failure_record.get(command, 0)
            failed = 0 if success else failed + 1
            self.failure_record[command] = failed
            if failed >= 3:
                logger.critical(f"任务 `{command}` 连续失败 3 次，退出")
                break

            # ── 重读配置（响应 WebUI 变更） ──
            self.config.load()

        logger.info("调度循环结束")

    def run(self, command):
        """运行指定任务。

        Args:
            command (str): 任务方法名（snake_case）

        Returns:
            bool: 是否成功完成
        """
        method = inflection.underscore(command)
        try:
            spec = get_task(command) or get_task(method)
            if spec is not None:
                logger.info(f"运行已注册任务 `{spec.command}`")
                task = spec.factory(config=self.config, device=self.device, task=spec.command)
                if hasattr(task, "_stop_event"):
                    task._stop_event = self._stop_event
                task.run()
            else:
                logger.warning(f"任务 `{command}` 未注册，回退到 E7AutoScript.{method}()")
                if not hasattr(self, method):
                    raise ScriptError(f"Unknown task command: {command}")
                self.__getattribute__(method)()
            return True
        except TaskEnd:
            logger.info(f"任务 `{command}` 正常结束")
            return True
        except GameStuckError as e:
            logger.warning(f"游戏可能卡死: {e}")
            self._restart_device()
            return False
        except ScriptError as e:
            logger.error(f"脚本错误，需要人工介入: {e}")
            raise
        except Exception as e:
            logger.error(f"任务 `{command}` 异常: {e}")
            return False

    def secret_shop(self):
        """运行秘密商店刷新购买任务。"""
        from tasks.secret_shop import SecretShopTask

        task = SecretShopTask(config=self.config, device=self.device)
        task._stop_event = self._stop_event
        task.run()

    def _restart_device(self) -> bool:
        """重启设备连接。"""
        logger.info("正在重启设备连接...")
        if self._device:
            try:
                self._device.disconnect()
            except Exception as e:
                logger.warning(f"断开设备连接异常: {e}")
        if self._device:
            try:
                return self._device.connect()
            except Exception as e:
                logger.warning(f"重建设备连接异常: {e}")
                return False
        return False

    def stop(self) -> None:
        """停止所有任务。"""
        logger.info("E7AutoScript 收到停止请求")
        self._stop_event.set()

    @property
    def running(self) -> bool:
        return self._device is not None


if __name__ == "__main__":
    alas = E7AutoScript()
    if alas.init():
        alas.loop()
