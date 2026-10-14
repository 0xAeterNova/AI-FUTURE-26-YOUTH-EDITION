"""Terminal-only judge-friendly commands."""
from __future__ import annotations
import argparse
import json
import os
import sys
from .documents import index_folder, load_index
from .engine import Engine
from .ollama import OllamaClient
from .evaluate import load_questions, retrieval_report, answer_report


def pretty_answer(result: dict, verbose: bool = False):
    print(f'\n[status: {result["status"]}] {result["answer"]}')
    for src in result.get("sources", []):
        print(f'   ↳ [{src["id"]}] {src["title"]} | page {src["page"]} | {src["file"]}')
    print(f'   ⏱ {result["elapsed_s"]:.2f}s')
    if verbose:
        print(f'   candidates: {result.get("service_ranks", [])[:5]}')
        if result.get("invalid_citations"):
            print(f'   invalid citations ignored: {result["invalid_citations"]}')


def main(argv: list[str] | None = None):
    p = argparse.ArgumentParser(prog="burhan", description="BURHAN | برهان — Arabic evidence-first chatbot")
    p.add_argument("--index", default="build/index.json", help="Indexed document JSON")
    p.add_argument("--model", default=os.getenv("BURHAN_MODEL", ""), help="EXACT shared Ollama model name; or BURHAN_MODEL")
    p.add_argument("--url", default="http://localhost:11434", help="Local Ollama API URL")
    p.add_argument("--context-chars", type=int, default=8500)
    p.add_argument("--max-services", type=int, default=2)
    p.add_argument("--think", action="store_true", help="Enable slower model reasoning; off by default")
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--no-schema", action="store_true", help="Compatibility with models that reject JSON schema")
    p.add_argument("--verbose", action="store_true")
    sp = p.add_subparsers(dest="cmd", required=True)
    def add_ingestion(a):
        a.add_argument('docs', nargs='?', default='docs')
        a.add_argument('--manifest', help='Page-to-service mapping for one merged file')
        a.add_argument('--ocr', choices=['auto','always','off'], default='auto',
                       help='Tesseract fallback on suspicious scanned pages')
        a.add_argument('--no-markitdown', action='store_true', help='Disable optional MarkItDown crosscheck')
    a = sp.add_parser('ingest', help='Index all documents and build Evidence Ledger')
    add_ingestion(a)
    a = sp.add_parser('prepare', help='One-command ingestion, evidence ledger and quality audit')
    add_ingestion(a)
    sp.add_parser('audit', help='Report extraction issues and possible conflicting claims')
    sp.add_parser('doctor', help='Read-only hardware / dependency / Ollama diagnostics')
    sp.add_parser("inspect", help="Inspect indexed service names and page extraction quality")
    sp.add_parser("models", help="List installed Ollama models")
    s = sp.add_parser("search", help="Inspect retrieval without invoking a model")
    s.add_argument("question")
    s.add_argument("--top", type=int, default=8)
    a = sp.add_parser("ask", help="Ask a single question")
    a.add_argument("question")
    sp.add_parser('chat', help='Interactive shell; /reset clears follow-up context')
    a = sp.add_parser('voice', help='Optional offline microphone question and spoken answer')
    a.add_argument('--seconds', type=int, default=6)
    a.add_argument('--whisper-model', default='small')
    a.add_argument('--speak', action='store_true', help='Read response with Windows installed Arabic voice')
    a = sp.add_parser('benchmark', help='Run model and record actual response timings on a labeled question set')
    a.add_argument('file')
    a.add_argument('--limit', type=int, default=10)
    a.add_argument('--save', default='build/benchmark.json')
    a = sp.add_parser('autotune', help='Retrieval-only ablation on human-labeled questions; no training')
    a.add_argument('file')
    a.add_argument('--save', default='build/autotune.json')
    s = sp.add_parser("eval", help="Evaluate a HUMAN-LABELLED JSONL gold set")
    s.add_argument("file")
    s.add_argument("--with-model", action="store_true")
    s.add_argument("--limit", type=int)
    s.add_argument("--save", default="")
    args = p.parse_args(argv)

    if args.cmd == 'doctor':
        from .doctor import doctor
        print(json.dumps(doctor(args.url), ensure_ascii=False, indent=2))
        return
    if args.cmd in ('ingest', 'prepare'):
        result = index_folder(args.docs, args.index, manifest=args.manifest, ocr=args.ocr,
                              use_markitdown=not args.no_markitdown)
        print(f'Indexed {len(result["documents"])} services, {sum(len(d["pages"]) for d in result["documents"])} pages, {len(result["chunks"])} chunks -> {args.index}')
        for d in result["documents"]:
            print(f'  {d["id"]}: {d["title"]} ({len(d["pages"])} pages)')
        for w in result['warnings']:
            print('WARNING:', w, file=sys.stderr)
        if args.cmd == 'prepare':
            from pathlib import Path
            report_path = Path(args.index).parent / 'evidence_audit.json'
            report = {'documents': len(result['documents']),
                      'pages': sum(len(d['pages']) for d in result['documents']),
                      'warnings': result['warnings'],
                      'extraction_reports': result['extraction_reports'],
                      'ledger': result['ledger']}
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'Quality, candidate facts & conflict report: {report_path}')
            print(f'Candidate facts: {len(result["ledger"]["facts"])}; potential conflicts: {len(result["ledger"]["potential_conflicts"])}')
            if any(not p['text'] for d in result['documents'] for p in d['pages']):
                print('CRITICAL: Some source pages are empty. Inspect OCR and source before judging.', file=sys.stderr)
        return
    if args.cmd == "models":
        client = OllamaClient("listing-only", base_url=args.url)
        print("\n".join(client.installed_models()) or "No Ollama models installed")
        return
    index = load_index(args.index)
    if args.cmd == 'audit':
        report = index.get('ledger', {})
        print(json.dumps({'warnings': index.get('warnings', []), 'ledger': report}, ensure_ascii=False, indent=2))
        return
    if args.cmd == 'autotune':
        from .retrieve import Retriever
        from pathlib import Path
        questions = [q for q in load_questions(args.file) if q.get('expected_doc')]
        if not questions:
            raise SystemExit('Autotune requires HUMAN-labeled expected_doc entries; refusing guess-based optimization')
        r = Retriever(index)
        configs = [(c, n) for c in (5000, 8500, 12000) for n in (1, 2, 3)]
        rows = []
        for chars, nserv in configs:
            hits_total = 0
            omissions = []
            for q in questions:
                hits = r.search(q['question'])
                _, pages, _ = r.context(q['question'], hits, max_chars=chars, max_services=nserv)
                if q['expected_doc'] in {p['doc_id'] for p in pages}:
                    hits_total += 1
                else:
                    omissions.append(q['question'])
            rows.append({'context_chars': chars, 'max_services': nserv,
                         'evidence_coverage': round(hits_total / len(questions), 3),
                         'misses': omissions})
        rows.sort(key=lambda x: (-x['evidence_coverage'], x['context_chars'], x['max_services']))
        result = {'warning': 'This selects retrieval evidence coverage, NOT answer accuracy. Manually inspect gold answers.',
                  'best_retrieval_config': rows[0], 'candidates': rows}
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.cmd == "inspect":
        for d in index["documents"]:
            print(f'{d["id"]} {d["title"]} ({d["file"]})')
            for page in d["pages"]:
                print(f'   {page["id"]}: {len(page["text"])} chars | {page["text"][:115].replace(chr(10), " /")}')
        for w in index.get("warnings", []):
            print("WARNING:", w)
        return
    # Search-only mode does not need Ollama at all.
    if args.cmd == "search":
        from .retrieve import Retriever
        r = Retriever(index)
        hits = r.search(args.question, top_k=args.top)
        print('Ranked services:', r.rank_services(args.question, hits))
        for h in hits:
            print(f'{h.chunk["id"]}: score={h.score:.4f} BM25={h.bm25:.2f} char={h.char:.3f} | {h.chunk["text"][:180]}')
        return
    needs_model = args.cmd in ('ask', 'chat', 'voice', 'benchmark') or (args.cmd == 'eval' and args.with_model)
    if needs_model and not args.model:
        p.error("Set BURHAN_MODEL to the exact shared model; PowerShell: $env:BURHAN_MODEL='qwen3:8b'")
    eng = None
    if needs_model:
        client = OllamaClient(args.model, base_url=args.url, context_tokens=args.num_ctx, think=args.think)
        eng = Engine(index, ollama=client, max_chars=args.context_chars,
                     max_services=args.max_services, use_schema=not args.no_schema)
    if args.cmd == "ask":
        pretty_answer(eng.ask(args.question), args.verbose)
    elif args.cmd == "chat":
        print('بُرهان جاهز. اكتب سؤالك بالعربية؛ /reset للمسح؛ /quit للخروج.')
        while True:
            try:
                q = input('سؤال > ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if q in ('/exit', '/quit', 'exit', 'quit'):
                break
            if q == '/reset':
                eng.previous_service = None
                print('تم مسح سياق الخدمة السابقة.')
                continue
            if q:
                pretty_answer(eng.ask(q), args.verbose)
    elif args.cmd == 'voice':
        from .voice import record_and_transcribe, speak_windows
        if not 1 <= args.seconds <= 30:
            p.error('--seconds must be between 1 and 30')
        print(f'Microphone recording for {args.seconds}s... speak Arabic now')
        heard = record_and_transcribe(seconds=args.seconds, model_name=args.whisper_model)
        print('Transcript:', heard['text'], '| confidence indicator:', heard['avg_logprob'])
        if not heard['text']:
            print('No intelligible speech; please type instead.')
            return
        confirm = input('Press ENTER to ask, or type a correction: ').strip()
        question = confirm or heard['text']
        result = eng.ask(question)
        pretty_answer(result, args.verbose)
        if args.speak and not speak_windows(result['answer']):
            print('Arabic system voice unavailable; answer remains visible above.')
    elif args.cmd == 'benchmark':
        from pathlib import Path
        qs = load_questions(args.file)[:args.limit]
        rows = []
        for q in qs:
            eng.previous_service = None
            a = eng.ask(q['question'])
            rows.append({'question': q['question'], 'status': a['status'], 'answer': a['answer'],
                         'sources': [x['id'] for x in a.get('sources', [])],
                         'elapsed_s': a['elapsed_s'], 'stats': a.get('ollama_stats', {})})
            print(f'{a["elapsed_s"]:.2f}s [{a["status"]}]: {q["question"]}')
        times = sorted(row['elapsed_s'] for row in rows)
        import statistics
        result = {'model': args.model, 'num_ctx': args.num_ctx, 'think': args.think,
                  'count': len(rows), 'median_seconds': statistics.median(times) if times else None,
                  'p90_seconds': times[min(len(times)-1, int(.9*len(times)))] if times else None,
                  'notes': 'Times are local measurements; manually review answer quality.', 'items': rows}
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k != 'items'}, ensure_ascii=False, indent=2))
    elif args.cmd == "eval":
        gold = load_questions(args.file)
        report = {"retrieval": retrieval_report(index, gold)}
        if args.with_model:
            report["answers"] = answer_report(eng, gold, args.limit)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.save:
            from pathlib import Path
            Path(args.save).parent.mkdir(parents=True, exist_ok=True)
            Path(args.save).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == "__main__":
    main()
