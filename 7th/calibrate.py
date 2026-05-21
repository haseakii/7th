"""
校准工具 - 帮助验证和调整游戏界面坐标

参考截图:
  screenshots/1.png   — 游戏大厅（亮度 ~149）
  screenshots/2.png   — 秘密商店（亮度 ~52，在 MuMu 模拟器上实际效果）

用法:
  python calibrate.py                          # 完整校准流程
  python calibrate.py --check                  # 只检查当前坐标
  python calibrate.py --crop-templates         # 从截图裁剪模板图片
  python calibrate.py --screenshot             # 立即截取一张新截图

该工具会在 screenshots/ 目录下生成带有标注的调试图片，
通过分析截图的像素特征来确定正确的按钮和物品位置。
"""

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager, AppConfig
from log import logger
from shop.navigator import ShopNavigator
from module.device.device import DeviceController


# ── 需要校准的坐标区域 ──────────────────────────────────────────────
# 每个条目：(名称, x1, y1, x2, y2, 期望颜色/特征)
CALIBRATION_POINTS = [
    # 导航相关
    ("LOBBY_检测区域",       80,  200, 160, 260, "大厅左侧导航栏"),
    ("秘密商店入口按钮",      80,  350, 200, 440, "左侧导航栏秘密商店入口"),
    ("秘密商店标识",          1100, 590, 1200, 630, "秘密商店右下角标识"),

    # 刷新按钮
    ("刷新按钮",              1000, 535, 1220, 565, "右下角金色刷新按钮"),
    ("刷新确认",              540,  380, 740,  440, "刷新确认弹窗绿色按钮"),
    ("刷新二次确认",          540,  440, 740,  500, "二次确认弹窗"),

    # 物品槽位
    ("物品槽0_图标区域",      250,  155, 650,  215, "第一个物品图标和名称"),
    ("物品槽0_价格区域",      650,  165, 800,  205, "第一个物品价格"),
    ("物品槽1_图标区域",      250,  215, 650,  275, "第二个物品图标和名称"),
    ("物品槽1_价格区域",      650,  225, 800,  265, "第二个物品价格"),
    ("物品槽2_图标区域",      250,  275, 650,  335, "第三个物品图标和名称"),
    ("物品槽2_价格区域",      650,  285, 800,  325, "第三个物品价格"),
    ("物品槽3_图标区域",      250,  335, 650,  395, "第四个物品图标和名称"),
    ("物品槽3_价格区域",      650,  345, 800,  385, "第四个物品价格"),
    ("物品槽4_图标区域",      250,  395, 650,  455, "第五个物品图标和名称"),
    ("物品槽4_价格区域",      650,  405, 800,  445, "第五个物品价格"),
    ("物品槽5_图标区域",      250,  455, 650,  515, "第六个物品图标和名称"),
    ("物品槽5_价格区域",      650,  465, 800,  505, "第六个物品价格"),

    # 购买相关
    ("购买确认按钮",          540,  380, 740,  440, "购买确认绿色按钮"),
    ("购买二次确认",          540,  440, 740,  500, "购买二次确认"),
    ("金币不足提示",          440,  300, 840,  380, "金币不足红色提示"),

    # 资源区域
    ("天空石数值区域",        1100, 5,   1260, 30,  "顶部天空石数值"),

    # 弹窗
    ("弹窗关闭按钮",          1114, 50,  1168, 104, "右上角弹窗关闭(X)"),

    # 滑动相关
    ("滑动起始",              640,  400, 640,  150, "向下滑动起点→终点"),
]


def load_image(path: str) -> np.ndarray:
    """加载截图并确保为 1280x720"""
    img = cv2.imread(path)
    if img is None:
        print(f"[FAIL] 无法加载图片: {path}")
        sys.exit(1)
    h, w = img.shape[:2]
    if w != 1280 or h != 720:
        img = cv2.resize(img, (1280, 720))
        print(f"  (已缩放 {w}x{h} → 1280x720)")
    return img


