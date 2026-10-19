# SPDX-License-Identifier: MIT
# Copyright (c) 2026 天津智慧筑基科技有限公司
[CmdletBinding(SupportsShouldProcess = $true)]
param([Parameter(Mandatory = $true)][string]$TargetDir, [switch]$Update)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'install-shared.ps1')
$ok = Install-SkillsToTarget -SourceDir (Join-Path $repoRoot 'skills') -TargetDir $TargetDir -PlatformName 'Doubao' -Update:$Update -WhatIf:$WhatIfPreference
if (-not $ok) { throw 'Doubao file installation did not complete successfully.' }
if (-not $WhatIfPreference) { Write-Host '[Doubao] Files copied to the explicitly selected workspace. Verify client support separately.' }
