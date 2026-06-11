"""E7 submodule stubs — ALAS 子模块管理的简化版本"""

from module.submodule.submodule import load_config, load_mod
from module.submodule.utils import (
    get_available_func,
    get_available_mod,
    get_available_mod_func,
    get_config_mod,
    get_func_mod,
    list_mod_dir,
    list_mod_instance,
)

__all__ = [
    'load_config', 'load_mod',
    'get_available_func', 'get_available_mod', 'get_available_mod_func',
    'get_config_mod', 'get_func_mod', 'list_mod_dir', 'list_mod_instance',
]
