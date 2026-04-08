# Orbital Inspect — Multi-Region Architecture

## Overview

Orbital Inspect is deployed in an **active-passive** configuration across two geographic regions. The primary region serves all live traffic; the secondary region maintains a warm standby and can accept traffic within the RTO window. All data planes replicate continuously to ensure RPO targets are met.

| Target | Value |
|--------|-------|
| RTO (Recovery Time Objective) | < 5 minutes |
| RPO (Recovery Point Objective) | < 1 minute (database) |
| Deployment model | Active-passive, 2 regions |
| Failover trigger | Manual (with automated health-check DNS) |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GLOBAL LAYER                                │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │   Route53 / Cloudflare  (health-check failover DNS)         │   │
│   │   orbital-inspect.io  →  primary-region  (active)           │   │
│   │                       ↘  secondary-region (standby, weight=0)│  │
│   └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │                                      │
          ▼                                      ▼
┌──────────────────────┐              ┌──────────────────────┐
│   PRIMARY REGION     │              │  SECONDARY REGION    │
│   (us-east-1)        │              │  (eu-west-1)         │
│                      │              │                      │
│  ┌────────────────┐  │              │  ┌────────────────┐  │
│  │  API Pods (3x) │  │              │  │  API Pods (2x) │  │
│  │  Worker Pods   │  │              │  │  Worker Pods   │  │
│  │  (stateless)   │  │              │  │  (stateless,   │  │
│  └───────┬────────┘  │              │  │   idle)        │  │
│          │           │              │  └───────┬────────┘  │
│  ┌───────▼────────┐  │   streaming  │  ┌───────▼────────┐  │
│  │  PostgreSQL    │──┼─────────────►│  │  PostgreSQL    │  │
│  │  (primary)     │  │  replication │  │  (replica,     │  │
│  │  Patroni HA    │  │              │  │   read-only)   │  │
│  └───────┬────────┘  │              │  └───────┬────────┘  │
│          │           │              │          │           │
│  ┌───────▼────────┐  │   Sentinel   │  ┌───────▼────────┐  │
│  │  Redis         │◄─┼─────────────►│  │  Redis         │  │
│  │  (master)      │  │  replication │  │  (replica)     │  │
│  └───────┬────────┘  │              │  └───────┬────────┘  │
│          │           │              │          │           │
│  ┌───────▼────────┐  │     S3 CRR   │  ┌───────▼────────┐  │
│  │  S3 Bucket     │──┼─────────────►│  │  S3 Bucket     │  │
│  │  (source)      │  │              │  │  (replica)     │  │
│  └────────────────┘  │              │  └────────────────┘  │
└──────────────────────┘              └──────────────────────┘
```

---

## Component Details

### 1. DNS — Route53 / Cloudflare

**Routing strategy**: Health-check based weighted failover.

- Primary record: weight 100, health check against `GET /api/health` on the primary load balancer.
- Secondary record: weight 0 (zero — no traffic), health check enabled.
- If the primary health check fails for **2 consecutive checks** (30-second interval), Route53 automatically promotes the secondary record to serve traffic.
- TTL: **30 seconds** to minimize cache bleed during failover.

**Cloudflare alternative**: Use Load Balancing with an origin pool per region and Steering Policy set to `failover`. Enable health checks on `/api/ready`.

---

### 2. Database — PostgreSQL with Streaming Replication

**Option A — Self-managed: Patroni**

- 3-node Patroni cluster in the primary region (1 leader + 2 synchronous standbys).
- 1 read replica in the secondary region (asynchronous streaming replication).
- `synchronous_commit = remote_apply` on the primary → RPO near zero within the primary region.
- Cross-region replica lag target: < 1 minute under normal write load.
- Patroni DCS: etcd (co-located in primary region) or Consul.
- On failover to secondary: replica is promoted to leader via `pg_ctl promote` or `patronictl failover`.

**Option B — Managed: AWS RDS Multi-AZ + Read Replica**

- RDS Multi-AZ in the primary region (synchronous standby, automatic in-region failover in ~60s).
- Cross-region read replica in the secondary region (async).
- On regional failover: promote the read replica to standalone instance, update the application `DATABASE_URL` secret.

**Connection pooling**: PgBouncer sidecar per API pod, transaction mode, pool size 20 per pod.

---

### 3. Cache and Queue — Redis Sentinel

- Primary region: Redis master + 2 replicas under Sentinel supervision.
- Secondary region: 1 Redis replica, promoted on failover.
- Sentinel quorum: 2 (requires majority of 3 Sentinel nodes in primary region).
- Cross-region replication: asynchronous. Acceptable data loss window: < 30 seconds of cache writes (cache is soft state; cache misses fall through to the database).
- Celery task queue uses a dedicated Redis logical DB (`DB 1`). On failover, workers in the secondary region reconnect to the newly promoted Redis master.

---

### 4. Object Storage — S3 Cross-Region Replication (CRR)

- Source bucket: `orbital-inspect-artifacts-us-east-1`
- Destination bucket: `orbital-inspect-artifacts-eu-west-1`
- Replication rule: replicate all objects, including delete markers.
- Replication SLA: objects available in destination within **15 minutes** of write (typically seconds).
- Application reads: always read from the local-region bucket. On secondary activation, the app environment variable `S3_BUCKET` is updated to point to the replica bucket.
- Versioning enabled on both buckets.

---

### 5. Application — Stateless API and Worker Pods

All API and Worker containers are **fully stateless**. No local disk state, no in-memory session state.

| Component | Primary (active) | Secondary (standby) |
|-----------|-----------------|---------------------|
| API pods | 3 replicas, serving traffic | 2 replicas, running but receiving 0 traffic (weight=0 at DNS/LB) |
| Celery workers | Running, consuming queue | Running at reduced concurrency, consuming same queue via cross-region Redis |
| Celery beat (scheduler) | 1 instance active | 1 instance paused (env `CELERY_BEAT_ENABLED=false`) |

Configuration is injected via environment variables and Kubernetes Secrets. Region-specific overrides (database URL, Redis URL, S3 bucket) are stored in per-region `ConfigMap` / `Secret` objects.

---

### 6. Observability

- Prometheus scrapers deployed in each region independently.
- Grafana with two datasources (one per region) and a unified dashboard with a region selector variable.
- PagerDuty alert rule: fire `P1` if primary health check fails for > 60 seconds.
- Runbook URL attached to every alert: `https://internal.orbital-inspect.io/runbooks/regional-failover`

