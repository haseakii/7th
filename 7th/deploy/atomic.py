"""
原子文件操作 — Windows 安全文件替换

确保文件写入的原子性和断电安全。
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable


def atomic_write(path: str, content: bytes) -> None:
    """原子写入文件：先写临时文件，再重命名覆盖。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_replace(src: str, dst: str) -> None:
    """原子替换文件。"""
    os.replace(src, dst)


def safe_rmtree(path: str, retries: int = 3) -> bool:
    """安全删除目录树，带重试。"""
    for i in range(retries):
        try:
            shutil.rmtree(path)
            return True
        except PermissionError:
            if i < retries - 1:
                import time
                time.sleep(0.5)
            else:
                return False
    return False
