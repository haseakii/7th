"""
ModuleBase — E7 轻量基类

替代 ALAS 的 module.base.base.ModuleBase，去除 ALAS 特有的依赖。
SecretShopTask 继承此类，仅需基本的 config/device 存储。
"""

from module.logger import logger


class ModuleBase:
    """E7 轻量模块基类。"""

    config = None
    device = None

    def __init__(self, config, device=None, task=None):
        """
        Args:
            config: E7Config 实例
            device: DeviceController 实例
            task: 任务名（仅兼容 ALAS 接口，不实际使用）
        """
        self.config = config
        self.device = device
        self.task = task
