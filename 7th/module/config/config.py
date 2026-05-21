"""
E7Config - 第七史诗 ALAS 风格配置系统

融合 ConfigManager 的 YAML 持久化与 ALAS 的 GeneratedConfig 属性访问模式。
"""

import copy
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from log import logger
from module.config.config_generated import GeneratedConfig


class E7Config(GeneratedConfig):
    """E7 配置管理器，支持 YAML 读写和运行时属性访问。"""

    def __init__(self, config_path: str = "config.yaml"):
        self._config_path = config_path
        self._lock = threading.RLock()
        self._raw_data: dict = {}
        self._loaded = False
        self.load()

    def load(self) -> None:
        """从 YAML 加载配置，设置属性到自身。"""
        path = Path(self._config_path)
        if not path.exists():
            logger.info(f"配置文件不存在: {self._config_path}")
            self._raw_data = self._defaults()
            self._apply()
            self.save()
            return

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        with self._lock:
            self._raw_data = self._merge_defaults(raw)
            self._apply()

        self._loaded = True

    def _defaults(self) -> dict:
        return {
            "device": {
                "serial": "127.0.0.1:16384",
                "screenshot_method": "ADB",
                "control_method": "ADB",
            },
            "shop": {
                "buy_bookmarks": True,
                "buy_mystic_medals": True,
                "buy_equipment": False,
                "buy_fodder": False,
                "max_refresh_count": 200,
                "gold_threshold": 0,
                "skystone_threshold": 0,
                "max_bookmarks": 0,
                "max_mystic_medals": 100,
                "max_skystone_spend": 0,
            },
            "webui_port": 8080,
        }

    def _merge_defaults(self, raw: dict) -> dict:
        """合并用户配置与默认值，缺失项用默认值填充。"""
        defaults = self._defaults()
        for section, values in defaults.items():
            if section not in raw:
                raw[section] = values
            elif isinstance(values, dict):
                for k, v in values.items():
                    raw[section].setdefault(k, v)
        return raw

    def _apply(self) -> None:
        """将 _raw_data 中的值设置为实例属性（扁平化命名）。"""
        for section, values in self._raw_data.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    attr = f"{section}_{key}"
                    setattr(self, attr, value)
            else:
                setattr(self, section, values)

    def save(self) -> None:
        path = Path(self._config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._raw_data, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)

    def get_raw(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._raw_data)

    def update(self, section: str, key: str, value: Any) -> None:
        with self._lock:
            if section not in self._raw_data:
                self._raw_data[section] = {}
            self._raw_data[section][key] = value
            attr = f"{section}_{key}"
            setattr(self, attr, value)
            self.save()

    def get_buy_list(self) -> Dict[str, bool]:
        shop = self._raw_data.get("shop", {})
        return {
            "bookmarks": shop.get("buy_bookmarks", True),
            "mystic_medals": shop.get("buy_mystic_medals", True),
            "equipment": shop.get("buy_equipment", False),
            "fodder": shop.get("buy_fodder", False),
        }

    # --- ALAS 兼容接口 ---
    @property
    def serial(self) -> str:
        return getattr(self, "device_serial", "127.0.0.1:16384")

    @property
    def screenshot_method(self) -> str:
        return getattr(self, "device_screenshot_method", "ADB")

    @property
    def control_method(self) -> str:
        return getattr(self, "device_control_method", "ADB")

    @property
    def task(self):
        return getattr(self, "_task", None)

    @task.setter
    def task(self, value):
        self._task = value

    @property
    def is_actual_task(self):
        return True
