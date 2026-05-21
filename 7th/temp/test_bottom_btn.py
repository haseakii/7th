"""
测试底栏绿色按钮 - 一次只测一个
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
    print("Failed to connect")
    sys.exit(1)

def check_scene(img=None):
    if img is None:
        img = device.screenshot()
    nav_top = float(cv2.cvtColor(img[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
    nav_mid = float(cv2.cvtColor(img[300:480, 80:160], cv2.COLOR_BGR2GRAY).mean())
    content = float(cv2.cvtColor(img[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
    return nav_top, nav_mid, content

def tap(x, y):
    subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)

# Verify lobby
nt, nm, ct = check_scene()
print(f"Current: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

# Test: bottom bar buttons
test_points = [
    ("Bottom bar btn at x=290", 290, 685),
    ("Bottom bar btn at x=740", 740, 685),
    ("Bottom bar btn at x=450", 450, 685),
    ("Bottom bar btn at x=580", 580, 685),
]

for name, x, y in test_points:
    print(f"\n--- {name} ({x}, {y}) ---")
    nt, nm, ct = check_scene()
    print(f"Before: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    tap(x, y)
    time.sleep(2.0)

    nt, nm, ct = check_scene()
    print(f"After:  nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    if nt < 80 and nm > 120 and ct < 100:
        print(">>> FOUND SECRET SHOP! <<<")
        img = device.screenshot()
        cv2.imwrite('D:\\software\\7th\\7th\\temp\\secret_shop_found.png', img)
        break
    elif nt < 100 or ct < 100:
        print("Entered some sub-menu, saving screenshot")
        img = device.screenshot()
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\submenu_x{x}_y{y}.png', img)
        # Return to lobby with BACK
        for _ in range(2):
            subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
                          capture_output=True, timeout=10)
            time.sleep(1.0)
        nt, nm, ct = check_scene()
        print(f"After BACK: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")
    else:
        print("No change (still in lobby)")
