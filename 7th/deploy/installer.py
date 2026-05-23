"""
Installer — 安装协调器

编排 Git init → Pip install 的完整安装流程。
"""

from typing import Optional

from deploy.config import DeployConfig
from deploy.git import GitManager
from deploy.pip import PipManager
from log import logger


class Installer:
    """安装协调器，执行 git init → pip install 流程。"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = DeployConfig(config_path)
        self.git = GitManager(config_path)
        self.pip = PipManager(config_path)

    def install(self, repo: Optional[str] = None) -> bool:
        """执行完整安装。"""
        logger.hr("E7 Shop Bot 安装", level=0)

        # Git 初始化
        repo = repo or self.config.Repository
        if repo:
            branch = self.config.Branch
            logger.info(f"初始化 Git 仓库: {repo} ({branch})")
            if not self.git.init(repo, branch):
                logger.warning("Git 初始化失败，跳过")
        else:
            logger.info("未配置仓库，跳过 Git 初始化")

        # Pip 安装依赖
        missing = self.pip.get_missing()
        if missing:
            logger.info(f"需要安装 {len(missing)} 个依赖")
            if not self.pip.install():
                logger.error("依赖安装失败")
                return False
        else:
            logger.info("所有依赖已满足")

        logger.info("安装完成！")
        return True

    def update(self) -> bool:
        """执行更新：git pull → pip install。"""
        logger.hr("E7 Shop Bot 更新", level=0)

        # Git 拉取更新
        if self.config.Repository:
            if not self.git.fetch():
                logger.warning("Git fetch 失败，跳过更新")
                return False
            if not self.git.has_update():
                logger.info("已经是最新版本")
                return True
            if not self.git.pull():
                logger.error("Git pull 失败")
                return False
        else:
            logger.info("未配置仓库，跳过 Git 更新")

        # Pip 更新依赖
        self.pip.install()

        logger.info("更新完成！请重启程序。")
        return True
