# SPDX-License-Identifier: MIT
# Copyright (c) 2026 天津智慧筑基科技有限公司
# Dot-source this file. Updates are opt-in; successful updates retain backups.

function Assert-NoInstallLinks {
    param([string]$Path, [switch]$Recurse)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Links and junctions are not supported: $cursor"
            }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
    if ($Recurse -and (Test-Path -LiteralPath $Path -PathType Container)) {
        foreach ($child in Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop) {
            if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Links and junctions are not supported: $($child.FullName)"
            }
            if ($child.PSIsContainer) { Assert-NoInstallLinks -Path $child.FullName -Recurse }
        }
    }
}

function Get-InstallFingerprint {
    param([string]$Path)
    $root = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $entries = foreach ($file in Get-ChildItem -LiteralPath $root -File -Recurse -Force -ErrorAction Stop | Sort-Object FullName) {
        $relative = $file.FullName.Substring($root.Length + 1)
        '{0}|{1}|{2}' -f $relative, $file.Length, (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash
    }
    return ($entries -join "`n")
}

function Install-SkillsToTarget {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$TargetDir,
        [Parameter(Mandatory = $true)][string]$PlatformName,
        [switch]$Update
    )
    $ErrorActionPreference = 'Stop'
    foreach ($path in @($SourceDir, $TargetDir)) {
        $full = [IO.Path]::GetFullPath($path)
        if ($full -eq [IO.Path]::GetPathRoot($full)) { throw 'Filesystem roots cannot be used as source or target.' }
    }
    $source = [IO.Path]::GetFullPath($SourceDir).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $target = [IO.Path]::GetFullPath($TargetDir).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $separator = [IO.Path]::DirectorySeparatorChar
    if ($source.Equals($target, [StringComparison]::OrdinalIgnoreCase) -or
        $source.StartsWith($target + $separator, [StringComparison]::OrdinalIgnoreCase) -or
        $target.StartsWith($source + $separator, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Source and target must be separate, non-overlapping directories.'
    }
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Source directory not found: $source" }
    if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath $target -PathType Container)) { throw 'Target must be a directory.' }
    Assert-NoInstallLinks -Path $source -Recurse
    Assert-NoInstallLinks -Path $target -Recurse
    $skills = @(Get-ChildItem -LiteralPath $source -Directory -Force | Sort-Object Name)
    if ($skills.Count -eq 0) { throw 'No source skill directories found.' }
    # WhatIf is a true preview: do not create target, lock, staging or backup directories.
    if ($WhatIfPreference) {
        foreach ($skill in $skills) {
            [void]$PSCmdlet.ShouldProcess((Join-Path $target $skill.Name), 'Preview skill installation')
        }
        Write-Host "[$PlatformName] Preview only; no files changed."
        return $true
    }
    if (-not $PSCmdlet.ShouldProcess($target, 'Install skills; existing skills require -Update')) { return $false }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    $targetParent = Split-Path -Parent $target
    $runId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N')
    $stageRoot = Join-Path $targetParent ('.aladmin-stage-' + $runId)
    $backupRoot = Join-Path (Join-Path $targetParent '.aladmin-backups') ((Split-Path -Leaf $target) + '-' + $runId)
    Assert-NoInstallLinks -Path $backupRoot
    $lock = $null
    $installed = 0; $skipped = 0; $failed = 0; $valid = 0
    try {
        # Keep the lock file after closing: deleting it can break exclusion on Unix.
        $lock = [IO.File]::Open((Join-Path $target '.aladmin-install.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        New-Item -ItemType Directory -Path $stageRoot | Out-Null
        foreach ($skill in $skills) {
            $name = $skill.Name
            $definition = Join-Path $skill.FullName 'SKILL.md'
            if (-not (Test-Path -LiteralPath $definition -PathType Leaf)) {
                $skipped++
                Write-Warning "[$PlatformName] Skipped ${name}: missing SKILL.md"
                continue
            }
            $text = [IO.File]::ReadAllText($definition)
            $match = [regex]::Match($text, '\A(?:\uFEFF)?---\r?\nname:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*\r?\n')
            if (-not $match.Success -or $match.Groups[1].Value -cne $name) {
                $failed++
                Write-Warning "[$PlatformName] Invalid skill metadata: $name"
                continue
            }
            $valid++
            $destination = Join-Path $target $name
            if ((Test-Path -LiteralPath $destination) -and -not $Update) {
                $skipped++
                Write-Host "[$PlatformName] Kept existing $name (use -Update to replace)."
                continue
            }
            $stage = Join-Path $stageRoot $name
            $backup = Join-Path $backupRoot $name
            $backupMoved = $false
            try {
                Assert-NoInstallLinks -Path $skill.FullName -Recurse
                $expected = Get-InstallFingerprint -Path $skill.FullName
                Copy-Item -LiteralPath $skill.FullName -Destination $stage -Recurse -Force -ErrorAction Stop
                Assert-NoInstallLinks -Path $stage -Recurse
                if ((Get-InstallFingerprint -Path $stage) -cne $expected) { throw 'Staged content verification failed.' }
                Assert-NoInstallLinks -Path $destination -Recurse
                if (Test-Path -LiteralPath $destination) {
                    if (-not (Test-Path -LiteralPath $destination -PathType Container)) { throw 'Existing destination is not a directory.' }
                    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
                    Move-Item -LiteralPath $destination -Destination $backup -ErrorAction Stop
                    $backupMoved = $true
                }
                Move-Item -LiteralPath $stage -Destination $destination -ErrorAction Stop
                $installed++
                if ($backupMoved) { Write-Host "[$PlatformName] Previous version retained: $backup" }
            }
            catch {
                $failed++
                Write-Warning "[$PlatformName] Failed ${name}: $($_.Exception.Message)"
                if ($backupMoved) {
                    if (-not (Test-Path -LiteralPath $destination)) {
                        try {
                            Move-Item -LiteralPath $backup -Destination $destination -ErrorAction Stop
                            Write-Warning "[$PlatformName] Previous version restored: $name"
                        }
                        catch { Write-Warning "[$PlatformName] Restore failed; backup retained at $backup" }
                    }
                    else { Write-Warning "[$PlatformName] Destination conflict; backup retained at $backup" }
                }
            }
        }
    }
    finally {
        try {
            if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction Stop }
        }
        finally { if ($null -ne $lock) { $lock.Dispose() } }
    }
    Write-Host "[$PlatformName] Installed=$installed Skipped=$skipped Failed=$failed"
    return ($failed -eq 0 -and $valid -gt 0)
}
