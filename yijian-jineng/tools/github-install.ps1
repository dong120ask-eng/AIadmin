param(
    [Parameter(Mandatory=$true,ParameterSetName='Url')][string]$ReleaseUrl,
    [Parameter(Mandatory=$true,ParameterSetName='Repo')][string]$Repository,
    [Parameter(Mandatory=$true,ParameterSetName='Repo')][string]$Version,
    [Parameter(ParameterSetName='Repo')][string]$AssetName='yijian-jineng-20261014-r8.zip',
    [Parameter(Mandatory=$true)][string]$Sha256,
    [string]$TargetRoot=(Join-Path $env:USERPROFILE 'SelfMediaWorkspace')
)
$ErrorActionPreference='Stop'
if ($PSCmdlet.ParameterSetName -eq 'Url') {
$uri=[Uri]$ReleaseUrl
if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'github.com' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -notmatch '^/[^/]+/[^/]+/releases/download/[^/]+/[^/]+\.zip$') { throw 'Use a versioned GitHub release ZIP URL.' }
} else {
    if ($Repository -notmatch '^[a-zA-Z0-9][a-zA-Z0-9-]*/[a-zA-Z0-9][a-zA-Z0-9_.-]*$' -or $Version -notmatch '^v[0-9][a-zA-Z0-9_.-]*$' -or $AssetName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]*\.zip$') { throw 'Invalid repository/version/asset' }
}
if ($Sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw 'Expected SHA256 is required from your trusted release instructions.' }
$stage=Join-Path $env:TEMP ('selfmedia-download-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$zipPath=Join-Path $stage 'bundle.zip'
if ($PSCmdlet.ParameterSetName -eq 'Url') {
    Invoke-WebRequest -Uri $ReleaseUrl -OutFile $zipPath -TimeoutSec 300 -UseBasicParsing
} else {
    $bundledGh=Join-Path (Split-Path -Parent $PSScriptRoot) 'offline\github-cli\bin\gh.exe'
    . (Join-Path $PSScriptRoot 'github-network.ps1')
    Enable-GitHubSystemProxy
    $gh=if (Test-Path -LiteralPath $bundledGh) { $bundledGh } else { (Get-Command gh -ErrorAction Stop).Source }
    & $gh auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI login required; private repository credentials are never embedded in this script.' }
    & $gh release download $Version --repo $Repository --pattern $AssetName --dir $stage
    if ($LASTEXITCODE -ne 0) { throw 'Release download failed' }
    Move-Item -LiteralPath (Join-Path $stage $AssetName) -Destination $zipPath
}
if ((Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Sha256.ToLowerInvariant()) { throw 'Downloaded package SHA256 mismatch; stopped.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $total=0L; $seen=@{}
    foreach ($entry in $zip.Entries) {
        $name=$entry.FullName.Replace('/','\')
        $dest=[IO.Path]::GetFullPath((Join-Path $stage $name))
        if (!$dest.StartsWith($stage+'\',[StringComparison]::OrdinalIgnoreCase) -or $name.Contains(':') -or (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'Unsafe ZIP entry' }
        if ($seen.ContainsKey($dest)) { throw 'Duplicate ZIP entry' }; $seen[$dest]=$true
        $total+=$entry.Length
        if ($total -gt 2GB -or $zip.Entries.Count -gt 30000) { throw 'Package exceeds size/file limits' }
    }
} finally { $zip.Dispose() }
Expand-Archive -LiteralPath $zipPath -DestinationPath $stage
$setups=@(Get-ChildItem -LiteralPath $stage -Filter setup.ps1 -File -Recurse)
if ($setups.Count -ne 1) { throw 'Expected exactly one deployment entry' }
& $setups[0].FullName -TargetRoot $TargetRoot
