"""Analyze the buy button area for price text"""
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

BUY_X = (1160, 1240)  # Green buy button

for i, (y1, y2) in enumerate(rows):
    # Full buy button area
    buy_img = img[y1:y2, BUY_X[0]:BUY_X[1]]
    h, w = buy_img.shape[:2]
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\buy_btn_{i}.png', buy_img)

    gray = cv2.cvtColor(buy_img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(buy_img, cv2.COLOR_BGR2HSV)

    # Check colors
    green_mask = (buy_img[:,:,1] > buy_img[:,:,0]) & (buy_img[:,:,1] > buy_img[:,:,2] * 0.8)
    bright_mask = hsv[:,:,2] > 80
    dark_mask = gray < 80

    print(f"\n=== Slot {i}: buy_btn area {w}x{h} ===")
    print(f"  Green pixels (G>R, G>B): {green_mask.sum()} / {w*h}")
    print(f"  Bright pixels (V>80): {bright_mask.sum()} / {w*h}")
    print(f"  Dark pixels (gray<80): {dark_mask.sum()} / {w*h}")

    if bright_mask.sum() > 0:
        bgr = (float(buy_img[:,:,0][bright_mask].mean()),
               float(buy_img[:,:,1][bright_mask].mean()),
               float(buy_img[:,:,2][bright_mask].mean()))
        print(f"  Bright BGR: ({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

    if dark_mask.sum() > 0:
        bgr = (float(buy_img[:,:,0][dark_mask].mean()),
               float(buy_img[:,:,1][dark_mask].mean()),
               float(buy_img[:,:,2][dark_mask].mean()))
        print(f"  Dark BGR: ({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

    # Check vertical structure
    print("  Vertical profile (bright pixels per row):")
    for yy in range(0, h, 5):
        row_slice = gray[yy:min(yy+5, h), :]
        bright_n = int((row_slice > 100).sum())
        dark_n = int((row_slice < 60).sum())
        if bright_n > 3 or dark_n > 3:
            print(f"    y_off={yy:3d}: bright={bright_n} dark={dark_n} mean={float(row_slice.mean()):.0f}")

    # Check horizontal
    print("  Horizontal profile:")
    for xx in range(0, w, 4):
        col_slice = gray[:, xx:min(xx+4, w)]
        bright_n = int((col_slice > 100).sum())
        if bright_n > 5:
            print(f"    x_off={xx:3d}: bright_n={bright_n} mean={float(col_slice.mean()):.0f}")

    # Try OCR on buy button (inverted threshold)
    from module.ocr.models import OCR_MODEL
    _, inv = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\buy_btn_inv_{i}.png', inv)

    az = OCR_MODEL.azur_lane
    result = az.atomic_ocr_for_single_lines([inv], cand_alphabet='0123456789')
    print(f"  OCR azur_lane: {result}")

print("\nDone!")
