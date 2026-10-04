import logging
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection


def otc2otf(input_file: str, output_dir: str = ".") -> None:
    """
    将TTC/OTC文件解包为TTF/OTF

    Args:
        input_file: 输入文件路径
        output_dir: 输出目录
    """
    if not os.path.exists(input_file):
        logging.error(f"文件不存在: {input_file}")
        input("按任意键退出...")
        sys.exit(1)

    try:
        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        collection = TTCollection(input_file)
        try:
            logging.info(f"正在解包 {input_file}, 包含 {len(collection.fonts)} 个字体")

            for i, font in enumerate(collection.fonts):
                # 尝试获取 PostScript 名称 (NameID 6)
                ps_name = ""
                try:
                    # getDebugName 可能返回 None
                    ps_name = font["name"].getDebugName(6)
                except Exception:
                    pass

                if not ps_name:
                    ps_name = f"font_{i}"

                # 清理文件名，只保留安全字符
                safe_name = "".join(
                    [c for c in ps_name if c.isalnum() or c in ("-", "_", ".")]
                )

                # 使用索引前缀保持顺序 (例如 00_MicrosoftYaHei.ttf)
                filename = f"{i:02d}_{safe_name}.ttf"
                output_path = os.path.join(output_dir, filename)

                font.save(output_path)
                font.close()
                logging.info(f"已解包: {output_path}")
        finally:
            collection.close()

    except Exception as e:
        logging.error(f"otc2otf 执行失败: {e}")
        input("按任意键退出...")
        sys.exit(1)


def otf2otc(input_files: list[str], output_file: str) -> None:
    """
    将多个TTF/OTF文件合并为TTC/OTC

    Args:
        input_files: 输入文件路径列表
        output_file: 输出文件路径
    """
    if not input_files:
        return

    try:
        collection = TTCollection()
        try:
            for f in input_files:
                logging.info(f"正在读取: {f}")
                font = TTFont(f)
                collection.fonts.append(font)

            # 确保输出目录存在
            output_dir = os.path.dirname(os.path.abspath(output_file))
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            collection.save(output_file)
            logging.info(f"已生成 TTC: {output_file}")
        finally:
            collection.close()
    except Exception as e:
        logging.error(f"otf2otc 执行失败: {e}")
        input("按任意键退出...")
        sys.exit(1)


def ttx_extract_name(input_file: str, output_dir: str = ".") -> None:
    """
    使用ttx提取name表

    Args:
        input_file: 输入字体文件
        output_dir: 输出目录
    """
    try:
        font = TTFont(input_file)
        try:
            basename = os.path.basename(input_file)
            # 保持与 ttx 命令行工具类似的行为，生成 .ttx 文件
            filename = os.path.splitext(basename)[0] + ".ttx"
            output_path = os.path.join(output_dir, filename)

            # 仅导出 name 表
            font.saveXML(output_path, tables=["name"])
            logging.info(f"已提取名称表: {output_path}")
        finally:
            font.close()
    except Exception as e:
        logging.error(f"ttx 提取name表失败: {e}")
        input("按任意键退出...")
        sys.exit(1)


def ttx_merge(base_font: str, ttx_file: str, output_dir: str = ".") -> None:
    """
    使用ttx合并/修改字体

    Args:
        base_font: 基础字体文件 (将被修改)
        ttx_file: 包含修改信息的ttx文件
        output_dir: 输出目录
    """
    try:
        if not os.path.exists(ttx_file):
            raise FileNotFoundError(f"TTX文件不存在: {ttx_file}")

        if os.path.getsize(ttx_file) == 0:
            raise ValueError(f"TTX文件为空: {ttx_file}")

        font = TTFont(base_font)
        try:
            # 导入 XML (merge)
            # 显式使用二进制模式打开，避免编码问题，让 fontTools/expat 自动处理 XML 声明中的编码
            with open(ttx_file, "rb") as f:
                font.importXML(f)

            # 确定输出路径
            basename = os.path.basename(base_font)
            output_path = os.path.join(output_dir, basename)

            # 确保输出目录存在
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            font.save(output_path)
            logging.info(f"已合并字体: {output_path}")
        finally:
            font.close()
    except Exception as e:
        # 尝试读取文件头以便诊断
        header = "无法读取"
        try:
            with open(ttx_file, "rb") as f:
                header = f.read(50)
        except Exception:
            pass
        logging.error(f"ttx 合并失败: {e} (文件头: {header})")
        input("按任意键退出...")
        sys.exit(1)
