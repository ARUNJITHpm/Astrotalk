"""Corpus loader (internal): curated seed chunks + ingested documents.

The knowledge base has two layers:
  1. CURATED — ``seed_data.SEED_CHUNKS``, hand-written for Tara's guardrails.
  2. INGESTED — chunks imported from approved external sources (classical
     texts, official temple pages) by ``ingest.py``, stored as JSON files in
     ``knowledge/ingested/``. Each carries a ``source`` provenance field and
     ``reviewed=False`` until the astrologer signs off (NEEDS_ASTROLOGER.md).

Retrieval treats unreviewed ingested chunks as SECOND-CLASS: their scores are
multiplied down so a curated chunk always outranks an import saying the same
thing. Flip ``reviewed`` to true (in the JSON) to lift the penalty.
"""

import json
from pathlib import Path

from app.modules.knowledge.seed_data import SEED_CHUNKS
from app.platform.logging_config import get_logger

logger = get_logger(__name__)

INGESTED_DIR = Path(__file__).parent / "ingested"

# Score multiplier for unreviewed ingested chunks (see module docstring).
IMPORT_PENALTY = 0.7


def load_corpus() -> list[dict]:
    """The full retrieval corpus: curated seeds first, then ingested files."""
    chunks: list[dict] = list(SEED_CHUNKS)
    seen = {c["id"] for c in chunks}
    if not INGESTED_DIR.exists():
        return chunks
    for path in sorted(INGESTED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("knowledge: skipping unreadable %s (%s)", path.name, exc)
            continue
        added = 0
        for c in data:
            cid = c.get("id")
            if not cid or not c.get("text") or cid in seen:
                continue
            seen.add(cid)
            chunks.append({
                "id": cid,
                "topic": c.get("topic", "imported"),
                "text": c["text"],
                "reviewed": bool(c.get("reviewed", False)),
                "source": c.get("source", path.stem),
            })
            added += 1
        logger.info("knowledge: loaded %d ingested chunk(s) from %s", added, path.name)
    return chunks


def penalized_ids(chunks: list[dict]) -> frozenset[str]:
    """Ids whose retrieval score gets IMPORT_PENALTY (unreviewed imports)."""
    return frozenset(
        c["id"] for c in chunks if c.get("source") and not c.get("reviewed")
    )
