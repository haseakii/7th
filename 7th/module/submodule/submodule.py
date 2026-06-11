"""
E7 submodule — ALAS 子模块管理（适配版）

参照 ALAS 源码，E7 只有单一 mod（alas），所有配置无多游戏后缀。
"""

import importlib

from module.logger import logger
from module.submodule.utils import *


def load_mod(name):
    """加载一个 mod 模块。E7 只有 alas，无法导入时返回 None。"""
    dir_name = get_mod_dir(name)
    if dir_name is None:
        logger.critical(f"No function matched: {name}")
        return None

    return importlib.import_module('.' + name, 'submodule.' + dir_name)


def load_config(config_name):
    """加载 E7 配置，返回 AzurLaneConfig 实例。"""
    from module.config.config import AzurLaneConfig

    mod_name = get_config_mod(config_name)
    # E7 固定为 alas，直接返回 AzurLaneConfig（我们的存根）
    return AzurLaneConfig(config_name)
