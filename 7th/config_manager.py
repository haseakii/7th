"""
ConfigManager 配置管理器

线程安全的配置管理，支持 YAML 读写、运行时更新和自动持久化。
包含 ShopConfig、DeviceConfig、AppConfig 数据类定义。
"""

import copy
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml

from log import logger


@dataclass
class ShopConfig:
    """商店购买配置"""
    buy_bookmarks: bool = True
    buy_mystic_medals: bool = True
    buy_equipment: bool = False
    buy_fodder: bool = False
    max_refresh_count: int = 200
    gold_threshold: int = 0
    skystone_threshold: int = 0
    max_bookmarks: int = 0          # 购买N个书签后停止（0=不限）
    max_mystic_medals: int = 0      # 购买N个神秘奖章后停止（0=不限）
    max_skystone_spend: int = 0     # 刷新消耗N个天空石后停止（0=不限）


@dataclass
class DeviceConfig:
    """设备连接配置"""
    serial: str = "127.0.0.1:16384"
    screenshot_method: str = "auto"
    control_method: str = "auto"
    ocr_method: str = "rapidocr"


@dataclass
class AppConfig:
    """完整应用配置"""
    device: DeviceConfig = field(default_factory=DeviceConfig)
    shop: ShopConfig = field(default_factory=ShopConfig)
    webui_port: int = 8080


class ConfigManager:
    """线程安全的配置管理器，支持 YAML 读写"""

    def __init__(self, config_path: str = "config.yaml"):
        self._config: AppConfig = AppConfig()
        self._config_path = config_path
        self._lock = threading.RLock()

    def load(self) -> AppConfig:
        """从 YAML 文件加载配置，文件不存在则生成默认模板"""
        path = Path(self._config_path)

        if not path.exists():
            logger.info(f"配置文件不存在，生成默认模板: {self._config_path}")
            self._config = AppConfig()
            self.save()
            self._log_config()
            return copy.deepcopy(self._config)

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 格式错误: {e}") from e

        if not isinstance(raw, dict):
            raise ValueError(f"YAML 格式错误: 期望字典，得到 {type(raw).__name__}")

        with self._lock:
            device_data = raw.get("device", {})
            shop_data = raw.get("shop", {})
            self._config = AppConfig(
                device=DeviceConfig(**{
                    k: v for k, v in device_data.items()
                    if k in DeviceConfig.__dataclass_fields__
                }),
                shop=ShopConfig(**{
                    k: v for k, v in shop_data.items()
                    if k in ShopConfig.__dataclass_fields__
                }),
                webui_port=raw.get("webui_port", 8080),
            )

        self._log_config()
        return copy.deepcopy(self._config)

    def save(self) -> None:
        """将当前配置持久化到 YAML 文件"""
        with self._lock:
            data = asdict(self._config)

        path = Path(self._config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def get(self) -> AppConfig:
        """线程安全地获取当前配置的副本"""
        with self._lock:
            return copy.deepcopy(self._config)

    def update(self, section: str, key: str, value: Any) -> None:
        """线程安全地更新单个配置项并自动持久化"""
        with self._lock:
            if section == "device":
                if not hasattr(self._config.device, key):
                    raise KeyError(f"DeviceConfig 没有属性 '{key}'")
                setattr(self._config.device, key, value)
            elif section == "shop":
                if not hasattr(self._config.shop, key):
                    raise KeyError(f"ShopConfig 没有属性 '{key}'")
                setattr(self._config.shop, key, value)
            elif section == "app":
                if not hasattr(self._config, key):
                    raise KeyError(f"AppConfig 没有属性 '{key}'")
                setattr(self._config, key, value)
            else:
                raise KeyError(f"未知的配置分组: '{section}'")
            self.save()

    def get_buy_list(self) -> Dict[str, bool]:
        """返回物品购买列表映射 {物品类型: 是否启用}"""
        with self._lock:
            shop = self._config.shop
            return {
                "bookmarks": shop.buy_bookmarks,
                "mystic_medals": shop.buy_mystic_medals,
                "equipment": shop.buy_equipment,
                "fodder": shop.buy_fodder,
            }

    def _log_config(self) -> None:
        """日志输出关键配置项"""
        cfg = self._config
        logger.info(f"配置已加载 - 设备: {cfg.device.serial}, "
                     f"截图: {cfg.device.screenshot_method}, "
                     f"控制: {cfg.device.control_method}, "
                     f"OCR: {cfg.device.ocr_method}")
        logger.info(f"购买列表 - 书签: {cfg.shop.buy_bookmarks}, "
                     f"神秘奖章: {cfg.shop.buy_mystic_medals}, "
                     f"装备: {cfg.shop.buy_equipment}, "
                     f"狗粮: {cfg.shop.buy_fodder}")
        logger.info(f"刷新上限: {cfg.shop.max_refresh_count}, "
                     f"天空石阈值: {cfg.shop.skystone_threshold}, "
                     f"金币阈值: {cfg.shop.gold_threshold}, "
                     f"书签上限: {cfg.shop.max_bookmarks or '不限'}, "
                     f"神秘上限: {cfg.shop.max_mystic_medals or '不限'}, "
                     f"天空石消耗上限: {cfg.shop.max_skystone_spend or '不限'}")
