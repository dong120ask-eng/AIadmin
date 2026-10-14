param([string]$TargetRoot = (Join-Path $env:USERPROFILE 'SelfMediaWorkspace'), [switch]$Plan)
$ErrorActionPreference = 'Stop'
$bundle = Split-Path -Parent $PSScriptRoot
$manifest = Join-Path $bundle 'bundle-manifest.json'
if (!(Test-Path -LiteralPath $manifest)) { throw 'Missing bundle manifest. Use the release package.' }
$entries = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($item in $entries) {
    $file = [IO.Path]::GetFullPath((Join-Path $bundle $item.path))
    if (!$file.StartsWith($bundle + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid manifest path' }
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw ('Missing: ' + $item.path) }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw ('Hash mismatch: ' + $item.path) }
}
$python = Join-Path $bundle 'offline\runtime\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Offline runtime missing; download the complete release package.' }
$target = [IO.Path]::GetFullPath($TargetRoot)
if ($target.TrimEnd('\').Equals($bundle.TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($bundle+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Target project must be outside the source bundle.' }
if ($target.TrimEnd('\') -eq [IO.Path]::GetPathRoot($target).TrimEnd('\')) { throw 'Choose a project folder, not a drive root' }
foreach ($hostFolder in @('.dsh', '.codebuddy', '.agents')) {
    $args = @((Join-Path $bundle 'tools\deploy.py'), '--target', (Join-Path $target ($hostFolder + '\skills')))
    if (!$Plan) { $args += @('--apply','--backup') }
    & $python -X utf8 @args
    if ($LASTEXITCODE -ne 0) { throw ('Deployment failed: ' + $hostFolder + '. Earlier hosts may already be deployed; keep their backup paths.') }
}
if (!$Plan) {
    # Keep the full tool chain locally so the USB can be unplugged. Never overwrite a previous release.
    $release = Join-Path $target ('releases\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $release -Force | Out-Null
    Copy-Item -LiteralPath $bundle -Destination $release -Recurse
    $localBundle = Join-Path $release (Split-Path -Leaf $bundle)
    @{ bundle=$localBundle; python=(Join-Path $localBundle 'offline\runtime\python.exe'); skills=30; time=(Get-Date -Format o) } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $target 'deployment-latest.json') -Encoding UTF8
    Write-Host ('Complete. Local tools: ' + $localBundle)
}
Write-Host ('Open this project folder in DeepSeek Harness / WorkBuddy / Codex: ' + $target)
