"""Scan each item row horizontally to find where price/buy button is"""
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

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

for slot_idx, (y1, y2) in enumerate(rows):
    print(f"\n=== Slot {slot_idx}: y={y1}-{y2} (h={y2-y1}) ===")
    # Scan across x for content
    for x_start in range(200, 1250, 40):
        x_end = min(x_start + 40, img.shape[1])
        seg = img[y1:y2, x_start:x_end]
        if seg.size == 0:
            continue
        gray = float(cv2.cvtColor(seg, cv2.COLOR_BGR2GRAY).mean())
        # Check for bright, colorful, or distinct content
        hsv = cv2.cvtColor(seg, cv2.COLOR_BGR2HSV)
        bright = seg[hsv[:,:,2] > 80]
        has_content = len(bright) > 20
        if has_content:
            bgr = (float(bright[:,0].mean()), float(bright[:,1].mean()), float(bright[:,2].mean()))
            n = len(bright)
        else:
            bgr = (0,0,0)
            n = 0
        # Also check for medium-brightness text
        mid = seg[(hsv[:,:,2] > 40) & (hsv[:,:,2] <= 128)]
        mid_n = len(mid)

        marker = ""
        if n > 200:
            marker = " [BUTTON?]"
        elif mid_n > 200:
            marker = " [TEXT?]"

        if n > 50 or mid_n > 100:
            print(f"  x={x_start:4d}-{x_end:4d}: gray={gray:6.0f} bright_n={n:5d} mid_n={mid_n:5d} BGR=({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f}){marker}")

print("\nDone!")
