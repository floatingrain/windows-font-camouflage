import glob
import logging
import os
import shutil

from config.loader import MapperConfig
from utils.font import ttx_extract_name, ttx_merge

from .base import BaseConverter


class TTFConverter(BaseConverter):
    """处理TTF文件的转换器

    流程：
    1. 提取 source_file 的 name 表
    2. 将 fake_file 复制到 workspace 作为基础字体
    3. 合并 name 表到基础字体
    4. 输出到 target-fonts
    """

    def convert_mapper(self, mapper: MapperConfig, workspace: str):
        source_label = os.path.basename(mapper.source_file)

        # 1. 提取 source_file 的名称表
        logging.info(f"正在提取名称表: {source_label}")
        ttx_extract_name(mapper.source_file, workspace)

        # 2. 定位对应的 ttx
        ttx_filename = os.path.splitext(source_label)[0] + ".ttx"
        ttx_file = os.path.join(workspace, ttx_filename)
        if not os.path.exists(ttx_file):
            candidates = glob.glob(os.path.join(workspace, "*.ttx"))
            if len(candidates) == 1:
                ttx_file = candidates[0]
            else:
                logging.warning(f"未找到名称表文件 {ttx_filename}，跳过: {source_label}")
                return

        # 3. 合并 fake_file 与 ttx
        target_basename = os.path.basename(mapper.source_file)
        output_ttf = os.path.join(workspace, target_basename)
        logging.info(f"正在生成: {target_basename}")
        shutil.copy2(mapper.fake_file, output_ttf)
        ttx_merge(output_ttf, ttx_file, workspace)

        # 4. 输出到 target-fonts
        target_dir = self._ensure_target_dir()
        output_file = os.path.join(target_dir, target_basename)
        shutil.copy2(output_ttf, output_file)
