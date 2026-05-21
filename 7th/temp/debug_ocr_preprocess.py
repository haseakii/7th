"""Debug OCR preprocessing"""
import sys, os, cv2, numpy as np

sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer, PRICE_X, PRICE_TEXT_COLOR
from module.base.utils import extract_letters, crop

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

for i, (y1, y2) in enumerate(rows):
    price_area = (PRICE_X[0], y1, PRICE_X[1], y2)
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]

    # Try different preprocessing methods
    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(price_img, cv2.COLOR_BGR2HSV)

    # Method 1: extract_letters with golden color
    extracted = extract_letters(price_img, letter=PRICE_TEXT_COLOR, threshold=128)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\pp_extract_{i}.png', extracted)

    # Method 2: Simple brightness threshold (V channel)
    _, v_thresh = cv2.threshold(hsv[:,:,2], 80, 255, cv2.THRESH_BINARY)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\pp_vthresh_{i}.png', v_thresh)

    # Method 3: Invert dark bg to white, text to black
    _, inv_thresh = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\pp_invthresh_{i}.png', inv_thresh)

    # Method 4: Extract CYAN pixels (high R+G, low B)
    # Cyan is RGB ~(0,255,255), BGR ~(255,255,0)
    # The actual text: BGR=(42,120,153) - high G and R, low B
    cyan_mask = (price_img[:,:,1] > 80) & (price_img[:,:,2] > 80) & (price_img[:,:,0] < 80)
    cyan_extract = np.zeros_like(gray)
    cyan_extract[cyan_mask] = 255
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\pp_cyan_{i}.png', cyan_extract)

    # Print stats
    print(f"Slot {i}: extracted_white={extracted.max()}, v_white={v_thresh.max()}, "
          f"inv_white={inv_thresh.max()}, cyan_white={cyan_extract.max()}")
    if extracted.max() > 0:
        print(f"  extract non-zero pixels: {(extracted > 0).sum()}")
    if v_thresh.max() > 0:
        print(f"  v_thresh non-zero: {(v_thresh > 0).sum()}")
    if inv_thresh.max() > 0:
        print(f"  inv_thresh non-zero: {(inv_thresh > 0).sum()}")
    if cyan_extract.max() > 0:
        print(f"  cyan non-zero: {(cyan_extract > 0).sum()}")

    # Also test OCR on each preprocessed version
    from module.ocr.models import OCR_MODEL
    ocr_model = OCR_MODEL.azur_lane

    for pp_name, pp_img in [("extract", extracted), ("v_thresh", v_thresh),
                              ("inv_thresh", inv_thresh), ("cyan", cyan_extract)]:
        if pp_img.max() > 0:
            result = ocr_model.atomic_ocr_for_single_lines([pp_img], cand_alphabet='0123456789')
            print(f"  OCR({pp_name}): {result}")

print("\nDone!")
