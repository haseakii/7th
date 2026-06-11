"""
E7 submodule utils — ALAS 子模块工具函数（适配版）

参照 ALAS 源码，E7 没有多 mod 多游戏支持，所有返回值针对单实例简化。
"""

import os
from pathlib import Path

MOD_DICT = {
    # E7 无多 mod，保留空字典
}
MOD_FUNC_DICT = {
    'SecretShop': 'alas',
}
MOD_CONFIG_DICT: dict = {}


def get_available_func():
    """返回 E7 可用的功能列表。"""
    return ('SecretShop',)


def get_available_mod():
    """返回可用 mod 集合。"""
    return set(MOD_DICT)


def get_available_mod_func():
    """返回可用 mod 功能集合。"""
    return set(MOD_FUNC_DICT)


def get_func_mod(func):
    """返回功能所属的 mod。"""
    return MOD_FUNC_DICT.get(func, 'alas')


def list_mod_dir():
    """列出 mod 目录映射。"""
    return list(MOD_DICT.items())


def get_mod_dir(name):
    """获取 mod 的目录名。"""
    return MOD_DICT.get(name)


def get_mod_filepath(name):
    """获取 mod 的文件路径。"""
    return os.path.join('./submodule', get_mod_dir(name))


def list_mod_template():
    """列出 template-{mod}.json 模板（E7 无多 mod 模板）。"""
    out = []
    config_dir = os.path.join(os.path.dirname(__file__), '../../config')
    if os.path.exists(config_dir):
        for file in os.listdir(config_dir):
            name, extension = os.path.splitext(file)
            config_name, mod_name = os.path.splitext(name)
            mod_name = mod_name[1:]
            if config_name == 'template' and extension == '.json' and mod_name != '':
                out.append(f'{config_name}-{mod_name}')
    return out


def list_mod_instance():
    """列出已创建的配置实例（E7：扫描 config/ 下的 .json）。"""
    global MOD_CONFIG_DICT
    MOD_CONFIG_DICT.clear()
    out = []
    config_dir = Path(__file__).resolve().parent.parent.parent / 'config'
    if config_dir.exists():
        for file in config_dir.iterdir():
            if file.suffix != '.json':
                continue
            name = file.stem
            # 跳过 args/menu/template 等系统文件
            if name in ('args', 'menu', 'template'):
                continue
            if '-' in name:
                config_name, mod_name = name.rsplit('-', 1)
                out.append(config_name)
                MOD_CONFIG_DICT[config_name] = mod_name
            else:
                out.append(name)
                MOD_CONFIG_DICT[name] = 'alas'

    # E7 fallback：没有实例时返回 default
    if not out:
        out = ['default']
        MOD_CONFIG_DICT['default'] = 'alas'

    return out


def get_config_mod(config_name):
    """
    返回配置所属的 mod 名称。

    Args:
        config_name (str):
    """
    if config_name.startswith('template-'):
        return config_name.replace('template-', '')
    try:
        return MOD_CONFIG_DICT[config_name]
    except KeyError:
        return 'alas'
