"""
Timer 计时器

从 Alas 原样复用的计时器工具。
"""

from time import time, sleep


class Timer:
    def __init__(self, limit, count=0):
        """
        Dual timer for time count and access count.
        Access count can provide robustness on slow devices where screen shot time cost > timer.limit

        Args:
            limit (int | float): Timer limit
            count (int): Timer access count. Default to 0.
        """
        self.limit = limit
        self.count = count
        self._start = 0.
        self._access = 0

    @classmethod
    def from_seconds(cls, limit, speed=0.5):
        """
        Create timer from given seconds

        Args:
            limit (int | float):
            speed (int | float): Approximate screen shot time cost
                if time cost > 0.5s, device is considered slow
        """
        count = int(limit / speed)
        return cls(limit, count=count)

    def start(self):
        """
        Start current timer.
        If timer not started, reached() always return True. So we can have fast first try on:

        interval = Timer(2)
        while 1:
            if interval.reached():
                pass
        """
        if self._start <= 0:
            self._start = time()
            self._access = 0

        return self

    def started(self):
        """
        Returns:
            bool:
        """
        return self._start > 0

    def current_time(self):
        """
        Returns:
            float:
        """
        if self._start > 0:
            diff = time() - self._start
            if diff < 0:
                diff = 0.
            return diff
        else:
            return 0.

    def current_count(self):
        """
        Returns:
            int:
        """
        return self._access

    def add_count(self):
        self._access += 1
        return self

    def reached(self):
        """
        Returns:
            bool:
        """
        # each reached() call is consider as an access
        self._access += 1
        if self._start > 0:
            return self._access > self.count and time() - self._start > self.limit
        else:
            # not started, return True for fast first try
            return True

    def reset(self):
        """
        Reset the timer as if it just started
        """
        self._start = time()
        self._access = 0
        return self

    def clear(self):
        """
        Reset the timer as if it never started
        """
        self._start = 0.
        self._access = self.count
        return self

    def reached_and_reset(self):
        """
        Returns:
            bool:
        """
        if self.reached():
            self.reset()
            return True
        else:
            return False

    def wait(self):
        """
        Wait until timer reached.
        """
        diff = self._start + self.limit - time()
        if diff > 0:
            sleep(diff)

    def __str__(self):
        return f'Timer(limit={round(self.current_time(), 3)}/{self.limit}, count={self._access}/{self.count})'

    __repr__ = __str__
