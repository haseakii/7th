"""
测试底栏按钮和游戏世界中的入口点
"""
import sys
sys.path.insert(0, 'D:\\software\\7th\\7th')

import os
import time
import cv2
import numpy as np
import subprocess

from config_manager import ConfigManager
from module.device.device import DeviceController, ADB_EXECUTABLE

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
if not device.connect():
    print("Connection failed")
    sys.exit(1)

def check_scene(img):
    """Check if we're in lobby or secret shop"""
    nav_top = img[200:260, 80:160]
    nav_top_bright = float(cv2.cvtColor(nav_top, cv2.COLOR_BGR2GRAY).mean())
    nav_mid = img[300:480, 80:160]
    nav_mid_bright = float(cv2.cvtColor(nav_mid, cv2.COLOR_BGR2GRAY).mean())
    content = img[150:520, 250:800]
    content_bright = float(cv2.cvtColor(content, cv2.COLOR_BGR2GRAY).mean())
    return nav_top_bright, nav_mid_bright, content_bright

def click(x, y):
    subprocess.run(
        [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
        capture_output=True, timeout=10
    )

def save_screenshot(name):
    img = device.screenshot()
    cv2.imwrite(os.path.join('D:\\software\\7th\\7th\\temp', name), img)
    return img

# Take baseline
img = save_screenshot("baseline.png")
nt, nm, ct = check_scene(img)
print(f"Baseline: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

# Candidates to test: bottom bar buttons and other UI elements
# Based on analysis:
# - Green button clusters in bottom bar at x=260-320 and x=720-760
# - High saturation areas in main game area
candidates = [
    # Bottom bar - green buttons
    ("Bottom bar green btn 1", 290, 690, 40, 60),
    ("Bottom bar green btn 2", 740, 690, 40, 60),
    ("Bottom bar green btn 3", 450, 690, 40, 60),
    ("Bottom bar green btn 4", 580, 690, 40, 60),
    ("Bottom bar left", 130, 690, 40, 60),
    # Main area - possible buildings/icons (x=200-900, y=200-500)
    ("Main area center", 640, 360, 40, 40),
    ("Main area left-center", 450, 400, 40, 40),
    ("Main area right-center", 850, 350, 40, 40),
    ("Main area top-center", 640, 200, 40, 40),
]

for name, cx, cy, rw, rh in candidates:
    print(f"\n--- Trying {name} at ({cx}, {cy}) ---")

    # Return to lobby first (press BACK a few times)
    for _ in range(3):
        click(100, 100)  # Click somewhere safe first
        time.sleep(0.5)

    # Take fresh screenshot and verify we're in lobby
    img = save_screenshot(f"before_{name.replace(' ', '_')}.png")
    nt, nm, ct = check_scene(img)
    print(f"  Before: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    if nt < 80 and nm > 120 and ct < 100:
        print("  Already in secret shop! Skipping.")
        continue
    if nt < 100:
        print("  Not in lobby (nav_top too dark), pressing BACK...")
        click(500, 500)  # click safe
        time.sleep(1)
        subprocess.run(
            [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
            capture_output=True, timeout=10
        )
        time.sleep(2)
        img = save_screenshot(f"after_back_{name.replace(' ', '_')}.png")
        nt, nm, ct = check_scene(img)
        print(f"  After BACK: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    # Click the candidate
    print(f"  Clicking at ({cx}, {cy})")
    click(cx, cy)

    # Wait for transition
    time.sleep(2.5)

    # Check scene
    img = device.screenshot()
    nt, nm, ct = check_scene(img)
    print(f"  After: nav_top={nt:.0f}, nav_mid={nm:.0f}, content={ct:.0f}")

    # Save result
    cv2.imwrite(os.path.join('D:\\software\\7th\\7th\\temp', f'result_{name.replace(" ", "_")}.png'), img)

    # Check secret shop signature
    if nt < 80 and nm > 120 and ct < 100:
        print(f"  *** FOUND! Secret shop entrance at {name} (cx={cx}, cy={cy}) ***")
        cv2.imwrite(os.path.join('D:\\software\\7th\\7th\\temp', 'secret_shop_found.png'), img)
        break

    # Check if we entered a sub-menu (nav top is somewhat darker)
    if nt < 120 and nt >= 80:
        print("  -> Entered a sub-menu (nav top moderately dark)")
        cv2.imwrite(os.path.join('D:\\software\\7th\\7th\\temp', f'submenu_{name.replace(" ", "_")}.png'), img)
        # Press BACK to return
        print("  Pressing BACK...")
        subprocess.run(
            [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
            capture_output=True, timeout=10
        )
        time.sleep(2.0)
    elif nt < 100:
        print("  -> Entered a dark sub-menu (nav top dark)")
        # Press BACK multiple times
        for _ in range(2):
            subprocess.run(
                [ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
                capture_output=True, timeout=10
            )
            time.sleep(1.0)
