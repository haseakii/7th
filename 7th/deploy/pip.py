"""
PipManager — Python 依赖管理

对比已安装依赖 vs 所需依赖，按需安装/升级。
"""

import importlib.metadata
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from deploy.config import DeployConfig
from module.logger import logger


class PipManager(DeployConfig):
    """Python 依赖安装管理。"""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)

    def get_installed(self) -> set:
        """返回已安装的包名集合。"""
        return {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}

    def get_required(self) -> List[str]:
        """读取 requirements.txt 返回所需依赖列表。"""
        req_file = Path(self.RequirementsFile)
        if not req_file.exists():
            return []
        with open(req_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    def get_missing(self) -> List[str]:
        """返回缺失的依赖列表。"""
        installed = self.get_installed()
        required = self.get_required()
        missing = []
        for req in required:
            # 处理版本限定符: package>=1.0, package==1.0
            pkg_name = req.split(">=")[0].split("==")[0].split("<=")[0].split("!=")[0].strip()
            if pkg_name.lower() not in installed:
                missing.append(req)
        return missing

    def install(self, packages: Optional[List[str]] = None) -> bool:
        """安装依赖。"""
        if packages is None:
            packages = self.get_missing()
        if not packages:
            logger.info("所有依赖已满足，无需安装")
            return True

        cmd = [sys.executable, "-m", "pip", "install"] + packages
        mirror = self.PypiMirror
        if mirror:
            cmd += ["-i", mirror]

        logger.info(f"安装 {len(packages)} 个依赖...")
        ret = subprocess.run(cmd, capture_output=True, text=True)
        if ret.returncode != 0:
            logger.error(f"依赖安装失败: {ret.stderr}")
            return False
        logger.info("依赖安装完成")
        return True

    def update(self) -> bool:
        """升级所有已安装依赖。"""
        required = self.get_required()
        if not required:
            return True
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + required
        mirror = self.PypiMirror
        if mirror:
            cmd += ["-i", mirror]
        ret = subprocess.run(cmd, capture_output=True, text=True)
        return ret.returncode == 0
