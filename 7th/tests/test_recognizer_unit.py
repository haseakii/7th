"""
ItemRecognizer 单元测试（新版本 - OCR 整区识别）
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tasks.secret_shop.recognizer import (
    ShopItem,
    ItemRecognizer,
    VALID_ITEM_TYPES,
    BUY_BTN_CLICK_X,
    MAX_SCROLL_COUNT,
    ROW_SCAN_X2,
)
from tasks.secret_shop.ocr_engine import TextBlock


@pytest.fixture
def mock_device():
    device = MagicMock()
    device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
    device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
    return device


@pytest.fixture
def recognizer(mock_device):
    return ItemRecognizer(mock_device)


class TestShopItem:
    def test_create_shop_item(self):
        item = ShopItem(
            item_type="bookmark", currency="gold", price=184000, slot_index=2,
            position=(400, 200, 950, 290), confidence=0.92,
        )
        assert item.item_type == "bookmark"
        assert item.slot_index == 2
        assert item.confidence == 0.92

    def test_all_valid_item_types(self):
        for item_type in VALID_ITEM_TYPES:
            item = ShopItem(
                item_type=item_type, currency="gold", price=100, slot_index=0,
                position=(400, 200, 950, 290), confidence=0.9,
            )
            assert item.item_type == item_type


class TestClassifyByText:
    """物品类型分类测试（基于文本关键词）"""

    def test_bookmark_keyword(self, recognizer):
        item_type, conf = recognizer._classify_by_text("召唤书签")
        assert item_type == "bookmark"
        assert conf > 0.5

    def test_mystic_keyword(self, recognizer):
        item_type, conf = recognizer._classify_by_text("神秘奖牌")
        assert item_type == "mystic_medal"
        assert conf > 0.5

    def test_equipment_keyword(self, recognizer):
        item_type, conf = recognizer._classify_by_text("装备")
        assert item_type in ("equipment", "unknown")
        assert conf > 0

    def test_unknown_text(self, recognizer):
        item_type, conf = recognizer._classify_by_text("无意义的文本abc")
        assert item_type == "unknown"
        assert conf < 0.5


class TestParseRowBlocks:
    """行解析测试"""

    def test_parse_bookmark_row(self, recognizer):
        blocks = [
            TextBlock(text="召唤书签", confidence=0.85, box=[(400, 200), (500, 200), (500, 230), (400, 230)]),
            TextBlock(text="184000", confidence=0.90, box=[(800, 205), (870, 205), (870, 225), (800, 225)]),
            TextBlock(text="金币", confidence=0.80, box=[(700, 205), (740, 205), (740, 225), (700, 225)]),
            TextBlock(text="1", confidence=0.95, box=[(1120, 210), (1140, 210), (1140, 230), (1120, 230)]),
        ]
        item = recognizer._parse_row_blocks(blocks, y1=200, y2=290, slot_index=0)
        assert item.item_type == "bookmark"
        assert item.slot_index == 0


class TestDeduplicateItems:
    def test_no_duplicates(self, recognizer):
        items = [
            ShopItem("bookmark", "gold", 184000, 0, (400, 200, 950, 290), 0.92),
            ShopItem("equipment", "gold", 50000, 1, (400, 290, 950, 380), 0.88),
        ]
        result = recognizer.deduplicate_items(items)
        assert len(result) == 2

    def test_removes_duplicates(self, recognizer):
        items = [
            ShopItem("bookmark", "gold", 184000, 0, (400, 200, 950, 290), 0.92),
            ShopItem("bookmark", "gold", 184000, 0, (400, 200, 950, 290), 0.90),
        ]
        result = recognizer.deduplicate_items(items)
        assert len(result) == 1

    def test_empty_list(self, recognizer):
        assert recognizer.deduplicate_items([]) == []


class TestBuyButtonPosition:
    def test_buy_btn_click_x_defined(self):
        assert BUY_BTN_CLICK_X == 1192

    def test_row_scan_x2_defined(self):
        assert ROW_SCAN_X2 == 1260
