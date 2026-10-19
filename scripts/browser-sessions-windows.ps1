[CmdletBinding()]
param(
 [ValidateSet('Setup','Tests','Register','Login','Inspect','Enqueue','Run','Status','Recover','Resolve','Revoke')][string]$Stage='Setup',
 [string]$PrivateRoot=(Join-Path $env:LOCALAPPDATA 'AIadmin-Browser'),
 [string]$Tenant='internal',[string]$Profile,[string]$Binding,[string]$Request,[string]$Config,[string]$Key,
 [string]$Task,[switch]$WorkerStopped,[int]$Limit=2
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Checked([string]$Exe,[string[]]$Arguments) {
 & $Exe @Arguments
 if ($LASTEXITCODE -ne 0) { throw '命令失败，停止并检查状态；不自动重试' }
}
if ($env:OS -ne 'Windows_NT') { throw '必须在Windows运行' }
$repo=Split-Path $PSScriptRoot -Parent
Set-Location $repo
$PrivateRoot=[IO.Path]::GetFullPath($PrivateRoot)
if ($PrivateRoot.StartsWith($repo,[StringComparison]::OrdinalIgnoreCase)) { throw '私有目录须位于仓库外' }
$checkPath=$PrivateRoot
while ($checkPath) {
 if (Test-Path $checkPath) {
  if ((Get-Item -LiteralPath $checkPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw '私有目录不得经过链接或重解析点' }
 }
 $parent=Split-Path $checkPath -Parent
 if ($parent -eq $checkPath) { break }; $checkPath=$parent
}
New-Item -ItemType Directory -Force -Path $PrivateRoot | Out-Null
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
# Set an exact protected ACL: remove inherited AND existing explicit grants.
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetOwner((New-Object Security.Principal.NTAccount($identity)))
$acl.SetAccessRuleProtection($true,$false)
$rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $PrivateRoot -AclObject $acl
$python=Join-Path $repo '.venv-browser\Scripts\python.exe'
if ($Stage -eq 'Setup') {
 Checked 'git' @('--version')
 Checked 'py' @('-3.12','-m','venv','.venv-browser')
 Checked $python @('-m','pip','install','playwright==1.55.0')
 Checked $python @('-m','playwright','install','chromium')
 Checked $python @('-m','pip','freeze','--local')
 Checked $python @('-m','unittest','discover','-v')
 Write-Host '依赖和隔离测试完成，真实平台尚未验收。';exit 0
}
if (!(Test-Path $python)) { throw '请先运行Setup' }
if ($Stage -eq 'Tests') { Checked $python @('-m','unittest','discover','-v');exit 0 }
$common=@('-m','workbench.browser_sessions','--data-dir',(Join-Path $PrivateRoot 'data'),'--profiles-root',(Join-Path $PrivateRoot 'profiles'),'--tenant',$Tenant)
switch ($Stage) {
 'Register' { if (!$Binding) { throw '需要Binding' };$cmd=@('register','--binding',$Binding,'--authorize-read') }
 'Login' { if (!$Profile) { throw '需要Profile' };$cmd=@('login','--profile',$Profile) }
 'Inspect' { if (!$Profile) { throw '需要Profile' };$cmd=@('login','--profile',$Profile,'--inspect') }
 'Enqueue' { if (!$Profile -or !$Request -or !$Key) { throw '需要Profile、Request、Key' };$cmd=@('enqueue','--profile',$Profile,'--request',$Request,'--key',$Key) }
 'Run' { if (!$Config) { throw '需要已核验Config' };$cmd=@('run','--config',$Config,'--limit',"$Limit") }
 'Revoke' { if (!$Profile) { throw '需要Profile' };$cmd=@('revoke','--profile',$Profile) }
 'Status' { $cmd=@('status') }
 'Recover' { $cmd=@('recover') }
 'Resolve' { if (!$Task -or !$WorkerStopped) { throw '须停止旧进程并指定Task' };$cmd=@('resolve','--task',$Task,'--worker-stopped') }
}
Checked $python ($common+$cmd)
