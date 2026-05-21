# Feature: auto-shop-refresh, Property 8: 日志格式包含必要信息
"""
属性测试：日志格式包含必要信息

对任意日志级别、模块名、消息内容，格式化后的日志字符串应包含：
- 时间戳（YYYY-MM-DD HH:MM:SS 格式）
- 日志级别标识
- 模块名称

**Validates: Requirements 5.7, 6.6, 8.2**
"""

import logging
import re
import sys
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given, settings

# 确保可以导入 7th 下的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from log import ShopBotFormatter

# 策略：四种日志级别
log_levels = st.sampled_from([logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR])
level_names = {logging.DEBUG: "DEBUG", logging.INFO: "INFO", logging.WARNING: "WARNING", logging.ERROR: "ERROR"}

# 策略：随机模块名（非空可打印文本，排除换行符以保持单行日志）
module_names = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r"),
    min_size=1,
    max_size=50,
)

# 策略：随机消息内容
messages = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r"),
    min_size=0,
    max_size=200,
)

# 时间戳正则：YYYY-MM-DD HH:MM:SS
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


@given(level=log_levels, module=module_names, message=messages)
@settings(max_examples=100)
def test_log_format_contains_required_info(level, module, message):
    """
    Property 8: 日志格式包含必要信息

    对任意日志级别、模块名、消息内容，格式化后的日志字符串应包含
    时间戳（YYYY-MM-DD HH:MM:SS）、级别标识和模块名称。

    **Validates: Requirements 5.7, 6.6, 8.2**
    """
    formatter = ShopBotFormatter()
    record = logging.LogRecord(
        name=module,
        level=level,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)

    # 1. 包含 YYYY-MM-DD HH:MM:SS 格式的时间戳
    assert TIMESTAMP_RE.search(result), f"Missing timestamp in: {result!r}"

    # 2. 包含日志级别标识
    expected_level = level_names[level]
    assert expected_level in result, f"Missing level '{expected_level}' in: {result!r}"

    # 3. 包含模块名称
    assert module in result, f"Missing module '{module}' in: {result!r}"
