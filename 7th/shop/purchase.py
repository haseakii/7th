"""
PurchaseEngine 购买引擎

执行物品购买操作：点击物品 → 确认弹窗 → 二次确认 → 验证结果。
使用 OCR 检测弹窗按钮文字，替代原有的固定坐标+颜色方案。
"""

import random
import time
from dataclasses import dataclass
from typing import List, Optional

from config_manager import ConfigManager
from log import logger
from module.base.timer import Timer
from module.device.device import DeviceController
from shop.ocr_engine import OCR
from shop.recognizer import ShopItem, BUY_BTN_X

# ---------------------------------------------------------------------------
# 物品类型到配置键的映射
# ---------------------------------------------------------------------------
ITEM_TYPE_TO_CONFIG_KEY = {
    "bookmark": "bookmarks",
    "mystic_medal": "mystic_medals",
    "equipment": "equipment",
    "fodder": "fodder",
}

# 弹窗按钮 OCR 搜索区域（底部弹窗区域）
POPUP_REGION = (300, 440, 950, 550)
POPUP_CONFIRM_REGION = (640, 440, 950, 550)  # 右侧"购买"/"确认"按钮
POPUP_CANCEL_REGION = (300, 440, 640, 550)   # 左侧"取消"按钮

# 弹窗按钮固定坐标（游戏内位置不变，比 OCR 可靠）
CONFIRM_BTN_POS = (818, 508)
CANCEL_BTN_POS = (482, 508)

# 金币不足文字检测区域
INSUFFICIENT_GOLD_REGION = (400, 280, 880, 400)

# 购买确认弹窗等待超时（秒）
CONFIRM_POPUP_TIMEOUT = 3.0

# 购买间隔范围（秒）
PURCHASE_INTERVAL_MIN = 0.5
PURCHASE_INTERVAL_MAX = 1.0

# 按钮文字点击偏移（相对于文字框中心点的像素偏移）
BUTTON_CLICK_OFFSET_Y = 15  # 点击文字下方一点（按钮通常在文字下方）


@dataclass
class PurchaseResult:
    """单次购买结果。"""
    item_type: str
    price: int
    success: bool
    reason: str = ""


