"""
ShopBot 主控类 - 协调所有模块执行自动购买循环

主循环流程：识别物品 → 购买匹配物品 → 刷新货架
按钮检测使用 OCR 替代固定坐标+颜色方案，更鲁棒。
"""

import threading
import time
from dataclasses import dataclass
from typing import List, Optional

from config_manager import ConfigManager
from log import logger
from module.base.timer import Timer
from module.device.device import DeviceController
from shop.navigator import ShopNavigator
from shop.ocr_engine import OCR
from shop.purchase import PurchaseEngine, PurchaseResult, CONFIRM_BTN_POS, CANCEL_BTN_POS, POPUP_CANCEL_REGION, POPUP_CONFIRM_REGION, CONFIRM_POPUP_TIMEOUT
from shop.recognizer import ItemRecognizer
from shop.scene import Scene
from shop.scene_manager import SceneManager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 刷新按钮搜索区域（底部左侧，扩展到屏幕最底部）
REFRESH_BTN_REGION = (50, 620, 400, 718)

# 弹窗检测区域（居中弹窗）
POPUP_REGION = (300, 440, 950, 550)

# 天空石数值区域（实测 x≈918, y≈34）
SKYSTONE_REGION = (860, 0, 990, 55)

# 金币数值区域（实测 x≈780）
GOLD_REGION = (450, 5, 970, 40)

# 滑动翻页参数
SCROLL_AREA = (800, 400, 800, 150)
SCROLL_WAIT = 0.5  # 等待滑动动画结束
MAX_SCROLL_COUNT = 8

# 刷新确认弹窗等待超时
REFRESH_CONFIRM_TIMEOUT = 3.0
REFRESH_MAX_RETRIES = 2
REFRESH_CONFIRM_BTN_POS = (748, 460)
SHELF_LOAD_WAIT = 0.5
SKYSTONE_PER_REFRESH = 3
MAX_CONSECUTIVE_ERRORS = 3


@dataclass
class RunStatistics:
    total_refreshes: int = 0
    bookmarks_bought: int = 0
    mystic_medals_bought: int = 0
    equipment_bought: int = 0
    skystone_spent: int = 0
    skystone_remaining: int = 0


