"""
程序入口 - 第七史诗秘密商店自动刷新购买工具

解析命令行参数，初始化 ConfigManager 和 ShopBot，
根据参数决定启动 Web UI 或直接运行。
"""

import argparse
import os
import sys

# PyInstaller 打包后，将 exe 所在目录设为工作目录
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

from config_manager import ConfigManager
from log import logger
from shop_bot import ShopBot


def main():
    parser = argparse.ArgumentParser(description="第七史诗秘密商店自动刷新购买工具")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--webui", action="store_true", help="启动 Web UI 管理界面")
    args = parser.parse_args()

    # Load config

    config = ConfigManager(args.config)
    config.load()

    # Create bot
    bot = ShopBot(config)

    if args.webui:
        try:
            from webui.app import ShopBotGUI
            gui = ShopBotGUI(config, bot)
            gui.start_server(port=config.get().webui_port)
        except Exception as e:
            logger.warning(f"Web UI 启动失败，降级为无 UI 模式: {e}")
            _run_headless(bot)
    else:
        _run_headless(bot)


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
