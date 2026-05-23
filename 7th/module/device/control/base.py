"""
控制策略基类 — 定义点击/滑动方法的标准接口
"""

from abc import ABC, abstractmethod


class ControlStrategy(ABC):
    """控制策略基类。所有控制方法继承此类并注册到 Registry。"""

    @abstractmethod
    def click(self, x: int, y: int) -> None:
        """点击指定坐标。"""
        raise NotImplementedError

    @abstractmethod
    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        """从 (sx, sy) 滑动到 (ex, ey)，持续 duration 秒。"""
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> bool:
        """一次性初始化。返回是否成功。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """短标识符，例如 'adb', 'uiautomator2'。"""
        raise NotImplementedError
