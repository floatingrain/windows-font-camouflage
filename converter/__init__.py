"""字体转换器

提供 TTC/TTF 两种转换器类型，以及统一的编排器入口。
"""

from .base import BaseConverter
from .ttc import TTCConverter
from .ttf import TTFConverter

CONVERTER_REGISTRY = {
    "ttc": TTCConverter,
    "ttf": TTFConverter,
}

__all__ = [
    "BaseConverter",
    "TTCConverter",
    "TTFConverter",
    "CONVERTER_REGISTRY",
]
