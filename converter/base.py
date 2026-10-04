import logging
import os
import tempfile
from abc import ABC, abstractmethod

from config.loader import ConverterConfig, MapperConfig


class BaseConverter(ABC):
    """转换器基类

    流水线：为每个 mapper 创建一个临时工作目录，子类在其中处理
    source_file（提取 name 表），合并到 fake_file，输出到 target-fonts。
    不再涉及系统目录、注册表或文件所有权。
    """

    TARGET_DIR = "target-fonts"

    def __init__(self, config: ConverterConfig):
        self.config = config
        self.mappers = config.mappers

    def run(self):
        """执行转换流程"""
        logging.info(f"开始处理转换器: {self.config.type}")
        for mapper in self.mappers:
            with tempfile.TemporaryDirectory() as workspace:
                self.convert_mapper(mapper, workspace)
        logging.info(f"转换器 {self.config.type} 处理完成")

    @abstractmethod
    def convert_mapper(self, mapper: MapperConfig, workspace: str):
        """处理单个 mapper

        Args:
            mapper: 单个字体映射配置
            workspace: 临时工作目录路径（已存在）
        """
        pass

    def _ensure_target_dir(self) -> str:
        """确保 target-fonts 目录存在并返回其绝对路径"""
        target_dir = os.path.join(os.getcwd(), self.TARGET_DIR)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        return target_dir
