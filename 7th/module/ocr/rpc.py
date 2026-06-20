"""
OCR RPC 客户端（本地模式）

本项目仅使用本地 OCR，此文件保留兼容性存根。
"""

from module.logger import logger


def start_ocr_server_process(port: int = 22268) -> None:
    """启动 OCR RPC 服务进程（E7 本地模式，无需启动）。"""
    logger.debug(f"OCR RPC server start skipped (local mode, port={port})")


def stop_ocr_server_process() -> None:
    """停止 OCR RPC 服务进程。"""
    pass
