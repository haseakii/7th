"""Test OCR with cnocr model (full Chinese model, more font-robust)"""
import sys, os, cv2, numpy as np

sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer, PRICE_X
from module.base.utils import extract_letters

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

from module.ocr.models import OCR_MODEL
cnocr_model = OCR_MODEL.cnocr  # Use the full Chinese model
print("cnocr model loaded")

for i, (y1, y2) in enumerate(rows):
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]
    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)

    # Try different preprocessing for cnocr model
    # Method 1: Inverted binary (dark text on white bg)
    _, inv_thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\cnocr_pp{i}.png', inv_thresh)

    # Method 2: Simple binary
    _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\cnocr_pp{i}b.png', thresh)

    for lang, model in [("cnocr", cnocr_model)]:
        for pp_name, pp_img in [("inv", inv_thresh), ("thresh", thresh)]:
            result = model.atomic_ocr_for_single_lines([pp_img], cand_alphabet='0123456789')
            if result and result[0]:
                print(f"Slot {i} {lang}/{pp_name}: {result[0]}")

    # Also try with azur_lane model for comparison
    az_model = OCR_MODEL.azur_lane
    for pp_name, pp_img in [("inv", inv_thresh), ("thresh", thresh)]:
        result = az_model.atomic_ocr_for_single_lines([pp_img], cand_alphabet='0123456789')
        if result and result[0]:
            print(f"Slot {i} azur_lane/{pp_name}: {result[0]}")

print("\nDone!")
