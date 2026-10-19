# SPDX-License-Identifier: MIT
# Copyright (c) 2026 天津智慧筑基科技有限公司
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Update,
    [string]$CodexTargetDir,
    [string]$WorkBuddyTargetDir,
    [string]$DshTargetDir,
    [string]$DoubaoTargetDir
)
$ErrorActionPreference = 'Stop'
$targets = @(
    @{ Script = 'install-codex.ps1'; Name = 'Codex'; Target = $CodexTargetDir },
    @{ Script = 'install-workbuddy.ps1'; Name = 'WorkBuddy'; Target = $WorkBuddyTargetDir },
    @{ Script = 'install-dsh.ps1'; Name = 'DSH'; Target = $DshTargetDir }
)
if ($DoubaoTargetDir) { $targets += @{ Script = 'install-doubao.ps1'; Name = 'Doubao'; Target = $DoubaoTargetDir } }
else { Write-Host '[Doubao] No workspace selected; use -DoubaoTargetDir to select the intended profile explicitly.' }
$failures = @()
foreach ($target in $targets) {
    try {
        & (Join-Path $PSScriptRoot $target.Script) -TargetDir $target.Target -Update:$Update -WhatIf:$WhatIfPreference
    }
    catch {
        $failures += $target.Name
        Write-Warning "[$($target.Name)] $($_.Exception.Message)"
    }
}
if ($failures.Count -gt 0) { throw ('Installation failed for: ' + ($failures -join ', ')) }
if ($WhatIfPreference) { Write-Host 'Preview completed; no files changed.' }
else { Write-Host 'All file installations completed. Client loading and runtime capabilities require separate verification.' }
