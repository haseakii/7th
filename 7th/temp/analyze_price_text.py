"""Analyze price text position within the price area"""
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

    # Vertical brightness profile
    print(f"\n=== Slot {i}: y={y1}-{y2}, price_area={w}x{h} ===")
    for yy in range(0, h, 5):
        row_slice = gray[yy:min(yy+5, h), :]
        mean_val = float(row_slice.mean())
        max_val = float(row_slice.max())
        # Count "bright" pixels
        bright_n = int((row_slice > 60).sum())
        if bright_n > 5:
            print(f"  y_off={yy:3d}: mean={mean_val:.0f} max={max_val:.0f} bright_n={bright_n}")

    # Horizontal brightness profile
    print(f"  Horizontal (where are the characters?):")
    for xx in range(0, w, 4):
        col_slice = gray[:, xx:min(xx+4, w)]
        bright_n = int((col_slice > 60).sum())
        if bright_n > 5:
            print(f"    x_off={xx:3d}: bright_n={bright_n}")

    # Try to find tight bounding box of text
    binary = (gray > 60).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"  Found {len(contours)} contours")
    for j, cnt in enumerate(contours[:10]):  # Top 10
        x, y, cw, ch = cv2.boundingRect(cnt)
        if ch > 5 and cw > 3:  # Filter noise
            print(f"    Contour {j}: x={x} y={y} w={cw} h={ch} area={cw*ch}")

    # Save tight crop of price text for OCR
    if len(contours) > 0:
        # Combine all contours
        all_pts = np.vstack([c for c in contours if cv2.boundingRect(c)[3] > 5 and cv2.boundingRect(c)[2] > 3])
        if len(all_pts) > 0:
            tx, ty, tw, th = cv2.boundingRect(all_pts)
            # Add padding
            tx = max(0, tx - 2)
            ty = max(0, ty - 2)
            tw = min(w - tx, tw + 4)
            th = min(h - ty, th + 4)
            tight_crop = price_img[ty:ty+th, tx:tx+tw]
            cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\tight_price_{i}.png', tight_crop)
            print(f"  Tight crop: {tx},{ty} {tw}x{th}")

print("\nDone!")
