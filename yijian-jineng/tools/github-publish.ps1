param([Parameter(Mandatory=$true)][string]$PackagePath, [Parameter(Mandatory=$true)][string]$SourcePath, [string]$Repository='dong120ask-eng/yijian-jineng', [string]$Version='v2026.10.14-r3', [switch]$Apply)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'github-network.ps1')
Enable-GitHubSystemProxy
if ($Repository -ne 'dong120ask-eng/yijian-jineng') { throw 'This reviewed publisher only targets dong120ask-eng/yijian-jineng' }
if ($Version -notmatch '^v[0-9][a-zA-Z0-9_.-]*$') { throw 'Invalid release version' }
$bundle=Split-Path -Parent $PSScriptRoot
$gh=Join-Path $bundle 'offline\github-cli\bin\gh.exe'
if (!(Test-Path -LiteralPath $gh)) { $gh=(Get-Command gh -ErrorAction Stop).Source }
$package=(Get-Item -LiteralPath $PackagePath -ErrorAction Stop).FullName
$source=(Get-Item -LiteralPath $SourcePath -ErrorAction Stop).FullName
$hash=(Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant()
if (!(Test-Path -LiteralPath (Join-Path $source 'skills\selfmedia-autopilot\SKILL.md'))) { throw 'Incomplete source tree' }
if (Test-Path -LiteralPath (Join-Path $source '.git')) { throw 'Existing local Git repository; inspect previous publication state before retry' }
# Expanded blocklist: credentials, keys, certs, binaries, archives, state.
$blockExt=@('.zip','.sqlite','.exe','.dll','.whl','.pem','.key','.p12','.pfx','.crt','.cer','.p7b','.keystore')
$leaked=Get-ChildItem -LiteralPath $source -Recurse -File | Where-Object {
    $_.Name -like '.env*' -or $_.Extension -in $blockExt
}
if ($leaked.Count -gt 0) {
    throw 'Repository source must exclude binaries, archives, live credentials, keys and certs: ' + ($leaked.FullName -join ', ')
}
Write-Host ('Plan: private repository ' + $Repository + '; release ' + $Version + '; SHA256 ' + $hash)
if (!$Apply) { return }
& $gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) { throw 'GitHub login required. Run the bundled gh auth login --hostname github.com --git-protocol https --web and complete authorization yourself.' }
$login=& $gh api user --jq .login
if ($LASTEXITCODE -ne 0 -or $login -ne 'dong120ask-eng') { throw 'Wrong GitHub account; stopped' }
# Never reuse or overwrite a pre-existing unrelated repository.
$existing=& $gh repo view $Repository --json nameWithOwner,isPrivate 2>$null
if ($LASTEXITCODE -eq 0) { throw 'Repository already exists. Inspect it before any retry; this script will not overwrite it.' }
Push-Location -LiteralPath $source
try {
    & git init --initial-branch=main
    if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
    & git add -- .
    if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
    & git -c user.name='dong120ask-eng' -c user.email='335087763+dong120ask-eng@users.noreply.github.com' commit -m 'Add reviewed self-media skills and portable deployment'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
    & $gh repo create $Repository --private --source $source --remote origin --description 'Yijian jineng: self-media skills, USB deployment and GitHub release deployment'
    if ($LASTEXITCODE -ne 0) { throw 'Repository creation failed; inspect remote state before retry' }
    $previousPath=$env:PATH
    $env:PATH=(Split-Path -Parent $gh)+';'+$env:PATH
    & git -c 'credential.helper=' -c 'credential.helper=!gh auth git-credential' push -u origin main
    if ($LASTEXITCODE -ne 0) { throw 'Push failed; repository may already exist. Inspect it before retry' }
    $notes=Join-Path $env:TEMP ('yijian-release-'+[Guid]::NewGuid().ToString('N')+'.md')
    @('30 skills. Windows x64 portable Python and dependencies included.','USB: extract and run deployment launcher.','Platform publishing remains pending real-account acceptance.','',('SHA256: '+$hash)) | Set-Content -LiteralPath $notes -Encoding UTF8
    & $gh release create $Version $package --repo $Repository --target main --title ('Yijian jineng '+$Version) --notes-file $notes
    if ($LASTEXITCODE -ne 0) { throw 'Release upload failed' }
    & $gh release view $Version --repo $Repository --json url,assets
    if ($LASTEXITCODE -ne 0) { throw 'Release verification failed' }
} finally { if ($previousPath) { $env:PATH=$previousPath }; Pop-Location }
