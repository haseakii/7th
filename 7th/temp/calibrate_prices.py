"""Calibrate price templates - user labels the prices on current screen"""
import sys, os, cv2, numpy as np

sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer, PRICE_X
from shop.price_reader import PriceReader, PRICE_X1, PRICE_X2, PRICE_Y_FRACTION

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()
img = device.screenshot()

rec = ItemRecognizer(device)
rows = rec._find_item_rows(img)

reader = PriceReader()

print("=" * 60)
print("价格模板校准")
print("=" * 60)
print(f"已加载模板: {len(reader.templates)} 种价格")
print(f"检测到 {len(rows)} 个物品行")
print()

for i, (y1, y2) in enumerate(rows):
    price_img = reader.extract_price_region(img, y1, y2)
    cv2.imwrite(f'D:\\software\\7th\\7th\\temp\\cal_price_{i}.png', price_img)

    # Try to recognize
    price, conf = reader.recognize(price_img)
    if price > 0:
        print(f"Slot {i}: 已识别价格 = {price} (置信度 {conf:.2f})")
    else:
        # Save unknown
        path = reader.save_unknown(price_img)
        print(f"Slot {i}: 新价格 (置信度 {conf:.2f}) -> {path}")

        # Ask user for the price
        try:
            user_input = input(f"  请输入 Slot {i} 的实际价格 (直接回车跳过): ").strip()
            if user_input.isdigit():
                actual_price = int(user_input)
                reader.save_template(price_img, actual_price)
                print(f"  -> 已保存模板: {actual_price}")
        except (EOFError, KeyboardInterrupt):
            print("  跳过")

print()
print(f"校准完成。模板总数: {len(reader.templates)} 种")
for price_val, templates in sorted(reader.templates.items()):
    print(f"  价格 {price_val}: {len(templates)} 个模板")
