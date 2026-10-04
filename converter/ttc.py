import glob
import logging
import os
import shutil

from config.loader import MapperConfig
from utils.font import otc2otf, otf2otc, ttx_extract_name, ttx_merge

from .base import BaseConverter


class TTCConverter(BaseConverter):
    """处理TTC文件的转换器

    流程：
    1. 将 source_file（TTC）解包到 workspace
    2. 为每个 TTF 提取 name 表（ttx）
    3. 将 fake_file 复制为对应 TTF 文件名，合并 ttx 生成新 TTF
    4. 收集所有新 TTF 打包为 TTC，输出到 target-fonts
    """

    def convert_mapper(self, mapper: MapperConfig, workspace: str):
        source_label = os.path.basename(mapper.source_file)

        # 1. 解包 TTC
        logging.info(f"正在解包 {mapper.source_file} ...")
        otc2otf(mapper.source_file, workspace)

        # 2. 提取每个 TTF 的 name 表
        extracted_fonts = sorted(glob.glob(os.path.join(workspace, "*.ttf")))
        if not extracted_fonts:
            logging.warning(f"未从 {source_label} 提取到任何 TTF 文件，跳过")
            return

        for font_file in extracted_fonts:
            logging.info(f"正在提取名称表: {os.path.basename(font_file)}")
            ttx_extract_name(font_file, workspace)

        # 3. 合并 fake_file 与各 ttx
        ttx_files = sorted(glob.glob(os.path.join(workspace, "*.ttx")))
        if not ttx_files:
            logging.warning(f"未找到名称表文件，跳过: {source_label}")
            return

        generated_ttfs = []
        for ttx_file in ttx_files:
            base_name = os.path.basename(ttx_file).replace(".ttx", ".ttf")
            output_ttf = os.path.join(workspace, base_name)

            logging.info(f"正在生成: {base_name}")
            shutil.copy2(mapper.fake_file, output_ttf)
            ttx_merge(output_ttf, ttx_file, workspace)
            generated_ttfs.append(output_ttf)

        # 4. 打包为 TTC 并输出
        target_dir = self._ensure_target_dir()
        output_file = os.path.join(target_dir, os.path.basename(mapper.source_file))
        logging.info(f"正在合并生成 TTC: {output_file}")
        otf2otc(generated_ttfs, output_file)
