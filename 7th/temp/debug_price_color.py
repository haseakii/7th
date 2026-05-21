"""Debug price area colors and OCR"""
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
print(f"Found {len(rows)} rows")

# For each row, analyze price area pixels in detail
for i, (y1, y2) in enumerate(rows):
    price_area = img[y1:y2, 800:950]
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_raw_{i}.png', price_area)

    hsv = cv2.cvtColor(price_area, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(price_area, cv2.COLOR_BGR2GRAY)

    # Check various pixel ranges
    for v_min, label in [(0, "all"), (40, "V>40"), (80, "V>80"), (128, "V>128"), (180, "V>180")]:
        mask = hsv[:,:,2] > v_min
        if mask.sum() > 0:
            bgr = (float(price_area[:,:,0][mask].mean()),
                   float(price_area[:,:,1][mask].mean()),
                   float(price_area[:,:,2][mask].mean()))
            print(f"  Slot {i} {label}: n={mask.sum()}, BGR=({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

    # Also check the GRAY version
    print(f"  Slot {i} gray: min={gray.min()}, max={gray.max()}, mean={gray.mean():.0f}")

    # Check the text areas using inverted threshold (dark text)
    for thresh, label in [(50, "dark<50"), (80, "dark<80"), (100, "dark<100")]:
        dark_mask = gray < thresh
        if dark_mask.sum() > 50:  # Some dark content
            bgr = (float(price_area[:,:,0][dark_mask].mean()),
                   float(price_area[:,:,1][dark_mask].mean()),
                   float(price_area[:,:,2][dark_mask].mean()))
            print(f"  Slot {i} {label}: n={dark_mask.sum()}, BGR=({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

    # Save a preprocessed version for OCR
    # Try: white text on dark bg (original assumption)
    white_text = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)[1]
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_binary_white_{i}.png', white_text)

    # Try: dark text on light bg (inverted)
    dark_text = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)[1]
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\price_binary_dark_{i}.png', dark_text)

print("\nDone!")
