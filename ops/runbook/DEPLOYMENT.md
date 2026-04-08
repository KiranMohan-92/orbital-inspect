# Orbital Inspect — Production Deployment Runbook

**Audience**: DevOps engineers with no prior Orbital Inspect knowledge.
**System**: Multi-agent satellite insurance underwriting intelligence platform.
**Architecture**: FastAPI backend + ARQ background workers + React/Vite frontend.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Environment Variables Reference](#2-environment-variables-reference)
3. [Database Setup (PostgreSQL)](#3-database-setup-postgresql)
4. [Redis Configuration](#4-redis-configuration)
5. [Storage Setup](#5-storage-setup)
6. [Auth Configuration](#6-auth-configuration)
7. [Backend Deployment](#7-backend-deployment)
8. [Worker Deployment](#8-worker-deployment)
9. [Frontend Deployment](#9-frontend-deployment)
10. [TLS Termination (nginx + Let's Encrypt)](#10-tls-termination-nginx--lets-encrypt)
11. [Monitoring (OpenTelemetry / Prometheus / Grafana)](#11-monitoring)
12. [Health Checks](#12-health-checks)
13. [Post-Deploy Verification](#13-post-deploy-verification)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

Ensure the following are installed and reachable on the target host before proceeding.

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| Python | 3.13+ | Use `pyenv` or system package |
| Node.js | 22+ | Use `nvm` or system package |
| PostgreSQL | 16+ | Required in production (SQLite is dev-only) |
| Redis | 7+ | Required for job queue and rate limiting |
| S3-compatible storage | — | AWS S3 or MinIO 2025+ |
| nginx | 1.25+ | Reverse proxy + TLS termination |
| certbot | latest | Let's Encrypt TLS certificates |

### Verify prerequisites

```bash
python3 --version        # must be 3.13.x
node --version           # must be 22.x
psql --version           # must be 16.x
redis-cli --version      # must be 7.x
nginx -v
certbot --version
```

---

## 2. Environment Variables Reference

All configuration is via environment variables (or a `.env` file in the backend directory). Every variable maps to the `Settings` class in `backend/config.py`.

**Production enforcement rules** (validated at startup — the app will refuse to start if violated):
- `APP_ENV=production` requires `DEMO_MODE=false`
- `APP_ENV=production` requires `AUTH_ENABLED=true`
- `APP_ENV=production` requires `WEBHOOK_SECRET_ENCRYPTION_KEY` to be set
- `AUTH_ENABLED=true` requires `JWT_SECRET` to be a strong random value (not the default)
- `STORAGE_BACKEND=s3` requires `STORAGE_BUCKET` to be set

### 2.1 Core Application

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_ENV` | string | `development` | Runtime environment. Must be `production` for prod deployments. Allowed: `development`, `staging`, `production`, `test`. |
| `GEMINI_API_KEY` | string | **required** | Google Gemini API key. No default — the app will not start without this. |
| `GEMINI_MODEL` | string | `gemini-2.5-flash` | Gemini model identifier to use for all 5 analysis agents. |
| `DEMO_MODE` | bool | `true` | Must be `false` in production. Enables pre-cached demo responses and disables auth when `true`. |

### 2.2 Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | string | SQLite path | SQLAlchemy async connection string. **Use `postgresql+asyncpg://` in production.** Example: `postgresql+asyncpg://orbital:pass@localhost:5432/orbital_inspect` |
| `DATABASE_AUTO_INIT` | bool | `false` | If `true`, runs schema creation on startup. Set to `false` in production — use Alembic migrations instead. |
| `DATA_DIR` | string | `backend/data` | Base directory for local data files (uploads, cache). Ignored when using S3 storage. |
| `UPLOADS_DIR` | string | `DATA_DIR/uploads` | Override directory for uploaded satellite images. |
| `DEMO_CACHE_DIR` | string | `DATA_DIR/demo_cache` | Directory for demo analysis cache files. |
| `DEMO_IMAGES_DIR` | string | `DATA_DIR/demo_images` | Directory for demo satellite images. |

### 2.3 Storage

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STORAGE_BACKEND` | string | `local` | Storage driver. Use `s3` in production (also works with MinIO). |
| `STORAGE_LOCAL_ROOT` | string | `DATA_DIR/storage` | Root path for local storage backend. Ignored when `STORAGE_BACKEND=s3`. |
| `STORAGE_BUCKET` | string | — | S3 bucket name. **Required when `STORAGE_BACKEND=s3`.** |
| `STORAGE_REGION` | string | `us-east-1` | AWS S3 region. |
| `STORAGE_ENDPOINT_URL` | string | — | Override S3 endpoint. Set to MinIO URL, e.g. `http://minio:9000`. Leave unset for AWS S3. |
| `STORAGE_ACCESS_KEY_ID` | string | — | AWS/MinIO access key ID. |
| `STORAGE_SECRET_ACCESS_KEY` | string | — | AWS/MinIO secret access key. |
| `STORAGE_PREFIX` | string | `orbital-inspect` | Key prefix for all objects stored in the bucket. |
| `STORAGE_FORCE_PATH_STYLE` | bool | `true` | Force path-style URLs. Required for MinIO; set to `false` for AWS S3. |
| `STORAGE_CREATE_BUCKET` | bool | `false` | Automatically create the bucket on startup if it does not exist. |
| `SIGNED_ARTIFACT_TTL_MINUTES` | int | `30` | Expiry for pre-signed artifact download URLs (minutes). |
| `REPORT_ARTIFACT_RETENTION_DAYS` | int | `30` | Number of days before report artifacts are eligible for cleanup. |

### 2.4 External Data Sources

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SPACE_TRACK_BASE_URL` | string | `https://www.space-track.org` | Space-Track.org API base URL. |
| `SPACE_TRACK_USERNAME` | string | — | Space-Track.org account username. Optional; enables orbital TLE data fetching. |
| `SPACE_TRACK_PASSWORD` | string | — | Space-Track.org account password. |
| `UCS_DATABASE_TEXT_URL` | string | — | URL for the UCS satellite database. Optional. |
| `SATNOGS_NETWORK_API_BASE` | string | `https://network.satnogs.org/api` | SatNOGS network API base URL. |
| `SATNOGS_MAX_OBSERVATIONS` | int | `10` | Maximum number of SatNOGS observations to fetch per analysis. |

### 2.5 Job Queue

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_URL` | string | `redis://localhost:6379` | Redis connection URL for ARQ job queue and rate limiting. |
| `REDIS_REQUIRED` | bool | `false` | If `true`, the app will refuse to start if Redis is unreachable. Recommended `true` in production. |
| `ANALYSIS_QUEUE_NAME` | string | `arq:queue` | ARQ queue name. Must match across API and worker processes. |
| `ANALYSIS_JOB_MAX_RETRIES` | int | `3` | Maximum retry attempts for failed analysis jobs. |
| `ANALYSIS_RETRY_BACKOFF_BASE_SECONDS` | int | `5` | Base seconds for exponential backoff between job retries. |

### 2.6 Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUTH_ENABLED` | bool | auto | Defaults to `!DEMO_MODE`. **Must be `true` in production.** |
| `JWT_SECRET` | string | `dev-secret-change-in-production` | HMAC signing secret for JWTs. **Must be replaced with a strong random value in production.** See [Section 6](#6-auth-configuration). |
| `JWT_PREVIOUS_SECRETS` | list[str] | `[]` | Previous JWT secrets for zero-downtime rotation. JSON array format: `["old-secret"]` |
| `JWT_EXPIRY_MINUTES` | int | `60` | JWT token lifetime in minutes. |
| `JWT_ISSUER` | string | `orbital-inspect` | JWT `iss` claim value. |
| `JWT_AUDIENCE` | string | `orbital-inspect-api` | JWT `aud` claim value. |
| `API_KEY_PREFIX` | string | `oi` | Prefix for generated API keys (e.g. `oi_...`). |
| `WEBHOOK_SECRET_ENCRYPTION_KEY` | string | — | Fernet key for encrypting stored webhook secrets. **Required in production.** See [Section 6](#6-auth-configuration). |
| `WEBHOOK_SECRET_PREVIOUS_KEYS` | list[str] | `[]` | Previous encryption keys for zero-downtime rotation. |

### 2.7 Resilience

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AGENT_TIMEOUT_SECONDS` | int | `120` | Per-agent Gemini call timeout in seconds. |
| `GEMINI_CIRCUIT_BREAKER_THRESHOLD` | int | `5` | Number of consecutive Gemini failures before the circuit breaker opens. |
| `JOB_TIMEOUT_SECONDS` | int | `300` | Maximum wall-clock time for a full analysis job (5 minutes). |
| `MIN_EVIDENCE_COMPLETENESS_FOR_DECISION` | float | `80.0` | Minimum evidence completeness percentage before a final decision is issued. |
| `REQUIRE_HUMAN_REVIEW_FOR_DECISIONS` | bool | `true` | If `true`, high-risk decisions are flagged for human review. |
| `GOVERNANCE_POLICY_VERSION` | string | `2026-04-03` | Policy version tag attached to all analysis audit records. |

### 2.8 Logging and Observability

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | string | `INFO` | Python log level. Allowed: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `LOG_FORMAT` | string | `json` | Log output format. Use `json` in production for structured log ingestion. |
| `METRICS_ENABLED` | bool | `true` | Enable internal metrics collection. |
| `PROMETHEUS_METRICS_ENABLED` | bool | `true` | Expose Prometheus metrics at `/metrics`. |
| `OTEL_ENABLED` | bool | `false` | Enable OpenTelemetry tracing. |
| `OTEL_REQUIRED` | bool | `false` | If `true`, app fails startup when OTEL collector is unreachable. |
| `OTEL_SERVICE_NAME` | string | `orbital-inspect` | Service name tag in traces and spans. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | string | — | OTLP HTTP endpoint, e.g. `http://otel-collector:4318/v1/traces`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | string | `""` | Additional OTLP headers as a comma-separated `key=value` string. |
| `OTEL_RESOURCE_ATTRIBUTES` | string | `""` | Additional resource attributes, e.g. `deployment.environment=production`. |
| `OTEL_TRACES_SAMPLER_RATIO` | float | `1.0` | Trace sampling ratio. `1.0` = 100%, `0.1` = 10%. |
| `OTEL_CONSOLE_EXPORTER` | bool | `false` | Also write traces to stdout. Useful for debugging. |
| `OBSERVABILITY_SHARED_TOKEN` | string | — | Shared bearer token for accessing `/api/observability/*` endpoints. |
| `OBSERVABILITY_PREVIOUS_TOKENS` | list[str] | `[]` | Previous tokens for zero-downtime rotation. |

### 2.9 Rate Limiting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RATE_LIMIT_BACKEND` | string | `memory` | Rate limiter storage. Use `redis` in production for multi-process correctness. |
| `ANALYSIS_RATE_LIMIT_PER_HOUR` | int | `20` | Maximum analysis requests per user per hour. |
| `REPORT_RATE_LIMIT_PER_HOUR` | int | `60` | Maximum report requests per user per hour. |
| `RATE_LIMIT_FAIL_OPEN` | bool | `true` | If `true`, allows requests when the rate limit backend is unreachable. Set `false` for strict enforcement. |

### 2.10 Caching

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_BACKEND` | string | `auto` | Cache storage. `auto` selects Redis if available, otherwise memory. Set `redis` explicitly in production. |
| `CACHE_DEFAULT_TTL_SECONDS` | int | `900` | Default cache TTL (15 minutes). |

### 2.11 CORS

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ALLOWED_ORIGINS` | list[str] | `localhost:5173` + others | JSON array of allowed CORS origins. **Set to your production frontend URL**, e.g. `["https://orbital.example.com"]`. |

---

## 3. Database Setup (PostgreSQL)

### 3.1 Create database and user

```bash
sudo -u postgres psql <<'SQL'
CREATE USER orbital WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE orbital_inspect OWNER orbital ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE orbital_inspect TO orbital;
SQL
```

### 3.2 Verify connection

```bash
psql "postgresql://orbital:CHANGE_ME_STRONG_PASSWORD@localhost:5432/orbital_inspect" -c "SELECT version();"
```

### 3.3 Run Alembic migrations

From the `backend/` directory:

```bash
cd /opt/orbital-inspect/backend

# Confirm current migration head
DATABASE_URL="postgresql+asyncpg://orbital:CHANGE_ME@localhost:5432/orbital_inspect" \
  alembic current

# Apply all pending migrations
DATABASE_URL="postgresql+asyncpg://orbital:CHANGE_ME@localhost:5432/orbital_inspect" \
  alembic upgrade head

# Verify
DATABASE_URL="postgresql+asyncpg://orbital:CHANGE_ME@localhost:5432/orbital_inspect" \
  alembic current
```

> **Important**: Do NOT set `DATABASE_AUTO_INIT=true` in production. Always use Alembic migrations to manage schema changes.

### 3.4 PostgreSQL tuning (recommended)

```sql
-- Edit /etc/postgresql/16/main/postgresql.conf
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

---

## 4. Redis Configuration

### 4.1 Install and start Redis 7

```bash
# Ubuntu/Debian
sudo apt-get install -y redis-server

# Enable and start
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify
redis-cli ping  # Expected: PONG
```

### 4.2 Production Redis configuration

Edit `/etc/redis/redis.conf`:

```conf
# Bind to localhost only (nginx or app on same host)
bind 127.0.0.1

# Require a password
requirepass CHANGE_ME_REDIS_PASSWORD

# Persist to disk (append-only)
appendonly yes
appendfsync everysec

# Set memory limit (adjust to available RAM)
maxmemory 512mb
maxmemory-policy allkeys-lru
```

```bash
sudo systemctl restart redis-server
redis-cli -a CHANGE_ME_REDIS_PASSWORD ping
```

### 4.3 Update `REDIS_URL` with password

```bash
REDIS_URL="redis://:CHANGE_ME_REDIS_PASSWORD@localhost:6379"
```

---

## 5. Storage Setup

Choose one of the two options below.

### Option A: Local Filesystem

Suitable for single-node deployments where no S3 is available. **Not recommended for multi-node** (workers and API must share the same filesystem).

```bash
mkdir -p /var/lib/orbital-inspect/storage
chown -R orbital:orbital /var/lib/orbital-inspect/storage
```

```bash
# .env values
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=/var/lib/orbital-inspect/storage
```

### Option B: MinIO (S3-compatible, self-hosted)

```bash
# Install MinIO server
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
sudo mv minio /usr/local/bin/

# Create data directory
sudo mkdir -p /var/lib/minio
sudo useradd -r -s /sbin/nologin minio-user
sudo chown -R minio-user:minio-user /var/lib/minio

# Create systemd service at /etc/systemd/system/minio.service
sudo tee /etc/systemd/system/minio.service > /dev/null <<'EOF'
[Unit]
Description=MinIO Object Storage
After=network.target

[Service]
User=minio-user
Group=minio-user
EnvironmentFile=/etc/minio/minio.env
ExecStart=/usr/local/bin/minio server $MINIO_VOLUMES --console-address :9001
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create config at /etc/minio/minio.env
sudo mkdir -p /etc/minio
sudo tee /etc/minio/minio.env > /dev/null <<'EOF'
MINIO_ROOT_USER=orbital
MINIO_ROOT_PASSWORD=CHANGE_ME_MINIO_PASSWORD
MINIO_VOLUMES=/var/lib/minio
EOF

sudo systemctl enable minio
sudo systemctl start minio

# Create the bucket using the MinIO client
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc && sudo mv mc /usr/local/bin/

mc alias set local http://localhost:9000 orbital CHANGE_ME_MINIO_PASSWORD
mc mb local/orbital-inspect
mc ls local/  # Confirm bucket exists
```

```bash
# .env values for MinIO
STORAGE_BACKEND=s3
STORAGE_BUCKET=orbital-inspect
STORAGE_ENDPOINT_URL=http://localhost:9000
STORAGE_ACCESS_KEY_ID=orbital
STORAGE_SECRET_ACCESS_KEY=CHANGE_ME_MINIO_PASSWORD
STORAGE_FORCE_PATH_STYLE=true
STORAGE_CREATE_BUCKET=false
```

### Option C: AWS S3

```bash
# .env values for AWS S3
STORAGE_BACKEND=s3
STORAGE_BUCKET=your-bucket-name
STORAGE_REGION=us-east-1
STORAGE_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
STORAGE_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
STORAGE_FORCE_PATH_STYLE=false
STORAGE_CREATE_BUCKET=false
```

---

## 6. Auth Configuration

### 6.1 Generate JWT secret

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Copy the output and set it as `JWT_SECRET`. This value must be identical across all API and worker processes.

### 6.2 Generate webhook encryption key (Fernet key)

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Copy the output and set it as `WEBHOOK_SECRET_ENCRYPTION_KEY`.

### 6.3 Generate observability token

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Set as `OBSERVABILITY_SHARED_TOKEN`.

### 6.4 Example auth section of `.env`

```bash
AUTH_ENABLED=true
JWT_SECRET=<64-char-random-string-from-step-6.1>
JWT_EXPIRY_MINUTES=60
JWT_ISSUER=orbital-inspect
JWT_AUDIENCE=orbital-inspect-api
WEBHOOK_SECRET_ENCRYPTION_KEY=<fernet-key-from-step-6.2>
OBSERVABILITY_SHARED_TOKEN=<random-token-from-step-6.3>
```

### 6.5 Secret rotation (zero-downtime)

To rotate `JWT_SECRET` without invalidating existing sessions:

1. Set `JWT_PREVIOUS_SECRETS=["<old-secret>"]` (JSON array)
2. Update `JWT_SECRET` to the new value
3. Restart all API processes
4. After all tokens with the old secret have expired (`JWT_EXPIRY_MINUTES`), clear `JWT_PREVIOUS_SECRETS`

Same pattern applies to `WEBHOOK_SECRET_PREVIOUS_KEYS` and `OBSERVABILITY_PREVIOUS_TOKENS`.

---

## 7. Backend Deployment

### 7.1 Create application user and directory

```bash
sudo useradd -r -s /bin/bash -d /opt/orbital-inspect orbital
sudo mkdir -p /opt/orbital-inspect
sudo chown orbital:orbital /opt/orbital-inspect
```

### 7.2 Deploy backend code

```bash
sudo -u orbital git clone https://github.com/your-org/orbital-inspect.git /opt/orbital-inspect
# Or copy the release archive
```

### 7.3 Install Python dependencies

```bash
cd /opt/orbital-inspect/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 7.4 Create production `.env`

```bash
sudo -u orbital tee /opt/orbital-inspect/backend/.env > /dev/null <<'EOF'
APP_ENV=production
DEMO_MODE=false
AUTH_ENABLED=true
GEMINI_API_KEY=your-gemini-api-key

DATABASE_URL=postgresql+asyncpg://orbital:DBPASS@localhost:5432/orbital_inspect
DATABASE_AUTO_INIT=false

REDIS_URL=redis://:REDISPASS@localhost:6379
REDIS_REQUIRED=true
RATE_LIMIT_BACKEND=redis
CACHE_BACKEND=redis

STORAGE_BACKEND=s3
STORAGE_BUCKET=orbital-inspect
STORAGE_ENDPOINT_URL=http://localhost:9000
STORAGE_ACCESS_KEY_ID=orbital
STORAGE_SECRET_ACCESS_KEY=MINIOPASS
STORAGE_FORCE_PATH_STYLE=true
STORAGE_CREATE_BUCKET=false

JWT_SECRET=GENERATED_JWT_SECRET
WEBHOOK_SECRET_ENCRYPTION_KEY=GENERATED_FERNET_KEY
OBSERVABILITY_SHARED_TOKEN=GENERATED_OBS_TOKEN

LOG_LEVEL=INFO
LOG_FORMAT=json
PROMETHEUS_METRICS_ENABLED=true
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production

ALLOWED_ORIGINS=["https://orbital.example.com"]
EOF

chmod 600 /opt/orbital-inspect/backend/.env
```

### 7.5 Run database migrations

```bash
cd /opt/orbital-inspect/backend
source .venv/bin/activate
alembic upgrade head
```

### 7.6 Create systemd service for API

```bash
sudo tee /etc/systemd/system/orbital-inspect-api.service > /dev/null <<'EOF'
[Unit]
Description=Orbital Inspect API
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
User=orbital
Group=orbital
WorkingDirectory=/opt/orbital-inspect/backend
EnvironmentFile=/opt/orbital-inspect/backend/.env
ExecStart=/opt/orbital-inspect/backend/.venv/bin/uvicorn main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    --access-log \
    --proxy-headers \
    --forwarded-allow-ips='127.0.0.1'
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable orbital-inspect-api
sudo systemctl start orbital-inspect-api
sudo systemctl status orbital-inspect-api
```

### 7.7 Verify API is responding

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

Expected response: `{"status": "ok", ...}`

> **Note on workers**: `--workers 4` spawns 4 uvicorn processes. Each shares the same Redis connection pool. For CPU-bound workloads, set workers to `2 * CPU_cores + 1`. The background agent pipeline runs via ARQ workers (Section 8), not inside the API processes.

---

## 8. Worker Deployment

The ARQ worker runs the 5-agent satellite analysis pipeline asynchronously. It must share the same `.env` as the API (same database, Redis, storage, Gemini key).

### 8.1 Create systemd service for ARQ worker

```bash
sudo tee /etc/systemd/system/orbital-inspect-worker.service > /dev/null <<'EOF'
[Unit]
Description=Orbital Inspect ARQ Analysis Worker
After=network.target postgresql.service redis-server.service orbital-inspect-api.service
Requires=postgresql.service redis-server.service

[Service]
User=orbital
Group=orbital
WorkingDirectory=/opt/orbital-inspect/backend
EnvironmentFile=/opt/orbital-inspect/backend/.env
ExecStart=/opt/orbital-inspect/backend/.venv/bin/python -m arq workers.analysis_worker.WorkerSettings
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable orbital-inspect-worker
sudo systemctl start orbital-inspect-worker
sudo systemctl status orbital-inspect-worker
```

### 8.2 Verify worker is connected to Redis

```bash
journalctl -u orbital-inspect-worker -n 50 --no-pager
# Look for: "Starting worker" and "Connected to redis"
```

### 8.3 Scaling workers

Run multiple worker instances for higher throughput. Each instance competes for jobs from the same queue:

```bash
# Example: 2 worker instances
sudo cp /etc/systemd/system/orbital-inspect-worker.service \
        /etc/systemd/system/orbital-inspect-worker@.service

# Edit the @ service to use %i for instance differentiation if needed
sudo systemctl enable orbital-inspect-worker@1 orbital-inspect-worker@2
sudo systemctl start orbital-inspect-worker@1 orbital-inspect-worker@2
```

---

## 9. Frontend Deployment

### 9.1 Build the frontend

```bash
cd /opt/orbital-inspect/frontend
npm ci
npm run build
# Output: frontend/dist/
```

### 9.2 Configure the API base URL

Before building, set the API URL via environment:

```bash
VITE_API_BASE_URL=https://orbital.example.com npm run build
```

Or create `frontend/.env.production`:

```bash
VITE_API_BASE_URL=https://orbital.example.com
```

### 9.3 Copy built assets to nginx document root

```bash
sudo mkdir -p /var/www/orbital-inspect
sudo cp -r /opt/orbital-inspect/frontend/dist/* /var/www/orbital-inspect/
sudo chown -R www-data:www-data /var/www/orbital-inspect
```

### 9.4 Configure nginx for the frontend (HTTP only, pre-TLS)

```bash
sudo tee /etc/nginx/sites-available/orbital-inspect > /dev/null <<'EOF'
server {
    listen 80;
    server_name orbital.example.com;

    root /var/www/orbital-inspect;
    index index.html;

    # SPA fallback — route all non-file requests to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to uvicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support — disable buffering for streaming analysis events
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Static assets with long cache
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2|woff|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/orbital-inspect /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 10. TLS Termination (nginx + Let's Encrypt)

### 10.1 Install certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### 10.2 Obtain TLS certificate

```bash
sudo certbot --nginx -d orbital.example.com --non-interactive --agree-tos -m admin@example.com
```

Certbot will automatically update the nginx config to redirect HTTP to HTTPS and add SSL directives.

### 10.3 Verify nginx config after certbot

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 10.4 Verify auto-renewal

```bash
sudo certbot renew --dry-run
```

### 10.5 Full production nginx config (post-certbot)

After certbot runs, your nginx config should include the following blocks. Review and harden as needed:

```nginx
server {
    listen 443 ssl http2;
    server_name orbital.example.com;

    ssl_certificate /etc/letsencrypt/live/orbital.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/orbital.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    root /var/www/orbital-inspect;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2|woff|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}

server {
    listen 80;
    server_name orbital.example.com;
    return 301 https://$host$request_uri;
}
```

---

## 11. Monitoring

### 11.1 Stack overview

The observability stack is defined in `docker-compose.observability.yml`. In production, you can run it alongside the main services or deploy the components independently.

| Component | Port | Role |
|-----------|------|------|
| OpenTelemetry Collector | 4317, 4318 | Receives traces from API and worker, forwards to Tempo |
| Prometheus | 9090 | Scrapes `/metrics` from the API; stores time-series |
| Grafana Tempo | 3200 | Distributed trace storage and query |
| Grafana | 3001 | Dashboards for metrics and traces |
| Alertmanager | 9093 | Routes Prometheus alerts to notification channels |

### 11.2 Quick start with Docker Compose (observability stack)

```bash
cd /opt/orbital-inspect

# Start only the observability stack (assumes API/worker/Redis/Postgres run via systemd)
docker compose -f docker-compose.observability.yml up -d

# Check all containers are running
docker compose -f docker-compose.observability.yml ps
```

### 11.3 Enable OpenTelemetry on the API and worker

Add to `.env`:

```bash
OTEL_ENABLED=true
OTEL_REQUIRED=false
OTEL_SERVICE_NAME=orbital-inspect-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,service.namespace=orbital-inspect
OTEL_TRACES_SAMPLER_RATIO=0.1
```

Restart both services:

```bash
sudo systemctl restart orbital-inspect-api orbital-inspect-worker
```

### 11.4 Prometheus scrape configuration

The API exposes metrics at `http://localhost:8000/metrics` when `PROMETHEUS_METRICS_ENABLED=true`. The Prometheus config at `ops/observability/prometheus/prometheus.yml` is pre-configured to scrape this endpoint.

Verify Prometheus is scraping:

```bash
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -A5 "orbital"
```

### 11.5 Grafana setup

1. Navigate to `http://localhost:3001` (or proxy through nginx)
2. Default credentials: `orbital` / `orbital_observability_password` (change immediately)
3. Datasources (Prometheus and Tempo) are pre-provisioned from `ops/observability/grafana/provisioning/`
4. Dashboards are pre-provisioned from `ops/observability/grafana/dashboards/`

```bash
# Change Grafana admin password
curl -X PUT http://orbital:orbital_observability_password@localhost:3001/api/user/password \
  -H "Content-Type: application/json" \
  -d '{"oldPassword":"orbital_observability_password","newPassword":"STRONG_NEW_PASSWORD","confirmNew":"STRONG_NEW_PASSWORD"}'
```

### 11.6 Alert configuration

Alertmanager config lives at `ops/observability/alertmanager/alertmanager.yml`. Edit it to add your notification channel (Slack, PagerDuty, email):

```yaml
receivers:
  - name: 'team-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK'
        channel: '#orbital-alerts'
```

---

## 12. Health Checks

### 12.1 `/api/health` — Liveness check

Returns `200 OK` when the process is running. Safe to use as a load balancer liveness probe.

```bash
curl -s https://orbital.example.com/api/health | python3 -m json.tool
```

Expected:

```json
{
  "status": "ok",
  "service": "orbital-inspect",
  "version": "..."
}
```

### 12.2 `/api/ready` — Readiness check

Returns `200 OK` when all dependencies (database, Redis, storage) are reachable. Use as a Kubernetes readiness probe or pre-traffic gate.

```bash
curl -s https://orbital.example.com/api/ready | python3 -m json.tool
```

A non-`200` response indicates a dependency is unavailable. Check the response body for the failing component.

### 12.3 `/metrics` — Prometheus metrics

```bash
curl -s http://127.0.0.1:8000/metrics | head -40
```

Returns Prometheus text format metrics including request counts, latency histograms, and agent event counters.

### 12.4 Systemd health check commands

```bash
# API service status
sudo systemctl status orbital-inspect-api

# Worker service status
sudo systemctl status orbital-inspect-worker

# Live log tails
journalctl -u orbital-inspect-api -f
journalctl -u orbital-inspect-worker -f
```

---

## 13. Post-Deploy Verification

After completing all sections above, run through this checklist:

```bash
# 1. Health endpoint
curl -sf https://orbital.example.com/api/health && echo "PASS: health"

# 2. Readiness endpoint
curl -sf https://orbital.example.com/api/ready && echo "PASS: ready"

# 3. TLS is valid
curl -sv https://orbital.example.com/api/health 2>&1 | grep -E "SSL|TLS|certificate"

# 4. API rejects unauthenticated requests (should return 401)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://orbital.example.com/api/analyses)
[ "$STATUS" = "401" ] && echo "PASS: auth enforced" || echo "FAIL: expected 401, got $STATUS"

# 5. Prometheus metrics are available
curl -sf http://127.0.0.1:8000/metrics | grep -q "orbital" && echo "PASS: metrics"

# 6. Redis connectivity
redis-cli -a REDISPASS ping && echo "PASS: redis"

# 7. Database connectivity
psql "postgresql://orbital:DBPASS@localhost:5432/orbital_inspect" -c "SELECT 1;" && echo "PASS: postgres"

# 8. Worker is processing (check queue length in Redis)
redis-cli -a REDISPASS llen arq:queue
```

### Smoke test script

If a smoke test script exists at `scripts/smoke_test.sh`, run it after deployment:

```bash
ORBITAL_URL=https://orbital.example.com bash /opt/orbital-inspect/scripts/smoke_test.sh
```

---

## 14. Troubleshooting

### App refuses to start with "JWT_SECRET must be set..."

The default `JWT_SECRET` is not allowed when `AUTH_ENABLED=true`. Generate a new secret:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Set the output as `JWT_SECRET` in `.env`.

### App refuses to start with "DEMO_MODE must be false..."

`APP_ENV=production` enforces `DEMO_MODE=false`. Set `DEMO_MODE=false` in `.env`.

### App refuses to start with "WEBHOOK_SECRET_ENCRYPTION_KEY must be set..."

Generate a Fernet key:

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Set it as `WEBHOOK_SECRET_ENCRYPTION_KEY` in `.env`.

### `asyncpg` connection errors at startup

- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Verify the `DATABASE_URL` user, password, host, and database name are correct
- Check PostgreSQL is accepting connections: `psql "postgresql://orbital:PASS@localhost:5432/orbital_inspect" -c "SELECT 1;"`
- Check pg_hba.conf allows the connection: `sudo cat /etc/postgresql/16/main/pg_hba.conf`

### Redis connection refused

- Verify Redis is running: `sudo systemctl status redis-server`
- Verify `REDIS_URL` includes the correct password if `requirepass` is set
- Test: `redis-cli -a REDISPASS ping`

### ARQ worker exits immediately

- Check worker logs: `journalctl -u orbital-inspect-worker -n 100 --no-pager`
- Common causes: invalid `DATABASE_URL`, Redis unreachable, missing `GEMINI_API_KEY`
- The worker imports `workers.analysis_worker.WorkerSettings` — ensure the Python path is correct

### SSE streaming hangs or disconnects prematurely

- Ensure nginx has `proxy_buffering off` and `proxy_read_timeout 600s` for `/api/` routes
- Each analysis streams SSE events for up to `JOB_TIMEOUT_SECONDS` (default 300s)

### Storage upload errors

- For MinIO: verify the bucket exists (`mc ls local/`) and credentials match `.env`
- For AWS S3: verify IAM permissions include `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on the bucket
- Check `STORAGE_FORCE_PATH_STYLE`: must be `true` for MinIO, `false` for AWS S3

### Gemini API errors / circuit breaker open

- Verify `GEMINI_API_KEY` is valid and has quota
- Circuit breaker opens after `GEMINI_CIRCUIT_BREAKER_THRESHOLD` consecutive failures (default: 5)
- Check agent logs for `circuit_breaker_open` events in structured log output
- The circuit breaker resets automatically after a cooldown period

### High analysis failure rate

- Check `MIN_EVIDENCE_COMPLETENESS_FOR_DECISION` (default: 80.0%) — analyses with insufficient evidence return `FURTHER_INVESTIGATION`
- Check worker logs for `degraded=True` events from individual agents
- Check the dead letter queue: `redis-cli -a REDISPASS lrange arq:dead 0 -1`

### CORS errors in browser

- Ensure `ALLOWED_ORIGINS` includes the exact frontend URL (including protocol and port)
- Example: `ALLOWED_ORIGINS=["https://orbital.example.com"]`
- Do not use a trailing slash in origin values

### Migrations fail on `alembic upgrade head`

- Ensure `DATABASE_URL` points to the correct database
- Check if there are dirty migration states: `alembic current`
- If the database is new and empty, `alembic upgrade head` should succeed from scratch
- Verify the `alembic/` directory is present in the backend directory

---

## Appendix: Minimal Production `.env` Template

```bash
# Core
APP_ENV=production
DEMO_MODE=false
AUTH_ENABLED=true
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-flash

# Database
DATABASE_URL=postgresql+asyncpg://orbital:DBPASS@localhost:5432/orbital_inspect
DATABASE_AUTO_INIT=false

# Redis
REDIS_URL=redis://:REDISPASS@localhost:6379
REDIS_REQUIRED=true
RATE_LIMIT_BACKEND=redis
CACHE_BACKEND=redis

# Storage (MinIO example)
STORAGE_BACKEND=s3
STORAGE_BUCKET=orbital-inspect
STORAGE_ENDPOINT_URL=http://localhost:9000
STORAGE_ACCESS_KEY_ID=orbital
STORAGE_SECRET_ACCESS_KEY=MINIOPASS
STORAGE_FORCE_PATH_STYLE=true
STORAGE_CREATE_BUCKET=false

# Auth (generate all three values — see Section 6)
JWT_SECRET=GENERATED_64_CHAR_RANDOM_STRING
WEBHOOK_SECRET_ENCRYPTION_KEY=GENERATED_FERNET_KEY
OBSERVABILITY_SHARED_TOKEN=GENERATED_TOKEN

# CORS
ALLOWED_ORIGINS=["https://orbital.example.com"]

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
PROMETHEUS_METRICS_ENABLED=true

# OpenTelemetry (optional but recommended)
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production
```
