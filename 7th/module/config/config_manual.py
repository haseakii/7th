"""
ManualConfig — 硬编码默认配置

放置 Python 级别的静态默认值，不写入 JSON 配置文件。
"""


class ManualConfig:
    """手动配置项，作为 E7Config MRO 的一部分。"""

    # 资源文件夹
    ASSETS_FOLDER = './assets'
    ASSETS_RESOLUTION = (1280, 720)

    # 设备
    BUTTON_OFFSET = 30
    WAIT_BEFORE_SAVING_SCREEN_SHOT = 1

    # 截图与控制
    SCREENSHOT_HANDLER = ['ADB', 'uiautomator2']
    CONTROL_HANDLER = ['ADB', 'uiautomator2']
    OCR_HANDLER = ['rapidocr', 'easyocr', 'paddleocr']

    # 任务调度优先级
    SCHEDULER_PRIORITY = """
    SecretShop
    """
