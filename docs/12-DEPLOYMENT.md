# 12 — Deployment

How Aetheris Health AI is packaged, deployed, and operated. Written for the MVP → v2.3 window; enterprise/Kubernetes deployment specifics live in a separate ops runbook when we get there.

---

## 1. Environments

| Environment | Purpose | Data | Access |
|---|---|---|---|
| Local | Dev machines | Fake / seed | Individual devs |
| Dev | Shared team dev | Fake | Team |
| Staging | Pre-prod validation | Anonymized copy | Team + pilot |
| Production | Live hospitals | Real | Deployment CI + on-call |

No shortcuts across environment boundaries. No prod data in dev, ever.

---

## 2. Artifacts

- **Backend Docker image** — `aetheris/backend:<git-sha>` published to registry
- **Frontend Docker image** — `aetheris/frontend:<git-sha>` (Nginx serving built static files)
- **Migration image** — same as backend; runs `alembic upgrade head` as its command

Images are tagged with both git SHA and a semver label on release (`aetheris/backend:v2.0.0`).

---

## 3. Compose Layout (MVP → v2.1)

```yaml
# docker-compose.yml (production reference)
services:
  postgres:
    image: postgres:15
    environment: [ ... ]
    volumes: [ postgres_data:/var/lib/postgresql/data ]
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes: [ redis_data:/data ]
    restart: unless-stopped

  backend:
    image: aetheris/backend:${IMAGE_TAG}
    env_file: .env
    depends_on: [postgres, redis]
    restart: unless-stopped

  worker:
    image: aetheris/backend:${IMAGE_TAG}
    command: rq worker default ai_batch reports
    env_file: .env
    depends_on: [postgres, redis]
    restart: unless-stopped

  scheduler:
    image: aetheris/backend:${IMAGE_TAG}
    command: python -m app.background.scheduler
    env_file: .env
    depends_on: [postgres, redis]
    restart: unless-stopped

  frontend:
    image: aetheris/frontend:${IMAGE_TAG}
    depends_on: [backend]
    restart: unless-stopped

  nginx:
    image: nginx:1.27
    volumes: [ ./infra/docker/nginx.conf:/etc/nginx/nginx.conf:ro ]
    ports: ["443:443", "80:80"]
    depends_on: [backend, frontend]
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

Nginx terminates TLS (Let's Encrypt via Certbot sidecar or ACME in Caddy), proxies `/api/*` to backend and everything else to the frontend static build.

---

## 4. Release Flow

```
Feature branch
   ↓ PR opened
CI: lint, tests, build image
   ↓ Review + approval
Merge to main
   ↓ CI on main
Publish image tags: main-<sha>, latest
   ↓
Auto-deploy to Dev
   ↓ Smoke tests
Manual promote to Staging
   ↓ E2E, load, security scans
Manual promote to Production
   ↓ Canary (10% traffic) — v2.2
   ↓ Full rollout
Post-release monitoring window (2 hours) — on-call attention
```

### Release Tagging

- Semver on the docs and API contract: `v2.0.0`, `v2.0.1`, `v2.1.0`
- Backend and frontend images share the same release tag for atomic rollout

---

## 5. Migrations

- Applied by a dedicated migration job that runs to completion **before** the new backend starts serving traffic
- Backwards-compatible migrations preferred (safe rollback)
- Long-running migrations (index builds, table rewrites) planned separately with explicit maintenance windows
- Rollback strategy documented per migration: some migrations are one-way (data enrichment); those require compensating migrations, not blind reversal

---

## 6. Configuration

- Environment variables only
- MVP: `.env` file on the host, permission `0600`, owned by the deploy user
- v2.2: secrets manager (Vault or cloud KMS) with runtime injection

Never store the `.env` file in the repo. Never share secrets over chat.

---

## 7. Health Checks

Backend exposes:

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | Liveness — is the process up? |
| `GET /readyz` | Readiness — DB and Redis reachable, migrations current |
| `GET /version` | Build SHA, version, uptime |
| `GET /metrics` | Prometheus format (auth-gated in prod) |

Nginx health-checks these; unhealthy backends are removed from the pool.

---

## 8. Observability

### 8.1 Logging

- Structured JSON to stdout
- Collected by Loki / Better Stack / hosted log service (choice per deployment)
- Retention: 30 days hot, 12 months cold
- Sensitive fields redacted at log emission (never trust the sink)

### 8.2 Metrics

- Prometheus scrape
- Grafana dashboards versioned in `infra/monitoring/grafana/dashboards/`
- Key SLIs:
  - HTTP request rate, error rate, p50/p95/p99 latency
  - DB pool utilization, active connections
  - Redis operations, hit rate
  - AI provider calls, error rate, cost per hour
  - Background job success/failure rate, queue depth

### 8.3 Traces (v2.1+)

- OpenTelemetry to Tempo / Jaeger / hosted
- Every request traced end-to-end (API → service → repository → DB, and AI calls)

### 8.4 Alerting

Fire-worthy alerts (page on-call):

- p95 latency > 1s for 5 minutes
- 5xx rate > 1% for 5 minutes
- DB pool exhausted for 1 minute
- All AI providers failing
- Payment recording failure spike
- Audit log write failure (data integrity)

Notice-worthy alerts (channel notification):

- Backup failure
- Certificate expiry within 14 days
- AI cost > 120% of daily budget

---

## 9. Backups

- **Database:** daily full + continuous WAL streaming
- **Object storage:** versioning + lifecycle policy; encrypted; separate region
- **Redis:** RDB snapshot every 6 hours (session data is refreshable, so lower priority)

Restore drills quarterly. Documented restore runbook. Restore time target ≤ 2 hours (MVP), ≤ 30 minutes (v2.3).

---

## 10. Rollback

- Every release is a Docker image tag. Rollback = deploy previous tag.
- Backwards-compatible migrations guarantee that the previous backend can run against the current DB schema
- Data-mutating migrations that cannot be rolled back require a "no-rollback" flag in the release notes; on-call has authority to hold the release for higher scrutiny

---

## 11. Scaling Levers (in order)

1. Horizontal scaling of backend containers (stateless already)
2. Increase Redis size + connections
3. PostgreSQL read replicas + read/write splitting in the ORM session factory
4. Separate the worker into its own scaling group
5. Extract the AI service into a standalone service
6. CDN in front of frontend
7. Move to Kubernetes when compose becomes the operator bottleneck (not before)

Each of these is a documented step, not an emergency scramble.

---

## 12. Deployment Targets (Pilot Phase)

- **Cloud MVP:** single DigitalOcean / Hetzner / AWS EC2 instance running docker-compose behind a managed load balancer, managed PostgreSQL and Redis. Cheap and easy.
- **On-premise (some pilots):** same compose, on hospital hardware, connected to our cloud for AI provider calls and licensing checks.

Both targets use the same images and the same env-driven configuration.

---

## 13. Deployment Runbook (MVP)

Prereq: images published, `.env` up to date on the target host.

1. `ssh` into deploy host
2. `cd /opt/aetheris`
3. `docker compose pull`
4. `IMAGE_TAG=<new-tag> docker compose run --rm backend alembic upgrade head`
5. `IMAGE_TAG=<new-tag> docker compose up -d`
6. Wait for `/readyz` to return 200 on all backend containers
7. Smoke test: login as a test user, book an appointment, generate an invoice, invoke AI summary
8. Watch dashboards for 30 minutes

If any step fails, rollback:

1. `IMAGE_TAG=<previous-tag> docker compose up -d`
2. Confirm health
3. Post to incident channel, open a postmortem doc

---

## 14. Disaster Recovery

- **RPO:** ≤ 15 minutes (MVP), ≤ 5 minutes (v2.3)
- **RTO:** ≤ 2 hours (MVP), ≤ 30 minutes (v2.3)
- Runbook: `docs/incidents/RUNBOOK-disaster-recovery.md` (to be authored before first paying hospital)
- Annual DR game day

---

## 15. Compliance-Adjacent Deployment Notes

- Data residency configurable per hospital (Indian pilots → Indian region)
- All prod hosts hardened (SSH keys only, no password auth, fail2ban)
- Access to prod hosts logged and reviewed
- Prod database credentials known to at most 2 humans + the CI system

---

## 16. When to Move to Kubernetes

Signals we're ready:

- More than one region in prod
- Multiple hospitals demanding independent deployment cadence
- Cost of orchestrator ops < cost of manual compose ops
- Need for auto-scaling policies more sophisticated than "add a container"

Signals we're not:

- Fewer than 20 hospitals in production
- Compose still deploys reliably
- Nobody is spending most of their day fighting the deployment system

We do not move to Kubernetes for prestige. We move when the current system is the bottleneck.
