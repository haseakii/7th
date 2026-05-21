"""
装饰器工具

从 Alas 原样复用的 cached_property 装饰器。
"""

from functools import wraps
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class cached_property(Generic[T]):
    """
    cached-property from https://github.com/pydanny/cached-property

    A property that is only computed once per instance and then replaces itself
    with an ordinary attribute. Deleting the attribute resets the property.
    """

    def __init__(self, func: Callable[..., T]):
        self.func = func

    def __get__(self, obj, cls) -> T:
        if obj is None:
            return self

        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def del_cached_property(obj, name):
    """
    Delete a cached property safely.

    Args:
        obj:
        name (str):
    """
    try:
        del obj.__dict__[name]
    except KeyError:
        pass


def has_cached_property(obj, name):
    """
    Check if a property is cached.

    Args:
        obj:
        name (str):
    """
    return name in obj.__dict__


def set_cached_property(obj, name, value):
    """
    Set a cached property.

    Args:
        obj:
        name (str):
        value:
    """
    obj.__dict__[name] = value
