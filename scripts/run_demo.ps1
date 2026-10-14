param([string]$Model = 'qwen3:8b')
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py=Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $py -m burhan --index build/demo.json prepare examples
if ($LASTEXITCODE -ne 0) { throw 'Demo ingestion failed' }
& $py -m burhan --index build/demo.json eval examples/gold.jsonl
$env:BURHAN_MODEL=$Model
& $py -m burhan --index build/demo.json --num-ctx 4096 chat
