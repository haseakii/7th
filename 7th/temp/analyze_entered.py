"""
分析进入的子菜单截图
"""
import sys, os, cv2, numpy as np

temp_dir = 'D:\\software\\7th\\7th\\temp'
img = cv2.imread(os.path.join(temp_dir, 'entered_Bottom btn area righ.png'))
h, w = img.shape[:2]
print(f"Image: {w}x{h}")

# Scene analysis
nt = float(cv2.cvtColor(img[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
nm = float(cv2.cvtColor(img[300:480, 80:160], cv2.COLOR_BGR2GRAY).mean())
ct = float(cv2.cvtColor(img[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
print(f"nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

# Full brightness grid
print("\n=== Brightness grid (40x40) ===")
for y in range(0, h, 40):
    row = []
    for x in range(0, w, 40):
        cell = img[y:min(y+40, h), x:min(x+40, w)]
        b = float(cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY).mean())
        if b < 50: sym = "##"
        elif b < 100: sym = "[]"
        elif b < 150: sym = ".."
        elif b < 200: sym = "  "
        else: sym = "__"
        row.append(sym)
    print(f"y={y:3d}: " + "".join(row))

# Saturation grid
print("\n=== Saturation grid (40x40) ===")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
for y in range(0, h, 40):
    row = []
    for x in range(0, w, 40):
        cell = hsv[y:min(y+40, h), x:min(x+40, w)]
        s = float(cell[:,:,1].mean())
        if s < 20: sym = "  "
        elif s < 50: sym = ".."
        elif s < 80: sym = "[]"
        elif s < 120: sym = "##"
        else: sym = "HH"
        row.append(sym)
    print(f"y={y:3d}: " + "".join(row))

# Also check what the nav bar looks like
print("\n=== Nav bar detail (x=60-200, y=0-720) ===")
for y in range(0, h, 20):
    strip = img[y:y+20, 60:200, :]
    b = float(strip[:,:,0].mean())
    g = float(strip[:,:,1].mean())
    r = float(strip[:,:,2].mean())
    hsv_strip = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    s = float(hsv_strip[:,:,1].mean())
    gray = float(cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY).mean())
    print(f"  y={y:3d}: gray={gray:.0f} sat={s:.0f} BGR=({b:.0f},{g:.0f},{r:.0f})")

cv2.imwrite(os.path.join(temp_dir, 'entered_analysis.png'), img)
print("\nSaved analysis image")

# Also check what the original lobby screenshot looks like most recently
img2 = cv2.imread(os.path.join(temp_dir, 'current_state.png'))
h2, w2 = img2.shape[:2]
nt2 = float(cv2.cvtColor(img2[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
nm2 = float(cv2.cvtColor(img2[300:480, 80:160], cv2.COLOR_BGR2GRAY).mean())
ct2 = float(cv2.cvtColor(img2[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
print(f"\n=== Lobby (current_state.png): nav_top={nt2:.0f}, nav_mid={nm2:.0f}, content={ct2:.0f} ===")
for y in range(0, h2, 40):
    row = []
    for x in range(0, w2, 40):
        cell = img2[y:min(y+40, h2), x:min(x+40, w2)]
        b = float(cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY).mean())
        if b < 50: sym = "##"
        elif b < 100: sym = "[]"
        elif b < 150: sym = ".."
        elif b < 200: sym = "  "
        else: sym = "__"
        row.append(sym)
    print(f"y={y:3d}: " + "".join(row))
