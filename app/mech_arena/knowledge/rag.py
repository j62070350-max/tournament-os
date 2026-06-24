"""
BM25-based Retrieval-Augmented Generation for the Mech Arena knowledge base.

No external vector database required — pure Python, runs in-memory.
Scales comfortably to thousands of markdown files.

BM25 parameters:
    k1 = 1.5  (term-frequency saturation)
    b  = 0.75 (document-length normalisation)
"""
import logging
import math
import re
from collections import defaultdict
from pathlib import Path

from .loader import KnowledgeChunk, load_knowledge_chunks

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset([
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
    "and", "or", "but", "with", "this", "that", "are", "was", "be", "as",
    "by", "from", "have", "has", "had", "do", "does", "did", "not", "can",
    "will", "i", "you", "my", "your", "we", "they", "he", "she", "what",
    "how", "when", "where", "which", "so", "if", "its", "than", "then",
    "me", "him", "her", "up", "out", "use", "get", "also", "just",
])

_BM25_K1 = 1.5
_BM25_B = 0.75


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, remove stopwords and short tokens."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


class KnowledgeBase:
    """
    In-memory BM25 knowledge base.

    Usage::

        kb = KnowledgeBase("knowledge")
        kb.load()                          # call once at startup
        chunks = kb.search("atlas build")  # returns list[KnowledgeChunk]
        kb.reload()                        # hot-reload from disk
    """

    def __init__(self, knowledge_dir: str | Path = "knowledge") -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self._chunks: list[KnowledgeChunk] = []
        # term → list of (doc_index, bm25_weight)
        self._index: dict[str, list[tuple[int, float]]] = defaultdict(list)
        self._loaded = False

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load all knowledge files and build the BM25 index. Call once at startup."""
        self._chunks = load_knowledge_chunks(self.knowledge_dir)
        self._build_index(self._chunks)
        self._loaded = True

    def reload(self) -> int:
        """
        Hot-reload knowledge files from disk without restarting the bot.
        Returns the new total chunk count.
        """
        self._chunks = []
        self._index = defaultdict(list)
        self._loaded = False
        self.load()
        return len(self._chunks)

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeChunk]:
        """
        Return the top_k most relevant chunks for *query* using BM25 scoring.
        Returns an empty list if the knowledge base is empty or not loaded.
        """
        if not self._loaded or not self._chunks:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = defaultdict(float)
        for token in query_tokens:
            for doc_idx, weight in self._index.get(token, []):
                scores[doc_idx] += weight

        if not scores:
            return []

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [self._chunks[idx] for idx, _ in ranked]

    @property
    def stats(self) -> dict:
        """Return a summary dict suitable for Discord embeds."""
        return {
            "chunks": len(self._chunks),
            "files": len({c.source for c in self._chunks}),
            "categories": sorted({c.category for c in self._chunks}),
            "index_terms": len(self._index),
            "loaded": self._loaded,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_index(self, chunks: list[KnowledgeChunk]) -> None:
        """Construct the BM25 inverted index from *chunks*."""
        self._index = defaultdict(list)

        # Step 1: per-document term frequencies + lengths
        tf_per_doc: list[dict[str, int]] = []
        doc_lengths: list[int] = []

        for chunk in chunks:
            tokens = _tokenize(chunk.content + " " + chunk.title)
            tf: dict[str, int] = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            tf_per_doc.append(dict(tf))
            doc_lengths.append(len(tokens))

        if not doc_lengths:
            return

        avg_len = sum(doc_lengths) / len(doc_lengths)
        N = len(chunks)

        # Step 2: document frequency per term
        df: dict[str, int] = defaultdict(int)
        for tf in tf_per_doc:
            for term in tf:
                df[term] += 1

        # Step 3: compute BM25 score for each (term, doc) pair and store
        for doc_idx, (tf, doc_len) in enumerate(zip(tf_per_doc, doc_lengths)):
            norm = _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / max(avg_len, 1))
            for term, freq in tf.items():
                idf = math.log((N - df[term] + 0.5) / (df[term] + 0.5) + 1)
                score = idf * (freq * (_BM25_K1 + 1)) / (freq + norm)
                self._index[term].append((doc_idx, score))

        logger.info(
            "BM25 index built: %d chunks, %d unique terms, avg_len=%.1f",
            N, len(self._index), avg_len,
        )
