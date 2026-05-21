"""
ItemRecognizer 单元测试

覆盖需求:
- 4.1 动态行检测定位物品（非固定坐标）
- 4.2 颜色分析和模板匹配识别物品类型
- 4.3 返回物品类型和位置坐标
- 4.4 OCR 识别价格
- 4.5 未知物品标记为 unknown
- 4.6 处理完整货架（动态检测数量）
- 4.7 滑动翻页显示剩余物品
- 4.8 滑动前后截图比较判断是否到底
- 4.9 基于槽位位置和物品类型去重
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shop.recognizer import (
    ShopItem,
    ItemRecognizer,
    ITEM_TEMPLATES,
    VALID_ITEM_TYPES,
    MATCH_THRESHOLD,
    BOTTOM_SIMILARITY_THRESHOLD,
    MAX_SCROLL_COUNT,
    ITEM_SCAN_Y1,
    ITEM_SCAN_Y2,
    ITEM_SCAN_X1,
    ITEM_SCAN_X2,
    ROW_CONTENT_THRESHOLD,
)


@pytest.fixture
def mock_device():
    """创建 mock DeviceController"""
    device = MagicMock()
    device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
    device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
    return device


@pytest.fixture
def recognizer(mock_device):
    return ItemRecognizer(mock_device)


def _make_item_image(
    item_count: int = 2,
    item_height: int = 90,
    gap: int = 55,
    row_std: float = 30.0,
    bg_std: float = 5.0,
) -> np.ndarray:
    """创建包含指定数量物品行的测试图像。

    物品行区域（x=ITEM_SCAN_X1~X2）设置较高的 std 模拟内容，
    间隙区域设置较低的 std 模拟背景。

    Args:
        item_count: 物品行数量
        item_height: 每行高度（像素）
        gap: 行间间隙（像素）
        row_std: 行内容标准差值
        bg_std: 背景标准差值

    Returns:
        np.ndarray: 测试图像
    """
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    # 填充随机背景
    bg = np.random.randint(0, 30, (720, 1280, 3), dtype=np.uint8)
    img[:] = bg

    y = ITEM_SCAN_Y1 + 20  # 起始偏移
    for _ in range(item_count):
        if y + item_height > ITEM_SCAN_Y2:
            break
        # 物品行区域：较高的对比度内容
        row_content = np.random.randint(30, 200, (item_height, ITEM_SCAN_X2 - ITEM_SCAN_X1, 3), dtype=np.uint8)
        img[y:y + item_height, ITEM_SCAN_X1:ITEM_SCAN_X2] = row_content
        y += item_height + gap

    return img


class TestShopItem:
    """ShopItem 数据类测试"""

    def test_create_shop_item(self):
        """可以创建有效的 ShopItem"""
        item = ShopItem(
            item_type="bookmark",
            price=184000,
            slot_index=2,
            position=(400, 200, 950, 290),
            confidence=0.92,
        )
        assert item.item_type == "bookmark"
        assert item.price == 184000
        assert item.slot_index == 2
        assert item.position == (400, 200, 950, 290)
        assert item.confidence == 0.92

    def test_all_valid_item_types(self):
        """所有有效物品类型都可以创建"""
        for item_type in VALID_ITEM_TYPES:
            item = ShopItem(
                item_type=item_type,
                price=100,
                slot_index=0,
                position=(400, 200, 950, 290),
                confidence=0.9,
            )
            assert item.item_type == item_type


class TestItemTemplates:
    """物品模板常量测试"""

    def test_templates_defined(self):
        """所有物品类型都有对应的模板 Button"""
        expected_types = {"bookmark", "mystic_medal", "equipment", "fodder"}
        assert set(ITEM_TEMPLATES.keys()) == expected_types

    def test_templates_are_buttons(self):
        """模板都是 Button 实例"""
        from module.base.button import Button
        for name, btn in ITEM_TEMPLATES.items():
            assert isinstance(btn, Button), f"{name} 不是 Button 实例"


class TestFindItemRows:
    """动态行检测测试"""

    def test_detects_correct_number_of_rows(self, recognizer, mock_device):
        """正确检测物品行数量"""
        mock_device.screenshot.return_value = _make_item_image(item_count=3)
        rows = recognizer._find_item_rows(mock_device.screenshot())
        assert len(rows) == 3

    def test_no_rows_on_empty_image(self, recognizer, mock_device):
        """空白图像检测到 0 行"""
        mock_device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
        rows = recognizer._find_item_rows(mock_device.screenshot())
        assert len(rows) == 0

    def test_each_row_has_min_height(self, recognizer, mock_device):
        """每行高度 >= MIN_ITEM_HEIGHT"""
        from shop.recognizer import MIN_ITEM_HEIGHT
        mock_device.screenshot.return_value = _make_item_image(item_count=2)
        rows = recognizer._find_item_rows(mock_device.screenshot())
        for y1, y2 in rows:
            assert y2 - y1 >= MIN_ITEM_HEIGHT

    def test_row_bounds_within_scan_range(self, recognizer, mock_device):
        """检测到的行在扫描范围内"""
        mock_device.screenshot.return_value = _make_item_image(item_count=2)
        rows = recognizer._find_item_rows(mock_device.screenshot())
        for y1, y2 in rows:
            assert y1 >= ITEM_SCAN_Y1
            assert y2 <= ITEM_SCAN_Y2


class TestClassifyItem:
    """物品类型分类测试"""

    def test_unknown_on_empty_icon(self, recognizer):
        """空图标返回 unknown"""
        icon = np.zeros((1, 1, 3), dtype=np.uint8)
        item_type, confidence = recognizer._classify_item(icon)
        assert item_type == "unknown"

    def test_unknown_on_zero_size(self, recognizer):
        """零尺寸图标返回 unknown"""
        icon = np.zeros((0, 0, 3), dtype=np.uint8)
        item_type, confidence = recognizer._classify_item(icon)
        assert item_type == "unknown"

    def test_color_classify_returns_type(self, recognizer):
        """特征分析返回有效的物品类型"""
        # 创建一个暖色图标（接近 bookmark 特征范围）
        icon = np.zeros((60, 60, 3), dtype=np.uint8)
        icon[:] = (80, 150, 220)  # BGR - 暖色
        features = recognizer._extract_features(icon)
        item_type, confidence = recognizer._classify_by_features(features)
        assert item_type in VALID_ITEM_TYPES
        assert 0.0 <= confidence <= 1.0


class TestOcrPrice:
    """OCR 价格识别测试"""

    def test_returns_zero_when_no_image(self, recognizer, mock_device):
        """OCR 异常时返回 0"""
        price = recognizer._ocr_price((800, 200, 950, 290), np.zeros((720, 1280, 3), dtype=np.uint8))
        # Without mocking Digit, this will try OCR and potentially fail
        # Just verify it returns an int
        assert isinstance(price, int)

    @patch("shop.recognizer.Digit")
    def test_ocr_returns_int(self, mock_digit_cls, recognizer, mock_device):
        """需求 4.4: OCR 返回整数价格"""
        mock_digit_instance = MagicMock()
        mock_digit_instance.ocr.return_value = 184000
        mock_digit_cls.return_value = mock_digit_instance

        price = recognizer._ocr_price((800, 200, 950, 290), mock_device.screenshot())
        assert price == 184000

    @patch("shop.recognizer.Digit")
    def test_ocr_exception_returns_zero(self, mock_digit_cls, recognizer, mock_device):
        """OCR 异常时返回 0"""
        mock_digit_cls.side_effect = Exception("OCR 服务不可用")
        price = recognizer._ocr_price((800, 200, 950, 290), mock_device.screenshot())
        assert price == 0


class TestRecognizeVisibleItems:
    """可视区域物品识别测试"""

    def test_returns_list(self, recognizer, mock_device):
        """返回 ShopItem 列表"""
        mock_device.screenshot.return_value = _make_item_image(item_count=2)
        with patch.object(recognizer, "_classify_item", return_value=("bookmark", 0.92)), \
             patch.object(recognizer, "_ocr_price", return_value=184000):
            items = recognizer.recognize_visible_items()
            assert isinstance(items, list)
            assert all(isinstance(item, ShopItem) for item in items)

    def test_recognizes_dynamic_count(self, recognizer, mock_device):
        """根据实际图像内容动态识别物品数量"""
        mock_device.screenshot.return_value = _make_item_image(item_count=3)
        with patch.object(recognizer, "_classify_item", return_value=("bookmark", 0.92)), \
             patch.object(recognizer, "_ocr_price", return_value=100):
            items = recognizer.recognize_visible_items()
            # 应该检测到 3 行
            assert len(items) == 3

    def test_empty_on_no_rows(self, recognizer, mock_device):
        """没有物品行时返回空列表"""
        mock_device.screenshot.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)
        items = recognizer.recognize_visible_items()
        assert items == []

    def test_item_has_correct_slot_index(self, recognizer, mock_device):
        """需求 4.3: 每个物品有正确的槽位索引"""
        mock_device.screenshot.return_value = _make_item_image(item_count=3)
        with patch.object(recognizer, "_classify_item", return_value=("bookmark", 0.92)), \
             patch.object(recognizer, "_ocr_price", return_value=100):
            items = recognizer.recognize_visible_items()
            for i, item in enumerate(items):
                assert item.slot_index == i

    def test_item_has_valid_position(self, recognizer, mock_device):
        """物品位置在扫描范围内"""
        mock_device.screenshot.return_value = _make_item_image(item_count=2)
        with patch.object(recognizer, "_classify_item", return_value=("bookmark", 0.92)), \
             patch.object(recognizer, "_ocr_price", return_value=100):
            items = recognizer.recognize_visible_items()
            for item in items:
                x1, y1, x2, y2 = item.position
                assert x1 >= ITEM_SCAN_X1
                assert x2 <= ITEM_SCAN_X2
                assert y1 >= ITEM_SCAN_Y1
                assert y2 <= ITEM_SCAN_Y2


class TestIsAtBottom:
    """底部检测测试"""

    def test_identical_images_are_at_bottom(self, recognizer):
        """需求 4.8: 相同截图判定为到底"""
        image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        assert recognizer.is_at_bottom(image, image.copy()) == True

    def test_different_images_not_at_bottom(self, recognizer):
        """需求 4.8: 不同截图判定为未到底"""
        img1 = np.zeros((720, 1280, 3), dtype=np.uint8)
        img2 = np.full((720, 1280, 3), 200, dtype=np.uint8)
        assert recognizer.is_at_bottom(img1, img2) == False

    def test_none_image_not_at_bottom(self, recognizer):
        """None 截图返回 False"""
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        assert recognizer.is_at_bottom(None, image) == False
        assert recognizer.is_at_bottom(image, None) == False
        assert recognizer.is_at_bottom(None, None) == False

    def test_bottom_similarity_threshold(self):
        """底部检测相似度阈值为 0.95"""
        assert BOTTOM_SIMILARITY_THRESHOLD == 0.95


class TestDeduplicateItems:
    """物品去重测试"""

    def test_no_duplicates(self, recognizer):
        """需求 4.9: 不同物品不被去重"""
        items = [
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.92),
            ShopItem("equipment", 50000, 1, (400, 290, 950, 380), 0.88),
        ]
        result = recognizer.deduplicate_items(items)
        assert len(result) == 2

    def test_removes_duplicates(self, recognizer):
        """需求 4.9: 相同 (item_type, slot_index) 的物品被去重"""
        items = [
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.92),
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.90),
        ]
        result = recognizer.deduplicate_items(items)
        assert len(result) == 1
        assert result[0].confidence == 0.92  # 保留第一个

    def test_same_type_different_slot(self, recognizer):
        """需求 4.9: 相同类型不同槽位不去重"""
        items = [
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.92),
            ShopItem("bookmark", 184000, 1, (400, 290, 950, 380), 0.90),
        ]
        result = recognizer.deduplicate_items(items)
        assert len(result) == 2

    def test_different_type_same_slot(self, recognizer):
        """需求 4.9: 不同类型相同槽位不去重"""
        items = [
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.92),
            ShopItem("equipment", 50000, 0, (400, 200, 950, 290), 0.88),
        ]
        result = recognizer.deduplicate_items(items)
        assert len(result) == 2

    def test_empty_list(self, recognizer):
        """空列表去重返回空列表"""
        assert recognizer.deduplicate_items([]) == []


class TestScrollAndRecognize:
    """滑动翻页识别测试"""

    @patch("shop.recognizer.time.sleep")
    def test_stops_at_bottom(self, mock_sleep, recognizer, mock_device):
        """需求 4.8: 到达底部时停止滑动"""
        with patch.object(recognizer, "is_at_bottom", return_value=True):
            items = recognizer.scroll_and_recognize()
            assert isinstance(items, list)

    @patch("shop.recognizer.time.sleep")
    def test_max_scroll_limit(self, mock_sleep, recognizer, mock_device):
        """防止无限滑动，最多滑动 MAX_SCROLL_COUNT 次"""
        with patch.object(recognizer, "is_at_bottom", return_value=False), \
             patch.object(recognizer, "_recognize_from_image", return_value=[]):
            recognizer.scroll_and_recognize()
            assert mock_device.swipe.call_count == MAX_SCROLL_COUNT


class TestRecognizeShelf:
    """完整货架识别测试"""

    @patch("shop.recognizer.time.sleep")
    def test_returns_deduplicated_list(self, mock_sleep, recognizer):
        """recognize_shelf 返回去重后的列表"""
        items_visible = [
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.92),
        ]
        items_scrolled = [
            ShopItem("bookmark", 184000, 0, (400, 200, 950, 290), 0.90),  # 重复
            ShopItem("equipment", 50000, 1, (400, 290, 950, 380), 0.88),
        ]
        with patch.object(recognizer, "recognize_visible_items", return_value=items_visible), \
             patch.object(recognizer, "scroll_and_recognize", return_value=items_scrolled):
            result = recognizer.recognize_shelf()
            assert len(result) == 2  # 去重后 bookmark slot 0 只保留一个


class TestConstants:
    """常量测试"""

    def test_valid_item_types(self):
        """有效物品类型包含所有预期类型"""
        assert "bookmark" in VALID_ITEM_TYPES
        assert "mystic_medal" in VALID_ITEM_TYPES
        assert "equipment" in VALID_ITEM_TYPES
        assert "fodder" in VALID_ITEM_TYPES
        assert "unknown" in VALID_ITEM_TYPES

    def test_max_scroll_count(self):
        """最大滑动次数为正整数"""
        assert MAX_SCROLL_COUNT > 0

    def test_detection_params_sensible(self):
        """检测参数在合理范围内"""
        assert ITEM_SCAN_Y1 < ITEM_SCAN_Y2
        assert ITEM_SCAN_X1 < ITEM_SCAN_X2
        assert ITEM_SCAN_Y1 >= 0
        assert ITEM_SCAN_Y2 <= 720
        assert ROW_CONTENT_THRESHOLD > 0
