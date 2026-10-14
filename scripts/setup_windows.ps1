param(
  [switch]$InstallOllama,
  [switch]$WithVoice,
  [switch]$Offline
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8='1'
Set-Location (Split-Path -Parent $PSScriptRoot)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host 'BURHAN 2.0 Windows preflight and setup' -ForegroundColor Cyan
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw 'Python launcher py.exe is missing. Install Python 3.11 or 3.12 and rerun.'
}
$ver = & py -3.11 --version 2>$null
if ($LASTEXITCODE -eq 0) { $pythonArg = '-3.11' }
else { $pythonArg = '-3' }
& py $pythonArg -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed' }
$py = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if ($Offline) {
  if (-not (Test-Path 'wheelhouse')) { throw 'wheelhouse missing; run prepare_offline.ps1 before event' }
  & $py -m pip install --no-index --find-links wheelhouse -e '.[documents,markitdown]'
} else {
  & $py -m pip install --upgrade pip setuptools wheel
  & $py -m pip install -e '.[documents,markitdown]'
}
if ($LASTEXITCODE -ne 0) { throw 'pip dependencies installation failed' }
if ($WithVoice) {
  & $py -m pip install -e '.[voice]'
  if ($LASTEXITCODE -ne 0) { throw 'Optional voice packages failed' }
}
if ($InstallOllama -and -not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host 'Installing native Windows Ollama via winget...'
  & winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
  Write-Host 'Close/reopen PowerShell after Ollama installation for PATH refresh.'
}
& $py -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
& $py -m burhan doctor
Write-Host 'Setup complete. See README_WINDOWS.md' -ForegroundColor Green
