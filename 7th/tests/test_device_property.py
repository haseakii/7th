# Feature: auto-shop-refresh, Property 11: 连接重试次数正确
"""
属性测试：连接重试次数正确

对任意 ADB 连接失败场景，DeviceController.connect() 应在最终失败前
恰好重试指定次数（max_retries），且 time.sleep 恰好被调用 max_retries - 1 次
（最后一次失败后不 sleep），每次 sleep 使用指定的 retry_delay。

**Validates: Requirements 1.2**
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hypothesis.strategies as st
from hypothesis import given, settings

from config_manager import DeviceConfig
from module.device.device import DeviceController

# --- 策略定义 ---

# 最大重试次数：1-10
max_retries_st = st.integers(min_value=1, max_value=10)

# 重试延迟：0.01-0.1 秒（快速测试）
retry_delays_st = st.floats(min_value=0.01, max_value=0.1, allow_nan=False, allow_infinity=False)


@given(max_retries=max_retries_st, retry_delay=retry_delays_st)
@settings(max_examples=100)
def test_connect_retry_count_correct(max_retries, retry_delay):
    """
    Property 11: 连接重试次数正确

    Mock ADB 连接始终失败，验证：
    1. subprocess.run 恰好被调用 max_retries 次
    2. time.sleep 恰好被调用 max_retries - 1 次（最后一次失败后不 sleep）
    3. 每次 sleep 调用使用指定的 retry_delay

    **Validates: Requirements 1.2**
    """
    config = DeviceConfig()
    dc = DeviceController(config)

    with patch("module.device.device.subprocess.run") as mock_run, \
         patch("module.device.device.time.sleep") as mock_sleep:

        # ADB 连接始终返回失败
        mock_run.return_value = MagicMock(stdout="failed to connect", returncode=1)

        result = dc.connect(max_retries=max_retries, retry_delay=retry_delay)

        # 连接应最终失败
        assert result is False, (
            f"connect() should return False when all retries fail, "
            f"but got {result} with max_retries={max_retries}"
        )

        # subprocess.run 应恰好被调用 max_retries 次
        assert mock_run.call_count == max_retries, (
            f"subprocess.run should be called exactly {max_retries} times, "
            f"but was called {mock_run.call_count} times"
        )

        # time.sleep 应恰好被调用 max_retries - 1 次
        expected_sleep_count = max_retries - 1
        assert mock_sleep.call_count == expected_sleep_count, (
            f"time.sleep should be called exactly {expected_sleep_count} times "
            f"(max_retries - 1), but was called {mock_sleep.call_count} times"
        )

        # 每次 sleep 调用应使用指定的 retry_delay
        for i, c in enumerate(mock_sleep.call_args_list):
            assert c == call(retry_delay), (
                f"sleep call #{i} should use delay={retry_delay}, "
                f"but got {c}"
            )
