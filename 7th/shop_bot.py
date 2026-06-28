"""
ShopBot 主控类 - 协调所有模块执行自动购买循环

主循环流程：识别物品 → 购买匹配物品 → 刷新货架
按钮检测使用 OCR 替代固定坐标+颜色方案，更鲁棒。
"""

import gc
import os
import threading
import time
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from types import SimpleNamespace
from typing import Dict, Union

from module.logger import logger
from module.base.timer import Timer
from module.device.device import DeviceController
from module.vision.frame import FrameContext, capture_device_frame
from module.vision.profile import SECRET_SHOP_PROFILE
from tasks.secret_shop.navigator import ShopNavigator
from tasks.secret_shop.ocr_engine import OCR
from tasks.secret_shop.purchase import PurchaseEngine, PurchaseResult, CONFIRM_BTN_POS, CANCEL_BTN_POS, POPUP_CANCEL_REGION, POPUP_CONFIRM_REGION, CONFIRM_POPUP_TIMEOUT
from tasks.secret_shop.recognizer import ItemRecognizer, SHELF_COMPARE_AREA
from tasks.secret_shop.scene import Scene
from tasks.secret_shop.scene_manager import SceneManager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 刷新按钮搜索区域（底部左侧）
REFRESH_BTN_REGION = SECRET_SHOP_PROFILE.refresh_button_region

# 弹窗检测区域（居中弹窗）
POPUP_REGION = SECRET_SHOP_PROFILE.popup_region

# 天空石数值区域（与标定值对齐：x=1100-1260, y=5-30）
SKYSTONE_REGION = SECRET_SHOP_PROFILE.skystone_region

# 金币数值区域（与标定值对齐）
GOLD_REGION = SECRET_SHOP_PROFILE.gold_region

# 滑动翻页参数
SCROLL_AREA = (800, 400, 800, 150)
SCROLL_WAIT = 0.5
SCROLL_SETTLE_TIMEOUT = 3.0  # 滑动后稳定超时（秒）
SCROLL_FRAME_SIMILARITY = 0.98  # 连续两帧相似度阈值（判定滑动动画完成）  # 等待滑动动画结束
MAX_SCROLL_COUNT = 8

