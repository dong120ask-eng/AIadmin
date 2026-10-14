param([string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
$bundle = Split-Path -Parent $PSScriptRoot
if (-not $WorkspaceRoot) {
    $WorkspaceRoot = Split-Path -Parent $bundle
    # Installed bundles live in <workspace>/releases/<unique-id>/<bundle>.
    $parent = Split-Path -Parent $WorkspaceRoot
    if ((Split-Path -Leaf $parent) -eq 'releases') {
        $candidate = Split-Path -Parent $parent
        if (Test-Path -LiteralPath (Join-Path $candidate 'deployment-latest.json')) { $WorkspaceRoot = $candidate }
    }
}
$python = Join-Path $bundle 'offline/runtime/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw '请使用包含离线 Python 的完整交付包，或由助手运行 progress_console.py。' }
& $python -X utf8 (Join-Path $PSScriptRoot 'progress_console.py') --root $WorkspaceRoot
if ($LASTEXITCODE -ne 0) { throw '进度页面未生成，请查看上面的修复提示。' }
Start-Process -FilePath (Join-Path $WorkspaceRoot 'work/progress-console/index.html')