class ShopBot:
    def __init__(self, config: ConfigManager, device: DeviceController = None):
        self.config = config
        cfg = config.get()
        self.device = device or DeviceController(cfg.device)
        self.navigator = ShopNavigator(self.device)
        self.recognizer = ItemRecognizer(self.device)
        self.purchase_engine = PurchaseEngine(self.device, config)
        self.stats = RunStatistics()
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ocr = OCR
        self.scene_manager = SceneManager(self._ocr)
        self._refresh_btn_pos = None  # 校准后缓存刷新按钮位置

    def start(self) -> None:
        if self._running:
            logger.warning("ShopBot 已在运行中")
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self.run_loop, daemon=True)
        self._thread.start()
        logger.info("ShopBot 已启动")

    def stop(self) -> None:
        logger.info("ShopBot 收到停止请求，将在当前循环结束后停止")
        self._stop_event.set()

    @property
    def alive(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # 启动校准
    # ------------------------------------------------------------------

    def _calibrate_before_loop(self) -> None:
        """找最便宜的金币物品点购买，校准确认按钮坐标后取消。

        流程：识别物品 → 选最便宜的 → 点击购买 → 等待弹窗 →
        OCR 对比确认按钮坐标 → 点击取消 → 继续主循环。
        """
        logger.info("===== 启动校准 =====")
        items = self.recognizer.recognize_visible_items()
        if not items:
            logger.warning("校准: 未识别到物品，跳过")
            return

        # 选最便宜的、有货的、金币购买的物品
        candidates = [
            it for it in items
            if it.stock_available and it.currency == "gold" and it.price > 0
        ]
        if not candidates:
            logger.warning("校准: 无可购买的金币物品，跳过")
            return

        target = min(candidates, key=lambda it: it.price)
        logger.info(f"校准: 选择 '{target.name_text}' 价格 {target.price}")

        # 点击购买按钮
        cx, cy = target.buy_button_pos or (1192, (target.position[1] + target.position[3]) // 2)
        logger.info(f"校准: 点击购买 @ ({cx}, {cy})")
        self.device.click_position(cx, cy)

        # 等待弹窗出现
        timer = Timer(CONFIRM_POPUP_TIMEOUT)
        timer.start()
        popup_detected = False
        confirm_ocr_pos = None

        while not timer.reached():
            image = self.device.screenshot()
            if image is None:
                continue

            # 检测取消按钮 → 弹窗存在
            cancel_pos = self.purchase_engine._find_popup_button(
                image, "取消", region=POPUP_CANCEL_REGION
            )
            if cancel_pos is None:
                time.sleep(0.3)
                continue

            popup_detected = True
            logger.info("校准: 弹窗已出现")

            # 在右侧找确认按钮，对比固定坐标
            for text in ("购买", "确认"):
                pos = self.purchase_engine._find_popup_button(
                    image, text, region=POPUP_CONFIRM_REGION
                )
                if pos:
                    confirm_ocr_pos = pos
                    dx = pos[0] - CONFIRM_BTN_POS[0]
                    dy = pos[1] - CONFIRM_BTN_POS[1]
                    dist = (dx ** 2 + dy ** 2) ** 0.5
                    logger.info(
                        f"校准: '{text}' OCR=({pos[0]},{pos[1]}) "
                        f"默认={CONFIRM_BTN_POS} 偏差=({dx},{dy}) {dist:.0f}px"
                        + (" ✓" if dist <= 30 else " ⚠ 偏差较大")
                    )
                    break

            # 点取消关闭弹窗
            logger.info(f"校准: 点击取消 {cancel_pos}")
            self.device.click_position(cancel_pos[0], cancel_pos[1])

            # 确认弹窗关闭
            for _ in range(6):
                time.sleep(0.3)
                check = self.device.screenshot()
                still_open = self.purchase_engine._find_popup_button(
                    check, "取消", region=POPUP_CANCEL_REGION
                )
                if still_open is None:
                    logger.info("校准: 弹窗已关闭")
                    break
                logger.info("校准: 弹窗未关闭，再点取消")
                self.device.click_position(cancel_pos[0], cancel_pos[1])
            break

        if not popup_detected:
            logger.warning("校准: 弹窗未出现，跳过校准")

        # 顺便缓存刷新按钮位置，后续刷新跳过 OCR
        self._cache_refresh_button()
        self._log_active_methods()

    def _log_active_methods(self) -> None:
        """打印当前使用的截图/控制方式。"""
        ss = self.device._screenshot_strategy
        cs = self.device._control_strategy
        ss_name = ss.name if ss else self.device.screenshot_method
        cs_name = cs.name if cs else self.device.control_method
        logger.info(f"截图方式: {ss_name}")
        logger.info(f"控制方式: {cs_name}")

    # ------------------------------------------------------------------
    # 场景校验
    # ------------------------------------------------------------------

    def _ensure_secret_shop(self, image=None) -> bool:
        """确保当前在秘密商店，如果不在则尝试恢复。

        Args:
            image: 可选的截图，不传时自动截图。

        检测当前场景并处理异常：
        - PURCHASE_POPUP → 点击取消关闭弹窗
        - LOBBY → 重新导航到秘密商店
        - UNKNOWN → 先关弹窗，再导航
        - SECRET_SHOP → 无需操作

        Returns:
            True 如果在（或已回到）秘密商店，False 表示无法恢复。
        """
        if image is None:
            image = self.device.screenshot()
        if image is None:
            return False

        scene = self.scene_manager.detect(image)
        logger.debug(f"场景校验: {scene.value}")

        if scene == Scene.SECRET_SHOP:
            return True

        if scene == Scene.PURCHASE_POPUP:
            logger.info("场景校验: 检测到购买弹窗残留，尝试关闭")
            if not self.purchase_engine.close_popup(image):
                logger.debug("未找到取消按钮，使用固定坐标")
                self.device.click_position(CANCEL_BTN_POS[0], CANCEL_BTN_POS[1])
            time.sleep(0.5)
            # 再次截图确认弹窗已关闭并重新校验
            after = self.device.screenshot()
            if after is not None and self.scene_manager.ensure(after, Scene.SECRET_SHOP):
                return True
            # 如果仍在弹窗状态，走导航流程（更彻底的恢复）
            logger.info("弹窗关闭后未回到商店，尝试导航")
            return self.navigator.navigate_to_secret_shop()

        if scene == Scene.LOBBY:
            logger.warning("场景校验: 检测到大堂，重新导航到秘密商店")
            return self.navigator.navigate_to_secret_shop()

        # UNKNOWN
        logger.warning("场景校验: 未知场景，尝试恢复")
        if self.navigator.handle_popup():
            time.sleep(1.0)
            after = self.device.screenshot()
            if after is not None and self.scene_manager.ensure(after, Scene.SECRET_SHOP):
                return True
        return self.navigator.navigate_to_secret_shop()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run_loop(self) -> None:
        consecutive_errors = 0
        try:
            if not self.device.connect():
                logger.error("设备连接失败，终止运行")
                return
            if not self.navigator.navigate_to_secret_shop():
                logger.error("导航至秘密商店失败，终止运行")
                return
            self._calibrate_before_loop()
            while not self._stop_event.is_set():
                refresh_count = self.stats.total_refreshes
                logger.info(f"===== 第 {refresh_count + 1} 轮 =====")

                # 场景校验：确保在秘密商店
                if not self._ensure_secret_shop():
                    logger.error("场景校验失败，无法回到秘密商店，终止运行")
                    break

                try:
                    results: List[PurchaseResult] = []

                    # 1. 先滑到顶部，确保从最上面开始
                    self._scroll_to_top()

                    # 2. 逐段下滑：识别当前可视 → 购买 → 再滑
                    results = self._scroll_down_and_buy()
                    self.update_statistics(results)
                    if self._stop_event.is_set():
                        break
                    if not self.check_resources():
                        logger.info("资源不足，停止刷新")
                        break
                    cfg = self.config.get()
                    if not self.should_continue(
                        self.stats.skystone_remaining,
                        cfg.shop.skystone_threshold,
                        self.stats.total_refreshes,
                        cfg.shop.max_refresh_count,
                        bookmarks_bought=self.stats.bookmarks_bought,
                        max_bookmarks=cfg.shop.max_bookmarks,
                        mystic_medals_bought=self.stats.mystic_medals_bought,
                        max_mystic_medals=cfg.shop.max_mystic_medals,
                        skystone_spent=self.stats.skystone_spent,
                        max_skystone_spend=cfg.shop.max_skystone_spend,
                    ):
                        logger.info("达到停止条件，结束运行")
                        break
                    if not self.refresh_shop():
                        logger.error("刷新货架失败，终止运行")
                        break
                    self.stats.total_refreshes += 1
                    self.stats.skystone_spent += SKYSTONE_PER_REFRESH
                    consecutive_errors = 0
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"主循环异常（连续第 {consecutive_errors} 次）: {e}")
                    if not self.recover_from_error():
                        logger.error("异常恢复失败")
                    else:
                        logger.info("异常恢复成功，继续运行")
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(f"连续 {MAX_CONSECUTIVE_ERRORS} 次恢复失败，终止运行")
                        break
        finally:
            self._running = False
            self._log_statistics()
            logger.info("ShopBot 已停止")

    # ------------------------------------------------------------------
    # 刷新按钮缓存（校准阶段 OCR 一次，后续复用）
    # ------------------------------------------------------------------

    def _cache_refresh_button(self) -> None:
        """截图 OCR 检测刷新按钮位置并缓存。"""
        image = self.device.screenshot()
        if image is None:
            return
        btn = self._find_refresh_button(image)
        if btn:
            self._refresh_btn_pos = btn
            logger.info(f"缓存刷新按钮位置: {btn}")
        else:
            logger.warning("未能检测到刷新按钮，后续将使用 OCR")

    # ------------------------------------------------------------------
    # 刷新
    # ------------------------------------------------------------------

    def _find_refresh_button(self, image) -> Optional[tuple]:
        """在底部区域搜索刷新按钮文字，返回点击坐标。

        搜索关键词包括 '重置'、'刷新'，降低置信度阈值以适配小字按钮。
        """
        keywords = ("立即更新", "重置", "刷新")
        for kw in keywords:
            blocks = self._ocr.read(image, region=REFRESH_BTN_REGION, min_confidence=0.3)
            for block in blocks:
                if kw in block.text:
                    cx, cy = int(block.cx), int(block.cy)
                    logger.debug(f"找到刷新按钮 '{kw}' 在 ({cx}, {cy})")
                    return (cx, cy)
        return None

    def _find_popup_confirm(self, image) -> Optional[tuple]:
        """在弹窗区域搜索 '确认' 文字，返回点击坐标。"""
        blocks = self._ocr.read(image, region=POPUP_REGION, min_confidence=0.4)
        for block in blocks:
            if "确认" in block.text:
                return (int(block.cx), int(block.cy))
        return None

    def refresh_shop(self) -> bool:
        """刷新货架（优先用缓存位置，跳过 OCR）。"""
        # 刷新前校验场景
        if not self._ensure_secret_shop():
            logger.error("场景校验失败，无法刷新")
            return False

        for attempt in range(1, REFRESH_MAX_RETRIES + 1):
            # 优先用缓存位置
            btn_pos = self._refresh_btn_pos
            if btn_pos is None:
                logger.info(f"寻找刷新按钮（第 {attempt} 次）")
                image = self.device.screenshot()
                btn_pos = self._find_refresh_button(image)

            if btn_pos is None:
                logger.warning(f"未找到刷新按钮（第 {attempt} 次）")
                self.device.save_error_screenshot(name=f"refresh_fail_{attempt}")
                time.sleep(1.0)
                continue

            logger.info(f"点击刷新按钮 {btn_pos}")
            self.device.click_position(btn_pos[0], btn_pos[1])

            # 等弹窗出现后直接点固定坐标，跳过 OCR
            time.sleep(0.4)
            logger.info(f"点击刷新确认 @ {REFRESH_CONFIRM_BTN_POS}")
            self.device.click_position(REFRESH_CONFIRM_BTN_POS[0], REFRESH_CONFIRM_BTN_POS[1])
            time.sleep(0.3)
            confirmed = True

            if confirmed:
                logger.info("等待货架加载...")
                time.sleep(SHELF_LOAD_WAIT)
                return True

            logger.warning(f"刷新确认弹窗未出现（第 {attempt} 次）")

        logger.error(f"刷新失败，已重试 {REFRESH_MAX_RETRIES} 次")
        return False

    # ------------------------------------------------------------------
    # 滑动翻页购买（先滑到顶，再逐段下滑，边滚边买）
    # ------------------------------------------------------------------

    def _scroll_to_top(self) -> None:
        """向上滑动回到货架顶部。

        刷新后货架默认在顶部，滑一次即可。
        """
        logger.info("滑动到货架顶部...")
        self.device.swipe(
            start=(SCROLL_AREA[2], SCROLL_AREA[3]),  # x=640, y=150
            end=(SCROLL_AREA[0], SCROLL_AREA[1]),    # x=640, y=400
        )
        time.sleep(0.3)

    def _scroll_down_and_buy(self) -> List[PurchaseResult]:
        """从顶部开始，逐段下滑识别并购买。

        流程：
          1. 识别当前可视物品 → 立即购买
          2. 向下滑一段 → 等待动画 → 识别新物品 → 立即购买
          3. 比较前后两次识别结果，无变化则认为到底

        Returns:
            本轮所有购买结果
        """
        all_results: List[PurchaseResult] = []
        prev_item_keys: set = set()

        for scroll_count in range(MAX_SCROLL_COUNT + 1):  # +1 因为第0次不滑动
            if self._stop_event.is_set():
                break

            # 第0次不滑动（已在顶部的初始视图）
            if scroll_count > 0:
                start = (SCROLL_AREA[0], SCROLL_AREA[1])   # (640, 400)
                end = (SCROLL_AREA[2], SCROLL_AREA[3])     # (640, 150)
                self.device.swipe(start, end)
                time.sleep(SCROLL_WAIT)

            # 截图一次，复用给场景校验和物品识别
            image = self.device.screenshot()
            if image is None:
                break

            # 场景校验
            if not self._ensure_secret_shop(image):
                logger.warning("场景校验失败，终止滑动购买")
                break

            # 识别当前可视物品，立即购买
            items = self.recognizer.recognize_visible_items(image)

            # 比较识别结果（去除 name_text 空白干扰），无变化则到底
            curr_keys = {(it.item_type, it.name_text.strip() if it.name_text else "", round(it.position[1] / 20))
                         for it in items}
            if prev_item_keys and curr_keys == prev_item_keys:
                logger.info(f"已到达货架底部（第 {scroll_count} 次滑动后，识别结果无变化）")
                break
            prev_item_keys = curr_keys

            results = self.purchase_engine.process_shelf(items)
            all_results.extend(results)
            logger.info(f"第 {scroll_count} 次查看，购买 {len(results)} 个物品")

        return all_results

    # ------------------------------------------------------------------
    # 资源检查
    # ------------------------------------------------------------------

    def check_resources(self) -> bool:
        """通过 OCR 读取天空石数量并检查是否足够。"""
        cfg = self.config.get()
        if cfg.shop.skystone_threshold <= 0:
            return True

        image = self.device.screenshot()
        value, conf = self._ocr.read_number(image, region=SKYSTONE_REGION, min_confidence=0.3)
        if value is not None:
            self.stats.skystone_remaining = value
            logger.info(f"天空石: {value} (conf={conf:.2f}), 阈值: {cfg.shop.skystone_threshold}")
            if value < cfg.shop.skystone_threshold:
                return False
        else:
            logger.warning("未能读取天空石数量，跳过检查")

        return True

    def should_continue(self, skystone_remaining, skystone_threshold,
                        refresh_count, max_refresh_count,
                        bookmarks_bought=0, max_bookmarks=0,
                        mystic_medals_bought=0, max_mystic_medals=0,
                        skystone_spent=0, max_skystone_spend=0):
        if skystone_remaining < skystone_threshold:
            logger.info(f"停止：天空石 {skystone_remaining} < 阈值 {skystone_threshold}")
            return False
        if refresh_count >= max_refresh_count:
            logger.info(f"停止：已刷新 {refresh_count} 次 >= 上限 {max_refresh_count}")
            return False
        if 0 < max_bookmarks <= bookmarks_bought:
            logger.info(f"停止：已购书签 {bookmarks_bought} >= 上限 {max_bookmarks}")
            return False
        if 0 < max_mystic_medals <= mystic_medals_bought:
            logger.info(f"停止：已购神秘奖章 {mystic_medals_bought} >= 上限 {max_mystic_medals}")
            return False
        if 0 < max_skystone_spend <= skystone_spent:
            logger.info(f"停止：消耗天空石 {skystone_spent} >= 上限 {max_skystone_spend}")
            return False
        return True

    def recover_from_error(self) -> bool:
        try:
            self.device.save_error_screenshot(name="error_recovery")
            logger.info("尝试恢复到秘密商店界面...")
            return self.navigator.navigate_to_secret_shop()
        except Exception as e:
            logger.error(f"异常恢复过程中出错: {e}")
            return False

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_statistics(self) -> RunStatistics:
        return RunStatistics(
            total_refreshes=self.stats.total_refreshes,
            bookmarks_bought=self.stats.bookmarks_bought,
            mystic_medals_bought=self.stats.mystic_medals_bought,
            equipment_bought=self.stats.equipment_bought,
            skystone_spent=self.stats.skystone_spent,
            skystone_remaining=self.stats.skystone_remaining,
        )

    def update_statistics(self, results: List[PurchaseResult]) -> None:
        for r in results:
            if not r.success:
                continue
            if r.item_type == "bookmark":
                self.stats.bookmarks_bought += 1
            elif r.item_type == "mystic_medal":
                self.stats.mystic_medals_bought += 1
            elif r.item_type == "equipment":
                self.stats.equipment_bought += 1

    def _log_statistics(self) -> None:
        s = self.stats
        logger.info("========== 运行统计 ==========")
        logger.info(f"总刷新次数: {s.total_refreshes}")
        logger.info(f"购买书签: {s.bookmarks_bought}")
        logger.info(f"购买神秘奖章: {s.mystic_medals_bought}")
        logger.info(f"购买装备: {s.equipment_bought}")
        logger.info(f"天空石消耗: {s.skystone_spent}")
        logger.info(f"天空石余量: {s.skystone_remaining}")
        logger.info("==============================")
