param([string]$Model = 'qwen3:8b')
$ErrorActionPreference='Stop'
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  throw 'Ollama not on PATH. Install Windows Ollama from https://ollama.com/download/windows, then restart terminal.'
}
Write-Host "Downloading optional PRACTICE model $Model. Confirm exact required competition tag tomorrow!"
& ollama pull $Model
if ($LASTEXITCODE -ne 0) { throw 'Model pull failed' }
& ollama list
& ollama ps
