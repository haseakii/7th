"""
E7Config — 第七史诗 ALAS 风格配置系统

MRO 继承链:
  ConfigUpdater → ManualConfig → GeneratedConfig → ConfigWatcher

用法:
  cfg = E7Config(config_name='default')
  cfg.Serial          # 从 JSON 中读取
  cfg.SERVER          # 从 ManualConfig 中读取
"""

import copy
import operator
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from module.logger import logger
from module.base.filter import Filter
from module.config.config_generated import GeneratedConfig
from module.config.config_manual import ManualConfig
from module.config.config_updater import ConfigUpdater, filepath_config
from module.config.watcher import ConfigWatcher
from module.config.deep import deep_get, deep_set
from module.config.utils import DEFAULT_TIME, ensure_time, parse_time, filepath_config as utils_filepath_config, read_file
from module.exception import RequestHumanTakeover, ScriptError


class TaskEnd(Exception):
    """任务正常结束。"""
    pass


# ── 重映射：扁平化属性名 → args.json 嵌套路径 ─────────────────────
# 格式: { 属性名: (组, 键) }
ARG_MAP = {
    # Device
    'Serial': ('Device.Connection', 'Serial'),
    'ScreenshotMethod': ('Device.Connection', 'ScreenshotMethod'),
    'ControlMethod': ('Device.Connection', 'ControlMethod'),
    'OcrMethod': ('Device.Connection', 'OcrMethod'),
    # SecretShop
    'BuyBookmarks': ('SecretShop.ShopItems', 'BuyBookmarks'),
    'BuyMysticMedals': ('SecretShop.ShopItems', 'BuyMysticMedals'),
    'BuyEquipment': ('SecretShop.ShopItems', 'BuyEquipment'),
    'BuyFodder': ('SecretShop.ShopItems', 'BuyFodder'),
    'MaxRefreshCount': ('SecretShop.RefreshSettings', 'MaxRefreshCount'),
    'MaxSkystoneSpend': ('SecretShop.RefreshSettings', 'MaxSkystoneSpend'),
    'GoldThreshold': ('SecretShop.Thresholds', 'GoldThreshold'),
    'SkystoneThreshold': ('SecretShop.Thresholds', 'SkystoneThreshold'),
    'MaxBookmarks': ('SecretShop.StopConditions', 'MaxBookmarks'),
    'MaxMysticMedals': ('SecretShop.StopConditions', 'MaxMysticMedals'),
    # Webui
    'WebuiPort': ('Webui.Server', 'WebuiPort'),
}

# 反向：嵌套路径根级分组名 → 扁平名前缀
PREFIX_MAP = {
    'Device': 'device',
    'SecretShop': 'shop',
    'Webui': 'webui',
}


