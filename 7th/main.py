"""
程序入口 - 第七史诗秘密商店自动刷新购买工具

支持三种运行模式：
  有界面: main.py                   （默认，直接运行带日志输出）
  WebUI:  main.py --webui          （Web UI 管理界面）
  ALAS:   main.py --alas           （使用 E7AutoScript + SecretShopTask，带调度器）

不传参数默认走 ALAS 框架（headless），不再走旧 YAML 配置路径。
"""

import argparse
import os
import sys

# PyInstaller 打包后，将 exe 所在目录设为工作目录
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

from module.logger import logger


def main():
    parser = argparse.ArgumentParser(description="第七史诗秘密商店自动刷新购买工具")
    parser.add_argument("--config", default="config.yaml", help="旧配置文件路径（ALAS 模式已忽略）")
    parser.add_argument("--webui", action="store_true", help="启动 Web UI 管理界面")
    parser.add_argument("--alas", action="store_true", help="使用 ALAS 框架模式运行（默认行为）")
    args = parser.parse_args()

    if args.webui:
        _run_webui()
    else:
        # --alas 和无参数都走 ALAS 框架（默认模式）
        _run_alas()


def _run_alas(config_name: str = "default") -> None:
    """使用 ALAS 框架模式运行（headless）。"""
    from alas import E7AutoScript
    logger.info("启动 E7AutoScript（ALAS 框架）...")
    alas = E7AutoScript(config_name=config_name)
    if alas.init():
        alas.run_secret_shop()


def _run_webui() -> None:
    """启动 ALAS 风格 Web UI。"""
    logger.info("启动 WebUI...")
    from gui import run as run_webui
    run_webui()


if __name__ == "__main__":
    main()
