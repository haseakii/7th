"""
从确认的大厅状态精确测试左侧栏所有按钮位置
"""
import sys, os, cv2, numpy as np, subprocess, time
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController, ADB_EXECUTABLE

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
if not device.connect():
    print("Failed")
    sys.exit(1)

def tap(x, y):
    subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)

def check():
    img = device.screenshot()
    nt = float(cv2.cvtColor(img[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
    nm = float(cv2.cvtColor(img[300:480, 80:160], cv2.COLOR_BGR2GRAY).mean())
    ct = float(cv2.cvtColor(img[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
    return nt, nm, ct, img

def go_back():
    subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
                  capture_output=True, timeout=10)
    time.sleep(1.2)

# Ensure lobby - press BACK until nav_top > 100 AND ct > 100
# With max attempts to prevent getting stuck
print("Ensuring lobby state...")
for attempt in range(12):
    nt, nm, ct, img = check()
    if nt > 100 and ct > 100:
        print(f"  In lobby: nt={nt:.0f}, nm={nm:.0f}, ct={ct:.0f}")
        break
    # If nav_top < 80 (submenu), one BACK should return to lobby
    # If nav_top > 100 but ct < 100 (partial change), also try BACK
    print(f"  Not lobby (nt={nt:.0f}, ct={ct:.0f}), BACK...")
    go_back()
else:
    print("Could not reach lobby!")
    sys.exit(1)

# Save baseline
cv2.imwrite('D:\\software\\7th\\7th\\temp\\sidebar_baseline.png', img)

# Test sidebar button positions
# Start from a fresh lobby for each test
test_positions = []
# Multiple x positions to find the correct clickable width
for x_pos in [90, 120, 140, 160]:
    for y_pos in range(180, 560, 20):
        test_positions.append((x_pos, y_pos))

print(f"\nTesting {len(test_positions)} positions...")

for i, (x_pos, y_pos) in enumerate(test_positions):
    # Ensure lobby before each click (quick check + BACK if needed)
    nt, nm, ct, img = check()
    if not (nt > 100 and ct > 100):
        for _ in range(6):
            go_back()
            nt, nm, ct, img = check()
            if nt > 100 and ct > 100:
                break
        if not (nt > 100 and ct > 100):
            print(f"  Lost lobby at pos {i}, aborting")
            break

    tap(x_pos, y_pos)
    time.sleep(1.5)
    nt2, nm2, ct2, img2 = check()

    diff = abs(nt2 - nt) + abs(nm2 - nm) + abs(ct2 - ct)
    if diff > 15:
        print(f"HIT ({i+1}/{len(test_positions)}): x={x_pos}, y={y_pos}: diff={diff:.0f} nt:{nt:.0f}->{nt2:.0f} ct:{ct:.0f}->{ct2:.0f}")
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\hit_x{x_pos}_y{y_pos}.png', img2)

        if nt2 < 80 and nm2 > 120 and ct2 < 100:
            print(f"\n>>> SECRET SHOP FOUND at x={x_pos}, y={y_pos}! <<<")
            sys.exit(0)

        # Go back to lobby
        for _ in range(3):
            go_back()
            nt, nm, ct, _ = check()
            if nt > 100 and ct > 100:
                break
    elif i % 10 == 0:
        print(f"  No hit at ({x_pos}, {y_pos})... ({i+1}/{len(test_positions)})")

print("\nDone testing all positions. No secret shop found.")
