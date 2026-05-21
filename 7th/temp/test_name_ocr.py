"""Test OCR on item NAME text (x=653-1039, large text) using cnocr full model"""
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

NAME_X = (653, 1039)

from module.ocr.models import OCR_MODEL
cn_model = OCR_MODEL.cnocr
az_model = OCR_MODEL.azur_lane

for i, (y1, y2) in enumerate(rows):
    name_img = img[y1:y2, NAME_X[0]:NAME_X[1]]
    h, w = name_img.shape[:2]
    gray = cv2.cvtColor(name_img, cv2.COLOR_BGR2GRAY)

    # The name text color - from the region analysis, BGR ~(95,108,128) which is grayish
    # Let me try various preprocessing
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\name_{i}.png', name_img)

    print(f"\n=== Slot {i}: name area {w}x{h} ===")

    # Preprocessing for name text
    # The text seems to be light gray on dark bg
    _, inv = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\name_inv_{i}.png', inv)

    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\name_otsu_{i}.png', otsu)

    # Try cnocr with full charset (no cand_alphabet restriction)
    for pp_name, pp_img in [("raw", gray), ("inv", inv), ("otsu", otsu)]:
        # cnocr full model
        result = cn_model.atomic_ocr_for_single_lines([pp_img])
        if result and result[0]:
            text = ''.join(str(c) for c in result[0])
            print(f"  cn/{pp_name} (full): '{text}'")

        # cnocr with digits only
        result = cn_model.atomic_ocr_for_single_lines([pp_img], cand_alphabet='0123456789')
        if result and result[0]:
            text = ''.join(str(c) for c in result[0])
            print(f"  cn/{pp_name} (digits): '{text}'")

        # azur_lane
        result = az_model.atomic_ocr_for_single_lines([pp_img])
        if result and result[0]:
            text = ''.join(str(c) for c in result[0])
            print(f"  az/{pp_name}: '{text}'")

    # Print brightness stats
    bright = (gray > 80).sum()
    print(f"  bright>80: {bright}/{gray.size}, mean_gray={gray.mean():.0f}")

print("\nDone!")
