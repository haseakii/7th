"""
Installer — 安装协调器

编排 Venv → Git → Pip 的完整安装/更新流程。
设计为 bootstrapper exe 的入口，提供和 ALAS 相同的"下载即运行"体验。
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from deploy.config import DeployConfig
from deploy.git import GitManager
from deploy.pip import PipManager
from module.logger import logger

# 项目根目录 — installer.py 所在 deploy/ 的上级
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 跨平台 venv Python 路径
if sys.platform == "win32":
    _VENV_PYTHON = _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
else:
    _VENV_PYTHON = _PROJECT_ROOT / ".venv" / "bin" / "python"


class Installer:
    """安装协调器。

    使用方式：
        首次：   python deploy/installer.py          # 自动创建 venv + 装依赖 + git clone
        更新：   python deploy/installer.py --update  # git pull + pip install
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config = DeployConfig(config_path)
        self.git = GitManager(config_path)
        self.pip = PipManager(config_path)
        self._venv_path = _PROJECT_ROOT / ".venv"
        self._venv_python = _VENV_PYTHON

    @property
    def venv_ready(self) -> bool:
        return self._venv_python.is_file()

    def _ensure_venv(self) -> bool:
        """创建/确保 .venv 虚拟环境存在。"""
        if self.venv_ready:
            logger.info(f"虚拟环境已就绪: {self._venv_path}")
            return True

        logger.hr("创建虚拟环境", level=1)
        logger.info(f"路径: {self._venv_path}")
        logger.info(f"Python: {sys.executable}")

        ret = subprocess.run(
            [sys.executable, "-m", "venv", str(self._venv_path)],
            capture_output=True, text=True, timeout=120,
        )
        if ret.returncode != 0:
            logger.error(f"创建虚拟环境失败: {ret.stderr}")
            return False

        # 升级 pip
        subprocess.run(
            [str(self._venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True, timeout=60,
        )

        logger.info("虚拟环境创建完成")
        return True

    def _pip_install(self) -> bool:
        """在 venv 中安装依赖。输出 pip 进度到终端。"""
        req_file = _PROJECT_ROOT / "requirements.txt"
        if not req_file.exists():
            logger.warning("requirements.txt 不存在，跳过")
            return True

        logger.hr("安装 Python 依赖", level=1)
        logger.info("下载大包（如 paddleocr、onnxruntime）可能需要几分钟，请耐心等待...")
        ret = subprocess.run(
            [str(self._venv_python), "-m", "pip", "install", "-r", str(req_file)],
            # 不捕获输出，让 pip 进度直接显示在终端
            timeout=1800,
        )
        if ret.returncode != 0:
            logger.error("依赖安装失败")
            return False

        logger.info("依赖安装完成")
        return True

    def install(self, repo: Optional[str] = None) -> bool:
        """执行完整安装流程。"""
        logger.hr("E7 Shop Bot 安装", level=0)

        # 1. 虚拟环境
        if not self._ensure_venv():
            logger.error("虚拟环境创建失败")
            return False

        # 2. Git 初始化
        repo = repo or self.config.Repository
        if repo:
            branch = self.config.Branch
            logger.info(f"初始化 Git 仓库: {repo} ({branch})")
            if not self.git.init(repo, branch):
                logger.warning("Git 初始化失败，跳过")
        else:
            logger.info("未配置仓库，跳过 Git 初始化")

        # 3. 安装依赖
        if not self._pip_install():
            return False

        logger.info("安装完成！")
        return True

    def update(self) -> bool:
        """执行更新：git pull → pip install。"""
        logger.hr("E7 Shop Bot 更新", level=0)

        if not self.venv_ready:
            logger.error("虚拟环境不存在，请先运行 install")
            return False

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
        self._pip_install()

        logger.info("更新完成！请重启程序。")
        return True

    def launch_gui(self) -> None:
        """通过 venv Python 启动 WebUI，替换当前进程。

        Windows 上用 subprocess.Popen + os._exit(0) 避免孤儿进程。
        Unix 上直接用 os.execv 替换进程镜像。
        """
        if not self.venv_ready:
            logger.error("虚拟环境未就绪，请先运行 install")
            return

        gui_py = _PROJECT_ROOT / "gui.py"
        if not gui_py.exists():
            logger.error(f"gui.py 不存在: {gui_py}")
            return

        logger.info(f"启动 WebUI: {gui_py}")

        if sys.platform == "win32":
            subprocess.Popen(
                [str(self._venv_python), str(gui_py)],
                cwd=str(_PROJECT_ROOT),
            )
            os._exit(0)
        else:
            os.execv(
                str(self._venv_python),
                [str(self._venv_python), str(gui_py)],
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="E7 Shop Bot 安装器")
    parser.add_argument("--update", action="store_true", help="更新模式")
    parser.add_argument("--repo", type=str, help="Git 仓库地址")
    args = parser.parse_args()

    inst = Installer()
    if args.update:
        inst.update()
    else:
        inst.install(repo=args.repo)
        inst.launch_gui()
