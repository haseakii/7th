"""Screen and task-specific vision profiles."""

from dataclasses import dataclass
from typing import Tuple

Region = Tuple[int, int, int, int]
Point = Tuple[int, int]


@dataclass(frozen=True)
class ScreenProfile:
    width: int = 1280
    height: int = 720


@dataclass(frozen=True)
class SecretShopProfile:
    screen: ScreenProfile = ScreenProfile()

    nav_top_region: Region = (80, 200, 160, 260)
    nav_mid_region: Region = (80, 300, 160, 400)
    content_region: Region = (250, 150, 800, 520)

    secret_shop_sidebar_threshold: int = 80
    lobby_nav_min_brightness: int = 100
    content_brightness_threshold: int = 100

    refresh_button_region: Region = (50, 620, 400, 718)
    refresh_confirm_position: Point = (748, 460)
    popup_region: Region = (300, 440, 950, 550)
    popup_confirm_region: Region = (640, 440, 950, 550)
    popup_cancel_region: Region = (300, 440, 640, 550)
    insufficient_gold_region: Region = (400, 280, 880, 400)
    skystone_region: Region = (1100, 0, 1260, 50)
    gold_region: Region = (790, 5, 970, 40)
    confirm_position: Point = (818, 508)
    cancel_position: Point = (482, 508)

    # ShopBot and ItemRecognizer intentionally swipe at different x positions.
    scroll_area: Tuple[int, int, int, int] = (800, 400, 800, 150)
    item_scroll_area: Tuple[int, int, int, int] = (640, 400, 640, 150)
    shelf_compare_area: Region = (300, 120, 900, 540)


SECRET_SHOP_PROFILE = SecretShopProfile()
