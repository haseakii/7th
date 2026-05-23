# Feature: auto-shop-refresh, Property 5: 识别结果数据结构完整性
"""
属性测试：识别结果数据结构完整性

对任意生成的 ShopItem 列表，每个元素都应包含有效的 item_type
（属于 'bookmark'|'mystic_medal'|'equipment'|'fodder'|'unknown' 之一）、
非负的 price、有效的 slot_index（0-5）、非空的 position 元组和
0-1 范围内的 confidence 值。

**Validates: Requirements 4.3**
"""

import sys
from pathlib import Path

# 确保可以导入 7th 下的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hypothesis.strategies as st
from hypothesis import given, settings

from tasks.secret_shop.recognizer import ShopItem, VALID_ITEM_TYPES

# --- 策略定义 ---

# 物品类型：从有效枚举值中选取
item_types = st.sampled_from(list(VALID_ITEM_TYPES))

# 价格：非负整数
prices = st.integers(min_value=0, max_value=10_000_000)

# 槽位索引：0-5
slot_indices = st.integers(min_value=0, max_value=5)

# 位置坐标：4 个非负整数的元组 (x1, y1, x2, y2)
positions = st.tuples(
    st.integers(min_value=0, max_value=1280),
    st.integers(min_value=0, max_value=720),
    st.integers(min_value=0, max_value=1280),
    st.integers(min_value=0, max_value=720),
)

# 置信度：0.0 到 1.0 之间的浮点数
confidences = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# 组合策略：ShopItem
shop_items = st.builds(
    ShopItem,
    item_type=item_types,
    price=prices,
    slot_index=slot_indices,
    position=positions,
    confidence=confidences,
)

# ShopItem 列表（0-12 个元素，覆盖空列表和多页货架场景）
shop_item_lists = st.lists(shop_items, min_size=0, max_size=12)


@given(items=shop_item_lists)
@settings(max_examples=100)
def test_shop_item_data_structure_integrity(items):
    """
    Property 5: 识别结果数据结构完整性

    对任意生成的 ShopItem 列表，验证每个元素的字段约束：
    - item_type 是有效枚举值之一
    - price 是非负整数
    - slot_index 在 0-5 范围内
    - position 是包含 4 个非负整数的元组
    - confidence 在 0.0-1.0 范围内

    **Validates: Requirements 4.3**
    """
    for item in items:
        # item_type 必须是有效枚举值
        assert item.item_type in VALID_ITEM_TYPES, (
            f"item_type {item.item_type!r} not in {VALID_ITEM_TYPES}"
        )

        # price 必须是非负整数
        assert isinstance(item.price, int), (
            f"price should be int, got {type(item.price)}"
        )
        assert item.price >= 0, (
            f"price should be non-negative, got {item.price}"
        )

        # slot_index 必须在 0-5 范围内
        assert isinstance(item.slot_index, int), (
            f"slot_index should be int, got {type(item.slot_index)}"
        )
        assert 0 <= item.slot_index <= 5, (
            f"slot_index should be 0-5, got {item.slot_index}"
        )

        # position 必须是包含 4 个非负整数的元组
        assert isinstance(item.position, tuple), (
            f"position should be tuple, got {type(item.position)}"
        )
        assert len(item.position) == 4, (
            f"position should have 4 elements, got {len(item.position)}"
        )
        for i, coord in enumerate(item.position):
            assert isinstance(coord, int), (
                f"position[{i}] should be int, got {type(coord)}"
            )
            assert coord >= 0, (
                f"position[{i}] should be non-negative, got {coord}"
            )

        # confidence 必须在 0.0-1.0 范围内
        assert isinstance(item.confidence, float), (
            f"confidence should be float, got {type(item.confidence)}"
        )
        assert 0.0 <= item.confidence <= 1.0, (
            f"confidence should be 0.0-1.0, got {item.confidence}"
        )
