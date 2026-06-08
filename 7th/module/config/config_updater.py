"""
ConfigUpdater — JSON 配置持久化

管理 config/{name}.json 的读写、变更追踪与自动保存。
"""

import json
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from module.logger import logger
from module.config.deep import deep_get, deep_iter, deep_set
from module.config.utils import filepath_args, write_file as _write_util


CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / 'config'


def filepath_config(config_name: str) -> Path:
    """返回配置文件的完整路径。"""
    return CONFIG_DIR / f'{config_name}.json'


class ConfigUpdater:
    """JSON 配置持久化，支持变更追踪与自动保存。"""

    config_name: str = ''
    data: dict = {}
    modified: dict = {}
    auto_update: bool = True
    _lock: threading.RLock = threading.RLock()

    def __init__(self, config_name: str):
        self.config_name = config_name
        self.data = self._load()
        self.modified = {}

    def _load(self) -> dict:
        """从 JSON 文件加载配置。"""
        path = filepath_config(self.config_name)
        if not path.exists():
            logger.info(f'配置文件不存在，创建默认: {path}')
            data = self._get_defaults()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return data

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 合并默认值确保不缺项
        defaults = self._get_defaults()
        merged = deepcopy(defaults)
        self._deep_merge(merged, data)
        if merged != data:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
        return merged

    def _get_defaults(self) -> dict:
        """从 args.json 提取默认值结构。"""
        args_path = Path(__file__).resolve().parent / 'argument' / 'args.json'
        if not args_path.exists():
            return {}
        with open(args_path, 'r', encoding='utf-8') as f:
            args = json.load(f)
        defaults = {}
        for path, arg in deep_iter(args, depth=3):
            if isinstance(arg, dict) and 'value' in arg:
                deep_set(defaults, path, deepcopy(arg['value']))
        return defaults

    def _deep_merge(self, base: dict, override: dict) -> None:
        """递归合并字典，override 覆盖 base（跳过 None 值防止覆盖默认）。"""
        for key, value in override.items():
            if value is None:
                continue
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = deepcopy(value)

    def save(self) -> None:
        """将当前数据持久化到 JSON 文件。"""
        path = filepath_config(self.config_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def update(self) -> None:
        """将变更（modified）写回 data 并保存。"""
        with self._lock:
            for path, value in self.modified.items():
                deep_set(self.data, path, value)
            self.modified.clear()
            self.save()

    def get(self, key: str, default=None):
        """通过点分隔路径获取配置值。"""
        return deep_get(self.data, key, default=default)

    def set(self, key: str, value: Any) -> None:
        """设置配置值并标记为已修改。"""
        self.modified[key] = value
        if self.auto_update:
            self.update()

    def __getitem__(self, key: str):
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    @staticmethod
    def write_file(config_name: str, data: dict, mod_name: str = 'alas') -> None:
        """写入 JSON 配置文件（ALAS WebUI 兼容接口）。

        Args:
            config_name: 配置名（如 'default'）
            data: 配置数据
            mod_name: mod 名称（E7 固定为 'alas'）
        """
        path = filepath_args(config_name, mod_name)
        _write_util(path, data)
