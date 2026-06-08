"""
ItemRecognizer 物品识别器

识别商店货架上的物品类型和价格，支持滑动翻页和去重。
使用动态行检测定位物品 + OCR 读取物品名和价格，替代原有的颜色阈值分类。

动态行检测：垂直扫描物品区域 (x=400-900)，按内容纹理分界切分为独立物品行。
物品分类：OCR 读取名称区域文本，匹配关键词确定类型。
价格识别：OCR 读取价格区域数字。
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from module.logger import logger
from tasks.secret_shop.ocr_engine import OCR

# ---------------------------------------------------------------------------
# 有效物品类型 & 货币类型
# ---------------------------------------------------------------------------
VALID_ITEM_TYPES = ("bookmark", "mystic_medal", "equipment", "fodder", "hero", "currency", "unknown")
VALID_CURRENCIES = ("gold", "skystone", "unknown")

# 物品行三行文本的高度比例分配
# 第一行：类型（英雄/装备/货币）
# 第二行：名称
# 第三行：可购买次数
TYPE_LINE_RATIO = 0.35  # 行顶部 35% 为类型行

# ---------------------------------------------------------------------------
# 类型行关键词（第一行）
# ---------------------------------------------------------------------------
TYPE_LINE_KEYWORDS = {
    "英雄": "hero",      # 低级英雄，不购买
    "装备": "equipment",
    "货币": "currency",  # 货币类，需进一步看名称行
}

# ---------------------------------------------------------------------------
# 名称行关键词（第二行）— 货币类下进一步细分
# ---------------------------------------------------------------------------
CURRENCY_KEYWORDS: Dict[str, Tuple[str, float]] = {
    "书签": ("bookmark", 0.95),
    "神秘": ("mystic_medal", 0.90),
    "奖牌": ("mystic_medal", 0.85),
    "徽章": ("mystic_medal", 0.80),
}

# ---------------------------------------------------------------------------
# 降级关键词（类型行未识别到时，全文兜底匹配）
# ---------------------------------------------------------------------------
FALLBACK_KEYWORDS: Dict[str, Tuple[str, float]] = {
    # 书签
    "书签": ("bookmark", 0.95),
    # 神秘奖牌 / 徽章
    "神秘": ("mystic_medal", 0.90),
    "奖牌": ("mystic_medal", 0.85),
    "徽章": ("mystic_medal", 0.80),
    # 英雄
    "英雄": ("hero", 0.80),
    # 装备
    "装备": ("equipment", 0.70),
    "武器": ("equipment", 0.70),
    "头盔": ("equipment", 0.70),
    "盔甲": ("equipment", 0.70),
    "装甲": ("equipment", 0.70),
    "戒指": ("equipment", 0.70),
    "项链": ("equipment", 0.70),
    "鞋": ("equipment", 0.70),
    "靴子": ("equipment", 0.70),
    "盾牌": ("equipment", 0.70),
    "剑": ("equipment", 0.65),
    "矛": ("equipment", 0.65),
    "杖": ("equipment", 0.65),
    "弓": ("equipment", 0.65),
    "神器": ("equipment", 0.65),
    # 狗粮
    "企鹅": ("fodder", 0.85),
    "狼": ("fodder", 0.75),
    "花": ("fodder", 0.70),
    "狮子": ("fodder", 0.70),
    "蝙蝠": ("fodder", 0.65),
    "史莱姆": ("fodder", 0.65),
    "精灵": ("fodder", 0.65),
    "精髓": ("fodder", 0.70),
    "符文": ("fodder", 0.70),
}

# 装备稀有度标识（出现在物品名称前，辅助判断装备）
_EQUIPMENT_RARITY = {"普通", "高级", "稀有", "传说", "史诗"}

# ---------------------------------------------------------------------------
# 动态物品检测参数
# 布局：NPC头像(100-250) → 物品图标(220-370) → 名称(400-750) → 价格(1050-1240)
# ---------------------------------------------------------------------------

# 垂直扫描区域（避开顶部 UI 和底部按钮）
ITEM_SCAN_Y1 = 80
ITEM_SCAN_Y2 = 718

# 水平扫描范围（物品内容区域）
ITEM_SCAN_X1 = 400
ITEM_SCAN_X2 = 900

# 行判定阈值
ROW_CONTENT_THRESHOLD = 15
MIN_ITEM_HEIGHT = 40

# OCR 识别区域（基于 1280x720 截图）
NAME_REGION = (400, 830)       # 物品名称区域（实测物品名可延伸到 x≈820+）
PRICE_REGION = (1050, 1240)    # 价格数字区域（含价格和购买按钮）
STOCK_REGION = (1090, 1140)    # 库存数量区域（x≈1112, 1/1 或 0/1）

# 非物品行过滤
TEXT_ROW_BRIGHTNESS_MAX = 160

# 滑动相关
SCROLL_AREA = (640, 400, 640, 150)
SCROLL_WAIT = 0.5
SHELF_COMPARE_AREA = (300, 120, 900, 540)
BOTTOM_SIMILARITY_THRESHOLD = 0.95
MAX_SCROLL_COUNT = 5

# 调试输出
SAVE_DEBUG_IMAGES = True
_DEBUG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_regions"
)

# 购买按钮 OCR 搜索区域
BUY_BTN_X = (500, 700)
BUY_BTN_REGION = (1150, 1260)  # 每行右侧"购买"文字 x 范围
BUY_BTN_CLICK_X = 1192  # 购买按钮固定 x 坐标（行右侧，不依赖 OCR）

# 整行扫描范围（一次覆盖名称+价格+库存+按钮）
ROW_SCAN_X2 = 1260


@dataclass
class ShopItem:
    """识别到的商店物品。

    Attributes:
        item_type: 物品类型
        currency: 货币类型 (gold/skystone/unknown)
        price: 价格
        slot_index: 当前视野中的槽位索引 (0,1,2,...)
        position: 物品在截图中的坐标区域 (x1, y1, x2, y2)
        confidence: 匹配置信度 (0.0-1.0)
        name_text: 识别到的原始文本
        stock_available: 是否有库存（1/1 有货, 0/1 已售罄）
    """
    item_type: str
    currency: str
    price: int
    slot_index: int
    position: tuple
    confidence: float
    name_text: str = ""
    stock_available: bool = True
    buy_button_pos: Optional[Tuple[int, int]] = None  # OCR 检测到的"购买"按钮坐标


class ItemRecognizer:
    """商店货架物品识别器。

    使用动态行检测定位物品行，OCR 读取物品名称和价格进行分类。
    相比颜色阈值方案，对 UI 变化和光照变化更鲁棒。
    """

    def __init__(self, device):
        self.device = device
        # OCR 引擎使用模块级单例
        self._ocr = OCR

    # ------------------------------------------------------------------
    # 动态行检测（保留原方案，效果稳定）
    # ------------------------------------------------------------------

    def _find_item_rows(self, image: np.ndarray) -> List[Tuple[int, int]]:
        """垂直扫描物品区域，动态检测物品行。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        strip = gray[:, ITEM_SCAN_X1:ITEM_SCAN_X2]

        rows: List[Tuple[int, int]] = []
        in_item = False
        item_start = 0

        for y in range(ITEM_SCAN_Y1, ITEM_SCAN_Y2):
            row_std = float(strip[y, :].std())
            has_content = row_std > ROW_CONTENT_THRESHOLD

            if has_content and not in_item:
                item_start = y
                in_item = True
            elif not has_content and in_item:
                if y - item_start >= MIN_ITEM_HEIGHT:
                    rows.append((item_start, y))
                in_item = False

        if in_item and y - item_start >= MIN_ITEM_HEIGHT:
            rows.append((item_start, ITEM_SCAN_Y2))

        # 过滤高亮度非物品行
        filtered = []
        for y1, y2 in rows:
            row_content = image[y1:y2, ITEM_SCAN_X1:ITEM_SCAN_X2]
            brightness = float(cv2.cvtColor(row_content, cv2.COLOR_BGR2GRAY).mean())
            if brightness < TEXT_ROW_BRIGHTNESS_MAX:
                filtered.append((y1, y2))
            else:
                logger.info(f"跳过文字行 y={y1}-{y2} (亮度={brightness:.0f})")

        return filtered

    # ------------------------------------------------------------------
    # 分层物品分类（类型行 → 名称行）
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_by_layers(type_text: str, name_text: str) -> Tuple[str, float]:
        """分层分类：先看类型行，再看名称行。"""
        # 类型行匹配
        for keyword, item_type in TYPE_LINE_KEYWORDS.items():
            if keyword in type_text:
                if item_type == "currency":
                    # 货币类 → 按名称行细分
                    for ck, (ctype, cconf) in CURRENCY_KEYWORDS.items():
                        if ck in name_text:
                            return ctype, cconf
                    return "currency", 0.80
                else:
                    return item_type, 0.90

        # 类型行未识别 → 全文兜底
        return ItemRecognizer._fallback_classify(type_text + name_text)

    @staticmethod
    def _fallback_classify(combined: str) -> Tuple[str, float]:
        """全文兜底匹配（类型行 OCR 漏读时使用）。"""
        if not combined.strip():
            return "unknown", 0.0

        matched_type = "unknown"
        best_conf = 0.0
        for keyword, (item_type, conf) in FALLBACK_KEYWORDS.items():
            if keyword in combined:
                if conf > best_conf:
                    best_conf = conf
                    matched_type = item_type

        # 稀有度标签 → 装备辅助判断
        if matched_type == "unknown":
            for rarity in _EQUIPMENT_RARITY:
                if rarity in combined:
                    return "equipment", 0.60

        return matched_type, best_conf

    @staticmethod
    def _classify_by_text(combined: str) -> Tuple[str, float]:
        """旧接口兼容 — 直接全文匹配。"""
        return ItemRecognizer._fallback_classify(combined)

    def _classify_by_ocr(self, image: np.ndarray, y1: int, y2: int) -> Tuple[str, float, str]:
        """通过 OCR 读取物品名称区域，匹配关键词确定物品类型。"""
        name_region = (NAME_REGION[0], y1, NAME_REGION[1], y2)
        blocks = self._ocr.read(image, region=name_region, min_confidence=0.3)

        texts = [b.text for b in blocks]
        combined = "".join(texts)
        matched_type, best_conf = self._classify_by_text(combined)

        if matched_type != "unknown":
            logger.debug(f"OCR 分类 '{combined}' → {matched_type} (conf={best_conf:.2f})")

        return matched_type, best_conf, combined

    def _read_price_by_ocr(self, image: np.ndarray, y1: int, y2: int) -> int:
        """通过 OCR 读取物品价格。

        Args:
            image: 完整 BGR 截图
            y1: 物品行上边界
            y2: 物品行下边界

        Returns:
            价格数值，未识别到时返回 0
        """
        price_region = (PRICE_REGION[0], y1, PRICE_REGION[1], y2)
        value, conf = self._ocr.read_number(image, region=price_region, min_confidence=0.3)
        if value is not None and value > 0:
            return value
        return 0

    def _detect_currency(self, image: np.ndarray, y1: int, y2: int) -> Tuple[str, float]:
        """检测物品货币类型。

        秘密商店中通常所有物品都用金币购买。
        通过 OCR 读取价格区域附近文本辅助判断：
        - 出现 '金币' → gold
        - 出现 '天空石'、'钻石' → skystone
        - 默认为 gold

        Returns:
            (货币类型, 置信度)
        """
        # 检查名称区域附近是否有关键词
        name_region = (NAME_REGION[0], y1, NAME_REGION[1], y2)
        texts = self._ocr.read_texts(image, region=name_region, min_confidence=0.3)
        combined = "".join(texts)

        if "天空" in combined or "钻石" in combined:
            return "skystone", 0.80

        # 秘密商店默认金币
        return "gold", 0.90

    def _check_stock(self, image: np.ndarray, y1: int, y2: int) -> bool:
        """检查物品库存状态。

        读取该行库存区域（x≈1090-1140），检测 "0/1" 或 "1/1"：
        - "1/1" 或未检测到 → 有货（默认有货，保守安全）
        - "0/1" → 已售罄

        Returns:
            True=有库存可买, False=已售罄
        """
        stock_region = (STOCK_REGION[0], y1, STOCK_REGION[1], y2)
        texts = self._ocr.read_texts(image, region=stock_region, min_confidence=0.3)
        combined = "".join(texts)
        if "0/1" in combined or "0/0" in combined:
            logger.debug(f"物品已售罄 y={y1}-{y2}: '{combined}'")
            return False
        return True

    # ------------------------------------------------------------------
    # 购买按钮检测
    # ------------------------------------------------------------------

    def _find_buy_button(self, image: np.ndarray, y1: int, y2: int) -> Optional[Tuple[int, int]]:
        """在物品行右侧搜索'购买'文字，返回按钮点击坐标。

        Args:
            image: 完整 BGR 截图
            y1: 物品行上边界
            y2: 物品行下边界

        Returns:
            (x, y) 按钮坐标，或 None
        """
        region = (BUY_BTN_REGION[0], y1, BUY_BTN_REGION[1], y2)
        blocks = self._ocr.read(image, region=region, min_confidence=0.4)
        for block in blocks:
            if "购买" in block.text:
                cx, cy = int(block.cx), int(block.cy)
                return (cx, cy)
        return None

    # ------------------------------------------------------------------
    # 主识别接口（单行单次 OCR）
    # ------------------------------------------------------------------

    def _parse_row_blocks(self, blocks, y1: int, y2: int, slot_index: int) -> ShopItem:
        """从 OCR 文字块列表中解析一行物品信息（不跑 OCR）。

        按 y 坐标分离三行文本：类型行 → 名称行，分层分类。
        """
        row_height = y2 - y1
        type_split = y1 + row_height * TYPE_LINE_RATIO

        type_texts = []
        name_texts = []
        price_digits = []
        stock_available = True
        buy_pos_ocr = None

        for b in blocks:
            cx = b.cx
            if cx < NAME_REGION[1]:  # < 830 → 名称区域
                if b.cy < type_split:
                    type_texts.append(b.text)  # 类型行（第一行）
                else:
                    name_texts.append(b.text)   # 名称行（第二行）
            elif PRICE_REGION[0] <= cx < PRICE_REGION[1]:  # 1050-1240 → 价格/库存
                text_clean = b.text.replace(",", "").replace(" ", "")
                if text_clean.isdigit():
                    price_digits.append(b)
                if "0/1" in b.text or "0/0" in b.text:
                    stock_available = False
            elif cx >= BUY_BTN_REGION[0] and "购买" in b.text:  # >= 1150 → 购买按钮
                buy_pos_ocr = (int(b.cx), int(b.cy))

        # 分层分类：类型行 → 名称行
        type_text = "".join(type_texts)
        name_text = "".join(name_texts)
        item_type, confidence = self._classify_by_layers(type_text, name_text)

        # 合并价格数字
        price = 0
        if price_digits:
            price_digits.sort(key=lambda b: b.cx)
            merged = ""
            for pb in price_digits:
                merged += pb.text.replace(",", "").replace(" ", "")
            if merged.isdigit():
                price = int(merged)

        # 货币类型
        combined_name = type_text + name_text
        currency = "skystone" if "天空" in combined_name else "gold"

        full_area = (ITEM_SCAN_X1, y1, ITEM_SCAN_X2, y2)

        # 购买按钮位置：优先用 OCR 检测，否则按行居中计算
        buy_pos = buy_pos_ocr or (BUY_BTN_CLICK_X, (y1 + y2) // 2)

        return ShopItem(
            item_type=item_type,
            currency=currency,
            price=price,
            slot_index=slot_index,
            position=full_area,
            confidence=confidence,
            name_text=combined_name,
            stock_available=stock_available,
            buy_button_pos=buy_pos,
        )

    def _recognize_single_row(self, image: np.ndarray, y1: int, y2: int, slot_index: int) -> ShopItem:
        """单次 OCR 识别一行物品（独立调用，用于外部）。"""
        full_region = (ITEM_SCAN_X1, y1, ROW_SCAN_X2, y2)
        blocks = self._ocr.read(image, region=full_region, min_confidence=0.3)
        return self._parse_row_blocks(blocks, y1, y2, slot_index)

    def _recognize_shelf_area(self, image: np.ndarray) -> List[ShopItem]:
        """对整个货架区域做一次 OCR，按行分割解析。"""
        item_rows = self._find_item_rows(image)
        if not item_rows:
            return []

        # 一次 OCR 覆盖整个可视物品区域
        scan_region = (ITEM_SCAN_X1, item_rows[0][0], ROW_SCAN_X2, item_rows[-1][1])
        all_blocks = self._ocr.read(image, region=scan_region, min_confidence=0.3)
        logger.debug(f"整区 OCR 检测到 {len(all_blocks)} 个文字块，{len(item_rows)} 行")

        items: List[ShopItem] = []
        for slot_index, (y1, y2) in enumerate(item_rows):
            # 行边界 ±5px 容差，防止 OCR 文字块紧贴边界外被漏过滤
            row_blocks = [b for b in all_blocks if y1 - 5 <= b.cy <= y2 + 5]
            item = self._parse_row_blocks(row_blocks, y1, y2, slot_index)

            # 整区 OCR 未识别出类型 → 对该行单独做一次 OCR 补救
            if item.item_type == "unknown" or item.confidence < 0.5:
                full_region = (ITEM_SCAN_X1, y1, ROW_SCAN_X2, y2)
                extra_blocks = self._ocr.read(image, region=full_region, min_confidence=0.3)
                if len(extra_blocks) > len(row_blocks):
                    row_blocks = [b for b in extra_blocks if y1 - 5 <= b.cy <= y2 + 5]
                    item = self._parse_row_blocks(row_blocks, y1, y2, slot_index)

            items.append(item)
            logger.info(
                f"物品 {slot_index} (y={y1}-{y2}): "
                f"'{item.name_text}' → {item.item_type} (conf={item.confidence:.2f}), "
                f"价格 {item.price}, 货币 {item.currency}"
                f"{', 已售罄' if not item.stock_available else ''}"
                f"{', 购买按钮 @ ' + str(item.buy_button_pos) if item.buy_button_pos else ''}"
            )

        return items

    def recognize_visible_items(self, image=None) -> List[ShopItem]:
        """识别当前可视区域内的所有物品（整区单次 OCR）。

        Args:
            image: 可选的截图，不传时自动截图。

        Returns:
            识别出的物品列表。
        """
        if image is None:
            image = self.device.screenshot()
        if image is None:
            return []

        return self._recognize_shelf_area(image)

    def recognize_shelf(self) -> List[ShopItem]:
        """识别完整货架上所有物品（含滑动翻页），去重后返回。"""
        logger.info("开始识别完整货架")
        items = self.recognize_visible_items()
        scrolled_items = self.scroll_and_recognize()
        all_items = items + scrolled_items
        result = self.deduplicate_items(all_items)
        logger.info(f"货架识别完成，共 {len(result)} 个物品")
        return result

    # ------------------------------------------------------------------
    # 滑动翻页
    # ------------------------------------------------------------------

    def scroll_and_recognize(self) -> List[ShopItem]:
        """滑动翻页并识别新物品，直到到达底部。"""
        all_new_items: List[ShopItem] = []
        prev_image = self.device.image

        for scroll_count in range(MAX_SCROLL_COUNT):
            start = (SCROLL_AREA[0], SCROLL_AREA[1])
            end = (SCROLL_AREA[2], SCROLL_AREA[3])
            self.device.swipe(start, end)
            time.sleep(SCROLL_WAIT)

            curr_image = self.device.screenshot()
            if curr_image is None:
                break

            if self.is_at_bottom(prev_image, curr_image):
                logger.info(f"已到达货架底部（第 {scroll_count + 1} 次滑动后）")
                break

            new_items = self._recognize_from_image(curr_image)
            all_new_items.extend(new_items)
            prev_image = curr_image

            logger.info(f"第 {scroll_count + 1} 次滑动，识别到 {len(new_items)} 个物品")

        return all_new_items

    def _recognize_from_image(self, image: np.ndarray) -> List[ShopItem]:
        """从给定截图识别物品（用于滑动后的新帧，整区单次 OCR）。"""
        return self._recognize_shelf_area(image)

    # ------------------------------------------------------------------
    # 底部检测与去重
    # ------------------------------------------------------------------

    def is_at_bottom(self, prev_image, curr_image) -> bool:
        if prev_image is None or curr_image is None:
            return False
        prev_crop = prev_image[
            SHELF_COMPARE_AREA[1]:SHELF_COMPARE_AREA[3],
            SHELF_COMPARE_AREA[0]:SHELF_COMPARE_AREA[2],
        ]
        curr_crop = curr_image[
            SHELF_COMPARE_AREA[1]:SHELF_COMPARE_AREA[3],
            SHELF_COMPARE_AREA[0]:SHELF_COMPARE_AREA[2],
        ]
        prev_gray = cv2.cvtColor(prev_crop, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_crop, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(prev_gray, curr_gray)
        similarity = 1.0 - (float(np.mean(diff)) / 255.0)
        return similarity > BOTTOM_SIMILARITY_THRESHOLD

    def deduplicate_items(self, items: List[ShopItem]) -> List[ShopItem]:
        seen = set()
        result = []
        for item in items:
            key = (item.item_type, item.slot_index)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result
