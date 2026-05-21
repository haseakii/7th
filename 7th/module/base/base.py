"""
ModuleBase - ALAS 风格的模块基类

为所有任务模块提供统一的基础设施：
- config / device 注入
- appear() 系列检测方法
- loop() 状态机语法糖
- image_crop / image_color_count 等图像工具
"""

from module.base.button import Button
from module.base.decorator import cached_property
from module.base.timer import Timer
from module.base.utils import *
from log import logger


class ModuleBase:
    config = None
    device = None

    def __init__(self, config, device=None, task=None):
        self.config = config
        self.device = device
        self.interval_timer = {}

    def ensure_button(self, button):
        return button

    def loop(self, skip_first=True, timeout=None):
        """状态机循环语法糖。"""
        if timeout is not None:
            if isinstance(timeout, Timer):
                timeout.reset()
            else:
                timeout = Timer.from_seconds(timeout).start()

        while True:
            if timeout is not None:
                if timeout.reached():
                    return

            if skip_first:
                skip_first = False
            else:
                self.device.screenshot()

            try:
                yield self.device.image
            except AttributeError:
                self.device.screenshot()
                yield self.device.image

    def appear(self, button, offset=0, interval=0, similarity=0.85, threshold=10):
        """检测按钮是否出现在当前画面。"""
        button = self.ensure_button(button)

        if interval:
            if button.name in self.interval_timer:
                if self.interval_timer[button.name].limit != interval:
                    self.interval_timer[button.name] = Timer(interval)
            else:
                self.interval_timer[button.name] = Timer(interval)
            if not self.interval_timer[button.name].reached():
                return False

        if isinstance(button, Button):
            appear = button.appear_on(self.device.image, threshold=threshold)
        else:
            return False

        if appear and interval:
            self.interval_timer[button.name].reset()

        return appear

    def appear_then_click(self, button, screenshot=False, genre='items',
                          offset=0, interval=0, similarity=0.85, threshold=30):
        appear = self.appear(button, offset=offset, interval=interval,
                             similarity=similarity, threshold=threshold)
        if appear:
            self.device.click(button)
        return appear

    def wait_until_appear(self, button, offset=0, skip_first_screenshot=False):
        while True:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
            if self.appear(button, offset=offset):
                break

    def wait_until_appear_then_click(self, button, offset=0):
        self.wait_until_appear(button, offset=offset)
        self.device.click(button)

    def wait_until_disappear(self, button, offset=0):
        while True:
            self.device.screenshot()
            if not self.appear(button, offset=offset):
                break

    def image_crop(self, button, copy=True):
        if isinstance(button, Button):
            return crop(self.device.image, button.area, copy=copy)
        elif hasattr(button, 'area'):
            return crop(self.device.image, button.area, copy=copy)
        else:
            return crop(self.device.image, button, copy=copy)

    def image_color_count(self, button, color, threshold=221, count=50):
        if isinstance(button, np.ndarray):
            image = button
        else:
            image = self.image_crop(button, copy=False)
        mask = color_similarity_2d(image, color=color)
        cv2.inRange(mask, threshold, 255, dst=mask)
        sum_ = cv2.countNonZero(mask)
        return sum_ > count

    def interval_reset(self, button, interval=3):
        if button is not None:
            if button.name in self.interval_timer:
                self.interval_timer[button.name].reset()
            else:
                self.interval_timer[button.name] = Timer(interval).reset()

    def interval_clear(self, button, interval=3):
        if button is not None:
            if button.name in self.interval_timer:
                self.interval_timer[button.name].clear()
            else:
                self.interval_timer[button.name] = Timer(interval).clear()
