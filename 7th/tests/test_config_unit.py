"""
ConfigManager 单元测试

覆盖需求:
- 2.1: 从 config.yaml 加载配置
- 2.2: 支持配置各参数
- 2.3: 配置文件不存在时生成默认模板
- 2.4: 无效 YAML 格式抛出异常
- 2.5: 物品购买列表映射
- 2.6: 加载后日志输出关键配置项
- 2.7: Web UI 配置变更持久化
- 2.8: 线程安全读写
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# 确保可以导入 7th 下的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config_manager import (
    AppConfig,
    ConfigManager,
    DeviceConfig,
    ShopConfig,
)


@pytest.fixture
def tmp_config_path(tmp_path):
    """返回临时目录下的配置文件路径"""
    return str(tmp_path / "config.yaml")


class TestDataclassDefaults:
    """测试数据类默认值 (需求 2.2)"""

    def test_shop_config_defaults(self):
        cfg = ShopConfig()
        assert cfg.buy_bookmarks is True
        assert cfg.buy_mystic_medals is True
        assert cfg.buy_equipment is False
        assert cfg.buy_fodder is False
        assert cfg.max_refresh_count == 200
        assert cfg.gold_threshold == 0
        assert cfg.skystone_threshold == 0

    def test_device_config_defaults(self):
        cfg = DeviceConfig()
        assert cfg.serial == "127.0.0.1:16384"
        assert cfg.screenshot_method == "auto"
        assert cfg.control_method == "auto"
        assert cfg.ocr_method == "rapidocr"

    def test_app_config_defaults(self):
        cfg = AppConfig()
        assert isinstance(cfg.device, DeviceConfig)
        assert isinstance(cfg.shop, ShopConfig)
        assert cfg.webui_port == 8080


class TestLoadConfig:
    """测试配置加载 (需求 2.1, 2.3, 2.4)"""

    def test_load_generates_default_when_missing(self, tmp_config_path):
        """需求 2.3: 配置文件不存在时生成默认模板"""
        mgr = ConfigManager(tmp_config_path)
        cfg = mgr.load()

        assert Path(tmp_config_path).exists()
        assert cfg == AppConfig()

    def test_generated_default_is_valid_yaml(self, tmp_config_path):
        """需求 2.3: 生成的默认模板是有效 YAML"""
        mgr = ConfigManager(tmp_config_path)
        mgr.load()

        with open(tmp_config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        assert isinstance(raw, dict)
        assert "device" in raw
        assert "shop" in raw
        assert "webui_port" in raw

    def test_load_existing_config(self, tmp_config_path):
        """需求 2.1: 从 YAML 文件加载配置"""
        data = {
            "device": {"serial": "192.168.1.100:5555", "screenshot_method": "uiautomator2", "control_method": "ADB"},
            "shop": {"buy_bookmarks": False, "buy_mystic_medals": True, "max_refresh_count": 100},
            "webui_port": 9090,
        }
        with open(tmp_config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        mgr = ConfigManager(tmp_config_path)
        cfg = mgr.load()

        assert cfg.device.serial == "192.168.1.100:5555"
        assert cfg.device.screenshot_method == "uiautomator2"
        assert cfg.shop.buy_bookmarks is False
        assert cfg.shop.max_refresh_count == 100
        assert cfg.webui_port == 9090

    def test_load_invalid_yaml_raises(self, tmp_config_path):
        """需求 2.4: 无效 YAML 格式抛出异常"""
        with open(tmp_config_path, "w", encoding="utf-8") as f:
            f.write(":\n  invalid: [yaml\n  broken")

        mgr = ConfigManager(tmp_config_path)
        with pytest.raises(ValueError, match="YAML 格式错误"):
            mgr.load()

    def test_load_non_dict_yaml_raises(self, tmp_config_path):
        """需求 2.4: YAML 内容不是字典时抛出异常"""
        with open(tmp_config_path, "w", encoding="utf-8") as f:
            f.write("- item1\n- item2\n")

        mgr = ConfigManager(tmp_config_path)
        with pytest.raises(ValueError, match="期望字典"):
            mgr.load()


class TestSaveConfig:
    """测试配置保存 (需求 2.7)"""

    def test_save_creates_file(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        mgr.save()
        assert Path(tmp_config_path).exists()

    def test_save_roundtrip(self, tmp_config_path):
        """保存后重新加载应得到相同配置"""
        mgr = ConfigManager(tmp_config_path)
        mgr._config.shop.buy_bookmarks = False
        mgr._config.device.serial = "10.0.0.1:5555"
        mgr.save()

        mgr2 = ConfigManager(tmp_config_path)
        cfg = mgr2.load()
        assert cfg.shop.buy_bookmarks is False
        assert cfg.device.serial == "10.0.0.1:5555"


class TestGetConfig:
    """测试线程安全获取 (需求 2.8)"""

    def test_get_returns_copy(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        cfg1 = mgr.get()
        cfg2 = mgr.get()
        assert cfg1 == cfg2
        assert cfg1 is not cfg2

    def test_get_copy_mutation_does_not_affect_original(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        cfg = mgr.get()
        cfg.shop.buy_bookmarks = False
        assert mgr.get().shop.buy_bookmarks is True


class TestUpdateConfig:
    """测试配置更新 (需求 2.7, 2.8)"""

    def test_update_shop_key(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        mgr.update("shop", "buy_bookmarks", False)
        assert mgr.get().shop.buy_bookmarks is False

    def test_update_device_key(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        mgr.update("device", "serial", "10.0.0.1:5555")
        assert mgr.get().device.serial == "10.0.0.1:5555"

    def test_update_app_key(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        mgr.update("app", "webui_port", 9090)
        assert mgr.get().webui_port == 9090

    def test_update_persists_to_file(self, tmp_config_path):
        """需求 2.7: 更新后自动持久化"""
        mgr = ConfigManager(tmp_config_path)
        mgr.update("shop", "max_refresh_count", 500)

        mgr2 = ConfigManager(tmp_config_path)
        cfg = mgr2.load()
        assert cfg.shop.max_refresh_count == 500

    def test_update_invalid_section_raises(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        with pytest.raises(KeyError, match="未知的配置分组"):
            mgr.update("invalid", "key", "value")

    def test_update_invalid_key_raises(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        with pytest.raises(KeyError, match="没有属性"):
            mgr.update("shop", "nonexistent_key", True)


class TestGetBuyList:
    """测试购买列表映射 (需求 2.5)"""

    def test_default_buy_list(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        buy_list = mgr.get_buy_list()
        assert buy_list == {
            "bookmarks": True,
            "mystic_medals": True,
            "equipment": False,
            "fodder": False,
        }

    def test_buy_list_reflects_updates(self, tmp_config_path):
        mgr = ConfigManager(tmp_config_path)
        mgr.update("shop", "buy_equipment", True)
        buy_list = mgr.get_buy_list()
        assert buy_list["equipment"] is True


class TestLogConfig:
    """测试配置加载后日志输出 (需求 2.6)"""

    def test_load_logs_key_config(self, tmp_config_path):
        """需求 2.6: 加载后日志输出关键配置项"""
        mgr = ConfigManager(tmp_config_path)
        with patch("config_manager.logger") as mock_logger:
            mgr.load()
            log_calls = [str(c) for c in mock_logger.info.call_args_list]
            combined = " ".join(log_calls)
            assert "127.0.0.1:16384" in combined
            assert "auto" in combined
