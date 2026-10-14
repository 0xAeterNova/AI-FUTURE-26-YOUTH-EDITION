$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$dest = Join-Path (Get-Location) ('build\burhan_backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.zip')
New-Item -ItemType Directory -Force 'build' | Out-Null
$files = @(Get-ChildItem -Path . -File -Recurse | Where-Object {
 $_.FullName -notmatch '\\(\.venv|wheelhouse|__pycache__|\.git)\\' -and
 $_.FullName -notmatch '\\build\\burhan_backup_' -and $_.Length -lt 100MB
})
Compress-Archive -LiteralPath $files.FullName -DestinationPath $dest -CompressionLevel Optimal
Write-Host "Backup saved to $dest"
