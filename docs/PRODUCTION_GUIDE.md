# Email Enrichment Platform — Production & Operational Guide

## 1. System Architecture

The Email Enrichment Platform is an enterprise-grade async platform designed to enrich company lists with verified domain data, contact candidate email permutations, and deliverability confidence scores.

```
CSV Upload / REST API
       │
       ▼
 FastApi API Server ──► Redis Job Queue ──► Multi-Worker Pool
       │                                        │
       ├──────────────┐                         ▼
       ▼              ▼               Enrichment Pipeline Engine
 Supabase DB   Redis Cache                      │
                                 ┌──────────────┼──────────────┐
                                 ▼              ▼              ▼
                            Tavily/Brand    MX DNS         SMTP Handshake
                            Search API     Lookup          Verification
```

---

## 2. Key Component Lifecycle & Queuing Architecture

1. **Job Ingestion & CSV Streaming**: CSV files uploaded to `/api/v1/jobs/upload` are validated, parsed in memory chunks (`CSV_CHUNK_SIZE=500`), stored in Supabase (`processing_jobs`), and pushed to Redis (`email_enrichment_jobs`).
2. **Worker Pool Execution**: Background worker instances consume job tasks via atomic Redis `BLPOP` commands, maintain heartbeats, update progress checkpoints, and handle task execution retries (`MAX_JOB_RETRIES=3`).
3. **Provider Circuit Breaker State Machine**:
   - `CLOSED`: Standard operation.
   - `OPEN`: Tripped after `CIRCUIT_BREAKER_FAILURE_THRESHOLD` failures or HTTP 429 rate limit. Cooldown period enforced for `CIRCUIT_BREAKER_RESET_TIMEOUT` seconds.
   - `HALF_OPEN`: Test mode allowing `CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` trial requests before recovering to `CLOSED`.

---

## 3. Configuration & Environment Reference

| Environment Variable | Default Value | Description |
|----------------------|---------------|-------------|
| `ENVIRONMENT` | `development` | Execution mode (`development`, `production`) |
| `LOG_LEVEL` | `INFO` | System logging verbosity |
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `SUPABASE_URL` | — | Supabase PostgreSQL project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Supabase admin service key |
| `DOMAIN_RESOLUTION_CONCURRENCY` | `20` | Max parallel domain search workers |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `3` | Consecutive provider failure ceiling |
| `CIRCUIT_BREAKER_RESET_TIMEOUT` | `30.0` | Circuit breaker OPEN cooldown (sec) |
| `CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` | `3` | Trial requests permitted in HALF_OPEN state |

---

## 4. Production Deployment Checklist & Commands

### Docker Compose Container Deployment

```bash
# 1. Clone repository and set production environment variables
cp .env.production.example .env

# 2. Build and launch containers in detached mode
docker-compose up -d --build

# 3. Inspect container logs
docker-compose logs -f backend worker

# 4. Verify system health probes
curl http://localhost:8000/api/health/ready
curl http://localhost:8000/api/health/live
```

---

## 5. Benchmarking & Monitoring Recommendations

- **Execution Benchmark**: Run `python scripts/benchmark.py --rows 1000` to measure throughput, latency, memory consumption, and verify zero memory leaks.
- **Monitoring Endpoints**:
  - GET `/api/v1/analytics/providers`: Inspect real-time provider health, circuit breaker states, 429 counts, and average latency metrics.
  - GET `/api/health`: Health status of database, Redis cache, and external APIs.
  - GET `/api/v1/analytics/performance`: Platform-wide throughput (rows/sec, emails/sec).

---

## 6. Backup & Recovery Strategy

1. **Database Backups**: Automated daily PostgreSQL snapshots managed via Supabase project dashboard or pg_dump cron jobs.
2. **Queue Resilience**: Redis persistence configured via `redis.conf` RDB snapshots (`save 60 1000`).
3. **Graceful Worker Shutdown**: Workers intercept `SIGTERM` signals, checkpoint current row progress to Supabase, and release active locks before terminating.
