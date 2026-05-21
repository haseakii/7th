"""Output ASCII art of the price area to understand the text layout"""
import sys, os, cv2, numpy as np

sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer, PRICE_X

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

for i, (y1, y2) in enumerate(rows):
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]
    h, w = price_img.shape[:2]
    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)

    print(f"\n{'='*80}")
    print(f"Slot {i}: price area {w}x{h} (PRICE_X={PRICE_X})")
    print(f"{'='*80}")

    # Print ASCII art at 2x horizontal scale for readability
    print("\n  ASCII (threshold at 80, '.'=dark '#'=bright):")
    for yy in range(0, h, 2):
        row_str = f"  y={yy:3d}: "
        for xx in range(w):
            val = gray[yy, xx]
            if val > 120:
                row_str += "##"
            elif val > 80:
                row_str += "::"
            elif val > 50:
                row_str += ".."
            else:
                row_str += "  "
        print(row_str)

    # Also print BGR values for the brightest pixels in each column
    print("\n  Bright pixel BGR analysis (top 5 per column):")
    for xx in range(w):
        col = gray[:, xx]
        bright_mask = col > 80
        if bright_mask.sum() > 0:
            bgr_vals = price_img[:, xx, :][bright_mask]
            avg_bgr = bgr_vals.mean(axis=0)
            # Find y-range of bright pixels in this column
            bright_ys = np.where(bright_mask)[0]
            y_min, y_max = bright_ys.min(), bright_ys.max()
            print(f"    x={xx:3d}: y={y_min}-{y_max} ({bright_mask.sum()}px) "
                  f"B=({avg_bgr[0]:.0f},{avg_bgr[1]:.0f},{avg_bgr[2]:.0f})")

    # Save for reference
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_ascii_{i}.png', price_img)

print("\nDone!")
