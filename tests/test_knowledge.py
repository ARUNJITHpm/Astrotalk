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
    # Vazhipadu offerings + Kerala deity profiles (both draft, reviewed=False).
    assert by_topic["vazhipadu"] == 30
    assert by_topic["deity"] == 15


def test_every_engine_star_has_a_relationship_trait():
    # The porutham reading grounds each partner's personality in this trait, so
    # every star the astrology engine can emit must resolve one.
    from app.modules.astrology_engine.swiss_ephemeris import NAKSHATRAS

    svc = _service()
    missing = [n for n in NAKSHATRAS if not svc.nakshatra_relationship(n)]
    assert missing == [], f"stars with no relationship trait: {missing}"
    assert svc.nakshatra_relationship("not-a-star") is None


def test_relationship_trait_is_folded_into_nakshatra_chunk():
    # The "how they love" facet must live inside the retrievable nakshatra chunk
    # (not a separate chunk — the nakshatra topic count is pinned at 28).
    svc = _service()
    trait = svc.nakshatra_relationship("അവിട്ടം")
    chunk = next(c for c in SEED_CHUNKS if c["id"] == "nakshatra-അവിട്ടം")
    assert trait and trait in chunk["text"]


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


def test_retrieve_vazhipadu_and_deity_queries():
    svc = _service()
    # Malayalam script, Manglish, and English must each reach the pack.
    thulabharam = svc.retrieve("തുലാഭാരം എന്താണ്?", k=3)
    assert any(c.id == "vazhipadu-thulabharam" for c in thulabharam)

    sade = svc.retrieve("ellu thiri shani saturday offering", k=3)
    assert any(c.id == "vazhipadu-ellu-thiri" for c in sade)

    deity = svc.retrieve("ഗുരുവായൂരപ്പൻ ആരാണ്?", k=3)
    assert any(c.id == "deity-krishna" for c in deity)


def test_retrieve_chovva_dosha_query():
    results = _service().retrieve("chovva dosha marriage mangal", k=3)
    assert any(c.id == "dosha-chovva" for c in results)
    # GUARDRAILS §1: dosha framing must carry agency, not doom.
    top = next(c for c in results if c.id == "dosha-chovva")
    assert "never a verdict" in top.text


def test_chunk_text_splits_at_sentences_with_overlap():
    from app.modules.knowledge.ingest import chunk_text

    text = " ".join(f"Sentence number {i} carries some astrological meaning worth keeping around." for i in range(30))
    chunks = chunk_text(text, chunk_chars=200)
    assert len(chunks) > 3
    assert all(len(c) >= 80 for c in chunks)
    # Overlap: the first sentence of chunk N+1 is the last of chunk N.
    first_of_second = chunks[1].split(".")[0]
    assert first_of_second in chunks[0]


def test_ingested_corpus_loads_and_ranks_below_curated(tmp_path, monkeypatch):
    import json as _json

    from app.modules.knowledge import corpus as corpus_mod
    from app.modules.knowledge.retrieval import HybridRetriever

    ingested = tmp_path / "ingested"
    ingested.mkdir()
    (ingested / "demo.json").write_text(_json.dumps([{
        "id": "ingested-demo-0001",
        "topic": "imported",
        "text": "Mercury retrograde is a season for review not dread, says the imported text.",
        "reviewed": False,
        "source": "demo source (test)",
    }]), encoding="utf-8")
    monkeypatch.setattr(corpus_mod, "INGESTED_DIR", ingested)

    retriever = HybridRetriever(use_dense=False)
    ids = [cid for cid, _ in retriever.search("mercury retrograde review dread", k=5)]
    assert "ingested-demo-0001" in ids  # imported chunk is retrievable...
    # ...but the curated chunk with the same vocabulary outranks it.
    assert ids.index("retrograde-mercury") < ids.index("ingested-demo-0001")
