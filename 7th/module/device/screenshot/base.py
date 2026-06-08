"""
截图策略基类 — 定义截图方法的标准接口
"""

import time
from abc import ABC, abstractmethod
from typing import List

import numpy as np

from module.logger import logger


class ScreenshotStrategy(ABC):
    """截图策略基类。所有截图方法继承此类并注册到 Registry。"""

    @abstractmethod
    def screenshot(self) -> np.ndarray:
        """截取一帧。返回 BGR 格式 numpy 数组。"""
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> bool:
        """一次性初始化（连接、推送二进制等）。返回是否成功。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """短标识符，例如 'adb', 'adb_raw', 'uiautomator2'。"""
        raise NotImplementedError

    def benchmark(self, iterations: int = 3) -> float:
        """运行 benchmark，返回平均耗时（毫秒）。

        Args:
            iterations: 测试次数，默认 3 次

        Returns:
            平均毫秒数
        """
        timings: List[float] = []
        for i in range(iterations):
            t0 = time.perf_counter()
            self.screenshot()
            elapsed = (time.perf_counter() - t0) * 1000
            timings.append(elapsed)
        avg = sum(timings) / len(timings)
        logger.debug(f"[{self.name}] benchmark: {avg:.1f}ms avg over {iterations} runs")
        return avg
