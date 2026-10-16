#Requires -Version 7.0
<#
    字体自动替换工具（PowerShell 7 版 · 开机替换方案）
    由 font-replace.bat 转换而来，用于替换被系统占用的核心字体。

    核心原理：
      直接覆盖被占用的字体文件会失败（共享冲突），因此本脚本改为把"替换"登记到
        HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\PendingFileRenameOperations
      由 Session Manager 在开机时（字体缓存服务与桌面进程启动之前）执行真正的删除与移入。
      此时没有任何进程持有字体句柄，因此核心系统字体也能被替换。

    使用限制：
      1. 暂存文件必须与目标字体位于同一个卷（开机重命名不支持跨卷），脚本统一使用 %SystemRoot%
      2. 替换在重启后才会真正生效
      3. 重启前不要删除脚本输出的暂存目录

     权限处理：
      暂存文件会先被设置为与系统字体完全一致的所有者（TrustedInstaller）与 ACL。
      因为开机执行的是"重命名"，不会重新继承目标目录的权限；若不预先设置，
      替换后的字体会带着 %SystemRoot%\Temp 的权限，导致非管理员进程（含以
      LocalService 运行的字体缓存服务）读不到字体文件，表现为"只替换了一部分"。

    行为说明：
      - 不再静默失败：复制、权限、登记操作的错误会实时输出
      - 不再逐个询问是否替换：扫描到的字体一律直接登记替换
      - 待替换字体来源：脚本同级的 processed-fonts 目录
#>

# ============================================================
# 函数：Y/N 选择（等价于批处理的 choice /C YN）
#   - TimeoutSeconds > 0 时，超时自动使用 DefaultChoice（等价于 choice /T /D）
# ============================================================
function Read-ChoiceYN {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [int]$TimeoutSeconds = 0,
        [string]$DefaultChoice = 'N'
    )

    $interactive = $true
    try { $null = [Console]::KeyAvailable } catch { $interactive = $false }

    if ($interactive) {
        Write-Host $Prompt -NoNewline
        $deadline = if ($TimeoutSeconds -gt 0) { (Get-Date).AddSeconds($TimeoutSeconds) } else { [datetime]::MaxValue }
        while ((Get-Date) -lt $deadline) {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true).Key
                if ($key -eq [ConsoleKey]::Y) { Write-Host 'Y'; return 'Y' }
                if ($key -eq [ConsoleKey]::N) { Write-Host 'N'; return 'N' }
            }
            Start-Sleep -Milliseconds 50
        }
        Write-Host $DefaultChoice
        return $DefaultChoice
    }

    # 非交互式环境（输入被重定向等）退化为 Read-Host
    while ($true) {
        $line = Read-Host $Prompt
        if ($line -eq 'Y' -or $line -eq 'y') { return 'Y' }
        if ($line -eq 'N' -or $line -eq 'n') { return 'N' }
        if ($TimeoutSeconds -gt 0 -and [string]::IsNullOrEmpty($line)) { return $DefaultChoice }
    }
}

# ============================================================
# 管理员权限检查
# ============================================================
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "请求管理员权限..."
    Start-Process pwsh.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

# ============================================================
# 注册 Win32 MoveFileEx（用于登记开机时的删除 / 移动）
#
# 注意：PowerShell 会把 $null 编组成"空字符串"而不是 NULL 指针。
# 若写成 MoveFileEx($file, $null, MOVEFILE_DELAY_UNTIL_REBOOT)，
# API 收到的将是空的目标路径（即"重命名为空路径"），从而返回
# ERROR_PATH_NOT_FOUND(3)，导致每个文件都登记失败。
# 因此"删除"必须走接受 IntPtr 的重载，显式传入 [IntPtr]::Zero。
# ============================================================
if (-not ('Win32.NativeMethods' -as [type])) {
    Add-Type -Namespace Win32 -Name NativeMethods -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "MoveFileExW")]
public static extern bool MoveFileEx(string lpExistingFileName, string lpNewFileName, uint dwFlags);

[DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "MoveFileExW")]
public static extern bool MoveFileExDelete(string lpExistingFileName, IntPtr lpNewFileName, uint dwFlags);
'@
}
$MOVEFILE_DELAY_UNTIL_REBOOT = 0x4

Write-Host "========================================"
Write-Host "          字体自动替换工具"
Write-Host "========================================"
Write-Host ""

# 设置路径
$script_dir = $PSScriptRoot
if ([string]::IsNullOrEmpty($script_dir)) {
    $script_dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
}
$source_dir = Join-Path -Path $script_dir -ChildPath 'processed-fonts'
$target_dir = Join-Path $env:SystemRoot 'Fonts'
# 暂存目录与目标字体同在 %SystemRoot% 卷上，满足开机重命名的同卷要求
$stage_dir = Join-Path $env:SystemRoot ("Temp\font-replace-" + (Get-Date).ToString('yyyyMMdd-HHmmss'))

if (-not (Test-Path -LiteralPath $source_dir)) {
    Write-Host "[错误] 未找到待替换字体目录: $source_dir"
    Write-Host "请先创建该目录并放入需要替换的字体文件（.ttc / .ttf / .otf）。"
    exit 1
}

New-Item -ItemType Directory -Path $stage_dir -Force | Out-Null

