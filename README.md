# CPPS Wand Ruffle

This repository is a fork of [Solero's Wand](https://github.com/solero/wand), a Club Penguin private-server stack that runs the Dash website, Houdini game servers, PostgreSQL, Redis, Snowflake, and original media files with Docker Compose.

The purpose of this fork is to add Ruffle support: a browser-playable Ruffle client, a media server, and a WebSocket-to-TCP proxy so the Flash client can run in modern browsers without the Adobe Flash Player plugin. Credit for the original stack, its architecture, and its upstream components belongs to the Wand project and its contributors.

> [!WARNING]
> Run this only with content you are authorized to use. This project is intended for local development and private testing.

## Components

| Component | Purpose | Default port |
| --- | --- | --- |
| Docker Compose `web` | Nginx for the website and static media | `WEB_PORT` (default `80`) |
| Docker Compose `dash` | Account registration and activation | `3000` |
| Docker Compose `houdini_login` | Game login server | `6112` |
| Docker Compose `houdini_blizzard` | English world server | `9875` |
| `web_server.py` | Ruffle landing page and media routing | `8888` |
| `ws_proxy.py` | Browser WebSocket bridge to the game servers | `8080`, `8081` |

The Ruffle client is served at `/play/ruffle.html` by `web_server.py`.

## Requirements

- A 64-bit Linux server or local Linux environment. Windows users should use WSL2.
- Git with submodule support.
- Docker Engine and the Docker Compose plugin.
- Python 3.9+ and `pip` for the Ruffle WebSocket proxy.
- Public DNS, a reverse proxy, and TLS for public HTTPS deployment.

For a small private deployment, allow at least 4 GB RAM and several GB of free disk space for Docker images, database data, and media assets.

## Installation

The Ruffle helper scripts use `/opt/cpps/wand` as their deployment path. The following commands intentionally clone there.

```bash
sudo mkdir -p /opt/cpps
sudo git clone --recurse-submodules https://github.com/usreray/cpps-wand-ruffle.git /opt/cpps/wand
sudo chown -R "$USER":"$USER" /opt/cpps/wand
cd /opt/cpps/wand
git submodule update --init --recursive
```

If you deploy elsewhere, update `DIRECTORY` and the `/opt/cpps/wand` paths in `web_server.py` before running it.

### Configure `.env`

Copy the example file and edit it. `.env` is ignored by Git.

```bash
cp .env.example .env
```

Replace the example host names and IP address, and use a long random database password. These are the most important values:

```dotenv
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-this-to-a-long-random-password

# Public web addresses
WEB_PORT=80
WEB_HOSTNAME=clubpenguin.example.com
WEB_LEGACY_PLAY=http://old.clubpenguin.example.com
WEB_LEGACY_MEDIA=http://legacy.clubpenguin.example.com
WEB_VANILLA_PLAY=http://play.clubpenguin.example.com
WEB_VANILLA_MEDIA=http://media.clubpenguin.example.com

# Game servers
GAME_ADDRESS=203.0.113.10
GAME_LOGIN_PORT=6112

# Snowflake
SNOWFLAKE_HOST=203.0.113.10
SNOWFLAKE_PORT=7002

# Optional services
WEB_RECAPTCHA_SITE=
WEB_RECAPTCHA_SECRET=
WEB_SENDGRID_KEY=
ALLOW_FORCESTART_SNOW=False
ALLOW_FORCESTART_TUSK=True
MATCHMAKING_TIMEOUT=30
```

`GAME_ADDRESS` and `SNOWFLAKE_HOST` must be reachable by players. `web_server.py` also reads `GAME_ADDRESS` from `.env` and inserts it into `ruffle.html`, so Ruffle can route game connections through the WebSocket proxy. If Nginx or another reverse proxy uses port `80`, set `WEB_PORT` to another port such as `8088`.

Do not commit `.env` or share its database password, mail credentials, or API keys.

### Apply required compatibility fixes

Before starting the services, run these two scripts from the repository root:

```bash
./scripts/apply-environment-data.sh
./scripts/apply-login-fix.sh
```

They are required for this fork's Ruffle flow:

- `apply-environment-data.sh` writes the environment-data files required by the client to locate the local game configuration.
- `apply-login-fix.sh` restores password verification in Houdini's login handler.

Without these fixes, the Ruffle client cannot complete its startup or players cannot log in successfully. Run them again after updating files that they patch, then restart the affected services.

### Start the core services

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

The first start initializes PostgreSQL from `houdini/houdini.sql` and can take longer. Open the site on the address configured by `WEB_PORT` after every required service reports as running.

Useful commands:

```bash
docker compose logs -f houdini_login
docker compose logs -f houdini_blizzard
docker compose restart dash
docker compose down
```

## Ruffle browser client

The Ruffle client needs two Python processes in addition to Docker Compose:

```bash
cd /opt/cpps/wand
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip websockets
```

Start the WebSocket bridge in one terminal:

```bash
cd /opt/cpps/wand
. .venv/bin/activate
python3 ws_proxy.py
```

Start the Ruffle media server in another terminal:

```bash
cd /opt/cpps/wand
python3 web_server.py
```

For local development, open:

```text
http://SERVER_IP:8888/play/ruffle.html
```

`ws_proxy.py` bridges browser WebSockets to the Docker-published login server on port `6112` and the Blizzard world server on port `9875`.

### Production reverse proxy

For HTTPS, terminate TLS in Nginx, Caddy, or another reverse proxy. Proxy the main Ruffle site to port `8888` and preserve WebSocket upgrades for both proxy paths. A minimal Nginx configuration is:

```nginx
location / {
    proxy_pass http://127.0.0.1:8888;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /ws/login {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}

location /ws/world {
    proxy_pass http://127.0.0.1:8081;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

With HTTPS, the browser automatically uses `wss://` for these endpoints. PostgreSQL is bound to `127.0.0.1:5432` by default. Do not expose Redis or Dash (`3000`) publicly. Restrict Docker-published game ports with a firewall when using a reverse proxy and the local WebSocket bridge.

## Included maintenance scripts

Run these from the repository root only when their described behavior is wanted:

```bash
./scripts/apply-nickname-approval-fix.sh
./scripts/apply-play-landing-links.sh
```

- `apply-nickname-approval-fix.sh` makes nickname approval available for all languages.
- `apply-play-landing-links.sh` directs the landing-page Login button to `/play/ruffle.html` and keeps navigation local.

Review the scripts after updating the Houdini submodule, since they intentionally patch its source files.

## Updating a deployment

Back up `.data/` and `.env` before updating. Then synchronize the deployment with the remote `main` branch and rebuild the containers:

```bash
cd /opt/cpps/wand
cp .env ~/wand-env.backup
git fetch origin
git checkout main
git reset --hard origin/main
[ -f .env ] || cp ~/wand-env.backup .env
git submodule update --init --recursive
./scripts/apply-environment-data.sh
./scripts/apply-login-fix.sh
docker compose up -d --build
```

Restart `web_server.py` and `ws_proxy.py` after updating them. If they are managed by systemd, restart their service units.

## Troubleshooting

### The game page does not load

- Confirm the media server is running: `curl -I http://127.0.0.1:8888/play/ruffle.html`.
- Check the terminal running `web_server.py` for missing-file requests.
- Verify the repository is at `/opt/cpps/wand`, or update the hard-coded paths in `web_server.py`.

### The game loads but cannot log in

- Check service health: `docker compose ps`.
- Inspect `docker compose logs -f houdini_login` and `docker compose logs -f houdini_blizzard`.
- Confirm `ws_proxy.py` can reach local ports `6112` and `9875`.
- For HTTPS, verify WebSocket upgrade rules for `/ws/login` and `/ws/world`.
- Confirm `GAME_ADDRESS` in `.env` is the server's public address, then restart `web_server.py`.

### A submodule directory is empty

```bash
git submodule update --init --recursive
```

### Services fail after changing `.env`

```bash
docker compose up -d --force-recreate
docker compose logs -f --tail=100
```
