param(
    [string]$Workspace = (Join-Path $env:USERPROFILE 'SelfMediaWorkspace'),
    [string]$Request = '读取 selfmedia-autopilot 和交付说明，先核对输入资料与未验收项，然后给出本次执行计划。',
    [string]$DshCommand,
    [string]$SessionId
)
$ErrorActionPreference = 'Stop'
if (-not $DshCommand) {
    $candidate = Get-Command dsh.cmd -ErrorAction SilentlyContinue
    if ($candidate) { $DshCommand = $candidate.Path }
    elseif (Test-Path -LiteralPath 'D:/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd') {
        $DshCommand = 'D:/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd'
    }
}
if (-not $DshCommand -or -not (Test-Path -LiteralPath $DshCommand)) {
    throw '找不到 DeepSeek Harness CLI，请用 -DshCommand 指定官方安装目录中的 dsh.cmd。'
}
$entryArgs = @('headless')
if ($SessionId) { $entryArgs += @('--session-id', $SessionId) }
$entryArgs += "工作目录为 $Workspace。先读取 selfmedia-autopilot 和交付说明。$Request"
Push-Location -LiteralPath $Workspace
try { & $DshCommand @entryArgs; if ($LASTEXITCODE -ne 0) { throw 'Harness 执行失败，请核对实际输出。' } }
finally { Pop-Location }
