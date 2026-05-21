"""
分析所有截图，找出哪些点击改变了场景
"""
import sys, os, cv2, numpy as np

temp_dir = 'D:\\software\\7th\\7th\\temp'
pngs = [f for f in os.listdir(temp_dir) if f.endswith('.png')]

results = []
for fname in sorted(pngs):
    path = os.path.join(temp_dir, fname)
    img = cv2.imread(path)
    if img is None:
        continue
    h, w = img.shape[:2]
    nav_top = float(cv2.cvtColor(img[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
    nav_mid = float(cv2.cvtColor(img[300:480, 80:160], cv2.COLOR_BGR2GRAY).mean())
    content = float(cv2.cvtColor(img[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
    results.append((fname, nav_top, nav_mid, content))

# Group by scene type
print("=== All Screenshots ===")
print(f"{'File':45s} {'nav_top':>8s} {'nav_mid':>8s} {'content':>8s} {'Scene':>15s}")
print("-"*85)
for fname, nt, nm, ct in results:
    if nt < 80 and nm > 120 and ct < 100:
        scene = "SECRET_SHOP"
    elif nt > 100 and ct > 100:
        scene = "LOBBY"
    elif nt < 100 and ct < 100:
        scene = "submenu"
    else:
        scene = "unknown"
    print(f"{fname:45s} {nt:8.0f} {nm:8.0f} {ct:8.0f} {scene:>15s}")
