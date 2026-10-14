"""Small manual gold-set evaluation, never model-generated ground truth."""
from __future__ import annotations
import json
from pathlib import Path
from .arabic import normalize
from .retrieve import Retriever


def load_questions(file: str) -> list[dict]:
    out = []
    for n, line in enumerate(Path(file).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if "question" not in obj:
            raise ValueError(f"Line {n} missing question")
        out.append(obj)
    return out


def retrieval_report(index: dict, questions: list[dict]) -> dict:
    r = Retriever(index)
    rows = []
    correct1 = correct2 = correct3 = 0
    known = 0
    for q in questions:
        expected = q.get("expected_doc", "")
        hits = r.search(q["question"])
        docs = [did for did, _ in r.rank_services(q["question"], hits)]
        if expected:
            known += 1
            correct1 += int(expected in docs[:1])
            correct2 += int(expected in docs[:2])
            correct3 += int(expected in docs[:3])
        rows.append({"question": q["question"], "expected": expected, "ranked_docs": docs[:3],
                     "retrieval_hit1": bool(expected and expected in docs[:1]),
                     "retrieval_hit2": bool(expected and expected in docs[:2])})
    return {"with_labels": known, "hit_at_1": round(correct1/known, 3) if known else None,
            "hit_at_2": round(correct2/known, 3) if known else None,
            "hit_at_3": round(correct3/known, 3) if known else None, "items": rows}


def answer_report(engine, questions: list[dict], limit: int | None = None) -> dict:
    out = []
    for q in questions[:limit]:
        # Prevent evaluation order carrying previous-service state.
        engine.previous_service = None
        result = engine.ask(q["question"])
        expect = q.get("expected_answer_contains", [])
        prohibited = q.get("must_not_contain", [])
        answer_norm = normalize(result["answer"])
        out.append({'question': q['question'], 'expected_status': q.get('expected_status'),
                    'status_matches': result['status'] == q['expected_status'] if q.get('expected_status') else None,
                    "status": result["status"],
                    "answer": result["answer"], "citations": result["citations"],
                    "elapsed_s": result["elapsed_s"],
                    "contains_required": (all(normalize(word) in answer_norm for word in expect) if expect else None),
                    "avoids_forbidden": (all(normalize(word) not in answer_norm for word in prohibited) if prohibited else None)})
    judged = [row['status_matches'] for row in out if row.get('status_matches') is not None]
    return {'count': len(out),
            'labeled_status_count': len(judged),
            'status_accuracy': round(sum(judged) / len(judged), 3) if judged else None,
            'items': out}
