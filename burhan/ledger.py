"""Deterministic, traceable candidate facts and conservative conflict alerts.

Neither numeric extraction nor a matching citation proves entailment; this ledger is a
review aid, not a semantic judge. It never asserts that a candidate is legally binding.
"""
from __future__ import annotations
import re
from .arabic import normalize

NUMBER = re.compile(r'(?<!\w)(\d+(?:[.,]\d+)?|[٠-٩]+(?:[.,][٠-٩]+)?)(?!\w)')
CUES = {
    'fee': ('رسوم', 'الرسم', 'تكلفة', 'التكلفة', 'دينار', 'دنانير', 'مجانا', 'مجانية', 'مبلغ'),
    'duration': ('مدة', 'خلال', 'يوم', 'أيام', 'ساعة', 'ساعات', 'أسبوع', 'اسبوع', 'شهر'),
    'age': ('العمر', 'السن', 'سنة من العمر', 'عاما من العمر'),
}
COND = ('اذا', 'في حال', 'لمن', 'حسب', 'استثناء', 'باستثناء', 'معفى', 'معفي', 'لذوي', 'لغير', 'اذا كان', 'للمواطن', 'للوافد', 'للطالب')

def classify(line: str) -> str | None:
    s = normalize(line)
    # A numbered age exemption mentioning fees is an age fact, not a fee amount.
    if re.search(r'(?:عمر|سن)\s*\d+|\d+\s*(?:عاما|سنه)\s*(?:من العمر|فما فوق|فما دون)', s):
        return 'age'
    # A word like رسوم takes priority over generic references to days elsewhere on same line.
    for field in ('fee', 'age', 'duration'):
        if any(normalize(w) in s for w in CUES[field]):
            return field
    return None


def values(line: str) -> list[str]:
    s = normalize(line)
    return list(dict.fromkeys(m.group(1).replace(',', '.') for m in NUMBER.finditer(s)))


def candidate_facts(index: dict) -> list[dict]:
    facts = []
    for d in index['documents']:
        for page in d['pages']:
            lines = page['text'].splitlines()
            for line_no, line in enumerate(lines, 1):
                field = classify(line)
                nums = values(line)
                if not field or not nums:
                    continue
                n = normalize(line)
                facts.append({
                    'service_id': d['id'], 'service': d['title'], 'field': field,
                    'values': nums, 'conditional': any(normalize(w) in n for w in COND),
                    'quote': line.strip(), 'source_id': page['id'], 'page': page['number'],
                    'line': line_no, 'file': d['file'], 'confidence': 'candidate_requires_review'
                })
    return facts


def potential_conflicts(facts: list[dict]) -> list[dict]:
    """Only flag differences in same named service and field; NEVER say confirmed."""
    groups = {}
    for row in facts:
        title = normalize(row['service'])
        group = (title, row['field'], row['conditional'])
        groups.setdefault(group, []).append(row)
    out = []
    for (_, field, conditional), rows in groups.items():
        for a_i, a in enumerate(rows):
            for b in rows[a_i + 1:]:
                if a['source_id'] == b['source_id'] and a['line'] == b['line']:
                    continue
                # Require distinct documents/pages for an evidence conflict candidate.
                if a['source_id'] == b['source_id']:
                    continue
                if len(a['values']) != 1 or len(b['values']) != 1:
                    continue
                if a['values'][0] == b['values'][0]:
                    continue
                # Avoid comparing a fee (5 JOD) to service ID / law number (2026).
                # This remains a manual-review-only candidate.
                out.append({'status': 'potential_conflict_needs_review', 'field': field,
                            'service': a['service'], 'conditional': conditional,
                            'a': a, 'b': b,
                            'warning': 'Verify same applicant, fee type, currency, effective date and applicability.'})
    return out


def build_ledger(index: dict) -> dict:
    facts = candidate_facts(index)
    return {'facts': facts, 'potential_conflicts': potential_conflicts(facts),
            'warning': 'Candidate facts and conflicts require original-document review.'}


def relevant_conflicts(index: dict, question: str, page_ids: set[str]) -> list[dict]:
    from .arabic import tokens
    ledger = index.get('ledger', {})
    q = normalize(question)
    # Never inject every conflict on every question.
    relevant = []
    for c in ledger.get('potential_conflicts', []):
        if not ({c['a']['source_id'], c['b']['source_id']} & page_ids):
            continue
        if not any(normalize(w) in q for w in CUES[c['field']]):
            continue
        relevant.append(c)
    return relevant
