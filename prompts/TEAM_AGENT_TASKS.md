# Team of 3 — autonomous/offline by tomorrow

## Person A — ingest and evidence quality (own `quality.py`, `documents.py`, `ledger.py`)
- Verify all real 10 services are indexed as distinct services; if one merged PDF, construct manifest with physical page numbers.
- Inspect sampled original source PDF pages manually: Arabic glyph order, headings, tables, numbers, scanned page OCR.
- Run `python -m burhan prepare docs` and `python -m burhan audit`.
- Verify suspected contradictions and all candidate fee/date/age facts against originals, label actual applicability; do not treat same page differences as proof.
- Build 30–40 HUMAN-checked gold questions, including negative/ambiguous/cross-service tests; never invent the expected value.

## Person B — Arabic retrieval and routing (own `arabic.py`, `retrieve.py`, `evaluate.py`)
- Run `python -m burhan eval gold.jsonl` and `python -m burhan autotune gold.jsonl`.
- Debug top misses with `python -m burhan search 'question'`, check lexical/dialect normalization and service titles.
- Compare whole-service context vs selected snippets for exception retention. No unsupported embeddings or index server.
- Add minimal targeted fixes with tests; re-evaluate holdout without peeking at labels.

## Person C — answer engine/performance (own `engine.py`, `ollama.py`, `cli.py`, PowerShell)
- Check exact organizer model `ollama list`; run `ollama ps` and `nvidia-smi` to confirm GPU layers and VRAM.
- Run `python -m burhan --model '<EXACT_MODEL>' benchmark gold.jsonl --limit 10`; review all answers and sources manually.
- Audit JSON-schema compatibility, unsupported claims, numbers, uncertainty, comparisons, response time.
- Keep user CLI usable without an external coding agent. Freeze code for the final 20 minutes, run all tests and backup.

Integrate through Git commits/branches or separate file ownership; do not have 3 agents edit the same code simultaneously. No external upload of organizer documents unless permitted.
