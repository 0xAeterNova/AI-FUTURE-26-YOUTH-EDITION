# بُرهان 2.0 | BURHAN — Arabic government-service QA

**Start here:** [README_WINDOWS.md](README_WINDOWS.md). This edition targets Windows 11 + RTX 5060 Ti 8GB, Intel i5-13400F, and 16GB RAM.

Competition: 42 Irbid AI Hackathon — Oct 15, 2026. Organizer chooses model; no frontend required; evaluation prioritizes correct document-grounded answers. Scripts operate without coding agents, internet inference, or fine-tuning.

Capabilities: canonical PDF page-based extraction with optional Tesseract Arabic OCR, local Microsoft MarkItDown cross-check, Arabic hybrid/service-aware retrieval, sourced evidence ledger, conservative conflict candidate reports, JSON-constrained single Ollama call, quote/numeric checks, eval/autotune/benchmark, optional Whisper CPU speech, PowerShell setup and day-of starter.

Quick commands after native Windows setup:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe -m burhan --index build\demo.json prepare examples
.\.venv\Scripts\python.exe -m burhan --index build\demo.json eval examples\gold.jsonl
$env:BURHAN_MODEL='qwen3:8b' # ONLY practice; use EXACT event tag tomorrow
.\.venv\Scripts\python.exe -m burhan --index build\demo.json chat
```

See [COMPETITION_RUNBOOK.md](COMPETITION_RUNBOOK.md) and [AGENTS.md](AGENTS.md) for strategy and coding-agent responsibilities.
