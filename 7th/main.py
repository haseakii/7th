"""Program entry point for E7 Shop Bot.

Default mode starts the ALAS-style scheduler. Use ``--webui`` to start the
management UI instead.
"""

import argparse
import os
import sys

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from module.logger import logger


def main():
    parser = argparse.ArgumentParser(description="E7 Shop Bot")
    parser.add_argument("--config", default=None, help="ALAS config name, defaults to 'default'")
    parser.add_argument("--config-name", default=None, help="ALAS config name, overrides --config")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--webui", action="store_true", help="Start Web UI")
    mode.add_argument("--alas", action="store_true", help="Start ALAS scheduler mode (default)")
    args = parser.parse_args()

    if args.webui:
        _run_webui()
    else:
        _run_alas(config_name=args.config_name or args.config or "default")


def _run_alas(config_name: str = "default") -> None:
    """Run in ALAS scheduler mode."""
    from alas import E7AutoScript

    logger.info(f"Starting E7AutoScript (ALAS scheduler), config={config_name}")
    alas = E7AutoScript(config_name=config_name)
    try:
        if alas.init():
            alas.loop()
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，正在退出")
        alas.stop()
    finally:
        if alas.device is not None:
            try:
                alas.device.disconnect()
            except Exception as e:
                logger.warning(f"断开设备连接异常: {e}")


def _run_webui() -> None:
    """Start the ALAS-style Web UI."""
    logger.info("Starting WebUI...")
    from gui import run as run_webui

    run_webui()


if __name__ == "__main__":
    main()
