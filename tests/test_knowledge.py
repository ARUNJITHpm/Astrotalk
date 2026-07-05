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


def test_seed_chunk_ids_are_unique():
    ids = [c["id"] for c in SEED_CHUNKS]
    assert len(ids) == len(set(ids))


def test_corpus_covers_the_production_content_plan():
    """The corpus follows the content plan: full planet×house grid, all 27
    nakshatras, all 9 dashas, all 12 lagnas, plus dosha framing."""
    by_topic: dict[str, int] = {}
    for c in SEED_CHUNKS:
        by_topic[c["topic"]] = by_topic.get(c["topic"], 0) + 1
    assert by_topic["planet-in-house"] == 108
    assert by_topic["nakshatra"] == 28  # 27 profiles + the general moon-mind chunk
    assert by_topic["dasha"] >= 9
    assert by_topic["lagna"] == 12
    assert by_topic["dosha"] >= 3
    # Prashnam: basics + honesty + sankhya-basics + 12 arudha + 12 lagna-house
    # + odd/even + 8 remainders.
    assert by_topic["prashnam"] == 37


def test_retrieve_malayalam_nakshatra_query():
    # Malayalam-script query must hit the matching nakshatra profile (the
    # tokenizer is unicode-aware and chunk texts carry Malayalam terms inline).
    results = _service().retrieve("ചോതി നക്ഷത്രം എങ്ങനെയാണ്", k=3)
    assert any(c.id == "nakshatra-ചോതി" for c in results)


def test_retrieve_mahadasha_query():
    results = _service().retrieve("shani mahadasha effects saturn dasha", k=3)
    assert any(c.id == "mahadasha-shani" for c in results)


def test_retrieve_prashnam_cues():
    # The cue strings astrology_engine.prashnam emits must pull the matching
    # prashnam chunks (the texts embed those exact tokens).
    svc = _service()
    arudha = svc.retrieve("prashnam arudha മേടം", k=3)
    assert any(c.id == "prashnam-arudha-മേടം" for c in arudha)

    house = svc.retrieve("prashnam lagna house 9 trikona", k=3)
    assert any(c.id == "prashnam-lagna-house-9" for c in house)

    thamboola = svc.retrieve("prashnam thamboola remainder 5", k=3)
    assert any(c.id == "prashnam-thamboola-rem-5" for c in thamboola)


def test_retrieve_chovva_dosha_query():
    results = _service().retrieve("chovva dosha marriage mangal", k=3)
    assert any(c.id == "dosha-chovva" for c in results)
    # GUARDRAILS §1: dosha framing must carry agency, not doom.
    top = next(c for c in results if c.id == "dosha-chovva")
    assert "never a verdict" in top.text
