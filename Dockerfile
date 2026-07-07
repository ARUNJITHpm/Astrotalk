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
# postgresql + sudo: the HF Space runs its own PostgreSQL inside this container
# (see scripts/start.sh), so the database lives on the Space instead of an
# external managed host. sudo lets the root entrypoint drop to the 'postgres'
# user, which the server requires. Not used by docker-compose (external PG).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libfribidi0 postgresql sudo \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY . .

EXPOSE 3000

# Default command (HF Space): boot the in-container Postgres, then migrate +
# serve. scripts/start.sh handles the data dir (HF /data persistent storage),
# cluster init, role/db creation, and sets DATABASE_URL to the local server.
# docker-compose overrides `command:` per service, so this is HF-only.
CMD ["bash", "scripts/start.sh"]
