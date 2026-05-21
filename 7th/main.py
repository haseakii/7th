"""
程序入口 - 第七史诗秘密商店自动刷新购买工具

支持两种运行模式：
  传统模式: main.py [--webui]        （使用 ConfigManager + ShopBot）
  ALAS 模式: main.py --alas             （使用 E7AutoScript + SecretShopTask）
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
        _run_webui(args.config)
    else:
        _run_headless(args.config)


def _run_alas(config_path: str) -> None:
    """使用 ALAS 框架模式运行。"""
    from alas import E7AutoScript
    logger.info("启动 ALAS 框架模式...")
    alas = E7AutoScript(config_name=config_path)
    if alas.init():
        alas.run_secret_shop()


def _run_webui(config_path: str) -> None:
    """启动 Web UI 界面。"""
    from config_manager import ConfigManager
    from shop_bot import ShopBot

    config = ConfigManager(config_path)
    config.load()
    bot = ShopBot(config)

    try:
        from webui.app import ShopBotGUI
        gui = ShopBotGUI(config, bot)
        gui.start_server(port=config.get().webui_port)
    except Exception as e:
        logger.warning(f"Web UI 启动失败: {e}")
        # 降级为无 UI 模式
        _run_headless(config_path)


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


def _run_headless(bot):
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
