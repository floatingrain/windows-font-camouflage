# Windows 字体转换工具

本项目是一个模块化的 Python 工具，用于将用户指定的字体（`fake_file`）伪装为 Windows 系统字体的元数据（`name` 表），生成与目标系统字体同名的 `target-fonts` 集合。生成的字体文件由用户自行安装，不再由本工具修改系统目录或注册表。

核心原理：提取原字体（`source_file`）的 `name` 表（元数据），合并到替换字体中，使 Windows 将替换字体识别为原字体。

## 目录结构

- `main.py`：程序入口（CLI）
- `config/`：配置加载逻辑及数据类定义
- `converter/`：字体转换核心逻辑（`base.py` 基类、`ttc.py` TTC 转换器、`ttf.py` TTF 转换器、`orchestrator.py` 编排器）
- `utils/`：通用工具（`font.py` 字体操作）
- `origin-fonts/`：待伪装的原字体（即配置中的 `source_file` 源）
- `fake-fonts/`：内置替换字体（MiSans 系列）
- `target-fonts/`：转换输出目录
- `config-example.json`：配置文件示例模板
- `yahei&segoe.json`：微软雅黑与 Segoe UI 转换配置参考
- `main.spec`：PyInstaller 打包配置文件

## 依赖

本项目使用 `uv` 管理依赖，需要 Python >= 3.14。

### 安装依赖

```bash
uv sync
```

## 使用方法

### 1. 准备字体文件

将原系统字体放入 `origin-fonts/`，将用于替换的字体放入 `fake-fonts/`。本项目已自带 `fake-fonts/MiSans` 系列作为示例替换字体。

### 2. 准备配置文件

你需要手动创建配置文件（参考以下示例），并在运行时通过 `-c` 参数指定路径：

- **通用模板**：仓库根目录下的 `config-example.json`
- **微软雅黑 & Segoe UI 转换**：参考仓库根目录下的 `yahei&segoe.json`

**配置说明**：

JSON 根路径必须包含一个 `converters` 数组。`converters` 数组下可包含两种字体转换器（由 `type` 字段指定 `ttc` 或 `ttf`）。每个 `converter` 下包含一个 `mappers` 数组，每个 mapper 由以下字段组成：

- `source_file`：原字体文件路径（提供 `name` 表的来源）
- `fake_file`：用于替换的字体文件路径（TTC 类型中，同一 converter 内只需在第一个 mapper 中指定即可）

### 3. 执行转换

```powershell
uv run python main.py convert -c my_config.json
```

或者，以管理员权限运行打包后产生的可执行文件：

```powershell
font-replace.exe convert -c my_config.json
```

转换结果将写入工作目录下的 `target-fonts/` 目录中，文件名与 `source_file` 同名。生成的文件由用户自行安装到系统中。

> 工具不再修改 `C:\Windows\Fonts`、注册表或文件所有权，因此**无需管理员权限**。

### 4. 注意事项

* **输出位置**：所有生成字体统一输出至 `target-fonts/`。
* **自动安装**：本工具**不再**自动将字体安装到 `C:\Windows\Fonts`，也**不再**修改注册表。请将 `target-fonts/` 中的文件手动复制到系统字体目录并完成安装。
* **临时目录**：每个 mapper 在独立的临时目录中处理，处理结束后自动清理。

## 开发

* `config/loader.py`：数据类层级 `Config` → `ConverterConfig` → `MapperConfig`（仅 `source_file`、`fake_file`），以及 `resource_check`。
* `converter/__init__.py`：导出 `BaseConverter`、`TTCConverter`、`TTFConverter`，并维护 `CONVERTER_REGISTRY` 映射（type 字符串 → 转换器类）。
* `converter/base.py`：定义 `BaseConverter` 抽象类。`run()` 为每个 mapper 创建临时工作目录并调用 `convert_mapper()`，子类实现具体的 name 表提取与合并。`BaseConverter` 提供 `_ensure_target_dir()` 辅助方法。
* `converter/orchestrator.py`：编排器，遍历配置中的 converters，按 type 在 `CONVERTER_REGISTRY` 中查找并执行。
* `converter/ttc.py`：TTC 转换器。流程：解包 `source_file` → 提取各 TTF 的 name 表 → 复制 `fake_file` 至对应文件名并合并 → 打包为 TTC 输出。
* `converter/ttf.py`：TTF 转换器。流程：提取 `source_file` 的 name 表 → 复制 `fake_file` → 合并 → 输出。
* `utils/font.py`：基于 fontTools 的字体操作（otc2otf/otf2otc 打包解包、ttx_extract_name/ttx_merge 名称表提取合并）。

本项目提供了 `main.spec` 文件，可以直接使用 PyInstaller 打包：

```bash
uv run pyinstaller main.spec --clean
```

打包完成后，可执行文件位于 `dist/` 目录下。
