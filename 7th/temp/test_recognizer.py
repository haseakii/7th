"""快速测试更新后的 recognizer"""
import sys, os
sys.path.insert(0, 'D:\\software\\7th\\7th')
from config_manager import ConfigManager
from module.device.device import DeviceController
from shop.recognizer import ItemRecognizer

config = ConfigManager('D:\\software\\7th\\7th\\config.yaml')
config.load()
cfg = config.get()

device = DeviceController(cfg.device)
device.connect()

rec = ItemRecognizer(device)
items = rec.recognize_visible_items()

print(f"\n=== 识别结果: {len(items)} 个物品 ===")
for item in items:
    print(f"  Slot {item.slot_index}: type={item.item_type}, price={item.price}, confidence={item.confidence:.2f}, pos={item.position}")
