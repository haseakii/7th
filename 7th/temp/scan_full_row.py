"""Scan full item row width to find ALL text regions and their positions"""
import sys, os, cv2, numpy as np

sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()
cv2.imwrite('D:\\software\\7th\\7th\\temp\\full_shop.png', img)

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

# Full screen width (typically 1280)
FULL_W = img.shape[1]

for i, (y1, y2) in enumerate(rows):
    row_img = img[y1:y2, :]
    h, w = row_img.shape[:2]
    gray = cv2.cvtColor(row_img, cv2.COLOR_BGR2GRAY)

    print(f"\n{'='*80}")
    print(f"Slot {i}: row y={y1}-{y2} height={h} full_width={w}")
    print(f"{'='*80}")

    # Full-width column brightness profile
    col_profile = (gray > 60).sum(axis=0)
    col_profile_bright = (gray > 80).sum(axis=0)

    # Find text regions (contiguous columns with bright pixels)
    regions = []
    in_region = False
    start = 0
    for xx in range(w):
        if col_profile_bright[xx] > 5 and not in_region:
            in_region = True
            start = xx
        elif col_profile_bright[xx] <= 5 and in_region:
            in_region = False
            if xx - start >= 3:
                regions.append((start, xx))
    if in_region and w - start >= 3:
        regions.append((start, w))

    print(f"\n  Text regions (col bright>80 >5px):")
    for rx1, rx2 in regions:
        region_w = rx2 - rx1
        region_img = row_img[:, rx1:rx2]
        region_gray = gray[:, rx1:rx2]
        # Get average color of bright pixels
        bright_mask = region_gray > 80
        if bright_mask.sum() > 0:
            avg_bgr = region_img[bright_mask].mean(axis=0)
        else:
            avg_bgr = np.array([0, 0, 0])

        # Estimate number of characters by looking for vertical gaps
        col_in_region = (region_gray > 80).sum(axis=0)
        # Count transitions from bright to dark as character separators
        chars = 0
        in_char = False
        for xx in range(region_w):
            if col_in_region[xx] > 3 and not in_char:
                in_char = True
                chars += 1
            elif col_in_region[xx] <= 3 and in_char:
                in_char = False

        print(f"    x={rx1}-{rx2} w={region_w}px: ~{chars} chars "
              f"BGR=({avg_bgr[0]:.0f},{avg_bgr[1]:.0f},{avg_bgr[2]:.0f})")

        # Save region for visual inspection
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\region_{i}_x{rx1}-{rx2}.png', region_img)

    # Also print detail for key areas
    print(f"\n  Detail of columns with bright>80 pixels:")
    for xx in range(0, w, 1):
        if col_profile_bright[xx] > 0:
            # Get top and bottom of bright region in this column
            bright_ys = np.where(gray[:, xx] > 80)[0]
            if len(bright_ys) > 0:
                y_top, y_bot = bright_ys[0], bright_ys[-1]
                # Average BGR of bright pixels
                bgr = row_img[bright_ys, xx, :].mean(axis=0)
                print(f"    x={xx:4d}: y={y_top}-{y_bot} ({len(bright_ys)}px) "
                      f"BGR=({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

print("\nDone!")
