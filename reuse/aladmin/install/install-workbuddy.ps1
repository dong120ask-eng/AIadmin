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
    $toolRoot = $null
    if (-not $toolRoot) { $toolRoot = Join-Path $profileRoot '.codebuddy' }
    $TargetDir = Join-Path $toolRoot 'skills'
    $legacyTarget = Join-Path (Join-Path $profileRoot '.workbuddy') 'skills'
    if (-not (Test-Path -LiteralPath $TargetDir) -and (Test-Path -LiteralPath $legacyTarget -PathType Container)) { $TargetDir = $legacyTarget }
}
$ok = Install-SkillsToTarget -SourceDir (Join-Path $repoRoot 'skills') -TargetDir $TargetDir -PlatformName 'WorkBuddy' -Update:$Update -WhatIf:$WhatIfPreference
if (-not $ok) { throw 'WorkBuddy installation did not complete successfully; review the preceding messages.' }
if (-not $WhatIfPreference) { Write-Host '[WorkBuddy] File installation completed. Restart the client and verify skill loading separately.' }
