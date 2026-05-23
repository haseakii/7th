"""
DeployConfig — 部署配置

从 config/deploy.yaml 读取 Git/Python/Pip 设置。
"""

from pathlib import Path
from typing import Optional


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class DeployConfig:
    """部署配置，管理 Git/Python/Pip/ADB 路径和设置。"""

    def __init__(self, config_path: Optional[str] = None):
        self._path = Path(config_path) if config_path else CONFIG_DIR / "deploy.yaml"
        self._data = self._load()

    # Git
    @property
    def Repository(self) -> str:
        return self._data.get("Repository", "")

    @property
    def Branch(self) -> str:
        return self._data.get("Branch", "main")

    @property
    def GitExecutable(self) -> str:
        return self._data.get("GitExecutable", "git")

    @property
    def AutoUpdate(self) -> bool:
        return self._data.get("AutoUpdate", True)

    # Python
    @property
    def PythonExecutable(self) -> str:
        return self._data.get("PythonExecutable", "python")

    @property
    def PypiMirror(self) -> Optional[str]:
        return self._data.get("PypiMirror", None)

    @property
    def RequirementsFile(self) -> str:
        return self._data.get("RequirementsFile", "requirements.txt")

    # Webui
    @property
    def WebuiHost(self) -> str:
        return self._data.get("WebuiHost", "0.0.0.0")

    @property
    def WebuiPort(self) -> int:
        return int(self._data.get("WebuiPort", 8080))

    @property
    def Theme(self) -> str:
        return self._data.get("Theme", "dark")

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            import yaml
            with open(self._path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
