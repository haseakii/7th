"""
从大厅状态测试 - 每次都确认在 lobby 再点
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
    nt = float(cv2.cvtColor(img[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
    nm = float(cv2.cvtColor(img[300:480, 80:160], cv2.COLOR_BGR2GRAY).mean())
    ct = float(cv2.cvtColor(img[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
    return nt, nm, ct, img

def tap(x, y):
    subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)

def ensure_lobby():
    """Press BACK until we detect lobby"""
    for _ in range(5):
        nt, nm, ct, img = check_scene()
        if nt > 100 and ct > 100:
            return True  # Already in lobby
        subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
                      capture_output=True, timeout=10)
        time.sleep(1.0)
    nt, nm, ct, img = check_scene()
    return nt > 100 and ct > 100

# First, ensure we're in lobby
print("Ensuring lobby...")
if not ensure_lobby():
    print("Could not reach lobby!")
    sys.exit(1)
print("In lobby!")

# Test points - based on E7 UI knowledge
# In E7 lobby, typical interactive areas include:
# - Buildings in the game world
# - Event icons
# - Bottom navigation
# - Sidebar

test_points = [
    # Game world buildings (might be secret shop)
    ("World area - left buildings", 300, 400, 40, 40),
    ("World area - center building", 550, 380, 40, 40),
    ("World area - right building", 850, 350, 40, 40),
    ("World area - far right", 1000, 300, 40, 40),
    # Where character might be
    ("Character area", 640, 450, 40, 40),
    # Bottom of game area (floor)
    ("Floor left", 300, 600, 40, 40),
    ("Floor center", 640, 600, 40, 40),
    ("Floor right", 900, 600, 40, 40),
    # Event/seasonal icons (typically stacked on the right)
    ("Right side events", 1150, 250, 40, 40),
    ("Right side events 2", 1150, 400, 40, 40),
    # Bottom nav buttons (more precise coords)
    ("Bottom btn area left", 160, 685, 40, 40),
    ("Bottom btn area right", 1120, 685, 40, 40),
]

for name, cx, cy, rw, rh in test_points:
    print(f"\n--- {name} ({cx}, {cy}) ---")

    # Ensure lobby
    if not ensure_lobby():
        print("Lost lobby state, skipping")
        continue

    nt, nm, ct, img = check_scene()
    print(f"Before: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    tap(cx, cy)
    time.sleep(2.0)

    nt, nm, ct, img = check_scene()
    print(f"After:  nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    if nt < 80 and nm > 120 and ct < 100:
        print(">>> SECRET SHOP FOUND! <<<")
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\secret_shop_cx{cx}_cy{cy}.png', img)
        break
    elif nt < 120 or ct < 130:
        print("-> Entered some sub-menu")
        cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\entered_{name[:20].strip()}.png', img)
    else:
        print("-> No change (still in lobby or no reaction)")