---

## Failover Procedure

### Automated Path (DNS health-check triggers)

1. Primary `/api/health` fails two consecutive Route53 checks (interval: 30s → triggers at ~60s).
2. Route53 automatically updates DNS to point to the secondary region load balancer.
3. Secondary API pods begin serving traffic (they were already running).
4. On-call engineer is paged via PagerDuty.
5. Engineer verifies secondary is healthy, then begins manual data-plane promotion steps below.

**Estimated automated cutover time: < 2 minutes (DNS TTL 30s + propagation).**

---

### Manual Failover Steps

Execute in order. Each step includes a verification check.

#### Step 1 — Confirm primary is unreachable

```bash
curl -sf https://orbital-inspect.io/api/health || echo "PRIMARY DOWN"
curl -sf https://secondary.orbital-inspect.io/api/health && echo "SECONDARY UP"
```

#### Step 2 — Promote PostgreSQL replica (secondary region)

**Patroni managed:**
```bash
# SSH into secondary region Patroni node
patronictl -c /etc/patroni/config.yml failover orbital-inspect \
  --master <primary-leader-name> \
  --candidate <secondary-replica-name> \
  --force
```

**RDS managed:**
```bash
aws rds promote-read-replica \
  --db-instance-identifier orbital-inspect-replica-eu-west-1 \
  --region eu-west-1
# Wait for status = available (typically 3-5 minutes)
aws rds wait db-instance-available \
  --db-instance-identifier orbital-inspect-replica-eu-west-1 \
  --region eu-west-1
```