Write-Host "待替换字体目录: $source_dir"
Write-Host "目标目录: $target_dir"
Write-Host "暂存目录: $stage_dir"
Write-Host ""

$file_count = 0
$scheduled_count = 0
$failed_count = 0

Write-Host "正在扫描字体文件..."
Write-Host ""

# 与批处理一致：按 *.ttc、*.ttf、*.otf 的顺序枚举（每组内按名称排序）
$font_files = @()
foreach ($pattern in @('*.ttc', '*.ttf', '*.otf')) {
    $font_files += Get-ChildItem -LiteralPath $source_dir -Filter $pattern -File |
        Sort-Object -Property Name
}

foreach ($font_file in $font_files) {
    # 对应批处理中的 if exist "%%f" 判断
    if (-not (Test-Path -LiteralPath $font_file.FullName)) { continue }

    $file_count++
    $filename = [System.IO.Path]::GetFileNameWithoutExtension($font_file.Name)
    $extension = $font_file.Extension
    $target_file = Join-Path $target_dir ($filename + $extension)
    $stage_file = Join-Path $stage_dir $font_file.Name
    $target_exists = Test-Path -LiteralPath $target_file

    Write-Host "[$file_count] 找到字体: $($font_file.Name)"
    if ($target_exists) {
        Write-Host "    目标位置已存在同名文件，登记为开机替换"
    }
    else {
        Write-Host "    目标位置不存在此文件，登记为开机新增"
    }

    # 第一步：把新字体暂存到与目标同一个卷
    Copy-Item -LiteralPath $font_file.FullName -Destination $stage_file -Force
    $stage_ok = $?
    if (-not $stage_ok -or -not (Test-Path -LiteralPath $stage_file)) {
        Write-Host "    [错误] 暂存副本创建失败，跳过此文件"
        $failed_count++
        Write-Host ""
        continue
    }
    Write-Host "    已暂存到: $stage_file"

    # 第二步：把暂存文件的所有者与 ACL 设置为与系统字体完全一致
    # 说明：文件被"移动"（重命名）时不会重新继承目标目录的权限，若不预先设置，
    #       替换后的字体将保留 %SystemRoot%\Temp 的权限，导致非管理员进程
    #       （包括以 LocalService 运行的字体缓存服务）读不到字体文件。
    Write-Host "    设置文件所有者与权限..."
    icacls "$stage_file" /setowner "NT SERVICE\TrustedInstaller" 1> $null
    icacls "$stage_file" /inheritance:r /grant:r "NT SERVICE\TrustedInstaller:(F)" "NT AUTHORITY\SYSTEM:(RX)" "*S-1-5-32-544:(RX)" "*S-1-5-32-545:(RX)" "*S-1-15-2-1:(RX)" "*S-1-15-2-2:(RX)" 1> $null
    if (-not $?) {
        Write-Host "    [警告] 设置文件权限失败，替换后的字体可能无法被字体缓存服务加载"
    }

    # 第三步：先登记"开机删除旧字体"（PendingFileRenameOperations 中重命名无法覆盖已存在的目标）
    if ($target_exists) {
        $deleted = [Win32.NativeMethods]::MoveFileExDelete($target_file, [IntPtr]::Zero, $MOVEFILE_DELAY_UNTIL_REBOOT)
        if (-not $deleted) {
            $err = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
            Write-Host "    [错误] 登记删除旧字体失败（Win32 错误码 $err），跳过此文件"
            Remove-Item -LiteralPath $stage_file -Force
            $failed_count++
            Write-Host ""
            continue
        }
    }

    # 第四步：再登记"开机把暂存文件移入目标位置"
    $moved = [Win32.NativeMethods]::MoveFileEx($stage_file, $target_file, $MOVEFILE_DELAY_UNTIL_REBOOT)
    if (-not $moved) {
        $err = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
        Write-Host "    [错误] 登记新字体移入失败（Win32 错误码 $err）"
        if ($target_exists) {
            Write-Host "    [严重警告] 已登记〝开机删除 $target_file〞但移入未登记成功，"
            Write-Host "               重启前必须清除该登记项，否则重启后该字体会丢失。"
            Write-Host "               清除命令（会一并清除其它程序登记的待执行项）："
            Write-Host "               Remove-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations"
        }
        $failed_count++
        Write-Host ""
        continue
    }

    Write-Host "    [已登记] 重启后生效"
    $scheduled_count++
    Write-Host ""
}

Write-Host "========================================"
Write-Host "操作完成！"
Write-Host "扫描到的字体文件: $file_count 个"
Write-Host "已登记开机替换: $scheduled_count 个"
Write-Host "登记失败: $failed_count 个"
Write-Host "暂存目录: $stage_dir"
Write-Host ""
Write-Host "注意：替换将在系统重启时执行，重启前请勿删除暂存目录"
Write-Host "========================================"

$reboot = Read-ChoiceYN -Prompt "是否立即重启系统以使字体生效 (Y/N) [Y,N]?" -TimeoutSeconds 30 -DefaultChoice 'N'
if ($reboot -eq 'Y') {
    Write-Host "系统将在30秒后重启，按 Ctrl+C 取消..."
    shutdown /r /t 30
}
else {
    Write-Host "请稍后手动重启系统以完成字体更新"
}

Read-Host "请按 Enter 键继续..."
