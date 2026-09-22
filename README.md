# Muhai

AI-powered accounting & finance OS for Turkish SMEs.
TEKNOFEST 2026 Financial Technologies · Team Nasimi BHOS · Team ID 821808 ·
Baku Higher Oil School.

---

## Architecture

Muhai is self-hosted. One Docker Compose stack holds the whole system, and it
depends on no third-party service to run.

```
  Browser (React)
        │
        │  nginx serves the bundle and proxies /api — one origin, no CORS
        ▼
  FastAPI  ──────────────▶  PostgreSQL 15   system of record
     │                      Redis 7         Celery broker
     │
     └── 2026 tax engine · Muhai Score · Prophet forecast · payroll
         Tesseract OCR · assistant (Gemini online, local BM25 offline)
```

The API has two halves. `/api/workspace` is the data layer: company profile,
invoices, transactions, products, employees and tax obligations, all scoped to
the signed-in account's company by the database itself. `/api/compute` is a
stateless calculation layer — it reads no table and is a pure function of the
snapshot posted to it.

Sessions are JWTs signed by the API and verified against the same secret.
Passwords are bcrypt hashes in Postgres.

## Running it

Docker is the only prerequisite.

```bash
cp .env.example .env         # then set SECRET_KEY: openssl rand -hex 32
docker compose up -d --build
```

That is the **development** stack: `docker-compose.override.yml` applies
automatically and adds source bind-mounts, `--reload`, and Postgres/Redis on
localhost. The API is on `:8000`.

The frontend runs outside Docker in development, because Vite's dev server is
the point:

```bash
npm --prefix web install
npm --prefix web run dev     # :5173
```

To see the production build instead: `docker compose --profile ui up -d web`,
then `http://localhost`.

Health check:

```bash
curl http://localhost:8000/health     # -> {"status":"healthy"}
```

Containers carry `restart: unless-stopped`, so after a reboot opening Docker
Desktop restores the stack — no compose command needed.

## Deploying

See [docs/DEPLOY.md](docs/DEPLOY.md). Short version, on the VPS:

```bash
cp .env.example .env         # set SECRET_KEY and POSTGRES_PASSWORD
docker compose -f docker-compose.yml up -d --build
```

The `-f` is what keeps the development override out of a production run.

## Tests

Dev dependencies are deliberately absent from the runtime image, so install
them into the running container once after a rebuild:

```bash
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec backend python -m pytest
```

## Layout

```
backend/            FastAPI — data + compute API, Alembic migrations
web/                Vite + React 18 frontend (src/, own package.json)
docs/               DEPLOY.md, RECOVERY.md, TEKNOFEST material
db_backup/          pg_dump of an earlier development database
docker-compose.yml            the deployable stack
docker-compose.override.yml   development layer, applied automatically
.env.example                  every setting the stack has
```

## Configuration

`.env` at the repository root configures the entire stack; the containers read
nothing else. `backend/.env` exists only for running the API on a workstation
outside Docker, and `web/.env.local` only for the Vite dev server.

`SECRET_KEY` is required — Compose refuses to start without it. Sessions are
signed with it, so changing it signs everyone out.
