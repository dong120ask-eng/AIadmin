$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
py -3 -c "import sys; assert sys.version_info >= (3,12), 'Requires Python 3.12 or newer'"
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 or newer first.' }
py -3 -m unittest discover -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Review output before starting.' }
Write-Host 'Ready. Start: py -3 -m workbench serve'
