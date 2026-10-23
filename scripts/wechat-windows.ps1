# Run from the checkout root. Does not import cookies or publish articles.
[CmdletBinding()]
param(
    [ValidateSet('Setup','Login','Inspect','Verify','Run','Reconcile','Tests')]
    [string]$Stage = 'Setup',
    [string]$ProfileRef = 'wechat-primary',
    [string]$PrivateRoot = (Join-Path $env:LOCALAPPDATA 'AIadmin-Wechat'),
    [string]$ExpectedId,
    [string]$Job,
    [string]$Key,
    [string]$Task,
    [string]$Tenant = 'internal',
    [switch]$WorkerStopped
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Run-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw '命令失败，停止；不要盲目重试保存。' }
}
if ($env:OS -ne 'Windows_NT') { throw '请在Windows运行' }
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
if ($ProfileRef -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$') { throw '会话名无效' }
$PrivateRoot = [IO.Path]::GetFullPath($PrivateRoot)
if ($PrivateRoot.StartsWith($repo, [StringComparison]::OrdinalIgnoreCase)) { throw '私有资料必须位于仓库外' }
New-Item -ItemType Directory -Force -Path $PrivateRoot | Out-Null
# Restrict this root to the current Windows identity; inherited by new files.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
Run-Checked 'icacls.exe' @($PrivateRoot, '/inheritance:r', '/grant:r', "${identity}:(OI)(CI)F")
$python = Join-Path $repo '.venv-wechat\Scripts\python.exe'
$profiles = Join-Path $PrivateRoot 'profiles'
$config = Join-Path $PrivateRoot 'verified-ui.json'
$assets = Join-Path $PrivateRoot 'assets'
$data = Join-Path $PrivateRoot 'data'
$binding = Join-Path $PrivateRoot 'binding.json'
if ($Stage -eq 'Setup') {
    Run-Checked 'git' @('--version')
    Run-Checked 'py' @('-3.12','-c','import sys; assert sys.version_info[:2] == (3,12)')
    if (-not (Test-Path $python)) { Run-Checked 'py' @('-3.12','-m','venv','.venv-wechat') }
    Run-Checked $python @('-m','pip','install','playwright')
    Run-Checked $python @('-m','playwright','install','chromium')
    Run-Checked $python @('-m','pip','freeze','--local')
    Run-Checked $python @('-m','unittest','discover','-v')
    New-Item -ItemType Directory -Force -Path $profiles,$assets,$data | Out-Null
    Write-Host '环境准备完成。尚未登录或核验真实UI。下一步 -Stage Inspect。'
    exit 0
}
if (-not (Test-Path $python)) { throw '先运行Setup' }
if ($Stage -eq 'Tests') { Run-Checked $python @('-m','unittest','discover','-v'); exit 0 }
if ($Stage -in @('Login','Inspect','Verify')) {
    $params = @('-m','workbench.wechat_session','--profiles-root',$profiles,'--profile-ref',$ProfileRef)
    if ($Stage -eq 'Inspect') { $params += '--inspect' }
    if ($Stage -eq 'Verify') {
        if (-not $ExpectedId -or -not (Test-Path $config)) { throw '先现场核对唯一ID与选择器配置' }
        $params += @('--config',$config,'--expected-id',$ExpectedId)
    }
    Run-Checked $python $params
    exit 0
}
foreach ($file in @($config,$binding)) { if (-not (Test-Path $file)) { throw '缺少现场核验配置；停止' } }
$common = @('-m','workbench','--data-dir',$data,'--tenant',$Tenant)
if ($Stage -eq 'Run') {
    if (-not $Job -or -not $Key) { throw '须指定真实已审核Job和版本Key' }
    Run-Checked $python ($common + @('wechat-browser-enqueue','--job',$Job,'--binding',$binding,'--assets-root',$assets,'--key',$Key,'--authorize-draft'))
    Run-Checked $python ($common + @('wechat-browser-run','--assets-root',$assets,'--config',$config,'--profiles-root',$profiles))
} elseif ($Stage -eq 'Reconcile') {
    if (-not $Task -or -not $WorkerStopped) { throw '先确认旧进程停止并指定Task' }
    Run-Checked $python ($common + @('wechat-browser-reconcile','--assets-root',$assets,'--config',$config,'--profiles-root',$profiles,'--task',$Task,'--worker-stopped'))
}