class PurchaseEngine:
    """执行物品购买操作。

    流程：点击物品 → 等待弹窗 → OCR 检测 "确认" 按钮 → 点击 → 验证。
    按钮检测使用 OCR 读取弹窗文字，不依赖固定坐标或颜色。
    """

    def __init__(self, device: DeviceController, config: ConfigManager):
        self.device = device
        self.config = config
        self._ocr = OCR

    def verify_confirm_position(self) -> None:
        """启动时校准确认按钮坐标。

        截图弹窗区域，用 OCR 检测"购买"/"确认"按钮位置，
        与固定坐标 CONFIRM_BTN_POS 对比，偏差过大则日志警告。
        """
        image = self.device.screenshot()
        if image is None:
            logger.warning("校准: 无法截图，跳过")
            return

        for text in ("购买", "确认"):
            pos = self._find_popup_button(image, text, region=POPUP_CONFIRM_REGION)
            if pos:
                dx = pos[0] - CONFIRM_BTN_POS[0]
                dy = pos[1] - CONFIRM_BTN_POS[1]
                dist = (dx ** 2 + dy ** 2) ** 0.5
                if dist > 30:
                    logger.warning(
                        f"校准: '{text}' OCR=({pos[0]},{pos[1]}) "
                        f"与默认 {CONFIRM_BTN_POS} 偏差 ({dx},{dy})={dist:.0f}px"
                    )
                else:
                    logger.info(
                        f"校准: '{text}' OCR=({pos[0]},{pos[1]}) "
                        f"偏差 {dist:.0f}px，坐标 OK"
                    )
                return

        logger.info("校准: 未检测到弹窗，使用默认坐标 %s", CONFIRM_BTN_POS)

    def should_buy(self, item: ShopItem) -> bool:
        """根据配置和货币类型判断是否应购买该物品。"""
        if item.item_type == "unknown":
            return False
        if not item.stock_available:
            logger.info(f"跳过已售罄物品: {item.item_type}")
            return False
        if item.currency == "skystone":
            logger.info(f"跳过天空石物品: {item.item_type}")
            return False
        buy_list = self.config.get_buy_list()
        config_key = ITEM_TYPE_TO_CONFIG_KEY.get(item.item_type)
        if config_key is None:
            return False
        return buy_list.get(config_key, False)

    # ------------------------------------------------------------------
    # 弹窗 OCR 检测
    # ------------------------------------------------------------------

    def _find_popup_button(self, image, button_text: str, region=POPUP_REGION) -> Optional[tuple]:
        """在弹窗区域搜索指定按钮文字，返回点击坐标 (x, y)。

        Args:
            image: 截图
            button_text: 要搜索的文字（如 "确认"、"取消"）
            region: 搜索区域

        Returns:
            (x, y) 点击坐标，或 None
        """
        blocks = self._ocr.read(image, region=region, min_confidence=0.4)
        for block in blocks:
            if button_text in block.text:
                # 点击文字中心下方一点（按钮在文字下方）
                cx = block.cx
                cy = block.cy + BUTTON_CLICK_OFFSET_Y
                logger.debug(f"找到按钮 '{button_text}' 在 ({cx:.0f}, {cy:.0f})")
                return (int(cx), int(cy))
        return None

    def _detect_confirm_popup(self, image) -> bool:
        """检测确认弹窗是否存在。

        购买弹窗有"购买"（右侧）+"取消"（左侧）按钮。
        刷新弹窗有"确认"（右侧）+"取消"（左侧）。
        左右分区搜索，避免弹窗标题文字干扰。

        Returns:
            bool: 弹窗是否存在
        """
        has_cancel = self._find_popup_button(image, "取消", region=POPUP_CANCEL_REGION) is not None
        has_buy = self._find_popup_button(image, "购买", region=POPUP_CONFIRM_REGION) is not None
        has_confirm = self._find_popup_button(image, "确认", region=POPUP_CONFIRM_REGION) is not None
        return has_cancel and (has_buy or has_confirm)

    def _detect_insufficient_gold(self, image) -> bool:
        """检测金币不足提示。"""
        blocks = self._ocr.read(image, region=INSUFFICIENT_GOLD_REGION, min_confidence=0.4)
        for block in blocks:
            if "不足" in block.text:
                logger.info(f"检测到金币不足提示: '{block.text}'")
                return True
        return False

    def _click_popup_button(self, image, button_text: str) -> bool:
        """搜索并点击弹窗中的按钮文字。

        Args:
            image: 截图
            button_text: 按钮文字

        Returns:
            bool: 是否找到并点击了按钮
        """
        pos = self._find_popup_button(image, button_text)
        if pos:
            logger.info(f"点击按钮 '{button_text}' 在 {pos}")
            self.device.click_position(pos[0], pos[1])
            time.sleep(0.3)
            return True
        return False

    def _click_confirm_in_popup(self, image) -> bool:
        """点击弹窗中的确认按钮（固定坐标，比 OCR 读文字位置更可靠）。

        Returns:
            bool: 是否点击了确认按钮
        """
        logger.info(f"点击确认按钮 @ {CONFIRM_BTN_POS}")
        self.device.click_position(CONFIRM_BTN_POS[0], CONFIRM_BTN_POS[1])
        time.sleep(0.3)
        return True

    # ------------------------------------------------------------------
    # 购买流程
    # ------------------------------------------------------------------

    def buy_item(self, item: ShopItem) -> PurchaseResult:
        """执行单个物品的购买流程。

        流程：点击物品 → 等待弹窗 → OCR 检测确认 → 点击确认/购买 → 验证。
        """
        logger.info(f"开始购买: {item.item_type}, 价格: {item.price}")

        # 1. 点击购买按钮（优先用 OCR 检测到的坐标，回退到行中央）
        if item.buy_button_pos:
            click_x, click_y = item.buy_button_pos
            logger.info(f"点击购买按钮 @ ({click_x}, {click_y})")
        else:
            y1, y2 = item.position[1], item.position[3]
            click_x = (BUY_BTN_X[0] + BUY_BTN_X[1]) // 2
            click_y = (y1 + y2) // 2
            logger.info(f"未检测到购买按钮，点击行中央 ({click_x}, {click_y})")
        self.device.click_position(click_x, click_y)

        # 2. 等待并处理确认弹窗
        confirm_timer = Timer(CONFIRM_POPUP_TIMEOUT)
        confirm_timer.start()
        confirmed = False

        while not confirm_timer.reached():
            image = self.device.screenshot()
            if image is None:
                continue

            # 检查金币不足
            if self._detect_insufficient_gold(image):
                reason = "金币不足"
                logger.warning(f"购买失败 - {item.item_type}: {reason}")
                self._close_popup(image)
                return PurchaseResult(
                    item_type=item.item_type,
                    price=item.price,
                    success=False,
                    reason=reason,
                )

            # 检测并点击确认弹窗
            if self._detect_confirm_popup(image):
                logger.info("检测到确认弹窗")
                self._click_confirm_in_popup(image)
                time.sleep(0.3)

                # 检查二次确认
                retry_img = self.device.screenshot()
                if self._detect_confirm_popup(retry_img):
                    logger.info("检测到二次确认弹窗")
                    self._click_confirm_in_popup(retry_img)
                    time.sleep(0.3)

                confirmed = True
                break

            time.sleep(0.3)

        # 弹窗未出现 → 重试
        if not confirmed:
            logger.warning(f"确认弹窗未出现，重试点击: {item.item_type}")
            self.device.click_position(click_x, click_y)
            time.sleep(1.0)
            retry_img = self.device.screenshot()

            if self._detect_confirm_popup(retry_img):
                logger.info("重试后检测到确认弹窗")
                self._click_confirm_in_popup(retry_img)
                confirmed = True

        if not confirmed:
            reason = "确认弹窗未出现"
            logger.warning(f"购买失败 - {item.item_type}: {reason}")
            return PurchaseResult(
                item_type=item.item_type,
                price=item.price,
                success=False,
                reason=reason,
            )

        # 3. 验证购买结果
        time.sleep(1.0)
        verify_img = self.device.screenshot()

        # 检查弹窗是否已关闭
        if self._detect_confirm_popup(verify_img):
            logger.warning(f"弹窗仍未关闭，重试确认: {item.item_type}")
            retry_confirmed = False
            retry_timer = Timer(2.0)
            retry_timer.start()
            while not retry_timer.reached():
                img = self.device.screenshot()
                if self._detect_confirm_popup(img):
                    self._click_confirm_in_popup(img)
                    time.sleep(0.3)
                    retry_confirmed = True
                    break
                time.sleep(0.3)

            if retry_confirmed:
                time.sleep(1.0)
                final_img = self.device.screenshot()
                if self._detect_confirm_popup(final_img):
                    reason = "弹窗确认后仍未关闭"
                    logger.warning(f"购买失败 - {item.item_type}: {reason}")
                    return PurchaseResult(
                        item_type=item.item_type,
                        price=item.price,
                        success=False,
                        reason=reason,
                    )

        logger.info(f"购买成功: {item.item_type}")
        return PurchaseResult(
            item_type=item.item_type,
            price=item.price,
            success=True,
        )

    def handle_confirm_popup(self) -> bool:
        """检测并处理确认弹窗（外部调用接口，兼容旧接口）。"""
        image = self.device.image
        if image is None:
            return False
        if self._detect_confirm_popup(image):
            self._click_confirm_in_popup(image)
            time.sleep(0.5)
            next_img = self.device.screenshot()
            if self._detect_confirm_popup(next_img):
                self._click_confirm_in_popup(next_img)
                time.sleep(0.5)
            return True
        return False

    def process_shelf(self, items: List[ShopItem]) -> List[PurchaseResult]:
        """处理整个货架的购买。"""
        results: List[PurchaseResult] = []
        bought_count = 0

        for item in items:
            if not self.should_buy(item):
                logger.info(f"跳过物品: {item.item_type}")
                continue

            result = self.buy_item(item)
            results.append(result)
            bought_count += 1

            logger.info(
                f"购买结果 - {result.item_type}: "
                f"{'成功' if result.success else '失败'}"
                f"{f' ({result.reason})' if result.reason else ''}"
            )

            interval = random.uniform(PURCHASE_INTERVAL_MIN, PURCHASE_INTERVAL_MAX)
            time.sleep(interval)

        logger.info(f"货架处理完成，共购买 {bought_count} 个物品")
        return results

    def close_popup(self, image) -> bool:
        """关闭当前弹窗（点击取消）。

        公开接口，供 SceneManager 等外部调用。

        Args:
            image: 截图

        Returns:
            bool: 是否成功找到并点击了取消按钮
        """
        return self._click_popup_button(image, "取消")

    def _close_popup(self, image) -> None:
        """尝试关闭当前弹窗（点击取消）。内部使用。"""
        try:
            if not self.close_popup(image):
                # 后备：点击弹窗外部区域
                self.device.click_position(800, 600)
                time.sleep(0.3)
        except Exception as e:
            logger.debug(f"关闭弹窗失败: {e}")
