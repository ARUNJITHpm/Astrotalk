"""Tests for the knowledge module's in-memory keyword fallback path.

These force the fallback (prefer_chroma=False) so they run regardless of whether
chromadb is installed — that fallback is what keeps the app booting without a
vector DB.
"""

from app.modules.knowledge.seed_data import SEED_CHUNKS
from app.modules.knowledge.service import KnowledgeService


def _service() -> KnowledgeService:
    return KnowledgeService(prefer_chroma=False)


def test_retrieve_finds_relevant_chunk():
    results = _service().retrieve("what does mercury retrograde mean", k=3)

    assert results
    top = results[0]
    assert top.id == "retrograde-mercury"
    assert top.score > 0


def test_retrieve_respects_k_limit():
    results = _service().retrieve("house career discipline planet", k=2)
    assert len(results) <= 2


def test_retrieve_k_zero_returns_empty():
    assert _service().retrieve("anything", k=0) == []


def test_retrieve_porutham_query():
    results = _service().retrieve("marriage compatibility porutham", k=3)
    assert any(c.topic == "porutham" for c in results)


def test_seed_chunks_are_unreviewed_placeholders():
    assert SEED_CHUNKS
    assert all(c["reviewed"] is False for c in SEED_CHUNKS)
    assert all(c["id"] and c["topic"] and c["text"] for c in SEED_CHUNKS)