Verify:
```bash
psql "$SECONDARY_DATABASE_URL" -c "SELECT pg_is_in_recovery();"
# Expected: f (false = now primary)
```

#### Step 3 — Update application secrets to point to new primary DB

```bash
kubectl -n orbital-inspect patch secret db-credentials \
  --patch '{"stringData": {"DATABASE_URL": "<new-primary-url>"}}'
kubectl -n orbital-inspect rollout restart deployment/api deployment/worker
```

#### Step 4 — Promote Redis replica

```bash
# On secondary Redis node
redis-cli -h <secondary-redis-host> SLAVEOF NO ONE
```

Update `REDIS_URL` secret:
```bash
kubectl -n orbital-inspect patch secret redis-credentials \
  --patch '{"stringData": {"REDIS_URL": "redis://<secondary-redis-host>:6379"}}'
kubectl -n orbital-inspect rollout restart deployment/api deployment/worker
```

#### Step 5 — Update S3 bucket env var

```bash
kubectl -n orbital-inspect patch configmap app-config \
  --patch '{"data": {"S3_BUCKET": "orbital-inspect-artifacts-eu-west-1"}}'
kubectl -n orbital-inspect rollout restart deployment/api deployment/worker
```

#### Step 6 — Re-enable Celery beat in secondary

```bash
kubectl -n orbital-inspect patch deployment celery-beat \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"celery-beat","env":[{"name":"CELERY_BEAT_ENABLED","value":"true"}]}]}}}}'
```

#### Step 7 — Verify smoke test passes on secondary

```bash
./ops/scripts/smoke_test.sh https://secondary.orbital-inspect.io
```

#### Step 8 — Update DNS weight to make secondary the explicit primary

```bash
# Route53: set secondary record weight=100, primary record weight=0
aws route53 change-resource-record-sets --hosted-zone-id <ZONE_ID> \
  --change-batch file://ops/dns/failover-to-secondary.json
```

**Total manual failover time target: < 5 minutes.**

---

## Failback Procedure (returning to primary region)

Once the primary region is restored:

1. Rebuild primary database from secondary (pg_basebackup or snapshot restore).
2. Re-establish streaming replication: primary region replica → secondary leader.
3. Verify replication lag < 1 minute.
4. Repeat Steps 2–8 in reverse (promoting primary region components).
5. Update DNS weights back to primary region.
6. Run smoke test on primary.
7. Reset secondary Celery beat to `CELERY_BEAT_ENABLED=false`.

---

## RTO / RPO Summary

| Component | RPO | RTO |
|-----------|-----|-----|
| PostgreSQL (Patroni, sync replication within region) | ~0s | < 60s (in-region auto-failover) |
| PostgreSQL (cross-region async replication) | < 1 minute | < 5 minutes (manual promote) |
| Redis (async replication) | < 30 seconds (soft state) | < 2 minutes |
| S3 artifacts | < 15 minutes | Immediate (replica bucket pre-existing) |
| DNS cutover | N/A | < 2 minutes (automated), 30s TTL |
| Full service restoration | — | **< 5 minutes** |

---

## Runbook Quick Reference

| Scenario | Action |
|----------|--------|
| Primary DB node crash (in-region) | Patroni auto-promotes standby, no manual action |
| Primary region network partition | DNS health check fires → automated DNS failover |
| Full primary region outage | Follow manual failover steps 1–8 above |
| Secondary region degraded (standby) | Page on-call, repair secondary; no customer impact |
| CRR replication lag > 15 min | Check S3 replication metrics, investigate source bucket permissions |

---

## Open Items / Future Improvements

- [ ] Implement automated failback script (`ops/scripts/failback.sh`)
- [ ] Add cross-region latency SLO alerting (p95 < 200ms)
- [ ] Evaluate active-active for read-only API endpoints via Cloudflare Workers
- [ ] Document Terraform modules for secondary region infrastructure provisioning
- [ ] Add chaos engineering runbook (simulated regional failover drills, monthly)
