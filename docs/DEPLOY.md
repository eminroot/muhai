# Deploying Muhai on a VPS

Everything Muhai needs runs in containers: Postgres, the FastAPI service and
the web app, plus a one-shot migration job. The server needs Docker and
nothing else — no Python, no Node, no Postgres, no third-party account.

Target: a small VPS. 2 vCPU / 4 GB RAM is comfortable; 2 GB works if you drop
`API_WORKERS` to 1. Prophet and Tesseract are the memory-hungry parts, and
both live in the backend image.

---

## 1. Prepare the server

Ubuntu 22.04 or 24.04, as root:

```bash
apt-get update && apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
```

Give Docker a swap file if the box has 2 GB — the frontend build step is the
peak, and an OOM there is a confusing failure:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Firewall: only 22, 80 and 443 need to be open. Postgres and the API are on an
internal Docker network and are not published at all.

```bash
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```

## 2. Get the code and configure it

```bash
git clone https://github.com/UghurGambarov/MuhAI.git /opt/muhai
cd /opt/muhai
cp .env.example .env
```

Edit `.env`. Two values matter before the first start:

| Variable | What to put |
|---|---|
| `SECRET_KEY` | `openssl rand -hex 32`. Compose refuses to start without it. Changing it later signs every user out. |
| `POSTGRES_PASSWORD` | Anything long. **Set it now** — after the volume is created, editing this no longer changes the password inside the database. |

`GEMINI_API_KEY` is optional: leave it empty and the assistant answers from its
local knowledge base and says so in the UI.

Leave `VITE_API_URL` empty. The browser then calls `/api` on its own origin and
the web container's nginx proxies it to the backend — no CORS to configure and
no hostname baked into the JavaScript bundle.

## 3. Start it

```bash
docker compose -f docker-compose.yml up -d --build
```

`-f docker-compose.yml` matters: without it Compose also applies
`docker-compose.override.yml`, which is the development layer (source
bind-mounts, `--reload`, published database ports). Make it a habit, or export
`COMPOSE_FILE=docker-compose.yml` in the deploy shell.

The first build takes several minutes — prophet and pandas compile.

Order is enforced by the compose file: Postgres becomes healthy, the one-shot
`migrate` service applies the Alembic revisions and exits, then the API and the
web app start. Migrations run exactly once, in one place, which is why the API
can safely run several uvicorn workers.

Check it:

```bash
docker compose -f docker-compose.yml ps          # migrate should be "exited (0)"
curl -fsS http://localhost/health                # {"status":"healthy"}
docker compose -f docker-compose.yml logs -f backend
```

## 4. TLS

The stack publishes plain HTTP on `WEB_PORT`. Terminate TLS in front of it.
Set `WEB_PORT=8080` in `.env`, `docker compose -f docker-compose.yml up -d web`,
then install Caddy on the host — it obtains and renews the certificate itself:

```bash
apt-get install -y caddy
```

`/etc/caddy/Caddyfile`:

```
muhai.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
systemctl reload caddy
```

nginx with certbot works equally well; the point is only that something
upstream owns 443 and the compose stack owns a loopback port.

## 5. Day-to-day

```bash
cd /opt/muhai
export COMPOSE_FILE=docker-compose.yml     # keeps the dev override out

docker compose ps                          # what is running
docker compose logs -f backend             # follow the API
docker compose restart backend             # restart one service
docker compose down                        # stop (volumes survive)
```

Everything carries `restart: unless-stopped`, so the stack comes back on its
own after a reboot.

### Deploying a new version

```bash
git pull
docker compose up -d --build
```

The `migrate` service applies any new revisions before the API restarts. Images
are only rebuilt when their inputs change; `requirements.txt` or a `Dockerfile`
edit triggers the slow path, a source edit does not.

### Backups

The database is the only stateful thing. Everything else is rebuildable from
the repository.

```bash
docker compose exec -T postgres pg_dump -U muhai -Fc muhai > muhai-$(date +%F).dump
```

As a nightly cron:

```bash
0 3 * * * cd /opt/muhai && docker compose -f docker-compose.yml exec -T postgres \
  pg_dump -U muhai -Fc muhai > /var/backups/muhai-$(date +\%F).dump
```

Restore into an empty database:

```bash
docker compose exec -T postgres pg_restore -U muhai -d muhai --clean --if-exists < muhai-2026-09-08.dump
```

Copy the dumps off the VPS. A backup on the machine it is protecting is not a
backup.

### Running the tests on the server

Dev dependencies are deliberately absent from the runtime image, and
`.dockerignore` keeps `tests/` out of it, so the suite runs from a checkout
rather than inside the deployed container:

```bash
docker compose run --rm --no-deps -v ./backend:/app -u root backend \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest"
```

---

## Troubleshooting

**`SECRET_KEY` error on `up`.** Compose is telling you `.env` has no
`SECRET_KEY`. Generate one with `openssl rand -hex 32`.

**`migrate` exits non-zero.** Read `docker compose logs migrate`. Usually the
database password in `.env` no longer matches the one baked into the volume at
`initdb` time. Either restore the old password or, on a throwaway environment,
`docker compose down -v` and start again — **that deletes the data**.

**The web app loads but every panel says the service is offline.** nginx is
serving the bundle but cannot reach the API. `docker compose ps backend` and
`docker compose logs backend`; the API container has usually failed its
healthcheck or crashed on a bad `DATABASE_URL`.

**502 from nginx right after `up`.** The backend is still starting — Prophet's
import is slow. Its healthcheck allows 40 seconds; give it that.

**OCR returns nothing useful.** The Turkish language pack lives in the backend
image (`tesseract-ocr-tur`). If you edited the Dockerfile, confirm it is still
installed: `docker compose exec backend tesseract --list-langs`.
