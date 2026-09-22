"""BM25 retrieval over the local knowledge base — standard library only.

Deliberately not a vector store. The corpus is a few dozen short Turkish
passages, so lexical ranking is both accurate enough and free of the things
that would hurt here: no model download, no embedding service, no cold start,
and nothing to fetch at runtime. That matters because the whole point of this
module is to answer when the network is gone.

Turkish needs two accommodations that plain BM25 does not give you:

* **Diacritic folding.** Users type "kar" for "kâr" and "gecikme zammi" for
  "zammı". Both sides are folded, reusing the same table the expense
  classifier uses.
* **Suffix-tolerant matching.** Turkish is agglutinative: "vergisi",
  "vergiden", "vergiyi" and "vergi" are the same concept, and a query term
  rarely appears in the exact surface form the document used. Terms are
  therefore also indexed by a truncated prefix, so a query token matches a
  document token that shares a stem.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.services.expense_classifier import _fold

# BM25 parameters. k1 controls term-frequency saturation, b the strength of
# length normalisation; these are the standard defaults and the corpus is far
# too small to justify tuning them.
_K1 = 1.5
_B = 0.75

# Turkish tokens shorter than this are not truncated — "kdv" and "sgk" must
# stay intact. Longer ones are cut so inflected forms collapse to one key.
_STEM_LEN = 5

_TOKEN_RE = re.compile(r"[0-9a-zçğıöşü]+")

# High-frequency Turkish function words carry no retrieval signal. Kept short
# on purpose: an over-eager stopword list silently deletes real queries.
# Folded at definition time — tokenize() folds before it consults this set, so
# an unfolded "nasıl" here would never match the "nasil" the tokenizer produces
# and the word would sail straight through as a content term.
_STOPWORDS = frozenset(
    _fold(w)
    for w in """
    ve veya ile ama fakat ancak ise de da ki mi mu mü mı mü için gibi kadar
    daha en çok az bir bu şu o ben sen biz siz onlar benim bizim
    ne nasıl neden niçin hangi kim nerede zaman acaba
    var yok olan olarak oldu olur olmak olacak
    beni bana bende benden onu ona onda ondan
    şey şeyler bunu buna bunun sonra önce nedir
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Fold, split, drop stopwords, and collapse inflected forms to a stem."""
    folded = _fold(text or "")
    out: list[str] = []
    for raw in _TOKEN_RE.findall(folded):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        out.append(raw if len(raw) <= _STEM_LEN else raw[:_STEM_LEN])
    return out


@dataclass(frozen=True)
class Hit:
    """One ranked result.

    `score` is raw BM25 and decides the ordering. `ratio` is idf-weighted
    query coverage in [0, 1] and is what callers threshold on — see
    `Bm25Index._coverage` for why the two jobs need different numbers.
    """

    key: str
    score: float
    ratio: float


class Bm25Index:
    """Immutable BM25 index over (key, text) pairs, built once at import."""

    def __init__(self, entries: list[tuple[str, str]]) -> None:
        self._keys: list[str] = []
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []

        for key, text in entries:
            tokens = tokenize(text)
            self._keys.append(key)
            self._tf.append(Counter(tokens))
            self._len.append(len(tokens))

        self._n = len(self._keys)
        self._avgdl = (sum(self._len) / self._n) if self._n else 0.0

        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())

        # Lucene-style idf: always positive, so a term present in every
        # document contributes ~0 rather than dragging a score negative.
        self._idf = {
            term: math.log(1 + (self._n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }
        # What a term occurring in no document would score. Unknown query words
        # count against coverage at this weight rather than being ignored.
        self._unseen_idf = math.log(1 + (self._n + 0.5) / 0.5)

    def _score_doc(self, i: int, q_tokens: list[str]) -> float:
        tf, dl = self._tf[i], self._len[i]
        if not dl:
            return 0.0
        norm = _K1 * (1 - _B + _B * dl / self._avgdl) if self._avgdl else _K1
        total = 0.0
        for term in q_tokens:
            f = tf.get(term)
            if not f:
                continue
            total += self._idf.get(term, 0.0) * (f * (_K1 + 1)) / (f + norm)
        return total

    def _coverage(self, i: int, q_terms: set[str], demand: float) -> float:
        """How much of the query's information content this document covers.

        BM25 is the right ranker but the wrong number to threshold on: its
        magnitude moves with query length and term rarity, so one fixed cutoff
        cannot mean the same thing for "kdv" and for a ten-word sentence.
        Coverage is idf-weighted and bounded to [0, 1], so a threshold is a
        statement about *how much of the question was understood*.

        Words the corpus has never seen stay in the denominator, weighted as
        if maximally rare. Dropping them instead looks tempting — they are
        unanswerable either way — but it makes a query that is mostly unknown
        score 1.0 off a single incidental hit: "Kedi besleyebilir miyim?"
        matched the hiring entry on "miyim" alone and scored perfectly.
        Keeping them means an answer must account for most of the question.
        """
        if not demand:
            return 0.0
        tf = self._tf[i]
        matched = sum(self._idf[t] for t in q_terms if t in tf)
        return matched / demand

    def search(self, query: str, k: int = 3) -> list[Hit]:
        q_tokens = tokenize(query)
        if not q_tokens or not self._n:
            return []
        q_terms = set(q_tokens)
        demand = sum(self._idf.get(t, self._unseen_idf) for t in q_terms)
        scored = [
            Hit(self._keys[i], s, self._coverage(i, q_terms, demand))
            for i in range(self._n)
            if (s := self._score_doc(i, q_tokens)) > 0
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]
