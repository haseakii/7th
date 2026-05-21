"""验证刷新按钮和确认弹窗的检测（不实际点击确认，只检测）"""
import sys, os, cv2, numpy as np
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()

# 刷新按钮区域 (80, 648, 320, 695)
refresh = img[648:695, 80:320]
cv2.imwrite('D:\\software\\7th\\7th\\temp\\refresh_btn_current.png', refresh)

# 分析刷新按钮颜色
hsv = cv2.cvtColor(refresh, cv2.COLOR_BGR2HSV)
bright = refresh[hsv[:,:,2] > 40]
if len(bright) > 0:
    b, g, r = float(bright[:,0].mean()), float(bright[:,1].mean()), float(bright[:,2].mean())
    print(f"Refresh button BGR: ({b:.0f}, {g:.0f}, {r:.0f})")

# 打印整个底栏的亮度
print("\nBottom bar (y=648-695) brightness per x segment:")
for x in range(0, 1280, 40):
    seg = img[648:695, x:min(x+40, 1280)]
    gray = float(cv2.cvtColor(seg, cv2.COLOR_BGR2GRAY).mean())
    bgr = (float(seg[:,:,0].mean()), float(seg[:,:,1].mean()), float(seg[:,:,2].mean()))
    print(f"  x={x:4d}: gray={gray:.0f}, BGR=({bgr[0]:.0f},{bgr[1]:.0f},{bgr[2]:.0f})")

# 也检查上方确认弹窗区域
confirm_y_range = (440, 520)
confirm = img[confirm_y_range[0]:confirm_y_range[1], 300:1000]
confirm_gray = float(cv2.cvtColor(confirm, cv2.COLOR_BGR2GRAY).mean())
confirm_bgr = (float(confirm[:,:,0].mean()), float(confirm[:,:,1].mean()), float(confirm[:,:,2].mean()))
print(f"\nConfirm area (300-1000, {confirm_y_range[0]}-{confirm_y_range[1]}): gray={confirm_gray:.0f}, BGR=({confirm_bgr[0]:.0f},{confirm_bgr[1]:.0f},{confirm_bgr[2]:.0f})")

print("\nDone!")
