"""Collect digit templates from price area for template matching OCR"""
import sys, os, cv2, numpy as np

sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer, PRICE_X
from module.base.utils import crop

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()
cv2.imwrite('D:\\software\\7th\\7th\\temp\\full_screenshot.png', img)

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

TEMPLATE_DIR = 'D:\\software\\7th\\7th\\temp\\digit_templates'
os.makedirs(TEMPLATE_DIR, exist_ok=True)

for i, (y1, y2) in enumerate(rows):
    # Get price area
    price_img = img[y1:y2, PRICE_X[0]:PRICE_X[1]]
    h, w = price_img.shape[:2]
    gray = cv2.cvtColor(price_img, cv2.COLOR_BGR2GRAY)

    # The price text is bright on dark bg. Use gradient-based approach to find text.
    # First, apply adaptive threshold to get binary
    # Try different methods to segment digits

    # Method: Use brightness threshold and morphological ops
    # The text is bright (mean ~100) on dark bg (mean ~30-60)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite(f'{TEMPLATE_DIR}/binary_{i}.png', binary)

    # Also try inverted
    _, inv_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cv2.imwrite(f'{TEMPLATE_DIR}/inv_binary_{i}.png', inv_binary)

    # Find connected components (individual characters)
    # Use the inverted binary (text = white on black)
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)

    print(f"\n=== Slot {i}: price area {w}x{h} ===")
    print(f"  Connected components: {n_labels - 1} (excluding background)")

    # Sort by x position
    components = []
    for j in range(1, n_labels):
        x, y, cw, ch, area = stats[j]
        if area > 10 and ch > 8 and cw > 3:  # Filter noise
            components.append((x, y, cw, ch, area, j))

    components.sort(key=lambda c: c[0])  # sort left-to-right

    print(f"  Valid components: {len(components)}")
    for x, y, cw, ch, area, j in components:
        # Extract digit with padding
        px1 = max(0, x - 1)
        py1 = max(0, y - 1)
        px2 = min(w, x + cw + 1)
        py2 = min(h, y + ch + 1)
        digit_img = inv_binary[py1:py2, px1:px2]

        # Save for manual labeling
        fname = f'slot{i}_x{x}_y{y}_{cw}x{ch}_area{area}.png'
        cv2.imwrite(f'{TEMPLATE_DIR}/{fname}', digit_img)
        print(f"    x={x} y={y} {cw}x{ch} area={area}: saved as {fname}")

    # Also try to extract using horizontal projection
    # Sum bright pixels per column
    col_profile = (gray > 80).sum(axis=0)
    print(f"  Column profile (bright>80):")
    for xx in range(0, w, 2):
        val = col_profile[xx:min(xx+2, w)].sum()
        if val > 5:
            print(f"    x={xx}: {val}")

    # Vertical profile
    row_profile = (gray > 80).sum(axis=1)
    print(f"  Row profile (bright>80):")
    for yy in range(0, h, 2):
        val = row_profile[yy:min(yy+2, h)].sum()
        if val > 5:
            print(f"    y={yy}: {val}")

    # Save the raw price area for reference
    cv2.imwrite(f'{TEMPLATE_DIR}/price_area_{i}.png', price_img)

print(f"\nTemplates saved to {TEMPLATE_DIR}")
print("Review the digit templates and label them (rename to digit_X.png where X is the digit)")
print("Then run the template matching test.")
