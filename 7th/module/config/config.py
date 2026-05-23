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
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from log import logger
from module.config.config_generated import GeneratedConfig
from module.config.config_manual import ManualConfig
from module.config.config_updater import ConfigUpdater, filepath_config
from module.config.config_watcher import ConfigWatcher
from module.config.deep import deep_get, deep_set


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


class E7Config(ConfigUpdater, ManualConfig, GeneratedConfig, ConfigWatcher):
    """E7 配置管理器。

    同时兼容两种用法:
      1. config_name='default' — 纯 JSON 模式（ALAS 风格）
      2. config_path='config.yaml' — YAML 模式（向后兼容，自动迁移到 JSON）

    ALAS 兼容接口:
      cfg.serial, cfg.screenshot_method, cfg.control_method
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
        ConfigWatcher.__init__(self)

        self._lock = threading.RLock()
        self._bound = {}  # 属性名 → 路径映射

        # 建立属性绑定
        self._bind_attrs()

        # 启动文件监听
        self.start_watcher(on_change=self._reload)

    def _bind_attrs(self) -> None:
        """将 ARG_MAP 中的属性绑定到 ConfigUpdater 的数据路径。"""
        for attr, (group, key) in ARG_MAP.items():
            path = f'{group}.{key}'
            self._bound[attr] = path

    def _reload(self) -> None:
        """配置文件外部变更时重新加载。"""
        with self._lock:
            old_data = copy.deepcopy(self.data)
            self.data = self._load()
            logger.info('配置已重载')

    def __getattr__(self, key: str):
        """支持通过属性名读取配置值。"""
        if key.startswith('_') or key in ('data', 'modified', 'auto_update', '_lock', '_bound',
                                           'config_name', 'stop_event'):
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
                   'config_name', 'stop_event', '_watcher_thread', '_stop_event',
                   '_last_mtime', '_on_change'):
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
        bak = yaml_path.with_suffix('.yaml.bak')
        yaml_path.rename(bak)
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
