#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys

from config.loader import load_config, resource_check
from converter.orchestrator import run_convert


class _ColorFormatter(logging.Formatter):
    """带 ANSI 颜色的日志格式化器"""

    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[94m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[91m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        color = self.COLORS.get(record.levelno, self.RESET)
        return f"{color}{msg}{self.RESET}"


_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(_ColorFormatter("%(levelname)s: %(message)s"))
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.addHandler(_handler)
_root.propagate = False


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description="Windows 字体转换工具：将 fake_file 按 source_file 的 name 表合并，输出到 target-fonts 目录"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # convert 子命令
    convert_parser = subparsers.add_parser(
        "convert", help="执行字体转换，输出到 target-fonts 目录"
    )
    convert_parser.add_argument(
        "-c", "--config", required=True, help="配置文件路径"
    )
    convert_parser.add_argument(
        "--ignore-check",
        action="store_true",
        help="跳过前置资源检查（resource_check），直接执行转换",
    )

    args = parser.parse_args()

    # 未指定子命令时显示帮助
    if not args.command:
        parser.print_help()
        return

    # 1. 加载配置
    config_path = os.path.abspath(args.config)
    logging.info(f"正在加载配置: {config_path}")
    config = load_config(config_path)

    if config is None:
        logging.error("配置加载失败，无法继续执行。")
        input("按任意键退出...")
        sys.exit(1)

    # 2. 进行前置检查
    if args.ignore_check:
        logging.warning("已启用 --ignore-check，跳过前置资源检查。")
    else:
        logging.info("正在检查配置资源...")
        if not resource_check(config):
            logging.error("前置资源配置检查未通过，请修正配置后重试。")
            input("按任意键退出...")
            sys.exit(1)

    # 3. 执行转换
    if args.command == "convert":
        run_convert(config)

    logging.info("字体转换完成，结果位于 target-fonts 目录。")


if __name__ == "__main__":
    main()
