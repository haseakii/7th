"""
DeployConfig — 部署配置

从 config/deploy.yaml 读取 Git/Python/Pip/Ocr/Discord 等设置。
对应 ALAS DeployConfig，适配 E7 默认值。
"""

from pathlib import Path
from typing import Optional


class ExecutionError(Exception):
    """执行错误，部署流程中发生异常时抛出。"""
    pass


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class DeployConfig:
    """部署配置，管理 Git/Python/Pip/ADB/OCR/Discord/远程访问等设置。

    使用 __getattr__ / __setattr__ 动态访问 _data 字典，
    兼容 ALAS webui config 的 __setattr__ 写入模式。
    """

    _CONFIG_KEYS = {
        'Repository', 'Branch', 'GitExecutable', 'AutoUpdate',
        'PythonExecutable', 'PypiMirror', 'RequirementsFile',
        'UseOcrServer', 'StartOcrServer', 'OcrServerPort', 'OcrClientAddress',
        'EnableReload', 'CheckUpdateInterval', 'AutoRestartTime',
        'DiscordRichPresence',
        'EnableRemoteAccess', 'SSHUser', 'SSHServer', 'Password', 'SSHKeyFilename',
        'WebuiHost', 'WebuiPort', 'Theme', 'Language', 'Run', 'CDN',
    }
    _DEFAULTS = {
        'Repository': '',
        'Branch': 'main',
        'GitExecutable': 'git',
        'AutoUpdate': True,
        'PythonExecutable': 'python',
        'PypiMirror': None,
        'RequirementsFile': 'requirements.txt',
        'UseOcrServer': False,
        'StartOcrServer': False,
        'OcrServerPort': 22268,
        'OcrClientAddress': '127.0.0.1:22268',
        'EnableReload': True,
        'CheckUpdateInterval': 5,
        'AutoRestartTime': '03:50',
        'DiscordRichPresence': False,
        'EnableRemoteAccess': False,
        'SSHUser': None,
        'SSHServer': None,
        'Password': None,
        'SSHKeyFilename': None,
        'WebuiHost': '0.0.0.0',
        'WebuiPort': 8080,
        'Theme': 'dark',
        'Language': 'zh-CN',
        'Run': '',
        'CDN': False,
    }

    def __init__(self, config_path: Optional[str] = None, file=None):
        # 绕过 __setattr__ 设置内部属性
        object.__setattr__(self, '_path', Path(config_path) if config_path else (
            Path(file) if file else CONFIG_DIR / 'deploy.yaml'
        ))
        object.__setattr__(self, '_data', self._load())

    def __getattr__(self, name: str):
        if name in self._CONFIG_KEYS:
            return self._data.get(name, self._DEFAULTS.get(name))
        raise AttributeError(f"'DeployConfig' has no attribute '{name}'")

    def __setattr__(self, name: str, value):
        if name in self._CONFIG_KEYS:
            self._data[name] = value
        else:
            object.__setattr__(self, name, value)

    def _load(self) -> dict:
        path = object.__getattribute__(self, '_path')
        if not path.exists():
            return dict(self._DEFAULTS)
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return {**self._DEFAULTS, **(yaml.safe_load(f) or {})}
        except Exception:
            return dict(self._DEFAULTS)