class E7Config(ConfigUpdater, ManualConfig, GeneratedConfig):
    """E7 配置管理器。

    同时兼容两种用法:
      1. config_name='default' — 纯 JSON 模式（ALAS 风格）
      2. config_path='config.yaml' — YAML 模式（向后兼容，自动迁移到 JSON）

    ALAS 兼容接口:
      cfg.serial, cfg.screenshot_method, cfg.control_method

    使用 ALAS ConfigWatcher 检测文件外部变更。
    """

    stop_event: threading.Event = None

    def __init__(self, config_name: str = 'default', config_path: Optional[str] = None):
        # ── YAML 迁移 ──
        if config_path is not None:
            yaml_path = Path(config_path)
            if yaml_path.exists():
                self._migrate_from_yaml(yaml_path, config_name)
                config_path = None  # 迁移后不再使用 YAML

        # ── 初始化 MRO 链 ──
        # ConfigUpdater.__init__ 需要 config_name
        ConfigUpdater.__init__(self, config_name=config_name)
        ManualConfig.__init__(self)
        GeneratedConfig.__init__(self)

        self._lock = threading.RLock()
        self._bound = {}  # 属性名 → 路径映射
        self._watcher_stop = threading.Event()
        self._pending_task = []
        self._waiting_task = []

        # 建立属性绑定
        self._bind_attrs()

        # 启动 ALAS ConfigWatcher（后台轮询线程）
        self._watcher = ConfigWatcher()
        self._watcher.config_name = config_name
        self._watcher.start_watching()
        self._start_watcher_thread()

    def _start_watcher_thread(self) -> None:
        """启动后台线程轮询配置文件变更。"""
        def _watch():
            while not self._watcher_stop.is_set():
                if self._watcher.should_reload():
                    self._reload()
                self._watcher_stop.wait(2)

        t = threading.Thread(target=_watch, name='ConfigWatcher', daemon=True)
        t.start()

    def _bind_attrs(self) -> None:
        """将 ARG_MAP 中的属性绑定到 ConfigUpdater 的数据路径。"""
        for attr, (group, key) in ARG_MAP.items():
            path = f'{group}.{key}'
            self._bound[attr] = path

    def _reload(self) -> None:
        """配置文件外部变更时重新加载。"""
        with self._lock:
            self.data = self._load()
            logger.info('配置已重载')

    def __getattr__(self, key: str):
        """支持通过属性名读取配置值。"""
        if key.startswith('_') or key in ('data', 'modified', 'auto_update', '_lock', '_bound',
                                           'config_name', 'stop_event', '_task',
                                           '_pending_task', '_waiting_task',
                                           '_watcher', '_watcher_stop'):
            raise AttributeError(key)

        # 1. 检查 ManualConfig 类属性
        if key in ManualConfig.__dict__:
            return ManualConfig.__dict__[key]

        # 2. 检查 ARG_MAP 绑定
        if key in self._bound:
            path = self._bound[key]
            return self.get(path)

        # 3. 尝试从 data 直接获取
        return self.get(key)

    def __setattr__(self, key: str, value: Any):
        """支持通过属性名写入配置值。"""
        if key in ('data', 'modified', 'auto_update', '_lock', '_bound',
                   'config_name', 'stop_event', '_watcher', '_watcher_stop',
                   '_task', '_pending_task', '_waiting_task'):
            super().__setattr__(key, value)
            return

        if key in self._bound:
            path = self._bound[key]
            self.modified[path] = value
            if self.auto_update:
                self.update()
        else:
            super().__setattr__(key, value)

    # ── 批量读取 ──

    def get_buy_list(self) -> Dict[str, bool]:
        """返回 {物品类型: 是否启用}。"""
        return {
            'bookmarks': self.BuyBookmarks,
            'mystic_medals': self.BuyMysticMedals,
            'equipment': self.BuyEquipment,
            'fodder': self.BuyFodder,
        }

    def get_raw(self) -> dict:
        """返回完整配置字典（深拷贝）。"""
        with self._lock:
            return copy.deepcopy(self.data)

    # ── 调度器接口 ──

    def load(self) -> None:
        """从磁盘重新读取配置 JSON。"""
        with self._lock:
            self.data = self._load()

    def get_next_task(self) -> None:
        """遍历 self.data 中所有任务，按优先级设置 pending_task / waiting_task。"""
        pending = []
        waiting = []
        error = []
        now = datetime.now().replace(microsecond=0)

        if not isinstance(self.data, dict):
            logger.error(f'self.data 不是 dict: {type(self.data)}')
            self.pending_task = []
            self.waiting_task = []
            return

        for key, data in self.data.items():
            if not isinstance(data, dict):
                continue
            func = Function(data)
            if not func.enable:
                continue
            if not isinstance(func.next_run, datetime):
                error.append(func)
            elif func.next_run <= now:
                pending.append(func)
            else:
                waiting.append(func)

        f = Filter(regex=r'(.*)', attr=['command'])
        f.load(self.SCHEDULER_PRIORITY)
        if pending:
            pending = f.apply(pending)
        if waiting:
            waiting = f.apply(waiting)
            waiting = sorted(waiting, key=operator.attrgetter('next_run'))
        if error:
            pending = error + pending

        self.pending_task = pending
        self.waiting_task = waiting

    def get_next(self) -> Function:
        """返回下一个要运行的任务。

        Raises:
            RequestHumanTakeover: 没有任务启用
        """
        self.get_next_task()

        if self.pending_task:
            task = self.pending_task[0]
            logger.attr('Task', task)
            return task

        if self.waiting_task:
            task = copy.deepcopy(self.waiting_task[0])
            logger.attr('Task', task)
            return task

        logger.critical('没有待运行或等待中的任务，请至少启用一个任务')
        raise RequestHumanTakeover

    def task_delay(self, success=None, server_update=None, target=None, minute=None, task=None):
        """设置 Scheduler.NextRun。

        Args:
            success (bool): 成功则延迟 SuccessInterval，失败则延迟 FailureInterval
            server_update (bool, str): 延迟到服务器更新
            target (datetime, str, list): 延迟到指定时间
            minute (int, float, tuple): 延迟 N 分钟
            task (str): 设置哪个任务的 NextRun，None 为当前任务
        """

        def ensure_delta(delay):
            return timedelta(seconds=int(ensure_time(delay, precision=3) * 60))

        run = []
        if success is not None:
            interval = self.Scheduler_SuccessInterval if success else self.Scheduler_FailureInterval
            run.append(datetime.now() + ensure_delta(interval))
        if server_update is not None:
            from module.config.utils import get_server_next_update
            srv = server_update if isinstance(server_update, str) else self.Scheduler_ServerUpdate
            run.append(get_server_next_update(srv))
        if target is not None:
            target = [target] if not isinstance(target, list) else target
            from module.config.utils import nearest_future
            run.append(nearest_future(target))
        if minute is not None:
            run.append(datetime.now() + ensure_delta(minute))

        if run:
            run = min(run).replace(microsecond=0)
            if task is None:
                task = self.task.command if self.task else 'SecretShop'
            logger.info(f'延迟任务 `{task}` 至 {run}')
            self.modified[f'{task}.Scheduler.NextRun'] = run.strftime('%Y-%m-%d %H:%M:%S')
            self.update()

    def task_call(self, task, force_call=True):
        """立即调用另一个任务。

        Args:
            task (str): 任务名
            force_call (bool): 即使任务被禁用也强制调用

        Returns:
            bool: 是否成功调用
        """
        if deep_get(self.data, keys=f'{task}.Scheduler.NextRun', default=None) is None:
            logger.error(f'任务 `{task}` 不存在')
            return False

        if force_call:
            logger.info(f'任务调用: {task}')
            self.modified[f'{task}.Scheduler.NextRun'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.modified[f'{task}.Scheduler.Enable'] = True
            if self.auto_update:
                self.update()
            return True
        else:
            logger.info(f'任务调用: {task} (跳过，用户已禁用)')
            return False

    @staticmethod
    def task_stop(message=''):
        """停止当前任务。"""
        if message:
            raise TaskEnd(message)
        else:
            raise TaskEnd

    def task_switched(self):
        """检查是否需要切换到其他任务。"""
        prev = self.task
        self.load()
        new = self.get_next()
        if prev and new and prev.command == new.command:
            logger.info(f'继续任务 `{new}`')
            return False
        else:
            logger.info(f'切换任务 `{prev}` 至 `{new}`')
            return True

    def check_task_switch(self, message=''):
        """如果任务已切换则停止当前任务。"""
        if self.task_switched():
            self.task_stop(message=message)

    def is_task_enabled(self, task):
        """检查指定任务是否启用。"""
        return bool(deep_get(self.data, keys=f'{task}.Scheduler.Enable', default=False))

    @property
    def pending_task(self) -> list:
        return self._pending_task

    @pending_task.setter
    def pending_task(self, value):
        self._pending_task = value

    @property
    def waiting_task(self) -> list:
        return self._waiting_task

    @waiting_task.setter
    def waiting_task(self, value):
        self._waiting_task = value

    @staticmethod
    def read_file(config_name, is_template=False):
        """ALAS 兼容接口 — 读取配置文件。"""
        path = utils_filepath_config(config_name)
        return read_file(path)

    @staticmethod
    def write_file(config_name, data, mod_name='alas'):
        """ALAS 兼容接口 — 写入配置文件。"""
        path = utils_filepath_config(config_name)
        from module.config.utils import write_file as util_write
        util_write(path, data)

    @staticmethod
    def save_callback(key, value):
        """ALAS 兼容的保存回调。"""
        return []

    # ── YAML 迁移 ──

    @staticmethod
    def _migrate_from_yaml(yaml_path: Path, config_name: str) -> None:
        """将旧 YAML 配置迁移到 JSON。"""
        try:
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                raw = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f'YAML 迁移读取失败: {e}')
            return

        # 映射 YAML 扁平结构到 args.json 嵌套结构
        json_data = {}
        device = raw.get('device', {})
        shop = raw.get('shop', {})

        deep_set(json_data, 'Device.Connection.Serial', device.get('serial', '127.0.0.1:16384'))
        deep_set(json_data, 'Device.Connection.ScreenshotMethod', device.get('screenshot_method', 'auto'))
        deep_set(json_data, 'Device.Connection.ControlMethod', device.get('control_method', 'auto'))
        deep_set(json_data, 'Device.Connection.OcrMethod', device.get('ocr_method', 'rapidocr'))

        deep_set(json_data, 'SecretShop.ShopItems.BuyBookmarks', shop.get('buy_bookmarks', True))
        deep_set(json_data, 'SecretShop.ShopItems.BuyMysticMedals', shop.get('buy_mystic_medals', True))
        deep_set(json_data, 'SecretShop.ShopItems.BuyEquipment', shop.get('buy_equipment', False))
        deep_set(json_data, 'SecretShop.ShopItems.BuyFodder', shop.get('buy_fodder', False))
        deep_set(json_data, 'SecretShop.RefreshSettings.MaxRefreshCount', shop.get('max_refresh_count', 200))
        deep_set(json_data, 'SecretShop.RefreshSettings.MaxSkystoneSpend', shop.get('max_skystone_spend', 0))
        deep_set(json_data, 'SecretShop.Thresholds.GoldThreshold', shop.get('gold_threshold', 0))
        deep_set(json_data, 'SecretShop.Thresholds.SkystoneThreshold', shop.get('skystone_threshold', 0))
        deep_set(json_data, 'SecretShop.StopConditions.MaxBookmarks', shop.get('max_bookmarks', 0))
        deep_set(json_data, 'SecretShop.StopConditions.MaxMysticMedals', shop.get('max_mystic_medals', 100))
        deep_set(json_data, 'Webui.Server.WebuiPort', raw.get('webui_port', 8080))

        # 写入 JSON
        json_path = filepath_config(config_name)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # 备份 YAML
        import os as _os
        bak = yaml_path.with_suffix('.yaml.bak')
        _os.replace(str(yaml_path), str(bak))
        logger.info(f'YAML 配置已迁移至 {json_path}，原文件备份为 {bak}')

    # ── ALAS 兼容接口 ──

    @property
    def serial(self) -> str:
        val = self.Serial
        return str(val) if val is not None else '127.0.0.1:16384'

    @property
    def screenshot_method(self) -> str:
        val = self.ScreenshotMethod
        return str(val) if val is not None else 'auto'

    @property
    def control_method(self) -> str:
        val = self.ControlMethod
        return str(val) if val is not None else 'auto'

    @property
    def task(self):
        return getattr(self, '_task', None)

    @task.setter
    def task(self, value):
        self._task = value

    @property
    def is_actual_task(self):
        return True


class Function:
    """ALAS Function — 表示调度系统中的一个可运行任务。

    从配置 JSON dict 构造，读取 Scheduler 组的数据。
    """

    def __init__(self, data):
        if isinstance(data, dict):
            self.enable = deep_get(data, 'Scheduler.Enable', default=False)
            self.command = deep_get(data, 'Scheduler.Command', default='')
            nr = deep_get(data, 'Scheduler.NextRun', default=DEFAULT_TIME)
            self.next_run = parse_time(nr)
        else:
            self.enable = False
            self.command = ''
            self.next_run = DEFAULT_TIME

    def __str__(self):
        enable = 'Enable' if self.enable else 'Disable'
        return f'{self.command} ({enable}, {str(self.next_run)})'

    __repr__ = __str__

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False
        return self.command == other.command and self.next_run == other.next_run


def name_to_function(name):
    """从任务名构建临时 Function 对象。"""
    func = Function({})
    func.command = name
    func.enable = True
    return func
