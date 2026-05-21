"""
OCR RPC 客户端（本地模式）

本项目仅使用本地 cnocr 模型，此文件保留以兼容 OCR 模块结构。
"""

from module.logger import logger


class ModelProxy:
    """本地 OCR 模型代理，直接从 models.py 加载模型。"""

    client = None
    online = False

    @classmethod
    def init(cls, address="127.0.0.1:22268"):
        cls.online = False
        logger.info("OCR running in local mode")

    @classmethod
    def close(cls):
        pass

    def __init__(self, lang):
        self.lang = lang

    def atomic_ocr_for_single_lines(self, img_list, cand_alphabet=None):
        from module.ocr.models import OCR_MODEL
        return OCR_MODEL.__getattribute__(self.lang).atomic_ocr_for_single_lines(
            img_list, cand_alphabet=cand_alphabet
        )


class ModelProxyFactory:
    def __init__(self, address=None):
        pass

    def __getattribute__(self, name):
        if name.startswith('_') or name in ('close',):
            return super().__getattribute__(name)
        if ModelProxy.client is None:
            ModelProxy.init()
        return ModelProxy(lang=name)

    def close(self):
        ModelProxy.close()
