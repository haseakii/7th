"""
快速检查当前游戏状态
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

img = device.screenshot()
h, w = img.shape[:2]
print(f"Screenshot: {w}x{h}")

nav_top = img[200:260, 80:160]
nav_top_bright = float(cv2.cvtColor(nav_top, cv2.COLOR_BGR2GRAY).mean())
nav_mid = img[300:480, 80:160]
nav_mid_bright = float(cv2.cvtColor(nav_mid, cv2.COLOR_BGR2GRAY).mean())
content = img[150:520, 250:800]
content_bright = float(cv2.cvtColor(content, cv2.COLOR_BGR2GRAY).mean())
print(f"nav_top={nav_top_bright:.0f}, nav_mid={nav_mid_bright:.0f}, content={content_bright:.0f}")

if nav_top_bright < 80 and nav_mid_bright > 120 and content_bright < 100:
    print("ALREADY IN SECRET SHOP!")
elif nav_top_bright > 100 and content_bright > 100:
    print("In LOBBY")
else:
    print(f"Unknown scene: {nav_top_bright:.0f}/{nav_mid_bright:.0f}/{content_bright:.0f}")

cv2.imwrite('D:\\software\\7th\\7th\\temp\\current_state.png', img)
print("Saved current_state.png")
