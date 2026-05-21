"""Test OCR with corrected price area (x=1040-1120) and golden text color"""
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

from shop.recognizer import ItemRecognizer, PRICE_X, PRICE_TEXT_COLOR
rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)
print(f"Found {len(rows)} rows")

from module.ocr.ocr import Digit
from module.base.button import Button

for i, (y1, y2) in enumerate(rows):
    # Use corrected price area
    price_area = (PRICE_X[0], y1, PRICE_X[1], y2)
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]

    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_fixed_{i}.png', price_img)

    # Analyze the content
    hsv = cv2.cvtColor(price_img, cv2.COLOR_BGR2HSV)
    # Check golden pixels
    bright = price_img[hsv[:,:,2] > 60]
    all_n = price_img.shape[0] * price_img.shape[1]

    print(f"\nSlot {i} (y={y1}-{y2}): price_area={price_area}")
    if len(bright) > 0:
        bgr = (float(bright[:,0].mean()), float(bright[:,1].mean()), float(bright[:,2].mean()))
        print(f"  Bright(V>60): n={len(bright)}/{all_n}, BGR=({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

    # Try OCR with golden text color
    digit_ocr = Digit(
        buttons=Button(
            area=price_area,
            color=PRICE_TEXT_COLOR,
            button=price_area,
            name=f"PRICE_{i}",
        ),
        letter=PRICE_TEXT_COLOR,
        threshold=128,
        name=f"PRICE_{i}",
    )
    digit_ocr.SHOW_LOG = False
    result = digit_ocr.ocr(img)
    print(f"  OCR result: {result}")

print("\nDone!")
