"""Test OCR on real game screenshot using cnocr"""
import sys, os, cv2, numpy as np

# Use ALAS Python to run
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()

cv2.imwrite('D:\\software\\7th\\7th\\temp\\ocr_test.png', img)

# Test Digit OCR on price areas
from module.ocr.ocr import Digit
from module.base.button import Button

# Find item rows first
from shop.recognizer import ItemRecognizer
rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)
print(f"Found {len(rows)} rows: {rows}")

for i, (y1, y2) in enumerate(rows):
    # Price area (same as recognizer uses)
    price_area = (800, y1, 950, y2)
    price_img = img[y1:y2, 800:950]
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_slot{i}.png', price_img)

    # Price digit OCR
    digit_ocr = Digit(
        buttons=Button(
            area=price_area,
            color=(255, 255, 255),
            button=price_area,
            name=f"PRICE_{i}",
        ),
        letter=(255, 255, 255),
        threshold=128,
        name=f"PRICE_{i}",
    )
    digit_ocr.SHOW_LOG = False
    result = digit_ocr.ocr(img)
    print(f"Slot {i} (y={y1}-{y2}): price = {result}")

    # Also check what the price area looks like
    gray = float(cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY).mean())
    hsv = cv2.cvtColor(price_img, cv2.COLOR_BGR2HSV)
    bright = price_img[hsv[:,:,2] > 128]
    if len(bright) > 0:
        print(f"  Price area: gray={gray:.0f}, bright_px={len(bright)}, "
              f"BGR=({float(bright[:,0].mean()):.0f},{float(bright[:,1].mean()):.0f},{float(bright[:,2].mean()):.0f})")

print("\nDone!")
