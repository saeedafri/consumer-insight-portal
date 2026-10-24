"""Question search for the portal (and later the chatbot's search tool): SQLite FTS5 in memory, standard library only.

One document per question wording (code + text + answer labels + survey titles), ranked by BM25 then recency.
A query is understood in four steps, each reported back so the screen can say what it did:

  1. spelling   words not in the index's own vocabulary are corrected to the closest one ("holidy" → "holiday")
  2. synonyms   config/search_synonyms.yml groups expand a word or phrase ("christmas" → holiday, gift, …)
  3. words      porter-stemmed FTS5 match of every word group (AND), each group an OR of its synonyms
  4. fallback   no hit → a sentence matches on most of its words (best first); a word or two → trigram match on
                word fragments (partial words, glued words); then any word

A plain-English question ("what do people think about tariffs") drops its question words first, so it searches
for what it is about.

≈ 3,000 documents index in well under a second and a query takes about a millisecond.
"""
from __future__ import annotations

import difflib
import re
import sqlite3
import threading
from pathlib import Path

import yaml

SYNONYMS = Path(__file__).resolve().parents[1] / "config" / "search_synonyms.yml"
WORD = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
# Words that say how a question is asked, not what about: dropped when anything else is left.
FILLER_WORDS = set("""a about an and are as at be by can could did do does doing for from had has have how i if in into is it
    its me much many my of on or our people person consumers consumer shoppers shopper americans should so than that the their them
    there these they think this those to us was we were what when where which who whom why will with would you your
    feel feeling feelings opinion opinions say says said tell show find percent percentage proportion any""".split())


def load_synonyms(path: Path = SYNONYMS) -> list[list[str]]:
    if not path.exists():
        return []
    return [[str(term).lower() for term in group] for group in (yaml.safe_load(path.read_text()) or {}).get("groups", [])]


class SearchIndex:
    def __init__(self, docs: list[dict], synonyms: list[list[str]] | None = None):
        """docs: dicts with qcode, text, answers (one string), titles (one string); other keys are returned as-is."""
        self.docs = docs
        self.synonyms = load_synonyms() if synonyms is None else synonyms
        self.lock = threading.Lock()   # one in-memory connection, shared by the API's threads
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE words USING fts5(qcode, text, answers, titles, tokenize='porter unicode61')")
        self.db.execute("CREATE VIRTUAL TABLE grams USING fts5(body, tokenize='trigram')")
        rows = [(i, d["qcode"], d["text"], d.get("answers", ""), d.get("titles", "")) for i, d in enumerate(docs)]
        self.db.executemany("INSERT INTO words (rowid, qcode, text, answers, titles) VALUES (?, ?, ?, ?, ?)", rows)
        self.db.executemany("INSERT INTO grams (rowid, body) VALUES (?, ?)",
                            [(i, f"{q} {t} {a} {ti}") for i, q, t, a, ti in rows])
        self.known = {w for _, q, t, a, ti in rows for w in WORD.findall(f"{q} {t} {a} {ti}".lower()) if len(w) > 2} \
            | {w for g in self.synonyms for term in g for w in WORD.findall(term)}
        self.vocab = sorted(self.known)

    def correct(self, word: str) -> str:
        if len(word) < 4 or word.isdigit() or word in self.known:
            return word
        close = difflib.get_close_matches(word, self.vocab, n=1, cutoff=0.8)
        return close[0] if close else word

    def understand(self, query: str) -> tuple[list[list[str]], list[str], list[str]]:
        """Word groups to AND together (each an OR of alternatives), plus the corrections and expansions made."""
        words = WORD.findall(query.lower())
        words = [w for w in words if w not in FILLER_WORDS] or words
        fixed = [self.correct(w) for w in words]
        corrections = [f"{a} → {b}" for a, b in zip(words, fixed) if a != b]
        text = " ".join(fixed)
        groups, used, expansions = [], set(), []
        for group in self.synonyms:   # phrases first: "buy now pay later" is one idea, not four words
            hit = next((term for term in sorted(group, key=len, reverse=True) if re.search(rf"\b{re.escape(term)}\b", text)), None)
            if hit:
                groups.append(group)
                used.update(WORD.findall(hit))
                expansions.append(f"{hit} → {', '.join(t for t in group if t != hit)}")
        groups += [[w] for w in fixed if w not in used]
        return groups, corrections, expansions

    @staticmethod
    def _fts(groups: list[list[str]], join: str) -> str:
        term = lambda t: " ".join(f'"{w}"' + ("*" if len(w) > 3 else "") for w in WORD.findall(t))   # prefix on long words
        alt = lambda g: "(" + " OR ".join(f"({term(t)})" if " " in t else term(t) for t in g) + ")"
        return f" {join} ".join(alt(g) for g in groups if any(WORD.findall(t) for t in g))

    def search(self, query: str, limit: int = 40, offset: int = 0) -> dict:
        groups, corrections, expansions = self.understand(query)
        how, ids, total = "words", [], 0
        with self.lock:
            if groups:
                ids, total = self._match("words", self._fts(groups, "AND"), limit, offset)
                if not ids and len(groups) > 2:   # a sentence: answers that match most of it, best first
                    how, (ids, total) = "most words", self._match("words", self._fts(groups, "OR"), limit, offset)
                if not ids:
                    fragments = [w for g in groups for t in g for w in WORD.findall(t) if len(w) >= 3]
                    if fragments:
                        how, (ids, total) = "fragments", self._match("grams", " OR ".join(f'"{w}"' for w in fragments), limit, offset)
                if not ids:
                    how, (ids, total) = "any word", self._match("words", self._fts(groups, "OR"), limit, offset)
        hidden = ("answers", "titles")   # searched, but too long to send back
        return {"results": [{k: v for k, v in self.docs[i].items() if k not in hidden} for i in ids], "total": total, "understood": {"corrected": corrections, "expanded": expansions, "matched_by": how}}

    def _match(self, table: str, expr: str, limit: int, offset: int = 0) -> tuple[list[int], int]:
        """One page of matches, best first (`limit` from `offset`), and how many match in all ("51–100 of 412")."""
        if not expr:
            return [], 0
        weights = "bm25(words, 10.0, 4.0, 2.0, 1.0)" if table == "words" else "bm25(grams)"
        try:   # rank by relevance, then the latest-asked wording first among near-ties
            rows = self.db.execute(f"SELECT rowid, {weights} FROM {table} WHERE {table} MATCH ? ORDER BY 2 LIMIT ?",
                                   (expr, (offset + limit) * 3)).fetchall()
            total = self.db.execute(f"SELECT COUNT(*) FROM {table} WHERE {table} MATCH ?", (expr,)).fetchone()[0]
        except sqlite3.OperationalError:   # a stray operator in user text: treat it as no match
            return [], 0
        ranked = sorted(rows, key=lambda r: (round(r[1], 1), -_recency(self.docs[r[0]])))
        return [r[0] for r in ranked[offset:offset + limit]], total


def _recency(doc: dict) -> int:
    return int(str(doc.get("last", "0"))[:10].replace("-", "") or 0)
