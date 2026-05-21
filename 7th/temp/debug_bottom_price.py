"""Focus on bottom portion of price area for digit recognition"""
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

from module.ocr.models import OCR_MODEL
az_model = OCR_MODEL.azur_lane

for i, (y1, y2) in enumerate(rows):
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]
    h, w = price_img.shape[:2]
    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)

    # Extract bottom portion (lower 40% of price area)
    bottom_start = int(h * 0.6)
    bottom_img = price_img[bottom_start:, :]
    bottom_gray = gray[bottom_start:, :]
    bh, bw = bottom_img.shape[:2]

    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\bottom_price_{i}.png', bottom_img)

    print(f"\n=== Slot {i}: bottom area {bw}x{bh} (from y={bottom_start}) ===")

    # Try multiple threshold methods on bottom area
    # Method 1: Binary inverse with Otsu
    _, inv_otsu = cv2.threshold(bottom_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\bottom_inv_{i}.png', inv_otsu)

    # Method 2: Adaptive threshold
    adaptive = cv2.adaptiveThreshold(bottom_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 15, 5)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\bottom_adapt_{i}.png', adaptive)

    # Method 3: Color-based extraction for cyan text
    b, g, r = bottom_img[:,:,0].astype(float), bottom_img[:,:,1].astype(float), bottom_img[:,:,2].astype(float)
    # Cyan text: high G+B, low R
    cyan_mask = (g > 80) & (b > 80) & (r < g * 0.8) & (r < b * 0.8)
    cyan_binary = np.zeros_like(bottom_gray)
    cyan_binary[cyan_mask] = 255
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\bottom_cyan_{i}.png', cyan_binary)

    # OCR on each preprocessing
    for pp_name, pp_img in [("inv_otsu", inv_otsu), ("adaptive", adaptive), ("cyan", cyan_binary)]:
        # Scale up 3x for OCR
        scaled = cv2.resize(pp_img, (bw*3, bh*3), interpolation=cv2.INTER_CUBIC)

        # Azur lane model
        result = az_model.atomic_ocr_for_single_lines([scaled], cand_alphabet='0123456789')
        detected = result[0] if result else []
        if detected:
            text = ''.join(str(c) for c in detected)
            print(f"  az/{pp_name}: '{text}'")

        # Also try original (not inverted)
        if pp_name.startswith("inv"):
            normal = 255 - pp_img
            scaled_n = cv2.resize(normal, (bw*3, bh*3), interpolation=cv2.INTER_CUBIC)
            result = az_model.atomic_ocr_for_single_lines([scaled_n], cand_alphabet='0123456789')
            detected = result[0] if result else []
            if detected:
                text = ''.join(str(c) for c in detected)
                print(f"  az/normal_{pp_name}: '{text}'")

    # Vertical projection to find individual character positions
    # Use bottom_gray: find columns with bright pixels
    col_bright = (bottom_gray > 80).sum(axis=0)
    print(f"  Column bright>80 profile:")
    for xx in range(bw):
        if col_bright[xx] > 3:
            print(f"    x={xx}: {col_bright[xx]} bright pixels")

    # Segment into character groups
    # A character group is a contiguous set of columns with bright pixels
    in_char = False
    char_regions = []
    start_x = 0
    for xx in range(bw):
        if col_bright[xx] > 3 and not in_char:
            in_char = True
            start_x = xx
        elif col_bright[xx] <= 3 and in_char:
            in_char = False
            if xx - start_x >= 2:  # At least 2px wide
                char_regions.append((start_x, xx))
    if in_char and bw - start_x >= 2:
        char_regions.append((start_x, bw))

    print(f"  Character regions: {char_regions}")

    # Extract and OCR each character
    for j, (cx1, cx2) in enumerate(char_regions):
        char_img = bottom_img[:, cx1:cx2]
        char_gray = bottom_gray[:, cx1:cx2]
        cw = cx2 - cx1

        # Scale up 4x
        char_scaled = cv2.resize(char_gray, (cw*4, bh*4), interpolation=cv2.INTER_CUBIC)
        _, char_bin = cv2.threshold(char_scaled, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\char_bottom_{i}_{j}_x{cx1}.png', char_bin)

        # OCR
        result = az_model.atomic_ocr_for_single_lines([char_bin], cand_alphabet='0123456789')
        detected = result[0] if result else []
        if detected:
            print(f"    char[{j}] x={cx1}-{cx2} ({cw}px): {detected}")

        # Also print pixel stats
        bright_n = (char_gray > 80).sum()
        print(f"      bright>80: {bright_n}/{char_gray.size}, mean_gray={char_gray.mean():.0f}")

print("\nDone!")
