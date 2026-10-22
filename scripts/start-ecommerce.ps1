param(
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'AIadmin\ecommerce-pilot'),
    [ValidateRange(1024,65535)][int]$Port = 8766,
    [switch]$NoBrowser,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location (Join-Path $PSScriptRoot '..')
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = (Get-Command py).Source
    $PythonArgs = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = (Get-Command python).Source
    $PythonArgs = @()
} else { throw '请安装 Python 3.12 或更新版，并启用 Python Launcher 或添加到 PATH。' }
& $PythonExe @PythonArgs -c "import sys,sqlite3; assert sys.version_info >= (3,12), 'Requires Python 3.12+'; from workbench.ecommerce import TOOLS,QUALITY; print('Python / SQLite / 离线分析模块检查通过')"
if ($LASTEXITCODE -ne 0) { throw '运行环境检查失败。需要Python 3.12+和完整源码目录。' }
if ($CheckOnly) { Write-Host '启动脚本检查通过，未启动服务器，未导入数据。'; exit 0 }
Write-Host '数据只保存在本机。备份前按Ctrl+C停止，再复制整个数据目录。'
Write-Host "数据目录：$DataDir"
Write-Host "浏览器打开：http://127.0.0.1:$Port"
Write-Host '若页面暂未出现，请在命令窗口显示服务地址后刷新。关闭本窗口或Ctrl+C可停止。'
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
& $PythonExe @PythonArgs -m workbench.ecommerce serve --data-dir $DataDir --port $Port
if ($LASTEXITCODE -ne 0) { throw '服务未能启动：请检查端口占用及目录写入权限。' }
