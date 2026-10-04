import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MapperConfig:
    """单个字体映射的配置"""

    source_file: str
    fake_file: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapperConfig":
        return cls(
            source_file=data["source_file"],
            fake_file=data["fake_file"],
        )


@dataclass
class ConverterConfig:
    """一个转换器（ttc/ttf）的配置"""

    type: str
    mappers: List[MapperConfig]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConverterConfig":
        return cls(
            type=data["type"],
            mappers=[MapperConfig.from_dict(m) for m in data["mappers"]],
        )


@dataclass
class Config:
    """配置根对象"""

    converters: List[ConverterConfig]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        return cls(
            converters=[ConverterConfig.from_dict(c) for c in data["converters"]]
        )


def load_config(config_path: str) -> Config | None:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        Config对象
    """
    if not os.path.exists(config_path):
        logging.error(f"配置文件不存在: {config_path}")
        input("按任意键退出...")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Config.from_dict(data)
    except json.JSONDecodeError as e:
        logging.error(f"配置文件JSON格式错误: {e}")
        input("按任意键退出...")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"配置文件缺少必要字段: {e}")
        input("按任意键退出...")
        sys.exit(1)
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        input("按任意键退出...")
        sys.exit(1)


def resource_check(config: Config) -> bool:
    """
    检查配置文件中的资源是否齐全

    - source_file 必须存在
    - fake_file 必须存在

    Args:
        config: 配置对象

    Returns:
        资源是否全部合法
    """
    valid = True

    for converter in config.converters:
        for mapper in converter.mappers:
            label = os.path.basename(mapper.source_file)

            if not os.path.exists(mapper.source_file):
                logging.warning(f"[{label}] 源字体不存在: {mapper.source_file}")
                valid = False

            if not mapper.fake_file or not os.path.exists(mapper.fake_file):
                logging.warning(f"[{label}] 替换字体不存在: {mapper.fake_file}")
                valid = False

    return valid
