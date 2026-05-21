"""
全面分析大厅布局，找到所有可点击的UI元素
"""
import sys
sys.path.insert(0, 'D:\\software\\7th\\7th')

import os
import cv2
import numpy as np

temp_dir = 'D:\\software\\7th\\7th\\temp'
img = cv2.imread(os.path.join(temp_dir, 'lobby_screenshot.png'))
h, w = img.shape[:2]

# Full grid with smaller cells
print("=== Full brightness grid (40x40 cells) ===")
for y in range(0, h, 40):
    row = []
    for x in range(0, w, 40):
        cell = img[y:min(y+40, h), x:min(x+40, w)]
        b = float(cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY).mean())
        # Use symbols for quick visual
        if b < 50:
            sym = "##"
        elif b < 100:
            sym = "[]"
        elif b < 150:
            sym = ".."
        elif b < 200:
            sym = "  "
        else:
            sym = "__"
        row.append(sym)
    print(f"y={y:3d}: " + "".join(row))

# Also analyze distinct color regions using HSV
print()
print("=== Saturation map (40x40 cells, high sat = UI elements) ===")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
for y in range(0, h, 40):
    row = []
    for x in range(0, w, 40):
        cell = hsv[y:min(y+40, h), x:min(x+40, w)]
        s = float(cell[:,:,1].mean())
        if s < 20:
            sym = "  "  # gray
        elif s < 50:
            sym = ".."  # low sat
        elif s < 80:
            sym = "[]"  # medium
        elif s < 120:
            sym = "##"  # high
        else:
            sym = "HH"  # very high
        row.append(sym)
    print(f"y={y:3d}: " + "".join(row))

# Look for specific features:
# 1. Bottom bar (typically where shop/action buttons are)
print()
print("=== Bottom bar analysis (y=620-720) ===")
bottom = img[620:720, :, :]
bottom_hsv = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
for x in range(0, w, 20):
    strip = bottom[:, x:min(x+20, w)]
    b = float(cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY).mean())
    s = float(bottom_hsv[:, x:min(x+20, w), 1].mean())
    if b < 100 or s > 50:
        h_val = float(bottom_hsv[:, x:min(x+20, w), 0].mean())
        print(f"  x={x:3d}: bright={b:.0f} sat={s:.0f} hue={h_val:.0f}")

# 2. Right side (often has character or menu)
print()
print("=== Right side analysis (x=1000-1280) ===")
right = img[:, 1000:1280, :]
right_hsv = cv2.cvtColor(right, cv2.COLOR_BGR2HSV)
for y in range(0, h, 30):
    strip = right[y:min(y+30, h), :, :]
    b = float(cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY).mean())
    s = float(right_hsv[y:min(y+30, h), :, 1].mean())
    print(f"  y={y:3d}: bright={b:.0f} sat={s:.0f}")

# 3. Store the debug image with labeled regions
debug = img.copy()
# Draw grid
for x in range(0, w, 160):
    cv2.line(debug, (x, 0), (x, h), (200, 200, 200), 1)
for y in range(0, h, 80):
    cv2.line(debug, (0, y), (w, y), (200, 200, 200), 1)
cv2.imwrite(os.path.join(temp_dir, 'lobby_grid.png'), debug)
print(f"\nDebug image saved")
