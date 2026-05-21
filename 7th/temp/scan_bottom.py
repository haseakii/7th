"""
精细扫描底栏 - 每40px点击一次，找出所有可点击底部按钮
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

def ensure_lobby():
    for _ in range(8):
        nt, nm, ct, img = check()
        if nt > 100 and ct > 100:
            return True
        subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
                      capture_output=True, timeout=10)
        time.sleep(1.0)
    nt, nm, ct, img = check()
    print(f"  ensure_lobby result: nt={nt:.0f}, nm={nm:.0f}, ct={ct:.0f}")
    return nt > 100 and ct > 100

# Scan bottom bar every 40px at y=685
print("=== Scanning bottom bar (y=685) ===")
for x in range(20, 1280, 40):
    if not ensure_lobby():
        print(f"Lost lobby at x={x}")
        break

    nt, nm, ct, img_before = check()
    tap(x, 685)
    time.sleep(1.5)
    nt2, nm2, ct2, img_after = check()

    diff = abs(nt2 - nt) + abs(nm2 - nm) + abs(ct2 - ct)
    status = "***" if diff > 20 else "   "
    if diff > 10:
        print(f"x={x:4d}: diff={diff:.0f} {status} nt:{nt:.0f}->{nt2:.0f} nm:{nm:.0f}->{nm2:.0f} ct:{ct:.0f}->{ct2:.0f}")

    # If scene changed, save and return to lobby
    if nt2 < 80 and nm2 > 120 and ct2 < 100:
        print(f">>> SECRET SHOP FOUND at x={x}! <<<")
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\found_ss_x{x}.png', img_after)
        break
    if nt2 < 120 or ct2 < 130:
        print(f"  -> Entered sub-menu at x={x}")
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\submenu_x{x}.png', img_after)
