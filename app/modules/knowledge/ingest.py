"""Build/refresh the knowledge RAG index from the seed data.

Run:  python -m app.modules.knowledge.ingest

Rebuilds the persistent dense (Chroma) index from ``seed_data.SEED_CHUNKS``.
The sparse (BM25) index is built in-memory at runtime, so it needs no ingest
step. Requires an OpenAI key (``MOCK_OPENAI=false``); otherwise it no-ops.
"""

from app.modules.knowledge.retrieval import reindex

if __name__ == "__main__":
    reindex()
