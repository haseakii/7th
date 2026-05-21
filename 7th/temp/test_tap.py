"""
验证 ADB tap 是否正常工作
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

def tap(x, y):
    print(f"  Tapping ({x}, {y})...")
    result = subprocess.run(
        [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
        capture_output=True, timeout=10, text=True
    )
    if result.stderr:
        print(f"  stderr: {result.stderr}")
    print(f"  stdout: {result.stdout}")

def screenshot_check(msg=""):
    img = device.screenshot()
    h, w = img.shape[:2]
    nav_top = float(cv2.cvtColor(img[200:260, 80:160], cv2.COLOR_BGR2GRAY).mean())
    content = float(cv2.cvtColor(img[150:520, 250:800], cv2.COLOR_BGR2GRAY).mean())
    print(f"  {msg}: {w}x{h}, nav_top={nav_top:.0f}, content={content:.0f}")
    return img

# Current state
img = screenshot_check("Current")

# Try tapping in the top-right (gear/settings icon area)
print("\nTest 1: Top-right corner (settings?)")
tap(1240, 30)
time.sleep(1.5)
screenshot_check("After tap top-right")

# Press BACK to return
subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
              capture_output=True, timeout=10)
time.sleep(1.0)

# Try tapping the center of the screen (character area)
print("\nTest 2: Center of screen")
tap(640, 360)
time.sleep(1.5)
screenshot_check("After tap center")

# BACK again
subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
              capture_output=True, timeout=10)
time.sleep(1.0)

# Try a different approach - check if there's a resolution mismatch
print("\nTest 3: Check actual display size via ADB")
result = subprocess.run(
    [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "wm", "size"],
    capture_output=True, timeout=10, text=True
)
print(f"  wm size: {result.stdout.strip()}")

result = subprocess.run(
    [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "dumpsys", "display"],
    capture_output=True, timeout=10, text=True
)
# Just get the display info lines
for line in result.stdout.split('\n'):
    if 'mDisplayHeight' in line or 'mDisplayWidth' in line or 'displayId' in line.lower():
        print(f"  {line.strip()}")

# Save current screenshot for reference
cv2.imwrite('D:\\software\\7th\\7th\\temp\\after_tests.png', img)
print("\nDone")
