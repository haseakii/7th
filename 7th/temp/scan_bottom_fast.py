"""
快速扫描底栏 - 一行点击过去，记录哪些位置触发了变化
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
    time.sleep(1.5)

# Ensure lobby
nt, nm, ct, img = check()
print(f"Start: nt={nt:.0f}, nm={nm:.0f}, ct={ct:.0f}")
if not (nt > 100 and ct > 100):
    for _ in range(5):
        go_back()
        nt, nm, ct, img = check()
        if nt > 100 and ct > 100:
            break
    print(f"After BACKs: nt={nt:.0f}, nm={nm:.0f}, ct={ct:.0f}")

# Take baseline (before any clicks)
nt_base, nm_base, ct_base, _ = check()
cv2.imwrite('D:\\software\\7th\\7th\\temp\\baseline_lobby.png', img)
print(f"Baseline: nt={nt_base:.0f}, nm={nm_base:.0f}, ct={ct_base:.0f}")

# Scan bottom bar (y=685) every 30px
# Only report changes, without trying to return to lobby after each
# We'll detect hits by significant deviation from baseline
results = []
hits = []
for x in range(20, 1260, 30):
    tap(x, 685)
    time.sleep(0.8)
    nt, nm, ct, img = check()
    results.append((x, nt, nm, ct))

    diff = abs(nt - 180) + abs(nm - 205) + abs(ct - 200)  # expected lobby values
    if diff > 30:
        hits.append((x, nt, nm, ct, diff))
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\hit_x{x}_nt{nt:.0f}.png', img)
        print(f"HIT at x={x}: nt={nt:.0f} nm={nm:.0f} ct={ct:.0f} diff={diff:.0f}")
        # Try to return to lobby
        for _ in range(5):
            go_back()
            nt2, nm2, ct2, _ = check()
            if nt2 > 100 and ct2 > 100:
                print(f"  Returned to lobby (after {_+1} BACKs)")
                break

print("\n=== All Hits ===")
print(f"{'x':>5s} {'nav_top':>8s} {'nav_mid':>8s} {'content':>8s} {'diff':>6s}")
for x, nt, nm, ct, d in hits:
    print(f"{x:5d} {nt:8.0f} {nm:8.0f} {ct:8.0f} {d:6.0f}")
