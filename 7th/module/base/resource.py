"""
Resource 资源管理基类

Button 和 Template 的基类，提供资源生命周期管理。
"""

from module.base.decorator import cached_property, del_cached_property


class Resource:
    instances = {}
    cached = []

    def resource_add(self, key):
        Resource.instances[key] = self

    def resource_release(self):
        for cache in self.cached:
            del_cached_property(self, cache)

    @classmethod
    def is_loaded(cls, obj):
        if hasattr(obj, '_image') and obj._image is None:
            return False
        elif hasattr(obj, 'image') and obj.image is None:
            return False
        return True

    @classmethod
    def resource_show(cls):
        from log import logger
        logger.hr('Show resource')
        for key, obj in cls.instances.items():
            if cls.is_loaded(obj):
                continue
            logger.info(f'{obj}: {key}')

    @staticmethod
    def parse_property(data, s=None):
        if isinstance(data, dict):
            return data.get(s, list(data.values())[0])
        return data
