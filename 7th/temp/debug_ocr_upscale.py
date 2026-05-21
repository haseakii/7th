"""Debug OCR with upscaling and individual character isolation"""
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
cn_model = OCR_MODEL.cnocr

for i, (y1, y2) in enumerate(rows):
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]
    h, w = price_img.shape[:2]
    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)

    # Save original
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_orig_{i}.png', price_img)

    # Find tight text bounding box
    binary = (gray > 60).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_cnts = [c for c in contours if cv2.boundingRect(c)[3] > 3 and cv2.boundingRect(c)[2] > 2]

    print(f"\n=== Slot {i}: price area {w}x{h} ===")

    if valid_cnts:
        all_pts = np.vstack(valid_cnts)
        tx, ty, tw, th = cv2.boundingRect(all_pts)
        tx = max(0, tx - 2)
        ty = max(0, ty - 2)
        tw = min(w - tx, tw + 4)
        th = min(h - ty, th + 4)

        tight = price_img[ty:ty+th, tx:tx+tw]
        tight_gray = cv2.cvtColor(tight, cv2.COLOR_BGR2GRAY)

        print(f"  Tight crop: {tw}x{th} at ({tx},{ty})")

        # Try upscaling 2x and 3x
        for scale in [1, 2, 3]:
            new_w, new_h = tw * scale, th * scale
            scaled = cv2.resize(tight, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            scaled_gray = cv2.resize(tight_gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

            # Various preprocessing
            # a) Inverted binary
            _, inv = cv2.threshold(scaled_gray, 100, 255, cv2.THRESH_BINARY_INV)
            cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_{i}_s{scale}_inv.png', inv)

            # b) Original
            cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_{i}_s{scale}_orig.png', scaled)

            for lang, model in [("az", az_model), ("cn", cn_model)]:
                for pp_name, pp_img in [("inv", inv), ("orig_gray", scaled_gray)]:
                    result = model.atomic_ocr_for_single_lines([pp_img], cand_alphabet='0123456789')
                    detected = result[0] if result else []
                    if detected:
                        text = ''.join(str(c) for c in detected)
                        print(f"  Scale {scale}x {lang}/{pp_name}: '{text}' {detected}")

        # Try isolating individual characters
        # Sort contours left-to-right
        rects = [(cv2.boundingRect(c), c) for c in valid_cnts]
        rects.sort(key=lambda x: x[0][0])  # sort by x

        print(f"  Individual chars ({len(rects)} contours):")
        for j, ((cx, cy, cw, ch), cnt) in enumerate(rects):
            # Pad
            cx1 = max(0, cx - 2)
            cy1 = max(0, cy - 2)
            cx2 = min(w, cx + cw + 2)
            cy2 = min(h, cy + ch + 2)
            char_img = price_img[cy1:cy2, cx1:cx2]
            char_gray = cv2.cvtColor(char_img, cv2.COLOR_BGR2GRAY)

            # Scale up 3x
            char_scaled = cv2.resize(char_img, (char_img.shape[1]*3, char_img.shape[0]*3), interpolation=cv2.INTER_CUBIC)
            char_gray_scaled = cv2.resize(char_gray, (char_gray.shape[1]*3, char_gray.shape[0]*3), interpolation=cv2.INTER_CUBIC)

            cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\char_{i}_{j}.png', char_scaled)

            # OCR on individual char
            for lang, model in [("az", az_model)]:
                result = model.atomic_ocr_for_single_lines([char_gray_scaled], cand_alphabet='0123456789')
                detected = result[0] if result else []
                if detected:
                    print(f"    char[{j}] x={cx} y={cy} {cw}x{ch}: {lang}={detected}")
                else:
                    print(f"    char[{j}] x={cx} y={cy} {cw}x{ch}: (no detection)")

            # Also print pixel stats
            bright = char_gray > 100
            dark = char_gray < 60
            print(f"      bright>{100}: {bright.sum()}/{char_gray.size}, dark<{60}: {dark.sum()}/{char_gray.size}, mean={char_gray.mean():.0f}")
    else:
        print("  No contours found in price area")

print("\nDone!")
