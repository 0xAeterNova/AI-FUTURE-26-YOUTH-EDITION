"""Zero-embedding Arabic hybrid search optimized for 10-20 short pages."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import math
from .arabic import normalize, tokens, character_ngrams

@dataclass
class Hit:
    chunk: dict
    score: float
    bm25: float
    char: float

class Retriever:
    def __init__(self, index: dict):
        self.index = index
        self.docs = {d["id"]: d for d in index["documents"]}
        self.chunks = index["chunks"]
        self.term_counts = [Counter(tokens(c["text"])) for c in self.chunks]
        self.char_counts = [Counter(character_ngrams(c["text"])) for c in self.chunks]
        self.df = Counter()
        self.cdf = Counter()
        for row in self.term_counts:
            self.df.update(row.keys())
        for row in self.char_counts:
            self.cdf.update(row.keys())
        self.avg_length = (sum(sum(row.values()) for row in self.term_counts) / max(len(self.chunks), 1))
        self.char_norms = [math.sqrt(sum((v * self._idf(g, self.cdf))**2 for g, v in row.items())) for row in self.char_counts]

    def _idf(self, term: str, df: Counter) -> float:
        n = max(1, len(self.chunks))
        return math.log(1 + (n - df.get(term, 0) + .5) / (df.get(term, 0) + .5))

    def _bm25(self, q: list[str], i: int) -> float:
        counter = self.term_counts[i]
        dl = sum(counter.values())
        score = 0.0
        for w in set(q):
            freq = counter[w]
            if freq:
                score += self._idf(w, self.df) * freq * 2.2 / (freq + 1.2 * (.25 + .75 * dl / max(1, self.avg_length)))
        return score

    def _char_cosine(self, q: Counter, i: int, qnorm: float) -> float:
        if not qnorm or not self.char_norms[i]:
            return 0.0
        score = 0
        row = self.char_counts[i]
        for ng, count in q.items():
            if ng in row:
                idf = self._idf(ng, self.cdf)
                score += count * row[ng] * idf * idf
        return score / (qnorm * self.char_norms[i])

    @staticmethod
    def _rrf(raw: list[float]) -> list[float]:
        order = sorted(range(len(raw)), key=lambda i: raw[i], reverse=True)
        # Only positive matches count. Rank fusion limits dominance of repeated boilerplate.
        out = [0.0] * len(raw)
        for rank, i in enumerate(order, 1):
            if raw[i] > 0:
                out[i] = 1.0 / (20 + rank)
        return out

    def search(self, question: str, top_k: int = 16) -> list[Hit]:
        if not self.chunks:
            return []
        qwords = tokens(question, expand=True)
        grams = Counter(character_ngrams(question))
        qnorm = math.sqrt(sum((v * self._idf(k, self.cdf)) ** 2 for k, v in grams.items()))
        bm = [self._bm25(qwords, i) for i in range(len(self.chunks))]
        ch = [self._char_cosine(grams, i, qnorm) for i in range(len(self.chunks))]
        bm_ranks, ch_ranks = self._rrf(bm), self._rrf(ch)
        qnormed = normalize(question)
        hits = []
        for i, c in enumerate(self.chunks):
            doc = self.docs[c["doc_id"]]
            title = normalize(doc["title"])
            title_terms = [w for w in tokens(title) if len(w) > 2]
            found = len([w for w in title_terms if w in qnormed])
            # Boost descriptive titles only when at least 2 distinctive terms match.
            title_boost = min(.05, .015 * found) if found >= 2 else 0.0
            score = bm_ranks[i] + ch_ranks[i] + title_boost
            if score > 0:
                hits.append(Hit(c, score, bm[i], ch[i]))
        return sorted(hits, key=lambda h: (-h.score, -h.bm25, h.chunk["id"]))[:top_k]

    def rank_services(self, question: str, hits: list[Hit], preferred: str | None = None) -> list[tuple[str, float]]:
        scores = {}
        normalized = normalize(question)
        for h in hits:
            doc_id = h.chunk["doc_id"]
            scores[doc_id] = max(scores.get(doc_id, 0.0), h.score)
        for d in self.index["documents"]:
            title = normalize(d["title"])
            if len(title) >= 8 and title in normalized:
                scores[d["id"]] = scores.get(d["id"], 0) + .12
            if preferred == d["id"]:
                scores[d["id"]] = scores.get(d["id"], 0) + .09
        return sorted(scores.items(), key=lambda pair: -pair[1])

    @staticmethod
    def is_global_question(question: str) -> bool:
        q = normalize(question)
        return any(v in q for v in (
            "جميع الخدمات", "كل الخدمات", "كافه الخدمات", "اي الخدمات",
            "اي من الخدمات", "قارن الخدمات", "قارن بين الخدمات",
            "من بين الخدمات", "الخدمات المتاحه", "قائمه الخدمات"))

    @staticmethod
    def _topic_words(question: str) -> list[str]:
        from .arabic import SYNONYMS
        qt = set(tokens(question, expand=False))
        words = set()
        for group in SYNONYMS:
            normalized = {normalize(x) for x in group}
            if qt & normalized:
                words |= normalized
        return list(words) or tokens(question)[:8]

    def _global_context(self, question: str, max_chars: int):
        """Topic-specific evidence ledger across all services, for cross-service questions."""
        pages = [p | {"title": d["title"], "file": d["file"], "doc_id": d["id"]}
                 for d in self.index["documents"] for p in d["pages"] if p["text"]]
        entire = sum(len(p["text"]) + 90 for p in pages)
        if entire <= max_chars:
            return "\n\n".join(f'[SOURCE {p["id"]}] {p["title"]}\n{p["text"]}' for p in pages), pages
        topic = self._topic_words(question)
        blocks = []
        for p in pages:
            lines = p["text"].splitlines()
            selected = set()
            for i, line in enumerate(lines):
                nl = normalize(line)
                if any(word in nl for word in topic):
                    selected.update(range(max(0, i-1), min(len(lines), i+2)))
            selected.add(0)
            snippet = "\n".join(lines[i] for i in sorted(selected))
            blocks.append((p, f'[SOURCE {p["id"]}] {p["title"]}\n{snippet}'))
        out, used, included = [], 0, []
        for p, block in blocks:
            if used + len(block) > max_chars and out:
                continue
            out.append(block[:max_chars-used])
            included.append(p)
            used += len(out[-1])
        return "\n\n".join(out), included

    def context(self, question: str, hits: list[Hit], preferred: str | None = None,
                max_chars: int = 12000, max_services: int = 2) -> tuple[str, list[dict], list[tuple[str, float]]]:
        """Prefer whole service pages, then back off to localized evidence when too large."""
        ranks = self.rank_services(question, hits, preferred=preferred)
        if self.is_global_question(question):
            content, pages = self._global_context(question, max_chars)
            return content, pages, ranks
        # A single clearly named service should not be diluted by unrelated services.
        explicit = [d for d in self.index["documents"] if len(normalize(d["title"])) >= 8 and normalize(d["title"]) in normalize(question)]
        if len(explicit) == 1 and not any(w in normalize(question) for w in ("قارن", "الفرق", "بين خدم", "مقارنه")):
            selected = [explicit[0]["id"]]
        else:
            selected = [did for did, _ in ranks[:max_services]]
        if not selected:
            return "", [], ranks
        pages = [p | {"title": d["title"], "file": d["file"], "doc_id": d["id"]}
                 for did in selected for d in [self.docs[did]] for p in d["pages"] if p["text"]]
        # Per-page references; no page numbers are invented for DOCX/text.
        whole_size = sum(len(p["text"]) + 100 for p in pages)
        if whole_size <= max_chars:
            return "\n\n".join(f'[SOURCE {p["id"]}] {p["title"]} | file={p["file"].split("/")[-1]} | page={p["number"]}\n{p["text"]}' for p in pages), pages, ranks
        ordered = [h for h in hits if h.chunk["doc_id"] in selected]
        excerpts = []
        included_pages = {}
        used = 0
        for h in ordered:
            chunk = h.chunk
            pg = next((p for p in pages if p["id"] == chunk["page_id"]), None)
            if pg is None:
                continue
            snippet = f'[SOURCE {pg["id"]}] {pg["title"]} | page={pg["number"]}\n{chunk["text"]}'
            if used + len(snippet) > max_chars and excerpts:
                continue
            excerpts.append(snippet[:max_chars-used])
            included_pages[pg["id"]] = pg
            used += min(len(snippet), max_chars-used)
            if used >= max_chars:
                break
        return "\n\n".join(excerpts), list(included_pages.values()), ranks
