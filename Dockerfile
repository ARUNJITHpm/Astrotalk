# Tara backend — modular monolith (FastAPI). Single image runs the API,
# the Celery worker, and Celery beat (command overridden per compose service).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build toolchain for C-extension deps that compile from source (no prebuilt
# wheel): pyswisseph builds its bundled libswe/sqlite3 with gcc. Slim base has
# no compiler, so install build-essential before pip.
# libfribidi0: lets Pillow's bundled libraqm shape complex text — required for
# correct Malayalam conjuncts on rendered cards (platform/cards.py). The
# Malayalam font itself ships in the repo (assets/fonts/).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libfribidi0 \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY . .

EXPOSE 3000

# Default command runs the API; worker/beat services override this.
# Shell form so ${PORT} expands: Render (and most PaaS) inject the port to bind
# to via $PORT; fall back to 3000 for local `docker run`.
# Migrations run first (scripts/migrate.py: stamp-or-upgrade, see its docstring)
# so the schema is current before the app takes traffic.
CMD python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3000}
