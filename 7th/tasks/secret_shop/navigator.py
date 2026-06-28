"""
ShopNavigator 商店导航器

从游戏大厅导航至秘密商店，支持场景检测、弹窗处理、导航超时。

场景检测策略（2026-05-08 实机截图校准）：
- 秘密商店特征：左侧导航顶部暗 (<80)，中部按钮亮 (>120)，内容区暗 (<100)
  左侧有 NPC 角色（y=390-600），右侧为商品列表（竖行排列）
- 游戏大厅特征：导航顶部亮 (>100)，内容区亮 (>100)
  左侧有完整导航栏，右侧为游戏世界场景
"""

import time

from module.logger import logger
from module.base.button import Button
from module.base.timer import Timer
from module.base.utils import crop
from module.device.device import DeviceController
from module.vision.frame import capture_device_frame, get_frame_image
from module.vision.profile import SECRET_SHOP_PROFILE
from tasks.secret_shop.scene import Scene

# ---------------------------------------------------------------------------
# Button 实例（2026-05-08 实机截图重新校准，1280×720 分辨率）
# area: 颜色检测区域 (x1, y1, x2, y2)
# color: 期望颜色 (r, g, b)
# button: 点击区域 (x1, y1, x2, y2)
# ---------------------------------------------------------------------------

# 秘密商店界面标识：左侧导航栏顶部（秘密商店为暗色/无明显导航栏）
SECRET_SHOP_SIDEBAR = Button(
    area=(80, 200, 160, 260),
    color=(200, 200, 200),
    button=(80, 200, 160, 260),
    name="SECRET_SHOP_SIDEBAR",
)

# 大厅界面标识：左侧导航栏
LOBBY_BTN = Button(
    area=(80, 200, 200, 500),
    color=(192, 179, 178),
    button=(80, 200, 200, 500),
    name="LOBBY_BTN",
)

# 秘密商店入口按钮（左侧栏 x=40-80, y=300-335，青色 "??" 图标按钮）
SECRET_SHOP_ENTRANCE_BTN = Button(
    area=(40, 300, 85, 335),
    color=(40, 174, 197),
    button=(40, 300, 85, 335),
    name="SECRET_SHOP_ENTRANCE_BTN",
)

# 弹窗关闭按钮（公告右上角的叉）
POPUP_CLOSE_BTN = Button(
    area=(1114, 50, 1168, 104),
    color=(255, 255, 255),
    button=(1114, 50, 1168, 104),
    name="POPUP_CLOSE_BTN",
)

# 颜色检测相似度阈值（用于 appear_on）
COLOR_THRESHOLD = 50

# 场景检测亮度阈值（2026-05-08 实机校准）
# - 秘密商店 (实测 ~55)：nav_top=53, nav_mid=177, content=55
# - 游戏大厅 (实测 ~185)：nav_top=185, nav_mid=205, content=201
SECRET_SHOP_SIDEBAR_THRESHOLD = SECRET_SHOP_PROFILE.secret_shop_sidebar_threshold
LOBBY_NAV_MIN_BRIGHTNESS = SECRET_SHOP_PROFILE.lobby_nav_min_brightness
CONTENT_BRIGHTNESS_THRESHOLD = SECRET_SHOP_PROFILE.content_brightness_threshold

# 导航默认超时（秒）
NAVIGATION_TIMEOUT = 30.0

# 场景检测后等待过渡的间隔（秒）
TRANSITION_WAIT = 1.5


