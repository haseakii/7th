"""
精简测试 - 只测左侧栏最可能的几个按钮位置
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
    r = subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
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
    time.sleep(1.0)

# Get to lobby
nt, nm, ct, img = check()
print(f"Initial: nt={nt:.0f}, nm={nm:.0f}, ct={ct:.0f}")
back_count = 0
while not (nt > 100 and ct > 100) and back_count < 10:
    go_back()
    nt, nm, ct, img = check()
    back_count += 1
    print(f"  After BACK {back_count}: nt={nt:.0f}, nm={nm:.0f}, ct={ct:.0f}")

if nt > 100 and ct > 100:
    print("In lobby!")
else:
    print("Couldn't reach lobby")
    sys.exit(1)

# Based on nav bar analysis:
# - y=270-330 has HIGH saturation (98-112) -> likely a button
# - y=460-480 has CYAN color -> likely a button
# Test multiple x positions for each
key_points = []
for x in [60, 80, 100, 120, 140, 160, 180, 200]:
    for y in [280, 310, 340, 370, 400, 430, 460]:
        key_points.append((x, y))

print(f"\nTesting {len(key_points)} key points...")
for x, y in key_points:
    # Verify lobby
    nt, nm, ct, _ = check()
    if not (nt > 100 and ct > 100):
        print(f"Lost lobby at ({x}, {y}), recovering...")
        for _ in range(5):
            go_back()
            nt, nm, ct, _ = check()
            if nt > 100 and ct > 100:
                break
        if not (nt > 100 and ct > 100):
            print("Can't recover, aborting")
            break

    tap(x, y)
    time.sleep(1.5)

    nt2, nm2, ct2, img2 = check()
    diff = abs(nt2 - nt) + abs(nm2 - nm) + abs(ct2 - ct)

    if diff > 15:
        print(f"HIT x={x} y={y}: nt={nt:.0f}->{nt2:.0f} nm={nm:.0f}->{nm2:.0f} ct={ct:.0f}->{ct2:.0f}")
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\hit_x{x}_y{y}.png', img2)

        if nt2 < 80 and nm2 > 120 and ct2 < 100:
            print(f">>> SECRET SHOP FOUND! x={x} y={y} <<<")
            sys.exit(0)

        # BACK to lobby
        for _ in range(3):
            go_back()
            nt, nm, ct, _ = check()
            if nt > 100 and ct > 100:
                break
    else:
        print(f"  ({x}, {y}): no change", end="\r")

print("\nDone")
