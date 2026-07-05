"""Ingest an approved document into the knowledge corpus / rebuild the index.

    # import a document (PDF / .txt / .md) as retrieval chunks:
    python -m app.modules.knowledge.ingest <file> --topic prasna-marga \
        --source "Prasna Marga (public domain translation, archive.org)"

    # rebuild the persistent dense (Chroma) index from the current corpus:
    python -m app.modules.knowledge.ingest --reindex

Document ingestion splits the text into ~600-character chunks at sentence-ish
boundaries, tags every chunk with ``source`` provenance and ``reviewed=False``,
and writes ``knowledge/ingested/<slug>.json`` — which ``corpus.load_corpus()``
picks up on the next app start. Unreviewed imports rank BELOW curated chunks
until an astrologer flips ``reviewed`` (see NEEDS_ASTROLOGER.md).

ONLY ingest sources that are public-domain / openly licensed AND compatible
with GUARDRAILS.md §1 — no fear-selling astrology content, ever. When in
doubt, don't ingest; curate by hand instead.
"""

import argparse
import json
import re
from pathlib import Path

from app.modules.knowledge.corpus import INGESTED_DIR

_CHUNK_CHARS = 600
_OVERLAP_SENTENCES = 1

# Sentence-ish boundaries for English and Malayalam prose.
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+|\n{2,}")


def extract_text(path: Path) -> str:
    """Plain text from a .pdf / .txt / .md file."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # lazy: optional dependency

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_text(text: str, chunk_chars: int = _CHUNK_CHARS) -> list[str]:
    """Split prose into ~chunk_chars pieces at sentence boundaries.

    Adjacent chunks share ``_OVERLAP_SENTENCES`` so a thought split across a
    boundary is still retrievable from either side.
    """
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in sentences:
        if size + len(sentence) > chunk_chars and current:
            chunks.append(" ".join(current))
            current = current[-_OVERLAP_SENTENCES:]
            size = sum(len(s) for s in current)
        current.append(sentence)
        size += len(sentence)
    if current:
        chunks.append(" ".join(current))
    # Drop fragments too small to carry meaning (page numbers, headers).
    return [c for c in chunks if len(c) >= 80]


def ingest(path: Path, topic: str, source: str, slug: str | None = None) -> Path:
    """Extract → chunk → write knowledge/ingested/<slug>.json; returns the path."""
    slug = slug or re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    pieces = chunk_text(extract_text(path))
    if not pieces:
        raise SystemExit(f"No usable text found in {path}")
    data = [
        {
            "id": f"ingested-{slug}-{i:04d}",
            "topic": topic,
            "text": piece,
            "reviewed": False,
            "source": source,
        }
        for i, piece in enumerate(pieces)
    ]
    INGESTED_DIR.mkdir(exist_ok=True)
    out = INGESTED_DIR / f"{slug}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a document into the knowledge corpus, or --reindex."
    )
    parser.add_argument("file", type=Path, nargs="?", help="PDF / .txt / .md to ingest")
    parser.add_argument("--topic", help='corpus topic tag, e.g. "prasna-marga"')
    parser.add_argument("--source",
                        help="provenance: title + license + URL, shown to reviewers")
    parser.add_argument("--slug", default=None, help="output name (defaults to file stem)")
    parser.add_argument("--reindex", action="store_true",
                        help="rebuild the persistent dense (Chroma) index and exit")
    args = parser.parse_args()

    if args.reindex:
        from app.modules.knowledge.retrieval import reindex

        reindex()
        return
    if not (args.file and args.topic and args.source):
        parser.error("document ingestion needs <file> --topic and --source")
    out = ingest(args.file, args.topic, args.source, args.slug)
    n = len(json.loads(out.read_text(encoding="utf-8")))
    print(f"ingested {n} chunk(s) → {out}")
    print("Chunks are reviewed=False and rank below curated content until an "
          "astrologer approves them (NEEDS_ASTROLOGER.md). Run --reindex if "
          "the dense index is enabled.")


if __name__ == "__main__":
    main()
