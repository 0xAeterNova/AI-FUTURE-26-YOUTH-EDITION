# October 15 competition execution - 4 hours

## Tonight (October 14): prepare without using contest documents
- Native Windows Ollama install, install Python deps using `scripts/setup_windows.ps1`.
- Pull **practice** candidates `qwen3:8b` (safer on 8GB) and optionally `qwen3.5:9b-q4_K_M` (may offload) if time/internet/disk permits; know model will be dictated by judges.
- Download and validate Tesseract Arabic `ara` if scanned service pages possible. Run MarkItDown cross-check on a local practice PDF.
- Stage optional voice dependencies and ASR model early *only after* typed-question pipeline works. Voice uses CPU to spare GPU.
- Run 31+ unit tests, ingest `practice/ten_services`, run mock questions, build offline wheels, create backup.
- Confirm organizers permit the desktop, local Python packages, optional OCR and optional speech models. Avoid agent dependency.

## 00:00–00:35: inspect source documents (person A leads)
- Check actual Ollama tag and `ollama ps`, model host permission and source page counts.
- Prepare docs in `docs/`, run `python -m burhan prepare docs`. If all services share one PDF, manually map service names/pages via manifest.
- Inspect warnings, missing pages, garbled Arabic. Never proceed with zero-length evidence. No practice documents in production index.

## 00:35–01:30: measured retrieval (person B leads)
- Team creates 30–40 questions covering all 10 services. A few questions kept as blind holdout.
- Run `python -m burhan eval gold.jsonl` and `python -m burhan autotune gold.jsonl`.
- Fix wrong service matches and missing exceptions before touching generation parameters.

## 01:30–02:35: answer reliability and speed (person C leads)
- Confirm exact shared model (one allowed). Warm it up. Benchmark 8–12 verified questions.
- Inspect incorrect numbers, conditions, negative answers, source support, dialect, follow-up references.
- If 4096 context truncates evidence and GPU allows, compare 6144 tokens; check `ollama ps` before increasing.
- Avoid a second LLM call except for a proven error category; keep latency measurable.

## 02:35–03:20: hard cases and conflict differentiation
- Evaluate cross-service questions, missing information, apparently contradictory service rules, and dialect mistakes.
- Verify actual contradiction versus difference in dates/eligibility before showing it.
- Optional microphone demo only if core is green and organizers allow extra ASR model.

## 03:20–04:00: freeze and demonstrate
- Stop code edits for last 20 minutes. Run tests and end-to-end CLI.
- Save metrics + `scripts/create_backup.ps1`; show original sources and documented limitations.
- Demo 5 questions: exact fee, Jordanian dialect, exception, two-service comparison, unsupported question. Avoid any unverified answer.

## Core principle
Converting 10 pages into a retrieval database is not model training. No need to alter Ollama weights. First place is not guaranteed. Documented correctness, source fidelity and reproducible evaluation are the levers most likely to matter.