# 刷新确认弹窗等待超时
REFRESH_CONFIRM_TIMEOUT = 3.0
REFRESH_MAX_RETRIES = 2
REFRESH_CONFIRM_BTN_POS = SECRET_SHOP_PROFILE.refresh_confirm_position
SHELF_LOAD_WAIT = 0.8
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
    """商店自动刷新购买主控类。

    接受 E7Config 作为配置，内部统一为 _cfg 对象。
    """

    @staticmethod
    def _normalize_config(config) -> SimpleNamespace:
        """统一不同配置类型为 _(cfg).device / .shop 访问方式。"""
        # E7Config → 映射为 SimpleNamespace
        if hasattr(config, 'BuyBookmarks'):
            from module.config.config import E7Config
            if isinstance(config, E7Config):
                return SimpleNamespace(
                    device=SimpleNamespace(
                        serial=config.serial,
                        screenshot_method=config.screenshot_method,
                        control_method=config.control_method,
                        ocr_method=getattr(config, 'OcrMethod', 'rapidocr'),
                    ),
                    shop=SimpleNamespace(
                        buy_bookmarks=config.BuyBookmarks,
                        buy_mystic_medals=config.BuyMysticMedals,
                        buy_equipment=config.BuyEquipment,
                        buy_fodder=config.BuyFodder,
                        max_refresh_count=config.MaxRefreshCount,
                        gold_threshold=config.GoldThreshold,
                        skystone_threshold=config.SkystoneThreshold,
                        max_bookmarks=config.MaxBookmarks,
                        max_mystic_medals=config.MaxMysticMedals,
                        max_skystone_spend=config.MaxSkystoneSpend,
                    ),
                )

        # fallback: 裸 SimpleNamespace 或 AppConfig
        if hasattr(config, 'device') and hasattr(config, 'shop') and config.device is not None and config.shop is not None:
            return config

        # fallback: 裸 dict
        return config

    @staticmethod
    def _extract_buy_list(cfg) -> Dict[str, bool]:
        """从 _cfg 提取 buy_list。"""
        shop = cfg.shop if hasattr(cfg, 'shop') else cfg
        return {
            'bookmarks': getattr(shop, 'buy_bookmarks', True),
            'mystic_medals': getattr(shop, 'buy_mystic_medals', True),
            'equipment': getattr(shop, 'buy_equipment', False),
            'fodder': getattr(shop, 'buy_fodder', False),
        }

    def __init__(self, config, device: DeviceController = None):
        self._raw_config = config
        self._cfg = self._normalize_config(config)
        cfg = self._cfg
        self.device = device or DeviceController(cfg.device)
        self.navigator = ShopNavigator(self.device)
        self.recognizer = ItemRecognizer(self.device)
        self.purchase_engine = PurchaseEngine(
            self.device,
            buy_list=self._extract_buy_list(cfg),
        )
        self.stats = RunStatistics()
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ocr = OCR
        self.scene_manager = SceneManager(self._ocr)
        self._refresh_btn_pos = None  # 校准后缓存刷新按钮位置
        self._skystone_known = False  # 首次 OCR 是否成功读到天空石
        self._skystone_check_counter = 99  # 首次检查强制 OCR

    # 保留 .config 属性访问（部分外部代码可能直接使用）
    def _capture_frame(self) -> Optional[FrameContext]:
        """Capture once and wrap the image with per-frame caches."""
        return capture_device_frame(self.device)

    @property
    def config(self):
        return self._raw_config

    def _should_continue_current_task(self) -> bool:
        """Stop only SecretShop when WebUI disables this task."""
        if self._stop_event.is_set():
            return False
        if not hasattr(self._raw_config, "is_task_enabled"):
            return True
        try:
            if hasattr(self._raw_config, "load"):
                self._raw_config.load()
            enabled = self._raw_config.is_task_enabled("SecretShop")
        except Exception as e:
            logger.warning(f"Failed to check SecretShop enable state: {e}")
            return True
        if not enabled:
            logger.info("SecretShop disabled in config; stopping current task only")
            return False
        return True

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

    def _cleanup_memory(self) -> None:
        """定期内存清理：GC + OpenCV 缓冲。"""
        gc.collect()
        try:
            import cv2
            cv2.setNumThreads(0)
        except Exception:
            pass

    def _wait_scroll_settle(self, timeout: float = SCROLL_SETTLE_TIMEOUT) -> bool:
        """等待滑动动画稳定。

        连续截两帧，若图像相似度 >= SCROLL_FRAME_SIMILARITY 则认为已稳定。
        首次等待 SCROLL_WAIT 后再开始检测（避免快速比较浪费截图调用）。
        超时返回 False（继续执行，不阻塞主循环）。
        """
        time.sleep(SCROLL_WAIT)

        import cv2
        deadline = time.time() + timeout
        try:
            prev = self.device.screenshot()
            if prev is None:
                return False

            while time.time() < deadline:
                curr = self.device.screenshot()
                if curr is None:
                    return False

                prev_crop = prev[
                    SHELF_COMPARE_AREA[1]:SHELF_COMPARE_AREA[3],
                    SHELF_COMPARE_AREA[0]:SHELF_COMPARE_AREA[2],
                ]
                curr_crop = curr[
                    SHELF_COMPARE_AREA[1]:SHELF_COMPARE_AREA[3],
                    SHELF_COMPARE_AREA[0]:SHELF_COMPARE_AREA[2],
                ]
                # 灰度转换 + 结构相似度
                pgray = cv2.cvtColor(prev_crop, cv2.COLOR_BGR2GRAY)
                cgray = cv2.cvtColor(curr_crop, cv2.COLOR_BGR2GRAY)
                diff = cv2.absdiff(pgray, cgray)
                similarity = 1.0 - (float(np.mean(diff)) / 255.0)

                if similarity >= SCROLL_FRAME_SIMILARITY:
                    return True

                prev = curr
                time.sleep(0.08)

            logger.warning(f"滑动稳定等待超时 ({timeout}s)")
            return False
        except Exception as e:
            logger.warning(f"滑动稳定检测异常: {e}")
            return False

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

        优先选已知类型的物品（排除 OCR 噪音），点击无弹窗则重试下一个。
        """
        logger.info("===== 启动校准 =====")
        items = self.recognizer.recognize_visible_items()
        if not items:
            logger.warning("校准: 未识别到物品，跳过")
            return

        # 选有货的、金币购买的物品
        base_candidates = [
            it for it in items
            if it.stock_available and it.currency == "gold" and it.price > 0
        ]
        if not base_candidates:
            logger.warning("校准: 无可购买的金币物品，跳过")
            self._cache_refresh_button()
            self._log_active_methods()
            return

        # 优先选已知类型（排除 OCR 噪音识别的 unknown）
        known = [it for it in base_candidates if it.item_type != "unknown" and it.confidence >= 0.5]
        candidates = known if known else base_candidates
        candidates.sort(key=lambda it: it.price)

        for target in candidates:
            logger.info(f"校准: 尝试 '{target.name_text}' 类型={target.item_type} 价格={target.price}")

            # 点击购买按钮
            cx, cy = target.buy_button_pos or (1192, (target.position[1] + target.position[3]) // 2)
            logger.info(f"校准: 点击购买 @ ({cx}, {cy})")
            self.device.click_position(cx, cy)

            # 等待弹窗出现（含一次重试点击）
            popup_detected = self._wait_calibration_popup(cx, cy)

            if popup_detected:
                logger.info("校准: 弹窗确认完成")
                break

            logger.warning(f"校准: 物品 '{target.name_text}' 点击无弹窗，尝试下一个")
        else:
            popup_detected = False

        if not popup_detected:
            logger.warning("校准: 所有物品均无弹窗，跳过")
        else:
            pass  # 坐标已缓存到 self._confirm_offsets

        # 顺便缓存刷新按钮位置，后续刷新跳过 OCR
        self._cache_refresh_button()
        self._log_active_methods()

    def _wait_calibration_popup(self, click_x: int, click_y: int) -> bool:
        """点击物品后等待弹窗，若超时则重试一次点击。

        Returns:
            True 如果弹窗出现并成功处理（取消关闭），False 否则。
        """
        for attempt in range(2):
            timer = Timer(CONFIRM_POPUP_TIMEOUT + 1.0 if attempt == 0 else CONFIRM_POPUP_TIMEOUT)
            timer.start()

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

                logger.info("校准: 弹窗已出现")

                # 在右侧找确认按钮，对比固定坐标
                for text in ("购买", "确认"):
                    pos = self.purchase_engine._find_popup_button(
                        image, text, region=POPUP_CONFIRM_REGION
                    )
                    if pos:
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
                        return True
                    logger.info("校准: 弹窗未关闭，再点取消")
                    self.device.click_position(cancel_pos[0], cancel_pos[1])
                return True

            if attempt == 0:
                logger.info("校准: 弹窗未出现，重试点击")
                self.device.click_position(click_x, click_y)

        return False

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
        frame_or_image = image if image is not None else self._capture_frame()
        if frame_or_image is None:
            return False

        scene = self.scene_manager.detect(frame_or_image)
        logger.debug(f"场景校验: {scene.value}")

        if scene == Scene.SECRET_SHOP:
            return True

        if scene == Scene.PURCHASE_POPUP:
            logger.info("场景校验: 检测到购买弹窗残留，尝试关闭")
            if not self.purchase_engine.close_popup(frame_or_image):
                logger.debug("未找到取消按钮，使用固定坐标")
                self.device.click_position(CANCEL_BTN_POS[0], CANCEL_BTN_POS[1])
            time.sleep(0.5)
            # 再次截图确认弹窗已关闭并重新校验
            after = self._capture_frame()
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
            after = self._capture_frame()
            if after is not None and self.scene_manager.ensure(after, Scene.SECRET_SHOP):
                return True
        return self.navigator.navigate_to_secret_shop()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run_loop(self) -> None:
        consecutive_errors = 0
        try:
            if not self.device.connect(stop_event=self._stop_event):
                logger.error("设备连接失败，终止运行")
                return
            if not self.navigator.navigate_to_secret_shop():
                logger.error("导航至秘密商店失败，终止运行")
                return
            self._calibrate_before_loop()
            while not self._stop_event.is_set():
                if not self._should_continue_current_task():
                    break
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
                    cfg = self._cfg
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
                    self.stats.skystone_remaining -= SKYSTONE_PER_REFRESH
                    self._skystone_check_counter += 1

                    # 定期强制 GC，清理 OCR/OpenCV 中间缓冲区
                    if self.stats.total_refreshes % 10 == 0:
                        self._cleanup_memory()

                    # 每 100 轮记录内存用量
                    if self.stats.total_refreshes % 100 == 0:
                        try:
                            import psutil
                            proc = psutil.Process(os.getpid())
                            mem = proc.memory_info()
                            logger.info(f"内存: RSS={mem.rss // 1024 // 1024}MB, VMS={mem.vms // 1024 // 1024}MB")
                        except Exception:
                            pass

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
        frame = self._capture_frame()
        if frame is None:
            return
        btn = self._find_refresh_button(frame)
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
        if not self._ensure_secret_shop():
            logger.error("场景校验失败，无法刷新")
            return False

        for attempt in range(1, REFRESH_MAX_RETRIES + 1):
            btn_pos = self._refresh_btn_pos
            if btn_pos is None:
                logger.info(f"寻找刷新按钮（第 {attempt} 次）")
                frame = self._capture_frame()
                btn_pos = self._find_refresh_button(frame) if frame is not None else None

            if btn_pos is None:
                logger.warning(f"未找到刷新按钮（第 {attempt} 次）")
                self.device.save_error_screenshot(name=f"refresh_fail_{attempt}")
                time.sleep(1.0)
                continue

            logger.info(f"点击刷新按钮 {btn_pos}")
            self.device.click_position(btn_pos[0], btn_pos[1])
            time.sleep(0.6)

            # 点固定坐标确认按钮
            logger.info(f"点击刷新确认 @ {REFRESH_CONFIRM_BTN_POS}")
            self.device.click_position(REFRESH_CONFIRM_BTN_POS[0], REFRESH_CONFIRM_BTN_POS[1])

            # 验证弹窗已关闭
            time.sleep(0.5)
            verify_frame = self._capture_frame()
            if verify_frame is not None and self._find_popup_confirm(verify_frame) is not None:
                logger.warning(f"刷新确认弹窗未关闭（第 {attempt} 次），重试")
                continue

            logger.info("等待货架加载...")
            time.sleep(SHELF_LOAD_WAIT)
            return True

        logger.error(f"刷新失败，已重试 {REFRESH_MAX_RETRIES} 次")
        return False

    # ------------------------------------------------------------------
    # 滑动翻页购买（先滑到顶，再逐段下滑，边滚边买）
    # ------------------------------------------------------------------

    @staticmethod
    def _shelf_is_at_bottom(prev: np.ndarray, curr: np.ndarray, threshold: float = 0.85) -> bool:
        """通过货架区域图像相似度判断是否到底。

        滑动前后对比货架区域 (y=120-540, x=300-900)，
        相似度高于阈值则认为到底（无新内容出现）。

        Args:
            prev: 滑动前的截图
            curr: 滑动后的截图
            threshold: 相似度阈值（0-1），默认 0.95

        Returns:
            True 如果图像相似度超过阈值（已到底）
        """
        import cv2
        gray_prev = cv2.cvtColor(prev[120:540, 300:900], cv2.COLOR_BGR2GRAY)
        gray_curr = cv2.cvtColor(curr[120:540, 300:900], cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray_prev, gray_curr)
        similarity = 1.0 - (float(diff.mean()) / 255.0)
        return similarity > threshold

    def _scroll_to_top(self) -> None:
        """向上滑动回到货架顶部。

        刷新后货架默认在顶部，滑一次即可。
        """
        logger.info("滑动到货架顶部...")
        self.device.swipe(
            start=(SCROLL_AREA[2], SCROLL_AREA[3]),  # x=640, y=150
            end=(SCROLL_AREA[0], SCROLL_AREA[1]),    # x=640, y=400
        )
        time.sleep(0.4)

    def _scroll_down_and_buy(self) -> List[PurchaseResult]:
        """从顶部开始，逐段下滑识别并购买。

        流程：
          1. 识别当前可视物品 → 立即购买
          2. 向下滑一段 → 等待动画 → 识别新物品 → 立即购买
          3. 图像相似度检测底部（快速）→ 备选 OCR 结果对比

        Returns:
            本轮所有购买结果
        """
        all_results: List[PurchaseResult] = []
        prev_item_keys: set = set()
        prev_shelf_image = None

        for scroll_count in range(MAX_SCROLL_COUNT + 1):  # +1 因为第0次不滑动
            if not self._should_continue_current_task():
                break

            # 第0次不滑动（已在顶部的初始视图）
            if scroll_count > 0:
                start = (SCROLL_AREA[0], SCROLL_AREA[1])
                end = (SCROLL_AREA[2], SCROLL_AREA[3])
                self.device.swipe(start, end)
                self._wait_scroll_settle()

                # 截图
                image = self.device.screenshot()
                if image is None:
                    break

                # 图像底部检测（比 OCR 快得多，~5ms vs ~300ms）
                if prev_shelf_image is not None and self._shelf_is_at_bottom(prev_shelf_image, image):
                    logger.info(f"接近货架底部（第 {scroll_count} 次滑动，图像相似度检测）")
                    # 到底前再识别一次，避免漏掉底部新出现的物品
                    items = self.recognizer.recognize_visible_items(image)
                    if items:
                        curr_keys = {(it.item_type, it.name_text.strip() if it.name_text else "", round(it.position[1] / 20))
                                     for it in items}
                        if curr_keys != prev_item_keys:
                            logger.info(f"到底前识别到 {len(items)} 个物品，尝试购买")
                            results = self.purchase_engine.process_shelf(items)
                            all_results.extend(results)
                            if results:
                                time.sleep(0.3)
                    break
            else:
                image = self.device.screenshot()
                if image is None:
                    break

            # 场景校验
            frame = FrameContext(image=image)
            if not self._ensure_secret_shop(frame):
                logger.warning("场景校验失败，终止滑动购买")
                break

            # 识别当前可视物品，立即购买
            items = self.recognizer.recognize_visible_items(image)

            # 备选：识别结果无变化也认为到底
            curr_keys = {(it.item_type, it.name_text.strip() if it.name_text else "", round(it.position[1] / 20))
                         for it in items}
            if prev_item_keys and curr_keys == prev_item_keys:
                logger.info(f"已到达货架底部（第 {scroll_count} 次滑动，识别结果无变化）")
                break
            prev_item_keys = curr_keys

            results = self.purchase_engine.process_shelf(items)
            all_results.extend(results)
            logger.info(f"第 {scroll_count} 次查看，购买 {len(results)} 个物品")

            # 购买后等屏幕稳定再滚动，防止弹窗残留导致漏识别
            if results:
                time.sleep(0.3)

            # 保存本轮截图（购买前的快照）用于下次底部检测
            prev_shelf_image = image

        return all_results

    # ------------------------------------------------------------------
    # 资源检查
    # ------------------------------------------------------------------

    def check_resources(self) -> bool:
        """检查天空石是否足够（每 10 轮 OCR 一次，中间用推算值）。"""
        cfg = self._cfg
        if cfg.shop.skystone_threshold <= 0:
            return True

        # 每 10 轮 OCR 校准一次，避免偏差累积；首次运行立即 OCR
        if self._skystone_check_counter >= 10 or not self._skystone_known:
            image = self._capture_frame()
            if image is None:
                logger.warning("Skystone OCR skipped: screenshot unavailable; using estimated value")
                self._skystone_known = True
                self._skystone_check_counter = 0
                return self.stats.skystone_remaining >= cfg.shop.skystone_threshold
            value, conf = self._ocr.read_number(
                image, region=SKYSTONE_REGION, min_confidence=0.3
            )
            if value is not None:
                self.stats.skystone_remaining = value
                self._skystone_known = True
                logger.info(f"天空石(OCR): {value} (conf={conf:.2f})")
            else:
                logger.warning("天空石 OCR 失败，使用推算值")
                self._skystone_known = True  # 标记已尝试过，后续用推算值
            self._skystone_check_counter = 0

        logger.info(
            f"天空石: {self.stats.skystone_remaining}, "
            f"阈值: {cfg.shop.skystone_threshold}"
        )
        if self._skystone_known and self.stats.skystone_remaining < cfg.shop.skystone_threshold:
            return False

        return True

    def should_continue(self, skystone_remaining, skystone_threshold,
                        refresh_count, max_refresh_count,
                        bookmarks_bought=0, max_bookmarks=0,
                        mystic_medals_bought=0, max_mystic_medals=0,
                        skystone_spent=0, max_skystone_spend=0):
        if skystone_threshold > 0 and skystone_remaining < skystone_threshold:
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
