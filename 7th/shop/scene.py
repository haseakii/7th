"""
场景枚举 — 定义游戏可能出现的界面状态。
"""

from enum import Enum


class Scene(str, Enum):
    """游戏场景枚举。

    检测优先级（从高到低）：
    1. PURCHASE_POPUP — 叠加在 secret_shop 之上的购买/刷新确认弹窗
    2. SECRET_SHOP   — 秘密商店货架界面
    3. LOBBY         — 游戏大厅
    4. UNKNOWN       — 其他（加载中、未知弹窗、战斗画面等）
    """
    SECRET_SHOP = "secret_shop"
    PURCHASE_POPUP = "purchase_popup"
    LOBBY = "lobby"
    UNKNOWN = "unknown"
