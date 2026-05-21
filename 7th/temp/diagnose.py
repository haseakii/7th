"""
诊断脚本：连接模拟器，截图，分析大厅布局
找到秘密商店入口按钮的正确坐标
"""
import sys
sys.path.insert(0, 'D:\\software\\7th\\7th')

import os
import cv2
import numpy as np
from config_manager import ConfigManager
from module.device.device import DeviceController

temp_dir = 'D:\\software\\7th\\7th\\temp'
os.makedirs(temp_dir, exist_ok=True)

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()
print('Device serial:', cfg.device.serial)

device = DeviceController(cfg.device)
if device.connect():
    print('Connected, taking screenshot...')
    img = device.screenshot()
    print('Image shape:', img.shape)

    save_path = os.path.join(temp_dir, 'lobby_screenshot.png')
    cv2.imwrite(save_path, img)
    print(f'Saved to {save_path}')
    print(f'File exists: {os.path.isfile(save_path)}')
    print(f'File size: {os.path.getsize(save_path)} bytes')

    # Analyze the left nav bar area (x=40 to x=220)
    nav = img[:, 40:220]
    nav_gray = cv2.cvtColor(nav, cv2.COLOR_BGR2GRAY)
    print()
    print('=== Left Nav Bar Analysis (x=40-220) ===')
    for y in range(0, img.shape[0], 20):
        strip = nav_gray[y:y+20, :]
        brightness = float(strip.mean())
        print(f'  y={y:3d}-{y+20:3d}: brightness={brightness:.0f}')

    # Analyze nav bar color channels to find buttons
    print()
    print('=== Left Nav Bar Color Analysis (x=40-200) ===')
    nav_bgr = img[:, 40:200, :]
    for y in range(0, img.shape[0], 20):
        strip = nav_bgr[y:y+20, :]
        b_mean = float(strip[:, 0].mean())
        g_mean = float(strip[:, 1].mean())
        r_mean = float(strip[:, 2].mean())
        print(f'  y={y:3d}-{y+20:3d}: B={b_mean:.0f} G={g_mean:.0f} R={r_mean:.0f}')
else:
    print('Connection failed')
