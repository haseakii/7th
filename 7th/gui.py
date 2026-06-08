"""
E7 GUI — uvicorn 服务器启动器

遵循 ALAS 模式，通过 uvicorn 启动 PyWebIO 应用的 FastAPI ASGI 服务。

用法:
  python gui.py                    # 默认 0.0.0.0:8080
  python gui.py --port 9090        # 自定义端口
  python gui.py --host 127.0.0.1   # 只监听本地
"""

import argparse
import asyncio
import os
import sys
import threading

# ── 修复 sys.path：优先使用 .venv 的包，避免与 ALAS toolkit 冲突 ──
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)  # D:\software\7th
_VENV_SITE = os.path.join(_PROJECT_DIR, '.venv', 'Lib', 'site-packages')
if os.path.isdir(_VENV_SITE):
    # 将 venv site-packages 移到 sys.path 最前面
    if _VENV_SITE in sys.path:
        sys.path.remove(_VENV_SITE)
    sys.path.insert(0, _VENV_SITE)

from module.logger import logger


def run():
    """启动 uvicorn 服务器。"""
    import uvicorn

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="E7 Shop Bot Web Service")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("-p", "--port", type=int, default=8080, help="监听端口")
    parser.add_argument("--electron", action="store_true", help="由 Electron 客户端启动")
    args, _ = parser.parse_known_args()

    logger.info(f"启动 WebUI: http://{args.host}:{args.port}")

    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    from module.webui import app as webui_app

    # webui_app.app 是 module.webui.fastapi.asgi_app 返回的 Starlette ASGI 应用
    # 直接挂载到 FastAPI 下
    fastapi_app = FastAPI(title="E7 Shop Bot")

    # 停止服务 API
    @fastapi_app.middleware("http")
    async def _shutdown_middleware(request, call_next):
        if request.url.path == "/api/shutdown" and request.method == "POST":
            logger.info("收到停止服务请求，正在关闭...")
            threading.Thread(target=lambda: os._exit(0), daemon=True).start()
            return PlainTextResponse("Server shutting down")
        return await call_next(request)

    # PyWebIO 页面路由
    # app() 函数解析参数并返回 Starlette ASGI 应用
    asgi_app = webui_app.app()
    fastapi_app.mount("/", asgi_app)

    uvicorn.run(fastapi_app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    run()
