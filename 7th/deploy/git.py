"""
GitManager — Git 仓库同步管理

支持 init/fetch/pull/reset 和增量更新。
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from deploy.config import DeployConfig
from module.logger import logger


class GitManager(DeployConfig):
    """Git 操作封装，继承 DeployConfig 获取仓库设置。"""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)
        self._ensure_git()

    def _ensure_git(self) -> str:
        """确保 git 可执行文件可用。"""
        exe = self.GitExecutable
        if os.path.exists(exe):
            return exe
        # fallback to PATH git
        return "git"

    def _run(self, cmd: list, **kwargs) -> subprocess.CompletedProcess:
        """运行 git 命令。"""
        git = self._ensure_git()
        full_cmd = [git] + cmd
        logger.info(f"Git: {' '.join(full_cmd)}")
        return subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            cwd=kwargs.pop("cwd", None),
            **kwargs,
        )

    def init(self, repo: str, branch: str = "main") -> bool:
        """初始化 git 仓库并拉取远程代码。"""
        logger.hr("Git Init", level=1)

        # git init
        ret = self._run(["init"])
        if ret.returncode != 0:
            logger.error(f"Git init 失败: {ret.stderr}")
            return False

        # git remote
        self._run(["remote", "add", "origin", repo])
        logger.info(f"远程仓库: {repo}")

        # git fetch
        ret = self._run(["fetch", "origin", branch])
        if ret.returncode != 0:
            logger.error(f"Git fetch 失败: {ret.stderr}")
            return False

        # git checkout
        ret = self._run(["checkout", "-f", branch])
        if ret.returncode != 0:
            logger.error(f"Git checkout 失败: {ret.stderr}")
            return False

        logger.info("Git 初始化完成")
        return True

    def fetch(self) -> bool:
        """获取远程更新。"""
        ret = self._run(["fetch", "origin"])
        if ret.returncode != 0:
            logger.warning(f"Git fetch 失败: {ret.stderr}")
            return False
        logger.info("Git fetch 完成")
        return True

    def pull(self) -> bool:
        """拉取远程更新并合并。"""
        ret = self._run(["pull", "--ff-only"])
        if ret.returncode != 0:
            logger.warning(f"Git pull 失败: {ret.stderr}")
            return False
        logger.info("Git pull 完成")
        return True

    def reset(self, branch: str = "main") -> bool:
        """硬重置到远程分支状态。"""
        ret = self._run(["reset", "--hard", f"origin/{branch}"])
        if ret.returncode != 0:
            logger.error(f"Git reset 失败: {ret.stderr}")
            return False
        logger.info("Git reset 完成")
        return True

    def current_commit(self) -> str:
        """获取当前 commit hash。"""
        ret = self._run(["rev-parse", "HEAD"])
        return ret.stdout.strip() if ret.returncode == 0 else ""

    def remote_commit(self, branch: str = "main") -> str:
        """获取远程分支的最新 commit hash。"""
        ret = self._run(["rev-parse", f"origin/{branch}"])
        return ret.stdout.strip() if ret.returncode == 0 else ""

    def has_update(self, branch: str = "main") -> bool:
        """检查是否有可用更新。"""
        local = self.current_commit()
        remote = self.remote_commit(branch)
        if local and remote:
            return local != remote
        return False
