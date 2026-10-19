# SPDX-License-Identifier: MIT
# Copyright (c) 2026 天津智慧筑基科技有限公司
[CmdletBinding(SupportsShouldProcess = $true)]
param([string]$TargetDir, [switch]$Update)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'install-shared.ps1')
if (-not $TargetDir) {
    $profileRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    if (-not $profileRoot) { throw 'User profile directory could not be resolved; specify -TargetDir.' }
    $toolRoot = $env:DSH_HOME
    if (-not $toolRoot) { $toolRoot = Join-Path $profileRoot '.dsh' }
    $TargetDir = Join-Path $toolRoot 'skills'
}
$ok = Install-SkillsToTarget -SourceDir (Join-Path $repoRoot 'skills') -TargetDir $TargetDir -PlatformName 'DSH' -Update:$Update -WhatIf:$WhatIfPreference
if (-not $ok) { throw 'DSH installation did not complete successfully; review the preceding messages.' }
if (-not $WhatIfPreference) { Write-Host '[DSH] File installation completed. Restart the client and verify skill loading separately.' }
