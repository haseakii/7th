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


@dataclass
class _PopupState:
    """单次 OCR 扫描弹窗的检测结果。"""
    has_cancel: bool = False
    has_buy_or_confirm: bool = False
    insufficient_gold: bool = False
    cancel_pos: Optional[Tuple[int, int]] = None


class PurchaseEngine:
    """执行物品购买操作。

    流程：点击物品 → 等待弹窗 → OCR 检测 "确认" 按钮 → 点击 → 验证。
    按钮检测使用 OCR 读取弹窗文字，不依赖固定坐标或颜色。
    """

    def __init__(self, device: DeviceController, config: ConfigManager):
        self.device = device
        self.config = config
        self._ocr = OCR

    # ------------------------------------------------------------------
    # 弹窗 OCR 扫描（单次 OCR 检测所有按钮状态）
    # ------------------------------------------------------------------

    def _scan_popup(self, image) -> _PopupState:
        """单次 OCR 扫描弹窗区域，检测所有按钮状态。

        覆盖弹窗按钮区域和金币不足提示区域，
        替代 _detect_confirm_popup + _detect_insufficient_gold 的多次 OCR。

        Args:
            image: 截图

        Returns:
            _PopupState 包含所有检测到的按钮。
        """
        scan_region = (
            POPUP_REGION[0],
            INSUFFICIENT_GOLD_REGION[1],
            POPUP_REGION[2],
            POPUP_REGION[3],
        )
        blocks = self._ocr.read(image, region=scan_region, min_confidence=0.4)

        state = _PopupState()
        for b in blocks:
            cx = int(b.cx)
            cy = int(b.cy)

            # 金币不足 (y=280-400)
            if ("不足" in b.text
                    and INSUFFICIENT_GOLD_REGION[0] <= cx <= INSUFFICIENT_GOLD_REGION[2]
                    and INSUFFICIENT_GOLD_REGION[1] <= cy <= INSUFFICIENT_GOLD_REGION[3]):
                state.insufficient_gold = True
            # 取消按钮 (y=440-550)
            elif ("取消" in b.text
                  and POPUP_CANCEL_REGION[0] <= cx <= POPUP_CANCEL_REGION[2]
                  and POPUP_CANCEL_REGION[1] <= cy <= POPUP_CANCEL_REGION[3]):
                state.has_cancel = True
                state.cancel_pos = (cx, cy + BUTTON_CLICK_OFFSET_Y)
            # 确认/购买按钮 (y=440-550)
            elif (("购买" in b.text or "确认" in b.text)
                  and POPUP_CONFIRM_REGION[0] <= cx <= POPUP_CONFIRM_REGION[2]
                  and POPUP_CONFIRM_REGION[1] <= cy <= POPUP_CONFIRM_REGION[3]):
                state.has_buy_or_confirm = True

        return state

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
        """检测确认弹窗是否存在（使用 _scan_popup 单次 OCR）。

        Returns:
            bool: 弹窗是否存在
        """
        state = self._scan_popup(image)
        return state.has_cancel and state.has_buy_or_confirm

    def _detect_insufficient_gold(self, image) -> bool:
        """检测金币不足提示（使用 _scan_popup 单次 OCR）。"""
        state = self._scan_popup(image)
        if state.insufficient_gold:
            logger.info("检测到金币不足提示")
        return state.insufficient_gold

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

            # 单次 OCR 扫描弹窗所有状态
            popup = self._scan_popup(image)

            # 检查金币不足
            if popup.insufficient_gold:
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
            if popup.has_cancel and popup.has_buy_or_confirm:
                logger.info("检测到确认弹窗")
                self._click_confirm_in_popup(image)
                time.sleep(0.3)

                # 检查二次确认（复用 _scan_popup）
                retry_img = self.device.screenshot()
                retry_popup = self._scan_popup(retry_img)
                if retry_popup.has_cancel and retry_popup.has_buy_or_confirm:
                    logger.info("检测到二次确认弹窗")
                    self._click_confirm_in_popup(retry_img)
                    time.sleep(0.3)

                confirmed = True
                break

            time.sleep(0.15)

        # 弹窗未出现 → 重试
        if not confirmed:
            logger.warning(f"确认弹窗未出现，重试点击: {item.item_type}")
            self.device.click_position(click_x, click_y)
            time.sleep(1.0)
            retry_img = self.device.screenshot()

            retry_popup = self._scan_popup(retry_img)
            if retry_popup.has_cancel and retry_popup.has_buy_or_confirm:
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
        time.sleep(0.5)
        verify_img = self.device.screenshot()

        # 检查弹窗是否已关闭
        verify_popup = self._scan_popup(verify_img)
        if verify_popup.has_cancel and verify_popup.has_buy_or_confirm:
            logger.warning(f"弹窗仍未关闭，重试确认: {item.item_type}")
            retry_timer = Timer(2.0)
            retry_timer.start()
            while not retry_timer.reached():
                img = self.device.screenshot()
                retry = self._scan_popup(img)
                if retry.has_cancel and retry.has_buy_or_confirm:
                    self._click_confirm_in_popup(img)
                    time.sleep(0.3)
                    break
                time.sleep(0.15)

            time.sleep(0.5)
            final_img = self.device.screenshot()
            final_popup = self._scan_popup(final_img)
            if final_popup.has_cancel and final_popup.has_buy_or_confirm:
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
