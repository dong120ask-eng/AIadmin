param([string]$Python = 'python', [switch]$AuthorizeModelCost)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python -m unittest discover -v
if ($LASTEXITCODE -ne 0) { throw '自动化测试失败' }
& $Python -m workbench.manager doctor
if ($LASTEXITCODE -ne 0) { throw '环境检查失败' }
if (-not $AuthorizeModelCost) {
    Write-Host '未授权模型费用，尚未执行真实Codex任务。确认后加 -AuthorizeModelCost 重跑。'
    exit 0
}
# Fresh database prevents accidentally authorizing unrelated existing queued work.
$trial = Join-Path $env:LOCALAPPDATA ('AIadmin-manager\acceptance-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $trial -Force | Out-Null
$db = Join-Path $trial 'manager.db'
& $Python -m workbench.manager --db $db submit '创建文件 hello.txt，内容为你好，AIadmin' --key 'acceptance-v1'
if ($LASTEXITCODE -ne 0) { throw '登记失败' }
& $Python -m workbench.manager --db $db run --authorize-local-task --allow-unknown-cost --timeout 90
$runCode = $LASTEXITCODE
& $Python -m workbench.manager --db $db status | Out-File (Join-Path $trial 'status.json') -Encoding utf8
Write-Host "验收记录目录：$trial"
if ($runCode -ne 0) { throw '真实调用未通过；检查status.json，不自动重试。' }
Write-Host '文字到Codex文件执行及独立检查通过。语音、Windows重启恢复仍须按文档现场验收。'
