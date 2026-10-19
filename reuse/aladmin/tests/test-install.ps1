# SPDX-License-Identifier: MIT
# Copyright (c) 2026 天津智慧筑基科技有限公司
$ErrorActionPreference = 'Stop'
$repository = Split-Path $PSScriptRoot -Parent
$installerDir = Join-Path $repository 'install'
. (Join-Path $installerDir 'install-shared.ps1')
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('aladmin-tests-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$passed = 0
function Assert-True { param([bool]$Value, [string]$Message) if (-not $Value) { throw $Message } }
function New-Fixture {
    $root = Join-Path $testRoot ([Guid]::NewGuid().ToString('N'))
    $source = Join-Path $root 'source'
    $target = Join-Path $root 'target'
    $skill = Join-Path $source 'example-skill'
    New-Item -ItemType Directory -Path $skill -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $skill 'SKILL.md'), "---`nname: example-skill`ndescription: fixture`n---`n")
    [IO.File]::WriteAllText((Join-Path $skill 'content.txt'), 'new-version')
    return @{ Root = $root; Source = $source; Target = $target; Skill = $skill }
}
function Install-Fixture { param($Fixture, [switch]$Update, [switch]$WhatIf) Install-SkillsToTarget -SourceDir $Fixture.Source -TargetDir $Fixture.Target -PlatformName 'Test' -Update:$Update -WhatIf:$WhatIf }
function Add-OldVersion {
    param($Fixture)
    $old = Join-Path $Fixture.Target 'example-skill'
    New-Item -ItemType Directory -Path $old -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $old 'content.txt'), 'user-version')
}
try {
    $f = New-Fixture
    Assert-True (Install-Fixture $f -WhatIf) 'Preview failed'
    Assert-True (-not (Test-Path -LiteralPath $f.Target)) 'Preview modified filesystem'
    $passed++

    $f = New-Fixture
    Assert-True (Install-Fixture $f) 'Fresh install failed'
    Assert-True ([IO.File]::ReadAllText((Join-Path $f.Target 'example-skill/content.txt')) -eq 'new-version') 'New content missing'
    $passed++

    $f = New-Fixture; Add-OldVersion $f
    Assert-True (Install-Fixture $f) 'Default skip failed'
    Assert-True ([IO.File]::ReadAllText((Join-Path $f.Target 'example-skill/content.txt')) -eq 'user-version') 'Existing user content overwritten'
    $passed++

    Assert-True (Install-Fixture $f -Update) 'Explicit update failed'
    $old = @(Get-ChildItem -LiteralPath (Join-Path $f.Root '.aladmin-backups') -File -Recurse)
    Assert-True ($old.Count -eq 1 -and [IO.File]::ReadAllText($old[0].FullName) -eq 'user-version') 'Previous version not retained'
    $passed++

    $f = New-Fixture; Add-OldVersion $f
    function Copy-Item { throw 'Injected copy failure' }
    try { Assert-True (-not (Install-Fixture $f -Update)) 'Copy error reported success' }
    finally { Remove-Item Function:\Copy-Item }
    Assert-True ([IO.File]::ReadAllText((Join-Path $f.Target 'example-skill/content.txt')) -eq 'user-version') 'Copy error damaged old version'
    $passed++

    $f = New-Fixture; Add-OldVersion $f
    function Move-Item {
        [CmdletBinding()]param([string]$LiteralPath, [string]$Destination)
        if ($LiteralPath -like '*aladmin-stage-*') { throw 'Injected promotion failure' }
        Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination -ErrorAction Stop
    }
    try { Assert-True (-not (Install-Fixture $f -Update)) 'Promotion error reported success' }
    finally { Remove-Item Function:\Move-Item }
    Assert-True ([IO.File]::ReadAllText((Join-Path $f.Target 'example-skill/content.txt')) -eq 'user-version') 'Promotion error did not restore old version'
    $passed++

    $f = New-Fixture
    [IO.File]::WriteAllText((Join-Path $f.Skill 'SKILL.md'), "---`nname: wrong-name`n---`n")
    Assert-True (-not (Install-Fixture $f)) 'Mismatched metadata accepted'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $f.Target 'example-skill'))) 'Invalid skill installed'
    $passed++

    $f = New-Fixture
    New-Item -ItemType Directory -Path $f.Target | Out-Null
    $held = [IO.File]::Open((Join-Path $f.Target '.aladmin-install.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $blocked = $false
    try { Install-Fixture $f | Out-Null } catch { $blocked = $true } finally { $held.Dispose() }
    Assert-True $blocked 'Concurrent install was not blocked'
    Assert-True (Install-Fixture $f) 'Lock not released for next installer'
    $passed++

    $f = New-Fixture; $blocked = $false
    try { Install-SkillsToTarget -SourceDir $f.Source -TargetDir (Join-Path $f.Source 'nested') -PlatformName 'Test' | Out-Null } catch { $blocked = $true }
    Assert-True $blocked 'Overlapping source and target accepted'
    $passed++

    $f = New-Fixture
    $linked = Join-Path $f.Source 'linked-skill'
    if ($env:OS -eq 'Windows_NT') { New-Item -ItemType Junction -Path $linked -Target $f.Skill | Out-Null }
    else { New-Item -ItemType SymbolicLink -Path $linked -Target $f.Skill | Out-Null }
    $blocked = $false
    try { Install-Fixture $f | Out-Null } catch { $blocked = $true }
    Assert-True $blocked 'Linked source accepted'
    # Remove the link itself before recursive fixture cleanup (especially Windows PowerShell 5.1).
    if ($env:OS -eq 'Windows_NT') { [IO.Directory]::Delete($linked) }
    else { Remove-Item -LiteralPath $linked -Force }
    $passed++

    $f = New-Fixture
    $sandboxRepo = Join-Path $f.Root 'repository'
    New-Item -ItemType Directory -Path $sandboxRepo | Out-Null
    Copy-Item -LiteralPath $installerDir -Destination (Join-Path $sandboxRepo 'install') -Recurse
    Copy-Item -LiteralPath $f.Source -Destination (Join-Path $sandboxRepo 'skills') -Recurse
    $codex = Join-Path $f.Root 'codex'; $workbuddy = Join-Path $f.Root 'workbuddy'; $dsh = Join-Path $f.Root 'dsh'
    $doubao = Join-Path $f.Root 'selected-doubao-profile'
    & (Join-Path $sandboxRepo 'install/install-all.ps1') -CodexTargetDir $codex -WorkBuddyTargetDir $workbuddy -DshTargetDir $dsh -DoubaoTargetDir $doubao
    foreach ($target in @($codex, $workbuddy, $dsh, $doubao)) { Assert-True (Test-Path -LiteralPath (Join-Path $target 'example-skill/SKILL.md')) 'Wrapper target missing' }
    $passed++

    $badTarget = Join-Path $f.Root 'target-is-file'
    [IO.File]::WriteAllText($badTarget, 'preserve')
    $engine = (Get-Process -Id $PID).Path
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $engine -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $sandboxRepo 'install/install-all.ps1') -CodexTargetDir $badTarget -WorkBuddyTargetDir $workbuddy -DshTargetDir $dsh 2>&1 | Out-Host
        $exitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previousPreference }
    Assert-True ($exitCode -ne 0) 'Aggregate wrapper exited successfully after platform failure'
    Assert-True ([IO.File]::ReadAllText($badTarget) -eq 'preserve') 'Failed target file changed'
    $passed++
    Write-Host "PASS: $passed installer behavior checks ($($PSVersionTable.PSVersion))"
    # The expected failing child process must not leak exit code 1 to the CI shell.
    $global:LASTEXITCODE = 0
}
finally {
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}
