"""Hybrid RAG retrieval engine (internal to the knowledge module).

Modeled on the project's ``db/`` reference stack (kept locally, gitignored):
  - SPARSE: BM25 over the corpus — always available, no API key, no native
    model. This alone is a real ranking function, so retrieval works fully
    offline.
  - DENSE: OpenAI-embedded vectors in a persistent Chroma store — layered in
    only when an OpenAI key is configured (``mock_openai`` / ``mock_chroma`` off).

Both retrievers return chunk ids with normalized scores; ``search`` merges them.
Cross-encoder reranking (the reference's third stage) is intentionally omitted
for now — it can be added later without changing this interface.

We never construct a Chroma client with the default ONNX embedding function, so
this engine cannot trigger the native onnxruntime crash the old path hit.
"""

import importlib.util
import re
from pathlib import Path

from app.modules.knowledge.seed_data import SEED_CHUNKS
from app.platform.config import get_settings
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

# Unicode-aware tokenizer. ``\w`` alone is NOT enough for Malayalam: Python's
# ``re`` excludes combining marks (vowel signs ോ/ി, virama ്), which shreds
# "ചോതി" into bare consonants. Including the whole Malayalam block (U+0D00–
# U+0D7F) keeps each Malayalam word intact so BM25 matches Malayalam queries.
_WORD = re.compile(r"[\wഀ-ൿ]+", re.UNICODE)

# Minimal English stopword set. Without a reranker, BM25 alone is sensitive to
# question words ("what does ... mean"), which can drown out the real query
# terms. Dropping function words keeps sparse ranking focused on content words;
# it does not touch Malayalam tokens.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "to", "of", "in", "on", "for", "and", "or", "it", "its", "this", "that",
        "these", "those", "what", "which", "who", "whom", "how", "when", "where",
        "why", "does", "do", "did", "me", "my", "i", "you", "your", "with", "as",
        "at", "by", "from", "about", "mean", "means", "tell", "can", "will",
        "would", "should",
    }
)

# Persistent vector store lives at the project root (gitignored). Built lazily
# the first time a dense backend is available.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CHROMA_DIR = _PROJECT_ROOT / "knowledge_vectordb"
_COLLECTION = "tara_knowledge"

# Blend weight for dense vs. sparse when both are present.
_DENSE_WEIGHT = 0.5
_SPARSE_WEIGHT = 0.5


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


class HybridRetriever:
    """BM25 (always) + dense Chroma (when configured), merged by score.

    ``use_dense=False`` forces sparse-only — used by tests and by any caller
    that wants a guaranteed offline, deterministic path.
    """

    def __init__(self, use_dense: bool = True) -> None:
        self._ids = [c["id"] for c in SEED_CHUNKS]
        self._bm25 = self._build_bm25()
        self._dense = self._build_dense() if use_dense else None
        if self._dense is None:
            logger.info("knowledge: sparse-only retrieval (BM25); no dense backend.")
        else:
            logger.info("knowledge: hybrid retrieval (BM25 + Chroma vectors).")

    # ---- backend setup ----

    def _build_bm25(self):
        from rank_bm25 import BM25Okapi

        corpus = [_tokenize(c["text"] + " " + c["topic"]) for c in SEED_CHUNKS]
        return BM25Okapi(corpus)

    def _build_dense(self):
        settings = get_settings()
        if settings.mock_chroma or settings.mock_openai or not settings.openai_api_key:
            return None
        if importlib.util.find_spec("langchain_chroma") is None:
            return None
        try:
            from langchain_chroma import Chroma
            from langchain_openai import OpenAIEmbeddings

            embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
            )
            store = Chroma(
                collection_name=_COLLECTION,
                embedding_function=embeddings,
                persist_directory=str(_CHROMA_DIR),
            )
            # (Re)seed whenever the corpus size changed; ids make the upsert
            # idempotent, so growing the seed data refreshes the index in place.
            if store._collection.count() != len(SEED_CHUNKS):
                store.add_texts(
                    texts=[c["text"] for c in SEED_CHUNKS],
                    metadatas=[
                        {"chunk_id": c["id"], "topic": c["topic"], "reviewed": c["reviewed"]}
                        for c in SEED_CHUNKS
                    ],
                    ids=[c["id"] for c in SEED_CHUNKS],
                )
            return store
        except Exception as exc:  # pragma: no cover - depends on network/optional dep
            logger.warning("knowledge: dense backend unavailable (%s); sparse-only.", exc)
            return None

    # ---- retrieval ----

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        """Return up to ``k`` ``(chunk_id, score)`` pairs, best first."""
        sparse = self._search_bm25(query, k)
        dense = self._search_dense(query, k) if self._dense is not None else {}

        combined: dict[str, float] = {}
        for cid in set(sparse) | set(dense):
            s = sparse.get(cid, 0.0)
            d = dense.get(cid, 0.0)
            combined[cid] = _DENSE_WEIGHT * d + _SPARSE_WEIGHT * s if dense else s

        ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
        return [(cid, score) for cid, score in ranked[:k] if score > 0]

    def _search_bm25(self, query: str, k: int) -> dict[str, float]:
        tokens = _tokenize(query)
        if not tokens:
            return {}
        scores = self._bm25.get_scores(tokens)
        top = max(scores) if len(scores) else 0.0
        if top <= 0:
            return {}
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        # Normalize to [0, 1] so sparse and dense scores are comparable.
        return {self._ids[i]: scores[i] / top for i in order if scores[i] > 0}

    def _search_dense(self, query: str, k: int) -> dict[str, float]:
        try:
            results = self._dense.similarity_search_with_relevance_scores(query, k=k)
        except Exception as exc:  # pragma: no cover - depends on backend availability
            logger.warning("knowledge: dense query failed (%s); sparse-only.", exc)
            return {}
        out: dict[str, float] = {}
        for doc, score in results:
            cid = doc.metadata.get("chunk_id")
            if cid is not None and score > 0:
                out[cid] = float(score)
        return out


def reindex() -> None:
    """Rebuild the persistent dense index from the current seed data.

    Run after changing the knowledge base: ``python -m app.modules.knowledge.ingest``.
    No-op (with a log line) when no dense backend is configured.
    """
    import shutil

    if _CHROMA_DIR.exists():
        shutil.rmtree(_CHROMA_DIR)
    retriever = HybridRetriever(use_dense=True)
    if retriever._dense is None:
        logger.info("knowledge.reindex: no dense backend configured; nothing to build.")
    else:
        logger.info("knowledge.reindex: dense index rebuilt at %s.", _CHROMA_DIR)
