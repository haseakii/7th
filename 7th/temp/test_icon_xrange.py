"""
测试不同 icon x-range 的分类效果
"""
import sys, os, cv2, numpy as np
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()
h, w = img.shape[:2]

# 使用 recognizer 的行检测
from shop.recognizer import ItemRecognizer
rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)
print(f"Detected {len(rows)} rows: {rows}")

def bright_features(icon_img):
    """Extract features from bright pixels only"""
    hsv = cv2.cvtColor(icon_img, cv2.COLOR_BGR2HSV)
    bright = icon_img[hsv[:,:,2] > 40]
    if len(bright) < 10:
        return None
    b, g, r = float(bright[:,0].mean()), float(bright[:,1].mean()), float(bright[:,2].mean())
    bh = float(cv2.cvtColor(bright.reshape(-1,1,3), cv2.COLOR_BGR2HSV)[:,:,0].mean())
    return {"B": b, "G": g, "R": r, "R/G": r/max(g,1), "H": bh, "bright%": len(bright)/(icon_img.shape[0]*icon_img.shape[1])}

# 测试多种 icon x-range
test_ranges = [
    (200, 280),   # 用户描述的 NPC头像右方
    (220, 300),
    (250, 330),
    (280, 360),
    (300, 380),
    (350, 430),
    (400, 470),   # 当前 recognizer 使用的
]

for slot_idx, (y1, y2) in enumerate(rows):
    icon_h = min(y2 - y1, 80)
    icon_y2 = min(y1 + icon_h, h)
    print(f"\n--- Slot {slot_idx}: y={y1}-{y2} (icon_h={icon_h}) ---")

    for (x1, x2) in test_ranges:
        icon = img[y1:icon_y2, x1:min(x2, w)]
        if icon.size == 0:
            continue
        f = bright_features(icon)
        if f:
            marker = "***" if f["R/G"] > 1.4 else ""
            print(f"  x={x1}-{x2}: BGR=({f['B']:.0f},{f['G']:.0f},{f['R']:.0f}) R/G={f['R/G']:.2f} H={f['H']:.0f} bright={f['bright%']:.0%} {marker}")

        # Save the best candidate for each slot
        if f and f["R/G"] > 1.4:
            cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\icon_slot{slot_idx}_x{x1}-{x2}.png', icon)

# 也测试整行区域（而不是只取顶部80px）
print("\n\n=== 使用整行高度测试 ===")
for slot_idx, (y1, y2) in enumerate(rows):
    print(f"\n--- Slot {slot_idx}: y={y1}-{y2} (full height={y2-y1}) ---")
    for (x1, x2) in [(200,280), (220,300), (250,330), (280,360), (400,470)]:
        icon = img[y1:y2, x1:min(x2, w)]
        f = bright_features(icon)
        if f:
            marker = "***" if f["R/G"] > 1.4 else ""
            print(f"  x={x1}-{x2}: BGR=({f['B']:.0f},{f['G']:.0f},{f['R']:.0f}) R/G={f['R/G']:.2f} H={f['H']:.0f} bright={f['bright%']:.0%} {marker}")

print("\nDone!")
