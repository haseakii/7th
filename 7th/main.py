"""
程序入口 - 第七史诗秘密商店自动刷新购买工具

支持两种运行模式：
  有界面: main.py --webui        （Web UI 管理界面）
  无界面: main.py                （直接运行，无 UI）
  ALAS:   main.py --alas         （使用 E7AutoScript + SecretShopTask）
"""

import argparse
import os
import sys

# PyInstaller 打包后，将 exe 所在目录设为工作目录
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

from log import logger


def main():
    parser = argparse.ArgumentParser(description="第七史诗秘密商店自动刷新购买工具")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--webui", action="store_true", help="启动 Web UI 管理界面")
    parser.add_argument("--alas", action="store_true", help="使用 ALAS 框架模式运行")
    args = parser.parse_args()

    if args.alas:
        _run_alas(args.config)
    elif args.webui:
        _run_webui()
    else:
        _run_headless(args.config)


def _run_alas(config_path: str) -> None:
    """使用 ALAS 框架模式运行。"""
    from pathlib import Path
    from alas import E7AutoScript
    logger.info("启动 ALAS 框架模式...")
    # config_path 用于触发旧 YAML 迁移，config_name 用于 JSON 配置名
    config_name = Path(config_path).stem if config_path else "default"
    alas = E7AutoScript(config_name=config_name, config_path=config_path)
    if alas.init():
        alas.run_secret_shop()


def _run_webui() -> None:
    """启动 ALAS 风格 Web UI。"""
    logger.info("启动 WebUI...")
    from gui import run as run_webui
    run_webui()


def _run_headless(config_path: str) -> None:
    """直接运行（无 Web UI）。"""
    from config_manager import ConfigManager
    from shop_bot import ShopBot

    config = ConfigManager(config_path)
    config.load()
    bot = ShopBot(config)
    bot.start()
    try:
        bot._thread.join()
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，正在停止...")
        bot.stop()
        if bot._thread:
            bot._thread.join(timeout=30)
    logger.info("程序退出")


if __name__ == "__main__":
    main()