def analyze_regions(img: np.ndarray, title: str):
    """分析预定义区域的特征值"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"{'区域名称':<20} {'位置':<22} {'B均值':>6} {'G均值':>6} {'R均值':>6} {'亮度':>6} {'标准差':>6}")
    print("-"*78)

    for name, x1, y1, x2, y2, desc in CALIBRATION_POINTS:
        region = img[y1:y2, x1:x2]
        if region.size == 0:
            continue
        b, g, r = cv2.split(region)
        gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        b_mean = b.mean()
        g_mean = g.mean()
        r_mean = r.mean()
        gray_mean = gray_region.mean()
        gray_std = gray_region.std()

        print(f"{name:<20} ({x1:4d},{y1:4d})-({x2:4d},{y2:4d}) "
              f"{b_mean:6.0f} {g_mean:6.0f} {r_mean:6.0f} "
              f"{gray_mean:6.0f} {gray_std:6.0f}")


def save_annotated_image(img: np.ndarray, path: str, title: str):
    """保存带有标注区域的调试图片"""
    debug = img.copy()

    colors = [
        (0, 255, 0),    # 绿
        (0, 0, 255),    # 红
        (255, 0, 0),    # 蓝
        (0, 255, 255),  # 黄
        (255, 0, 255),  # 紫
        (255, 255, 0),  # 青
    ]

    for i, (name, x1, y1, x2, y2, desc) in enumerate(CALIBRATION_POINTS):
        color = colors[i % len(colors)]
        cv2.rectangle(debug, (x1, y1), (x2, y2), color, 2)
        cv2.putText(debug, f"{i}", (x1+2, y1+12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    # 添加图例
    legend_y = 10
    for i, (name, _, _, _, _, _) in enumerate(CALIBRATION_POINTS):
        color = colors[i % len(colors)]
        cv2.putText(debug, f"{i}:{name}", (10, legend_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
        legend_y += 14

    # 添加标题
    cv2.putText(debug, title, (400, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # 添加坐标网格 (100px间隔)
    for x in range(0, 1281, 100):
        cv2.line(debug, (x, 0), (x, 720), (100, 100, 100), 1)
        cv2.putText(debug, str(x), (x+2, 715), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (100, 100, 100), 1)
    for y in range(0, 721, 100):
        cv2.line(debug, (0, y), (1280, y), (100, 100, 100), 1)
        cv2.putText(debug, str(y), (2, y+10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (100, 100, 100), 1)

    cv2.imwrite(path, debug)
    print(f"  标注图片已保存: {path}")


def crop_templates(img: np.ndarray, assets_dir: Path):
    """从截图裁剪模板图片保存到 assets/e7/"""
    assets_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print("  裁剪模板图片")
    print(f"{'='*60}")

    # 定义要裁剪的模板
    # 注意：物品图标模板（bookmark 等）需要从已知物品的参考截图中裁剪，
    # 或者从游戏资源文件中提取。下面的坐标是占位值，裁剪结果需要
    # 人工检查并重命名到正确的物品类型。
    templates = [
        # (模板名, x1, y1, x2, y2, 说明)
        # 物品图标（60x60 从槽位左侧裁剪）
        ("bookmark",        250, 155, 310, 215, "书签图标"),
        ("mystic_medal",    250, 215, 310, 275, "神秘奖章图标"),
        ("equipment",       250, 275, 310, 335, "装备图标"),
        ("fodder",          250, 335, 310, 395, "狗粮图标"),
        # 按钮坐标（需校准）
        ("refresh_btn",     1000, 535, 1220, 565, "刷新按钮"),
        ("confirm_btn",     540, 380, 740, 440, "确认按钮"),
        ("popup_close",     1114, 50, 1168, 104, "弹窗关闭"),
    ]

    for name, x1, y1, x2, y2, desc in templates:
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            print(f"  [FAIL] {name:20s} ({desc}): 无效区域 ({x1},{y1})-({x2},{y2})")
            continue

        # 保存为 PNG
        save_path = assets_dir / f"{name}.png"
        cv2.imwrite(str(save_path), crop)
        file_size = save_path.stat().st_size / 1024
        b, g, r = cv2.split(crop)
        print(f"  [OK] {name:20s} ({desc}): {crop.shape[1]}x{crop.shape[0]} "
              f"B={b.mean():.0f} G={g.mean():.0f} R={r.mean():.0f} [{file_size:.1f}KB] -> {save_path.name}")


def calibrate_coordinates(img: np.ndarray):
    """自动校准坐标，寻找更好的区域"""
    print(f"\n{'='*60}")
    print("  坐标自动校准建议")
    print(f"{'='*60}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 整体亮度统计
    print(f"\n  整体亮度: {gray.mean():.0f}")
    print(f"  分辨率: {w}x{h}")

    # 查找左侧导航栏按钮区（秘密商店中按钮在 y=300-480）
    print("\n  左侧导航栏按钮:")
    nav_strip = img[200:550, 80:160]
    nav_gray = cv2.cvtColor(nav_strip, cv2.COLOR_BGR2GRAY)
    for y_off in range(0, 320, 10):
        row = nav_gray[y_off, :]
        if row.mean() > 80:
            print(f"    y={200+y_off}: 按钮亮度={row.mean():.0f}")

    # 查找底部刷新按钮区域 (找亮绿色区域)
    print("\n  底部按钮区域(绿色像素检测):")
    for y in range(500, 600):
        row_color = img[y, 900:1280]
        g_ch = row_color[:, 1].astype(int)
        r_ch = row_color[:, 0].astype(int)
        b_ch = row_color[:, 2].astype(int)
        green_px = int(((g_ch > r_ch + 10) & (g_ch > b_ch + 10)).sum())
        if green_px > 100:
            # 找到绿色段的起止 x
            green_mask = (g_ch > r_ch + 10) & (g_ch > b_ch + 10)
            segments = []
            start = -1
            for rx in range(len(green_mask)):
                if green_mask[rx]:
                    if start < 0:
                        start = rx
                else:
                    if start >= 0:
                        segments.append((start + 900, rx + 900))
                        start = -1
            if start >= 0:
                segments.append((start + 900, 1279))
            for sx, ex in segments:
                if ex - sx > 20:
                    print(f"    y={y}: 绿色按钮 x={sx}-{ex} (宽{ex-sx}px)")
            break

    # 查找物品行 (找重复的水平结构)
    print("\n  物品行候选 (高纹理行):")
    for y in range(130, 550, 5):
        row = gray[y, 250:800]
        if row.std() > 25 and row.mean() < 100:
            print(f"    y={y}: 纹理丰富 (std={row.std():.1f}, mean={row.mean():.1f})")


def take_screenshot(config_path: str = "config.yaml"):
    """通过 ADB 截取一张新截图"""
    print("正在通过 ADB 截图...")
    config = ConfigManager(config_path)
    config.load()
    cfg = config.get()

    device = DeviceController(cfg.device)
    if not device.connect():
        print("[FAIL] 设备连接失败")
        return None

    image = device.screenshot()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    save_path = f"screenshots/{timestamp}.png"
    cv2.imwrite(save_path, image)
    print(f"[OK] 截图已保存: {save_path}")

    # 立即分析
    analyze_regions(image, f"新截图分析 - {save_path}")
    save_annotated_image(image, f"screenshots/annotated_{timestamp}.png", "新截图 - 标注区域")
    calibrate_coordinates(image)

    return save_path


def main():
    parser = argparse.ArgumentParser(description="第七史诗秘密商店坐标校准工具")
    parser.add_argument("--image", default="screenshots/2.png",
                       help="要分析的截图路径 (默认: screenshots/2.png = 秘密商店)")
    parser.add_argument("--lobby", default="screenshots/1.png",
                       help="大厅截图路径 (默认: screenshots/1.png = 大厅)")
    parser.add_argument("--check", action="store_true", help="只检查当前坐标")
    parser.add_argument("--crop-templates", action="store_true", help="裁剪模板图片")
    parser.add_argument("--screenshot", action="store_true", help="从设备截取新截图")
    args = parser.parse_args()

    if args.screenshot:
        take_screenshot()
        return

    # 加载并分析商店截图
    img = load_image(args.image)
    analyze_regions(img, f"商店截图分析 - {args.image}")
    save_annotated_image(img, "screenshots/calib_shop.png", "商店截图 - 标注区域")
    calibrate_coordinates(img)

    # 分析大厅截图
    if os.path.exists(args.lobby):
        lobby_img = load_image(args.lobby)
        analyze_regions(lobby_img, f"大厅截图分析 - {args.lobby}")
        save_annotated_image(lobby_img, "screenshots/calib_lobby.png", "大厅截图 - 标注区域")

    # 裁剪模板
    if args.crop_templates:
        assets_dir = Path(__file__).parent / "assets" / "e7"
        crop_templates(img, assets_dir)
        # 也从大厅截图裁剪
        if os.path.exists(args.lobby):
            lobby_img = load_image(args.lobby)
            # 额外大厅模板
            lobby_templates = [
                ("lobby",           80,  200, 200, 500, "大厅左侧导航"),
                ("secret_shop_entrance", 80, 350, 200, 440, "秘密商店入口"),
            ]
            for name, x1, y1, x2, y2, desc in lobby_templates:
                crop = lobby_img[y1:y2, x1:x2]
                cv2.imwrite(str(assets_dir / f"{name}.png"), crop)
                print(f"  [OK] {name:25s} ({desc}): {crop.shape[1]}x{crop.shape[0]} -> {assets_dir / f'{name}.png'}")

    print(f"\n{'='*60}")
    print("  校准完成！")
    print(f"{'='*60}")
    print(f"  标注图片:")
    print(f"    商店: screenshots/calib_shop.png")
    print(f"    大厅: screenshots/calib_lobby.png")
    print(f"\n  下一步:")
    print(f"  1. 查看标注图片确认区域是否正确")
    print(f"  2. 如需调整，修改 {__file__} 中的 CALIBRATION_POINTS")
    print(f"  3. 调整后重新运行: python {__file__}")
    print(f"  4. 确认无误后运行: python {__file__} --crop-templates")
    print(f"  5. 再运行: python calibrate.py --screenshot 测试真实游戏截图")


if __name__ == "__main__":
    main()
