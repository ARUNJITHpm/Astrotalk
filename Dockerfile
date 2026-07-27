# Nithara — modular monolith (FastAPI) plus the React PWA it serves at /.
# The single image runs the API, the Celery worker, and Celery beat (command
# overridden per compose service).

# ---- Stage 1: build the frontend ----
# app-nithara/dist is a build artefact and stays gitignored, so the image has to
# produce it. Deps are installed from the lockfile alone first, keeping the npm
# layer cached across source-only changes.
FROM node:20-slim AS frontend

WORKDIR /build

COPY app-nithara/package.json app-nithara/package-lock.json ./
RUN npm ci

COPY app-nithara/ ./
# Empty base URL = same origin. The API and the app are served by one process,
# so the browser never makes a cross-origin call and no CORS layer is needed.
ENV VITE_API_BASE=""
RUN npm run build


# ---- Stage 2: build the operator console ----
# Same shape as the stage above, separate so a console-only change does not
# invalidate the consumer app's npm layer (and vice versa). Vite's `base` puts
# the output under /console-app/, which is where app/main.py mounts it.
FROM node:20-slim AS console

WORKDIR /build

COPY app-console/package.json app-console/package-lock.json ./
RUN npm ci

COPY app-console/ ./
ENV VITE_API_BASE=""
RUN npm run build


# ---- Stage 3: the app ----
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

# The frontend build, into the path app/main.py serves the SPA from. Copied
# after the source so it survives even if a stale dist/ leaks into the context.
COPY --from=frontend /build/dist ./app-nithara/dist
COPY --from=console /build/dist ./app-console/dist

EXPOSE 3000

# Default command runs the API; worker/beat services override this.
# Shell form so ${PORT} expands: HF/Render (and most PaaS) inject the port to
# bind to via $PORT; fall back to 3000 for local `docker run`.
# Migrations run first (scripts/migrate.py: stamp-or-upgrade, see its docstring)
# so the schema is current before the app takes traffic. DATABASE_URL points at
# the external managed Postgres (Neon), set as a Space secret.
CMD python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3000}
