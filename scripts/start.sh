#!/usr/bin/env bash
# HF Space entrypoint: boot an in-container PostgreSQL, then run migrations + API.
#
# This lets the database live INSIDE the Hugging Face Space instead of an
# external managed host (Neon). It is the default Docker CMD; docker-compose
# overrides `command:` per service, so local dev still uses its own Postgres
# container and never runs this script.
#
# ⚠️  DATA DURABILITY: an HF Space's container disk is wiped on every rebuild
# (each git push) and on restarts. Postgres data survives ONLY if it lives on
# HF *persistent storage*, which mounts at /data. This script uses /data/pgdata
# when /data is a writable mount, and otherwise falls back to an ephemeral dir
# with a loud warning. Enable persistent storage in the Space settings to keep
# user accounts and charts across deploys.
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-tara}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-tara}"
POSTGRES_DB="${POSTGRES_DB:-tara}"

PG_BIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)"
if [ -z "${PG_BIN}" ] || [ ! -x "${PG_BIN}/postgres" ]; then
  echo "FATAL: PostgreSQL is not installed in this image." >&2
  exit 1
fi

# Pick a data directory: prefer HF persistent storage, else ephemeral (+ warn).
if [ -d /data ] && [ -w /data ]; then
  PGDATA="${PGDATA:-/data/pgdata}"
else
  PGDATA="${PGDATA:-/var/lib/postgresql/data}"
  echo "WARNING: HF persistent storage (/data) not available." >&2
  echo "         Using ephemeral ${PGDATA} — the database will RESET on every" >&2
  echo "         Space rebuild/restart. Enable persistent storage to keep data." >&2
fi
mkdir -p "${PGDATA}"

# Postgres refuses to run as root. If we're root, drop to the 'postgres' system
# user (created by the postgres apt package) via sudo; otherwise run as-is.
if [ "$(id -u)" = "0" ]; then
  chown -R postgres:postgres "${PGDATA}"
  as_pg() { sudo -u postgres "$@"; }
else
  as_pg() { "$@"; }
fi

# Initialize the cluster on first boot (empty data dir). trust auth is safe here
# because the server only listens on localhost inside the container.
if [ ! -s "${PGDATA}/PG_VERSION" ]; then
  echo "start: initializing new Postgres cluster at ${PGDATA}"
  as_pg "${PG_BIN}/initdb" -D "${PGDATA}" -U postgres --auth=trust --encoding=UTF8 >/dev/null
fi

echo "start: launching Postgres"
as_pg "${PG_BIN}/pg_ctl" -D "${PGDATA}" -w -t 60 \
  -o "-p 5432 -k ${PGDATA} -c listen_addresses=localhost" \
  -l "${PGDATA}/server.log" start

until as_pg "${PG_BIN}/pg_isready" -q -h localhost -p 5432; do
  echo "start: waiting for Postgres to accept connections..."
  sleep 1
done

# Create the app role + database if they don't exist yet (idempotent).
as_pg "${PG_BIN}/psql" -v ON_ERROR_STOP=1 -h localhost -U postgres -d postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
    CREATE ROLE ${POSTGRES_USER} LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  END IF;
END
\$\$;
SQL
if ! as_pg "${PG_BIN}/psql" -tAq -h localhost -U postgres -d postgres \
     -c "SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB}'" | grep -q 1; then
  as_pg "${PG_BIN}/psql" -v ON_ERROR_STOP=1 -h localhost -U postgres -d postgres \
    -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER}"
fi

# Point the app at the local server. This export overrides any external
# DATABASE_URL still set as a Space secret (e.g. the old Neon one).
export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"

echo "start: running migrations"
python scripts/migrate.py

echo "start: launching API on port ${PORT:-3000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3000}"
