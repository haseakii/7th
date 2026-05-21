"""Extract just the price text (x=1071-1104, upper portion) and OCR with upscaling"""
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

# Price text is at x=1071-1104 (cyan, upper portion of row)
PRICE_X1, PRICE_X2 = 1071, 1104

from module.ocr.models import OCR_MODEL
az_model = OCR_MODEL.azur_lane
cn_model = OCR_MODEL.cnocr

for i, (y1, y2) in enumerate(rows):
    row_h = y2 - y1
    # Extract the upper portion (top 45% of row) where the price text is
    upper_h = int(row_h * 0.45)
    price_img = img[y1:y1+upper_h, PRICE_X1:PRICE_X2]
    ph, pw = price_img.shape[:2]

    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(price_img, cv2.COLOR_BGR2HSV)

    # Save raw
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_focused_{i}.png', price_img)

    print(f"\n=== Slot {i}: price region {pw}x{ph} (row y={y1}-{y2}) ===")

    # Preprocessing methods
    preprocessed = {}

    # Method 1: Extract cyan pixels (BGR: high B, high G, low R)
    b, g, r = price_img[:,:,0].astype(float), price_img[:,:,1].astype(float), price_img[:,:,2].astype(float)
    cyan_mask = (b > 100) & (g > 100) & (r < b * 0.7)
    cyan_bin = np.zeros_like(gray)
    cyan_bin[cyan_mask] = 255
    preprocessed["cyan"] = cyan_bin

    # Method 2: Simple binary inverse with various thresholds
    for th in [60, 80, 100]:
        _, inv = cv2.threshold(gray, th, 255, cv2.THRESH_BINARY_INV)
        preprocessed[f"inv{th}"] = inv

    # Method 3: OTSU
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    preprocessed["otsu"] = otsu

    # Method 4: Adaptive threshold
    adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, 11, 3)
    preprocessed["adapt"] = adapt

    # Method 5: Extract bright on dark (V channel from HSV)
    _, v_thresh = cv2.threshold(hsv[:,:,2], 80, 255, cv2.THRESH_BINARY)
    preprocessed["v80"] = v_thresh

    # Try each preprocessing at multiple scales
    for pp_name, pp_img in preprocessed.items():
        if pp_img.max() == 0:
            continue

        nz = (pp_img > 0).sum()
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\pp_{i}_{pp_name}.png', pp_img)

        # Scale 2x, 3x, 4x
        for scale in [2, 3, 4]:
            scaled = cv2.resize(pp_img, (pw*scale, ph*scale), interpolation=cv2.INTER_CUBIC)
            # Re-threshold after scaling
            _, scaled = cv2.threshold(scaled, 127, 255, cv2.THRESH_BINARY)

            # Try azur_lane
            result = az_model.atomic_ocr_for_single_lines([scaled], cand_alphabet='0123456789')
            text = ''.join(str(c) for c in result[0]) if result and result[0] else ""
            if text:
                print(f"  az/{pp_name} x{scale}: '{text}' nz={nz}")

            # Try cnocr (full char set)
            result = cn_model.atomic_ocr_for_single_lines([scaled], cand_alphabet='0123456789')
            text = ''.join(str(c) for c in result[0]) if result and result[0] else ""
            if text:
                print(f"  cn/{pp_name} x{scale}: '{text}' nz={nz}")

    # Also try: normalize brightness and contrast, then OCR
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    for th in [80, 100, 120]:
        _, inv = cv2.threshold(normalized, th, 255, cv2.THRESH_BINARY_INV)
        for scale in [3, 4]:
            scaled = cv2.resize(inv, (pw*scale, ph*scale), interpolation=cv2.INTER_CUBIC)
            _, scaled = cv2.threshold(scaled, 127, 255, cv2.THRESH_BINARY)
            result = az_model.atomic_ocr_for_single_lines([scaled], cand_alphabet='0123456789')
            text = ''.join(str(c) for c in result[0]) if result and result[0] else ""
            if text:
                print(f"  az/norm_inv{th} x{scale}: '{text}'")

    # Print pixel stats
    print(f"  Gray stats: mean={gray.mean():.0f} median={np.median(gray):.0f} "
          f"min={gray.min()} max={gray.max()}")

    # Find the actual text bounding box within this region
    bright_mask = gray > 80
    if bright_mask.sum() > 10:
        bright_ys, bright_xs = np.where(bright_mask)
        tx1, tx2 = bright_xs.min(), bright_xs.max()
        ty1, ty2 = bright_ys.min(), bright_ys.max()
        print(f"  Text bbox: x={tx1}-{tx2} ({tx2-tx1+1}px) y={ty1}-{ty2} ({ty2-ty1+1}px)")

        # Extract tight crop
        tight = price_img[ty1:ty2+1, tx1:tx2+1]
        th, tw = tight.shape[:2]
        tight_gray = cv2.cvtColor(tight, cv2.COLOR_BGR2GRAY)

        # OCR on tight crop at 4x
        for scale in [4, 5]:
            scaled = cv2.resize(tight_gray, (tw*scale, th*scale), interpolation=cv2.INTER_CUBIC)
            for th_val in [60, 80, 100]:
                _, sbin = cv2.threshold(scaled, th_val, 255, cv2.THRESH_BINARY_INV)
                result = az_model.atomic_ocr_for_single_lines([sbin], cand_alphabet='0123456789')
                text = ''.join(str(c) for c in result[0]) if result and result[0] else ""
                if text:
                    print(f"  tight x{scale} inv{th_val}: '{text}'")

print("\nDone!")
