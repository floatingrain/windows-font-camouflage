"""字体转换编排器

按 converter type 在 CONVERTER_REGISTRY 中查找对应类并执行。
新增转换器类型只需在 converter.__init__ 中注册即可。
"""

import logging

from config.loader import Config

from . import CONVERTER_REGISTRY


def run_convert(config: Config) -> None:
    """执行转换：按 converter type 实例化并运行各转换器"""
    for converter_config in config.converters:
        converter_type = converter_config.type.lower()
        converter_cls = CONVERTER_REGISTRY.get(converter_type)
        if converter_cls is None:
            logging.warning(
                f"未知的转换器类型: {converter_type}，"
                f"已知类型: {sorted(CONVERTER_REGISTRY.keys())}，跳过"
            )
            continue
        converter_cls(converter_config).run()
