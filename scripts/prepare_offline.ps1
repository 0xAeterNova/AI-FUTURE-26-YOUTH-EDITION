$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'Run setup_windows.ps1 first' }
New-Item -ItemType Directory -Force -Path 'wheelhouse' | Out-Null
& $py -m pip download --dest wheelhouse pip setuptools wheel '.[documents,markitdown,voice]'
if ($LASTEXITCODE -ne 0) { throw 'Offline wheel staging failed' }
Write-Host 'Wheelhouse created. Wheels are platform/Python-version specific.' -ForegroundColor Green
Write-Host 'Ollama and its model weights are NOT included. Install/download before leaving internet.'
