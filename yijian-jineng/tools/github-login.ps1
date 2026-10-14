$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'github-network.ps1')
Enable-GitHubSystemProxy
$gh=Join-Path (Split-Path -Parent $PSScriptRoot) 'offline\github-cli\bin\gh.exe'
& $gh auth login --hostname github.com --git-protocol https --web
if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication did not complete. No password or token needs to be sent to the assistant.' }
