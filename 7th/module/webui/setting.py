"""
State — 全局共享状态单例

存储 WebUI 的运行状态、主题、重启事件等。
"""

import threading
from typing import Optional


class State:
    """全局共享状态，所有属性为类变量。"""

    # 重启事件（由 gui.py 设置）
    restart_event: Optional[threading.Event] = None

    # 主题
    theme: str = "dark"

    # 部署配置（由 deploy/config.py 设置）
    deploy_config = None

    # 日志
    logger = None

    # ShopBot 实例（页面刷新后仍保留）
    bot = None

    # 统计数据缓存（页面刷新后不归零）
    last_stats = {
        "total_refreshes": 0,
        "bookmarks_bought": 0,
        "mystic_medals_bought": 0,
        "skystone_remaining": 0,
    }

    # 总览页是否激活（页面刷新时自动关闭旧线程）
    overview_active: bool = False
