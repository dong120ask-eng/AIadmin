param([string]$Python = 'python', [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python -c "import sys,sqlite3,tkinter; assert sys.version_info >= (3,12), 'Python 3.12+ required'"
if ($LASTEXITCODE -ne 0) { throw '请安装包含Tcl/Tk的Python 3.12或更高版本，并设置Python参数。' }
& $Python -m workbench.manager doctor
if ($LASTEXITCODE -ne 0) { throw '环境检查失败' }
if (-not $CheckOnly) { & $Python -m workbench.manager desktop }