class ShopNavigator:
    """从游戏大厅导航至秘密商店。

    E7 国服横向版（1280x720）特性：
    - 左侧导航栏（x=80-200）竖排按钮
    - 秘密商店界面：整体偏暗 (~52)，左侧导航顶部暗 (<80)，中部按钮亮 (>120)
    - 游戏大厅：整体偏亮 (~149)，导航和内容区均较亮 (>100)
    """

    def __init__(self, device: DeviceController):
        self.device = device

    def _capture_frame(self):
        """Capture once and wrap the image with per-frame caches."""
        return capture_device_frame(self.device)

    def detect_current_scene(self) -> Scene:
        """检测当前界面状态。

        通过多区域亮度分析判断场景：
        - SECRET_SHOP: 导航顶暗+导航中亮+内容区暗
        - LOBBY: 导航顶亮+内容区亮

        Returns:
            Scene 枚举值。
        """
        image = self._capture_frame()

        if self._is_secret_shop(image):
            logger.info("场景检测: 秘密商店")
            return Scene.SECRET_SHOP

        if self._is_lobby(image):
            logger.info("场景检测: 游戏大厅")
            return Scene.LOBBY

        logger.warning("场景检测: 未知界面")
        return Scene.UNKNOWN

    def _is_secret_shop(self, image) -> bool:
        """通过多区域亮度特征检测是否在秘密商店。

        秘密商店特征（基于实际游戏截图校准）：
        - 左侧导航顶部暗 (<80) — 区别于大厅的明亮
        - 左侧导航中部按钮亮 (>120) — 竖排三按钮
        - 内容区域暗 (<100) — 物品稀疏排列

        Args:
            image: BGR 格式的截图

        Returns:
            bool: 是否在秘密商店
        """
        # 左侧导航顶部亮度检查
        image = get_frame_image(image)
        if image is None:
            return False

        nav_top = crop(image, (80, 200, 160, 260))
        nav_top_bright = float(nav_top[:, :, :3].mean())

        if nav_top_bright > SECRET_SHOP_SIDEBAR_THRESHOLD:
            return False

        # 左侧导航中部按钮区域（y=300-400，秘密商店此处有亮色按钮）
        nav_mid = crop(image, (80, 300, 160, 400))
        nav_mid_bright = float(nav_mid[:, :, :3].mean())

        # 内容区域（物品槽位区）
        content = crop(image, (250, 150, 800, 520))
        content_bright = float(content[:, :, :3].mean())

        logger.debug(
            f"秘密商店检测: 导航顶部={nav_top_bright:.0f} "
            f"导航中部={nav_mid_bright:.0f} 内容区={content_bright:.0f}"
        )

        return nav_mid_bright > LOBBY_NAV_MIN_BRIGHTNESS and content_bright < CONTENT_BRIGHTNESS_THRESHOLD

    def _is_lobby(self, image) -> bool:
        """检测是否在大厅。

        大厅特征（基于实际游戏截图校准）：
        - 左侧导航顶部较亮 (>100) — 有竖排按钮图标
        - 内容区域较亮 (>100) — 显示各种功能入口

        Args:
            image: BGR 格式的截图

        Returns:
            bool: 是否在大厅
        """
        # 左侧导航顶部
        image = get_frame_image(image)
        if image is None:
            return False

        nav_top = crop(image, (80, 200, 160, 260))
        nav_top_bright = float(nav_top[:, :, :3].mean())

        # 内容区域
        content = crop(image, (250, 150, 800, 520))
        content_bright = float(content[:, :, :3].mean())

        logger.debug(f"大厅检测: 导航顶部={nav_top_bright:.0f} 内容区={content_bright:.0f}")
        return nav_top_bright > LOBBY_NAV_MIN_BRIGHTNESS and content_bright > CONTENT_BRIGHTNESS_THRESHOLD

    def navigate_to_secret_shop(self, timeout: float = NAVIGATION_TIMEOUT) -> bool:
        """从当前界面导航至秘密商店。

        E7 国服横向版（1280x720）：
        - 秘密商店入口在左侧 x=40-85, y=300-335（青色 "??" 图标按钮）
        - 点击后直接进入秘密商店界面

        Args:
            timeout: 导航超时秒数，默认 30.0

        Returns:
            bool: 是否成功到达秘密商店
        """
        logger.info(f"开始导航至秘密商店（超时 {timeout}s）")
        timer = Timer(limit=timeout)
        timer.start()

        while not timer.reached():
            scene = self.detect_current_scene()

            if scene == Scene.SECRET_SHOP:
                logger.info("已到达秘密商店")
                return True

            if scene == Scene.LOBBY:
                logger.info("从大厅点击左侧导航栏的秘密商店入口")
                self.device.click(SECRET_SHOP_ENTRANCE_BTN)
                time.sleep(TRANSITION_WAIT)
                continue

            # UNKNOWN — 尝试处理弹窗
            if self.handle_popup():
                logger.info("已关闭弹窗，继续导航")
                time.sleep(TRANSITION_WAIT)
                continue

            # 无法识别且无弹窗，短暂等待后重试
            logger.warning("界面无法识别且无弹窗，等待后重试")
            time.sleep(TRANSITION_WAIT)

        logger.error(f"导航超时（{timeout}s），未能到达秘密商店")
        return False

    def handle_popup(self) -> bool:
        """检测并关闭意外弹窗。

        对当前截图进行颜色检测，如果检测到弹窗关闭按钮则点击关闭。

        Returns:
            bool: 是否检测到并关闭了弹窗
        """
        frame = self._capture_frame()
        image = get_frame_image(frame)
        if image is None:
            return False

        if POPUP_CLOSE_BTN.appear_on(image, threshold=COLOR_THRESHOLD):
            logger.info("检测到弹窗，点击关闭")
            self.device.click(POPUP_CLOSE_BTN)
            return True

        return False
