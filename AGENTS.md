# BURHAN 2.0 agent instructions - 42 Irbid government-service QA

Competition: October 15, 2026. Legal advance preparation confirmed; coding agents may be prohibited during actual contest. Project MUST function offline, independently of AI coding agents.

## Non-negotiable
- Do not replace the event-shared model, fabricate scores/flags, use remote inference or leak government documents.
- Deliver Windows 11 + NVIDIA + Python 3.11 native functionality. User GPU is RTX 5060 Ti 8 GB (nvidia-smi), RAM 16 GB, CPU i5-13400F.
- Focus on judged factual answer correctness, relevant-service routing, Arabic dialects, exceptions, contradictions, real citations, abstention and latency.
- Preserve document page IDs. MarkItDown Markdown cannot override PDF page IDs; use PyMuPDF as canonical source, cross-check MarkItDown and fall back to verified OCR only on unreadable pages.
- Contrast a verified evidence quote with the original source; numeric checking and source-ID validity alone do not prove factual support.
- Risky government contradictions must be marked *potential / manual review*, never confirmed without same conditions/date/currency applicability.
- Avoid vector DB, complex agent orchestration, frontend or LoRA training unless benchmark evidence proves value.
- Optional audio uses CPU/offline; never prevent text CLI from working.
- Preserve default single Ollama call with `think:false` where supported and 4096-token context initially; benchmark before expanding.

## Best improvements before competition
1. Add 40 human-confirmed gold Q&A labels across 10 practice services, no false government rules.
2. Benchmark against real organizer model tag and measure answer quality and latency.
3. Fix missed exceptions, wrong service routing, OCR Arabic/table extraction first.
4. Add optional cross-encoder reranking only if measurable held-out improvement and allowed runtime.
5. Keep Windows single-command setup and tests green.

Run `python -m unittest discover -s tests -v`, then `python -m burhan --index build/demo.json prepare examples --no-markitdown`, `python -m burhan --index build/demo.json eval examples/gold.jsonl`, and mocked Ollama test. Each change needs a test; never make improvements purely to impress judges.
