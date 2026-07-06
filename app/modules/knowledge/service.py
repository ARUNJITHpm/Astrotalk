"""Public service for the knowledge module — RAG retrieval over the interpretation base.

This is the ONLY surface other modules may depend on (AGENTS.md); chat calls
retrieve() to ground replies in real interpretation text.

Retrieval is hybrid (see ``retrieval.HybridRetriever``): BM25 sparse — always on,
no API key — plus OpenAI-embedded Chroma vectors when a key is configured. The
sparse path guarantees the rest of the app keeps working with no vector DB and
no network. Cross-encoder reranking is deferred (added later).
"""

from app.modules.knowledge.retrieval import HybridRetriever
from app.modules.knowledge.schemas import KnowledgeChunk
from app.platform.logging_config import get_logger

logger = get_logger(__name__)


class KnowledgeService:
    def __init__(self, prefer_chroma: bool = True) -> None:
        # prefer_chroma keeps the historical name/flag: True = hybrid (dense if
        # available), False = sparse-only (deterministic, offline).
        self._retriever = HybridRetriever(use_dense=prefer_chroma)
        # The retriever's corpus = curated seeds + ingested documents.
        self._by_id = {c["id"]: c for c in self._retriever._corpus}

    def nakshatra_relationship(self, nakshatram_ml: str) -> str | None:
        """The compatibility-facing ("how they love") trait for a birth star.

        Keyed by the Malayalam name the astrology engine emits. Returns ``None``
        for an unknown star so callers degrade gracefully. Chat uses this to
        ground a porutham reading in each partner's own nakshatra.
        """
        from app.modules.knowledge.seed_data import relationship_trait

        return relationship_trait(nakshatram_ml)

    def retrieve(self, query: str, k: int = 3) -> list[KnowledgeChunk]:
        """Return up to ``k`` interpretation chunks most relevant to ``query``."""
        if k <= 0:
            return []
        hits = self._retriever.search(query, k)
        chunks: list[KnowledgeChunk] = []
        for chunk_id, score in hits:
            seed = self._by_id.get(chunk_id)
            if seed is None:  # pragma: no cover - index/seed drift guard
                continue
            chunks.append(
                KnowledgeChunk(
                    id=seed["id"],
                    topic=seed["topic"],
                    text=seed["text"],
                    score=score,
                    reviewed=seed["reviewed"],
                )
            )
        return chunks
