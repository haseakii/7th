"""
诊断脚本 - 校准物品识别器
分析当前秘密商店截图中的物品位置、颜色特征，并与 recognizer.py 的参数对比
"""
import sys, os, cv2, numpy as np, time
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
if not device.connect():
    print("Failed to connect")
    sys.exit(1)

# Take screenshot
img = device.screenshot()
if img is None:
    print("Failed to screenshot")
    sys.exit(1)

cv2.imwrite('D:\\software\\7th\\7th\\temp\\calibrate_current.png', img)
print(f"Screenshot saved: {img.shape}")

h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# ============================================================
# 1. 分析整个画面：打印亮度网格
# ============================================================
print("\n=== 1. 画面亮度网格 (每隔40px采样) ===")
print(f"{'y/x':>6s}", end="")
for x in range(40, w, 40):
    print(f"{x:6d}", end="")
print()
for y in range(40, h, 40):
    print(f"{y:6d}", end="")
    for x in range(40, w, 40):
        x1, y1, x2, y2 = max(0,x-20), max(0,y-20), min(w,x+20), min(h,y+20)
        b = float(img[y1:y2, x1:x2, :3].mean())
        print(f"{b:6.0f}", end="")
    print()

# ============================================================
# 2. 水平扫描 - 找出物品内容在哪些 x 范围
# ============================================================
print("\n=== 2. 水平亮度分布 (y=80-620, 每10px一行) ===")
for y in range(80, min(620, h), 10):
    row_strip = gray[y, :]
    # 找亮度变化大的区段
    row_std = float(np.array([np.std(row_strip[x:x+20]) for x in range(0, w-20, 10)]).mean())
    if row_std > 15:
        print(f"y={y:3d}: std={row_std:.1f} ", end="")
        # 打印该行各段的亮度
        segments = [float(gray[y, x:min(x+40, w)].mean()) for x in range(0, w, 40)]
        print(f"segs={[f'{s:.0f}' for s in segments]}")

# ============================================================
# 3. 垂直扫描 - 使用 recognizer 的 x=400-900 范围检测行
# ============================================================
print("\n=== 3. 垂直扫描 x=400-900 (recognizer 当前扫描区域) ===")
strip = gray[:, 400:900]
in_item = False
item_start = 0
rows_400_900 = []
for y in range(80, min(620, h)):
    row_std = float(strip[y, :].std())
    if row_std > 15 and not in_item:
        item_start = y
        in_item = True
    elif row_std <= 15 and in_item:
        if y - item_start >= 40:
            rows_400_900.append((item_start, y))
        in_item = False
if in_item:
    rows_400_900.append((item_start, min(620, h)))

print(f"检测到 {len(rows_400_900)} 行: {rows_400_900}")

# ============================================================
# 4. 垂直扫描 - x=150-230 (实际物品位置)
# ============================================================
print("\n=== 4. 垂直扫描 x=150-250 (实际物品图标区域) ===")
strip2 = gray[:, 150:250]
in_item = False
item_start = 0
rows_150_250 = []
for y in range(80, min(620, h)):
    row_std = float(strip2[y, :].std())
    if row_std > 15 and not in_item:
        item_start = y
        in_item = True
    elif row_std <= 15 and in_item:
        if y - item_start >= 40:
            rows_150_250.append((item_start, y))
        in_item = False
if in_item:
    rows_150_250.append((item_start, min(620, h)))

print(f"检测到 {len(rows_150_250)} 行: {rows_150_250}")

# ============================================================
# 5. 对每个检测到的物品行分析特征
# ============================================================
print("\n=== 5. 物品特征分析 ===")

# 使用实际检测到的行来分析
analyze_rows = rows_400_900 if rows_400_900 else rows_150_250

for i, (y1, y2) in enumerate(analyze_rows):
    item_h = y2 - y1
    print(f"\n--- 物品行 {i}: y={y1}-{y2} (高度={item_h}) ---")

    # 扫描该行内各x段的颜色
    for x_start in range(100, 900, 50):
        x_end = min(x_start + 50, w)
        seg = img[y1:min(y2, h), x_start:x_end]
        if seg.size == 0:
            continue
        bgr = (float(seg[:,:,0].mean()), float(seg[:,:,1].mean()), float(seg[:,:,2].mean()))
        hsv = cv2.cvtColor(seg, cv2.COLOR_BGR2HSV)
        h_mean = float(hsv[:,:,0].mean())
        s_mean = float(hsv[:,:,1].mean())
        v_mean = float(hsv[:,:,2].mean())
        # 过滤暗像素
        bright = seg[hsv[:,:,2] > 40]
        if len(bright) > 20:
            bb = float(bright[:,0].mean())
            bg = float(bright[:,1].mean())
            br = float(bright[:,2].mean())
            bh = float(cv2.cvtColor(bright.reshape(-1,1,3), cv2.COLOR_BGR2HSV)[:,:,0].mean())
            rg = br / max(bg, 1.0)
            bpct = len(bright) / (seg.shape[0] * seg.shape[1])
            if rg > 1.2:
                print(f"  x={x_start:3d}-{x_end:3d}: BGR=({bb:.0f},{bg:.0f},{br:.0f}) H={bh:.0f} R/G={rg:.2f} bright={bpct:.0%} ***")
            elif bpct > 0.3:
                print(f"  x={x_start:3d}-{x_end:3d}: BGR=({bb:.0f},{bg:.0f},{br:.0f}) H={bh:.0f} R/G={rg:.2f} bright={bpct:.0%}")

    # 保存该物品行的图标区域（x=150-230 实际位置 或 x=400-470 recognizer 区域）
    for save_name, (sx, ex) in [("actual", (150,230)), ("recognizer", (400,470))]:
        crop_img = img[y1:y2, sx:min(ex, w)]
        if crop_img.size > 0:
            path = f'D:\\software\\7th\\7th\\temp\\item{i}_{save_name}_y{y1}.png'
            cv2.imwrite(path, crop_img)
            print(f"  Saved {save_name} icon: {path}")

# ============================================================
# 6. 测试 recognizer 本身的 _find_item_rows
# ============================================================
print("\n=== 6. 测试 recognizer._find_item_rows ===")
from shop.recognizer import ItemRecognizer, ITEM_SCAN_X1, ITEM_SCAN_X2
rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)
print(f"recognizer 检测到 {len(rows)} 行: {rows}")

# 对每行测试分类
for slot_idx, (y1, y2) in enumerate(rows):
    icon_img = img[y1:min(y1+min(y2-y1, 80), h), ITEM_SCAN_X1:ITEM_SCAN_X2]
    features = rec._extract_features(icon_img)
    item_type, conf = rec._classify_by_features(features)
    print(f"  Slot {slot_idx} (y={y1}-{y2}): type={item_type}, conf={conf:.2f}")
    if features:
        print(f"    R/G={features.get('rg_ratio',0):.2f} H={features.get('avg_h',0):.0f} BGR={tuple(f'{v:.0f}' for v in features.get('avg_bgr',(0,0,0)))}")

print("\nDone!")
