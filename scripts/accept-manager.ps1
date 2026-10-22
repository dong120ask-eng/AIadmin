param([string]$Python = 'python', [switch]$AuthorizeModelCost, [switch]$CheckSpeech)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw '此脚本仅供Windows实机验收' }
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA不可用' }
# Isolated database; never consumes an existing user's queue.
$trial = Join-Path $env:LOCALAPPDATA ('AIadmin-manager\acceptance-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $trial | Out-Null
$db = Join-Path $trial 'manager.db'
function Invoke-LoggedPython([string]$LogPath, [string[]]$Arguments) {
    # Avoid PS5.1 treating successful native stderr (unittest) as terminating errors.
    & $Python -c "import subprocess,sys; f=open(sys.argv[1],'wb'); r=subprocess.run([sys.executable]+sys.argv[2:],stdout=f,stderr=subprocess.STDOUT); f.close(); sys.exit(r.returncode)" $LogPath @Arguments
    return $LASTEXITCODE
}
$evidence = [ordered]@{
    schema = 2; started_at = (Get-Date).ToUniversalTime().ToString('o')
    source_sha = ''; os = [Environment]::OSVersion.VersionString
    automated_tests = 'not_run'; doctor = $null; task_id = $null
    model_cost_authorized = [bool]$AuthorizeModelCost
    billing = 'unknown'; text_cli_file_readback = 'not_run'
    speech = 'not_run'; interruption_recovery = 'manual_required'
    os_sandbox_and_network = 'manual_required'; merge_ready = $false
}
try {
    $sha = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw '无法确定源码版本' }
    $evidence.source_sha = [string]$sha
    & $Python -c "import sys,tkinter,sqlite3; assert sys.version_info >= (3,12)"
    if ($LASTEXITCODE -ne 0) { throw '需要Python 3.12+及Tk' }
    $testCode = Invoke-LoggedPython -LogPath (Join-Path $trial 'automated-tests.log') -Arguments @('-m', 'unittest', 'discover', '-v')
    if ($testCode -ne 0) { $evidence.automated_tests = 'failed'; throw '自动化测试失败，详见日志' }
    $evidence.automated_tests = 'passed'
    $doctorText = & $Python -m workbench.manager --db $db doctor
    if ($LASTEXITCODE -ne 0) { throw '环境诊断失败' }
    $evidence.doctor = ($doctorText -join "`n") | ConvertFrom-Json
    if ($CheckSpeech) {
        Write-Host '请说：创建文件 hello.txt，内容为你好，AIadmin。识别结果不会自动登记或执行。'
        & $Python -c "from workbench.manager_voice import WindowsSpeech; s=WindowsSpeech(); print(s.listen()); s.speak('本地文件任务语音播报验收，请确认听到这句话。')"
        if ($LASTEXITCODE -ne 0) { $evidence.speech = 'failed'; throw '语音接口失败' }
        $observed = Read-Host '是否已核对中文识别结果，并实际听到正确播报？输入YES才记录通过'
        $evidence.speech = if ($observed -ceq 'YES') { 'operator_confirmed' } else { 'not_confirmed' }
    }
    if ($AuthorizeModelCost) {
        if (-not $evidence.doctor.codex_installed -or -not $evidence.doctor.codex_authenticated) {
            throw '真实原生Codex未安装或未认证，不调用模型'
        }
        $taskText = & $Python -m workbench.manager --db $db submit '创建文件 hello.txt，内容为你好，AIadmin' --key 'acceptance-v2'
        if ($LASTEXITCODE -ne 0) { throw '任务登记失败' }
        $task = ($taskText -join "`n") | ConvertFrom-Json
        $evidence.task_id = $task.id
        $evidence.text_cli_file_readback = 'started_result_unknown'
        $runCode = Invoke-LoggedPython -LogPath (Join-Path $trial 'run-summary.log') -Arguments @('-m', 'workbench.manager', '--db', $db, 'run', '--task-id', $task.id, '--authorize-local-task', '--allow-unknown-cost', '--timeout', '90')
        $statusText = & $Python -m workbench.manager --db $db status
        if ($LASTEXITCODE -ne 0) { throw '状态读取失败' }
        ($statusText -join "`n") | Set-Content (Join-Path $trial 'status.json') -Encoding UTF8
        if ($runCode -ne 0) { throw '真实调用失败或结果未知；不自动重试，按恢复流程核查' }
        # Read the actual file again in a fresh host process; exit code alone is insufficient.
        $readback = "import json,sys; from pathlib import Path; from workbench.manager import check_file; tasks=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')); assert len(tasks)==1; t=tasks[0]; assert t['id']==sys.argv[2] and t['state']=='checked'; r=check_file(Path(t['result']['path']).parent,t['payload']['contract']); assert r==t['result']; print(r['sha256'])"
        $readCode = Invoke-LoggedPython -LogPath (Join-Path $trial 'readback.log') -Arguments @('-c', $readback, (Join-Path $trial 'status.json'), $task.id)
        if ($readCode -ne 0) { throw '独立二次回读失败' }
        $evidence.text_cli_file_readback = 'passed'
    } else {
        Write-Host '未授权模型费用，本轮只做离线检查；真实Codex执行未验收。'
    }
} catch {
    $evidence.failure = [string]$_.Exception.Message
    throw
} finally {
    $evidence.finished_at = (Get-Date).ToUniversalTime().ToString('o')
    $evidence | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $trial 'evidence.json') -Encoding UTF8
    Write-Host "验收证据目录：$trial"
    Write-Host '此脚本不会批准合并；Windows沙箱、网络边界、中断恢复及语音闭环仍按文档核验。'
}
