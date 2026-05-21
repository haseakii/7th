"""测试刷新按钮点击和确认弹窗检测（不确认，按BACK取消）"""
import sys, os, cv2, numpy as np, subprocess, time
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController, ADB_EXECUTABLE

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()

def tap(x, y):
    subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "tap", str(x), str(y)],
                   capture_output=True, timeout=10)

def go_back():
    subprocess.run([ADB_EXECUTABLE, "-s", cfg.device.serial, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=10)
    time.sleep(1.0)

# 1. 截图并保存当前状态
img_before = device.screenshot()
cv2.imwrite('D:\\software\\7th\\7th\\temp\\before_refresh.png', img_before)

# 2. 验证刷新按钮可见
from module.base.button import Button
REFRESH_BTN = Button(
    area=(80, 648, 320, 695),
    color=(60, 94, 59),
    button=(80, 648, 320, 695),
    name="REFRESH_BTN",
)

if REFRESH_BTN.appear_on(img_before, threshold=50):
    print("Refresh button detected [OK]")
else:
    print("Refresh button NOT detected [FAIL]")
    # Check actual color
    refresh_area = img_before[648:695, 80:320]
    hsv = cv2.cvtColor(refresh_area, cv2.COLOR_BGR2HSV)
    bright = refresh_area[hsv[:,:,2] > 40]
    if len(bright) > 0:
        print(f"  Actual BGR: ({float(bright[:,0].mean()):.0f}, {float(bright[:,1].mean()):.0f}, {float(bright[:,2].mean()):.0f})")

# 3. 点击刷新按钮
print("\nClicking refresh button...")
# Center of the button area
tap(200, 670)
time.sleep(2.0)

# 4. 截图检测确认弹窗
img_confirm = device.screenshot()
cv2.imwrite('D:\\software\\7th\\7th\\temp\\after_refresh_click.png', img_confirm)

# 检查确认弹窗
REFRESH_CONFIRM_BTN = Button(
    area=(300, 488, 1000, 511),
    color=(87, 48, 17),
    button=(300, 488, 1000, 511),
    name="REFRESH_CONFIRM",
)

if REFRESH_CONFIRM_BTN.appear_on(img_confirm, threshold=40):
    print("Refresh confirmation dialog detected [OK]")

    # 检查确认按钮区域的实际颜色
    confirm_area = img_confirm[488:511, 300:1000]
    cv2.imwrite('D:\\software\\7th\\7th\\temp\\confirm_area.png', confirm_area)
    hsv = cv2.cvtColor(confirm_area, cv2.COLOR_BGR2HSV)
    bright = confirm_area[hsv[:,:,2] > 40]
    if len(bright) > 0:
        print(f"  Confirm area BGR: ({float(bright[:,0].mean()):.0f}, {float(bright[:,1].mean()):.0f}, {float(bright[:,2].mean()):.0f})")

    # 打印确认弹窗区域的亮度信息
    for y_off in range(0, img_confirm.shape[0], 60):
        seg = img_confirm[y_off:min(y_off+30, img_confirm.shape[0]), 200:1100]
        if seg.size == 0:
            continue
        gray = float(cv2.cvtColor(seg, cv2.COLOR_BGR2GRAY).mean())
        if gray > 30:
            print(f"  Row y={y_off}: gray={gray:.0f}")

    # 5. 按BACK取消
    print("\nPressing BACK to cancel refresh...")
    go_back()
    time.sleep(1.5)

    img_after_back = device.screenshot()
    cv2.imwrite('D:\\software\\7th\\7th\\temp\\after_cancel.png', img_after_back)

    # 验证回到秘密商店
    from shop.navigator import ShopNavigator
    nav = ShopNavigator(device)
    scene = nav.detect_current_scene()
    print(f"Scene after cancel: {scene}")
else:
    print("No refresh confirmation dialog detected")

    # 打印整个屏幕的亮度分布看看发生了什么
    print("\nScreen analysis after click:")
    for y_off in range(0, img_confirm.shape[0], 100):
        seg = img_confirm[y_off:min(y_off+60, img_confirm.shape[0]), 200:1100]
        if seg.size == 0:
            continue
        gray = float(cv2.cvtColor(seg, cv2.COLOR_BGR2GRAY).mean())
        if gray > 40:
            print(f"  y={y_off}: gray={gray:.0f}")

    # 尝试返回
    go_back()

print("\nDone!")
