# Feature: auto-shop-refresh, Property 4: 购买决策与配置一致
"""
属性测试：购买决策与配置一致

对任意 ShopItem 和 ShopConfig 的购买列表配置，PurchaseEngine.should_buy(item)
的返回值应等于配置中对应物品类型的启用状态。即：当 shop.buy_bookmarks=True 且
item.item_type='bookmark' 时返回 True，当 shop.buy_bookmarks=False 时返回 False，
对所有物品类型均成立。'unknown' 类型的物品永远返回 False，无论配置如何。

**Validates: Requirements 5.1**
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# 确保可以导入 7th 下的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hypothesis.strategies as st
from hypothesis import given, settings

from config_manager import ConfigManager, ShopConfig
from shop.purchase import ITEM_TYPE_TO_CONFIG_KEY, PurchaseEngine
from shop.recognizer import ShopItem

# ---------------------------------------------------------------------------
# 策略定义
# ---------------------------------------------------------------------------

# 有效的可购买物品类型（不含 unknown）
KNOWN_ITEM_TYPES = list(ITEM_TYPE_TO_CONFIG_KEY.keys())

# 所有有效物品类型（含 unknown）
ALL_ITEM_TYPES = KNOWN_ITEM_TYPES + ["unknown"]

# 随机物品类型
item_types = st.sampled_from(ALL_ITEM_TYPES)

# 随机 ShopConfig（随机布尔值控制每种物品是否购买）
shop_configs = st.builds(
    ShopConfig,
    buy_bookmarks=st.booleans(),
    buy_mystic_medals=st.booleans(),
    buy_equipment=st.booleans(),
    buy_fodder=st.booleans(),
    max_refresh_count=st.just(200),
    gold_threshold=st.just(0),
    skystone_threshold=st.just(0),
)

# 随机 ShopItem
shop_items = st.builds(
    ShopItem,
    item_type=item_types,
    price=st.integers(min_value=0, max_value=999999),
    slot_index=st.integers(min_value=0, max_value=5),
    position=st.tuples(
        st.integers(min_value=0, max_value=1280),
        st.integers(min_value=0, max_value=720),
        st.integers(min_value=0, max_value=1280),
        st.integers(min_value=0, max_value=720),
    ),
    confidence=st.floats(min_value=0.0, max_value=1.0),
)


# ---------------------------------------------------------------------------
# 辅助：从 ShopConfig 构建 buy_list 映射（与 ConfigManager.get_buy_list 一致）
# ---------------------------------------------------------------------------
def _expected_buy_list(shop_cfg: ShopConfig) -> dict:
    return {
        "bookmarks": shop_cfg.buy_bookmarks,
        "mystic_medals": shop_cfg.buy_mystic_medals,
        "equipment": shop_cfg.buy_equipment,
        "fodder": shop_cfg.buy_fodder,
    }


@given(item=shop_items, shop_cfg=shop_configs)
@settings(max_examples=100)
def test_purchase_decision_matches_config(item, shop_cfg):
    """
    Property 4: 购买决策与配置一致

    对任意 ShopItem 和 ShopConfig，should_buy 的返回值应等于配置中
    对应物品类型的启用状态。unknown 类型永远返回 False。

    **Validates: Requirements 5.1**
    """
    # 构建 mock ConfigManager，返回与 shop_cfg 一致的 buy_list
    mock_config = MagicMock(spec=ConfigManager)
    mock_config.get_buy_list.return_value = _expected_buy_list(shop_cfg)

    # DeviceController 不参与 should_buy，使用 mock
    mock_device = MagicMock()

    engine = PurchaseEngine(mock_device, mock_config)
    result = engine.should_buy(item)

    # 计算期望值
    if item.item_type == "unknown":
        expected = False
    else:
        config_key = ITEM_TYPE_TO_CONFIG_KEY.get(item.item_type)
        if config_key is None:
            expected = False
        else:
            buy_list = _expected_buy_list(shop_cfg)
            expected = buy_list.get(config_key, False)

    assert result == expected, (
        f"should_buy mismatch for item_type={item.item_type!r}: "
        f"got {result}, expected {expected}, "
        f"config={_expected_buy_list(shop_cfg)}"
    )
