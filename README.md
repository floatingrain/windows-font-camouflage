# Windows 字体转换工具

本项目是一个模块化的 Python 工具，用于将用户指定的字体（`fake_file`）伪装为 Windows 系统字体的元数据（`name` 表），生成与目标系统字体同名的 `processed-fonts` 集合。

核心原理：提取原字体（`source_file`）的 `name` 表（元数据），合并到替换字体中，使 Windows 将替换字体识别为原字体。

工作流分为两步：

1. **转换**（`main.py`，Python）：生成伪装字体到 `processed-fonts/`，不触碰系统目录或注册表。
2. **替换**（`font-replace.ps1`，PowerShell 7）：把生成好的字体登记为开机替换，写入 `C:\Windows\Fonts`。详见 [安装字体到系统](#安装字体到系统font-replaceps1)。

## 目录结构

- `main.py`：程序入口（CLI）
- `font-replace.ps1`：字体替换脚本（PowerShell 7），把 `processed-fonts/` 中的字体登记为开机替换
- `config/`：配置加载逻辑及数据类定义
- `converter/`：字体转换核心逻辑（`base.py` 基类、`ttc.py` TTC 转换器、`ttf.py` TTF 转换器、`orchestrator.py` 编排器）
- `utils/`：通用工具（`font.py` 字体操作）
- `system-original-fonts/`：待伪装的原字体（即配置中的 `source_file` 源）
- `wanted-fonts/`：内置替换字体（MiSans 系列）
- `processed-fonts/`：转换输出目录（同时作为 `font-replace.ps1` 的待替换字体来源）
- `registries/`：字体注册表备份（`fonts-clean-WIN11-26H2.reg`、`fonts-with-office.reg`）
- `config-example.json`：配置文件示例模板
- `yahei&segoe.json`：微软雅黑与 Segoe UI 转换配置参考
- `main.spec`：PyInstaller 打包配置文件
- `font-camouflage.exe`：打包后的可执行文件

## 依赖

本项目使用 `uv` 管理依赖，需要 Python >= 3.14。

字体替换脚本 `font-replace.ps1` 需要 **PowerShell 7（`pwsh`）**，不支持 Windows PowerShell 5.1。

### 安装依赖

```bash
uv sync
```

## 使用方法

### 1. 准备字体文件

将原系统字体放入 `system-original-fonts/`，将用于替换的字体放入 `wanted-fonts/`。本项目已自带 `wanted-fonts/MiSans` 系列作为示例替换字体。

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
font-camouflage.exe convert -c my_config.json
```

转换结果将写入工作目录下的 `processed-fonts/` 目录中，文件名与 `source_file` 同名。安装环节交给 `font-replace.ps1`（见下一节）。

> Python 转换工具不再修改 `C:\Windows\Fonts`、注册表或文件所有权，因此**无需管理员权限**。

### 4. 注意事项

* **输出位置**：所有生成字体统一输出至 `processed-fonts/`。
* **自动安装**：Python 工具**不再**自动将字体安装到 `C:\Windows\Fonts`，也**不再**修改注册表。安装工作交给 `font-replace.ps1`（见下一节）或手动完成。
* **临时目录**：每个 mapper 在独立的临时目录中处理，处理结束后自动清理。

## 安装字体到系统（`font-replace.ps1`）

`font-replace.ps1` 负责把 `processed-fonts/` 中生成好的字体真正安装进 `C:\Windows\Fonts`，用于替换被系统占用的核心字体（如 `msyh.ttc`、`segoeui.ttf`）。它是 `font-replace.bat` 的 PowerShell 7 重写版，需要 **PowerShell 7（`pwsh`）** 运行；脚本头部已声明 `#Requires -Version 7.0`。

### 核心原理

直接覆盖被占用的字体文件会因共享冲突而失败，因此脚本改为把“替换”登记到注册表 `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\PendingFileRenameOperations`，由 Session Manager 在**开机时**（字体缓存服务与桌面进程启动之前）执行真正的删除与移入。此时没有任何进程持有字体句柄，核心系统字体也能被替换。

每个字体文件的处理流程：

1. **暂存**：把 `processed-fonts/` 中的字体复制到与系统字体同卷的暂存目录（`%SystemRoot%\Temp\font-replace-<时间戳>`）。
2. **设置权限**：将暂存文件的所有者与 ACL 设置为与系统字体完全一致（`NT SERVICE\TrustedInstaller`）。因为开机执行的是“重命名”，不会重新继承目标目录权限；若不预先设置，替换后的字体会带着 `%SystemRoot%\Temp` 的权限，导致以 `LocalService` 运行的字体缓存服务读不到字体，表现为“只替换了一部分”。
3. **登记删除**：若目标位置已存在同名文件，先登记"开机删除旧字体"（`MoveFileEx` + `MOVEFILE_DELAY_UNTIL_REBOOT`，用 `IntPtr.Zero` 重载显式表示删除）。
4. **登记移入**：再登记"开机把暂存文件移入目标位置"。

### 使用方法

1. 先用 Python 工具完成转换，确认 `processed-fonts/` 中已有所需字体。
2. 以管理员身份运行（脚本会自动请求提权，通过 `Start-Process pwsh.exe -Verb RunAs`）：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\font-replace.ps1
```

3. 按提示选择是否立即重启。若选择是，系统将在 30 秒后重启（`shutdown /r /t 30`）；否则请稍后手动重启。

### 限制与注意事项

* **重启后生效**：所有替换都是在重启时执行的，脚本本身不会立即改变系统字体。
* **同卷要求**：开机重命名不支持跨卷，因此暂存目录固定在 `%SystemRoot%\Temp` 下，不要改动这个位置。
* **不要提前删除暂存目录**：重启前删除会导致替换失败，脚本结束时输出的暂存目录路径请保留。
* **需要管理员权限**：涉及注册表写入与 `icacls` 权限设置，必须提权运行。
* **不再静默失败**：复制、权限设置、登记三条链路中的错误会实时输出，并给出失败计数；若“登记删除”成功而“登记移入”失败，脚本会提示清除 `PendingFileRenameOperations` 的命令，避免重启后字体丢失。
* **不再逐个询问**：扫描到的 `.ttc` / `.ttf` / `.otf` 一律直接登记替换。
* **注册表备份**：`registries/` 目录提供了字体注册表备份文件，必要时可导入回滚。

## 开发

* `config/loader.py`：数据类层级 `Config` → `ConverterConfig` → `MapperConfig`（仅 `source_file`、`fake_file`），以及 `resource_check`。
* `converter/__init__.py`：导出 `BaseConverter`、`TTCConverter`、`TTFConverter`，并维护 `CONVERTER_REGISTRY` 映射（type 字符串 → 转换器类）。
* `converter/base.py`：定义 `BaseConverter` 抽象类。`run()` 为每个 mapper 创建临时工作目录并调用 `convert_mapper()`，子类实现具体的 name 表提取与合并。`BaseConverter` 提供 `_ensure_target_dir()` 辅助方法。
* `converter/orchestrator.py`：编排器，遍历配置中的 converters，按 type 在 `CONVERTER_REGISTRY` 中查找并执行。
* `converter/ttc.py`：TTC 转换器。流程：解包 `source_file` → 提取各 TTF 的 name 表 → 复制 `fake_file` 至对应文件名并合并 → 打包为 TTC 输出。
* `converter/ttf.py`：TTF 转换器。流程：提取 `source_file` 的 name 表 → 复制 `fake_file` → 合并 → 输出。
* `utils/font.py`：基于 fontTools 的字体操作（otc2otf/otf2otc 打包解包、ttx_extract_name/ttx_merge 名称表提取合并）。
* `font-replace.ps1`：独立的系统字体安装环节，与 Python 部分无耦合；仅依赖脚本同级的 `processed-fonts/` 目录。

> `font-replace.ps1` 的 PowerShell 代码约定：以 PowerShell 7（`pwsh`）为运行时，文件头声明 `#Requires -Version 7.0`，提权使用 `Start-Process pwsh.exe -Verb RunAs`，不编写 Windows PowerShell 5.1 兼容代码。

本项目提供了 `main.spec` 文件，可以直接使用 PyInstaller 打包：

```bash
uv run pyinstaller main.spec --clean
```

打包完成后，可执行文件位于 `dist/` 目录下。
