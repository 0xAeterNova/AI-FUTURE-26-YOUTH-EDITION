param(
  [string]$Model = $env:BURHAN_MODEL,
  [string]$Docs = 'docs',
  [int]$NumCtx = 4096,
  [switch]$SkipChat
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8='1'
Set-Location (Split-Path -Parent $PSScriptRoot)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$py = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'Virtual env missing. Run scripts/setup_windows.ps1 first.' }
if (-not (Test-Path $Docs)) { throw "Document folder '$Docs' not found" }
if (-not @(Get-ChildItem -Path $Docs -Recurse -File | Where-Object {$_.Extension -match '^\.(pdf|docx|txt|md)$'}).Count) {
  throw 'Documents folder has no supported documents. Copy organizer files into docs/ first.'
}
if (-not $Model) { throw 'Supply the organizers exact model: -Model qwen3:8b (example only)' }
$env:BURHAN_MODEL = $Model
Write-Host '--- Hardware and installed model diagnostics ---' -ForegroundColor Cyan
& $py -m burhan doctor
if ($LASTEXITCODE -ne 0) { throw 'Doctor failed' }
Write-Host '--- Source extraction, service indexing and evidence audit ---' -ForegroundColor Cyan
& $py -m burhan prepare $Docs
if ($LASTEXITCODE -ne 0) { throw 'Document ingestion failed' }
& $py -m burhan inspect
if ($LASTEXITCODE -ne 0) { throw 'Index inspection failed' }
Write-Host 'READ ALL EXTRACTION WARNINGS ABOVE, AND audit output build/evidence_audit.json' -ForegroundColor Yellow
if (Test-Path 'gold.jsonl') {
  & $py -m burhan eval gold.jsonl --save build/eval_retrieval.json
  if ($LASTEXITCODE -ne 0) { throw 'Retrieval evaluation failed' }
}
if (-not $SkipChat) {
  & $py -m burhan --num-ctx $NumCtx chat
}
