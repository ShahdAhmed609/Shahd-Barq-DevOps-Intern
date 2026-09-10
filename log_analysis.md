# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.


1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?

2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts
## Results
## Timeline and correlated examples
## Conclusions and limits

# Log Analysis

Analysis performed with a read-only Python script
(`log_analysis/analyze.py`) against unmodified copies of `logs/access.log`,
`logs/error.log`, `logs/application.log`. Originals were never edited.

## Commands / scripts

```bash
# Full script: log_analysis/analyze.py
# Run with:
python log_analysis/analyze.py > log_analysis/full_output.txt

# Ad-hoc verification commands used throughout:
wc -l logs/access.log logs/error.log logs/application.log
grep "Connection refused" logs/error.log | wc -l
grep "upstream timed out" logs/error.log | wc -l
grep "<request_id>" logs/access.log
grep "<request_id>" logs/application.log
```

`analyze.py` loads each JSON-lines file, catches and reports malformed
lines instead of crashing, and joins access.log/application.log/error.log
records on the shared `request_id` field.

## Results

### Q1 — Interval, valid/malformed/duplicate lines

- **Interval covered:** `2026-08-20T11:00:00.015Z` to `2026-08-20T11:29:57.578Z` (~30 minutes).
- **access.log:** 726 raw lines → 725 valid JSON, 1 malformed (line 311,
  truncated mid-object at `11:12:48Z`). Of the 725 valid lines, 5 pairs
  (10 lines) are **exact duplicates** — identical `request_id`, timestamp,
  and all fields — leaving **720 distinct requests**. Duplicates occur at
  exactly 5-minute intervals (11:05:00, 11:10:00, 11:15:00, 11:20:00,
  11:25:00), always on `GET /`, always 200 — consistent with a periodic
  log-shipping/collector artifact rather than a real double-request or an
  nginx retry (retries are a separate, distinct pattern — see Q6).
- **error.log:** 68 lines, plain-text nginx error format (not JSON), no
  malformed entries detected (format has no strict schema to violate).
- **application.log:** 730 raw lines → 729 valid JSON, 1 malformed (line
  401, truncated mid-object at `11:17:00Z`). No duplicate `request_id`s
  found in application.log.

### Q2 — Distinct client requests and deduplication

**720 distinct client requests**, determined by deduplicating access.log on
`request_id` (see Q1). Retries were not double-counted: when nginx retried
a failed upstream, it produced **one** access.log line with a
comma-separated `upstream`/`upstream_status` field (e.g.
`"upstream_status":"502, 200"`), not two separate lines — so no additional
deduplication was needed for retries specifically, only for the 5 exact
duplicate lines described above.

### Q3 — Final client status counts and error rate

Denominator: **720** (distinct client requests, deduplicated).

| Status | Count | % |
|---|---|---|
| 200 | 615 | 85.42% |
| 503 | 47 | 6.53% |
| 502 | 40 | 5.56% |
| 404 | 10 | 1.39% |
| 504 | 8 | 1.11% |

**Error rate (non-200 / total): 105/720 = 14.58%**

### Q4 — Failures by path, time window, backend

| Path | Failures | Status | Window | Backend |
|---|---|---|---|---|
| `/`, `/health`, `/records`, `/counter` | 40 (502) | 502 | 11:05:02–11:09:57 | 172.23.0.12 (app-02) only |
| `/ready`, `/counter` | 32 (503) | 503 | 11:12:09–11:15:52 | both instances |
| `/ready`, `/records` | 16 (503) | 503 | 11:20:07–11:21:45 | both instances |
| `/records` | 8 (504) | 504 | 11:25:14–11:26:47 | both instances |
| various | 10 (404) | 404 | scattered, `/missing` path | both instances (expected/benign) |

### Q5 — Latency percentiles

Method: nearest-rank percentile over `request_time` (seconds, as recorded
by nginx per request), n=725 (raw, including duplicates — latency is a
per-line measurement, so duplicates were not excluded here since they
represent the same real value twice, not a distortion of the distribution).

- **Median: 0.054s**
- **p95: 2.001s**

The large gap between median and p95 is explained by Incident 4: the 8
`/records` requests that hit the ~2.0s timeout dominate the tail of the
distribution.

### Q6 — Retried requests

**19 requests** hit multiple upstreams (identified via comma-separated
`upstream` field in access.log). **All 19 (100%) succeeded** — each was
first attempted against the down instance (172.23.0.12), failed, then
retried against the healthy instance (172.23.0.11), which returned 200.
This occurred only for `/ready` (10) and `/instance` (9) during Incident 1;
`/health`, `/records`, `/counter`, `/` received no retry during the same
incident and were returned to the client as 502 — an inconsistency not
fully explainable from the log data alone (see Q10).

## Timeline and correlated examples

| # | Window (UTC) | Duration | Type | Root cause |
|---|---|---|---|---|
| 1 | 11:05:02–11:09:57 | ~4m55s | 502 (40 client-facing / 59 connection attempts) | app-02 connectivity flapping |
| 2 | 11:12:09–11:15:52 | ~3m43s | 503 (32) | Redis dependency failure |
| 3 | 11:20:07–11:21:45 | ~1m38s | 503 (16) | Postgres dependency failure (fast-fail) |
| 4 | 11:25:14–11:26:47 | ~1m33s | 504 (8) | Postgres latency — false failures |

**Incident 1 — app-02 flapping.** error.log shows repeated `Connection
refused` to `172.23.0.12:8080` starting 11:05:02. Not continuous: request
`lab-000238` (GET /missing) reached app-02 successfully at 11:09:52.544
(confirmed 404 in both access.log and application.log), before the pattern
resumed briefly and fully recovered at 11:10:02.503. No `dependency_error`
entries logged by app-02 during this window — consistent with a
connectivity-level failure, not an app crash.

**Incident 2 — Redis failure.** application.log: 32 `dependency_error`
events, `dependency: redis`, alternating `app-01`/`app-02` instance IDs —
confirms shared Redis backend, both instances equally affected.
Example: `lab-000292` — access.log 503 on `/ready` via 172.23.0.12;
application.log `dependency_error` on `redis`, same request_id, same
instance.

**Incident 3 — Postgres failure (fast).** 16 `dependency_error` events,
`dependency: postgres`. Example: `lab-000484` — access.log 503 on `/ready`;
application.log `dependency_error` on `postgres`, same instance (app-02),
same request_id.

**Incident 4 — Postgres latency (false failures).** All 8 requests
returned 504 to the client, but the same `request_id`s in application.log
show status 200 with duration_ms ~2700 (2.7s) — the backend succeeded, but
nginx gave up at ~2.0s, before the actual response arrived. This is the
clearest example of a proxy-layer failure that does NOT indicate an
application/dependency failure (see Q9).

### One correlated failed request and one successful request

**Failed (Incident 3, Postgres dependency error), `request_id: lab-000484`:**

access.log: {"request_id":"lab-000484","path":"/ready","status":503,
"upstream":"172.23.0.12:8080","timestamp":"2026-08-20T11:20:07.540Z"}
application.log: {"request_id":"lab-000484","event":"dependency_error",
"dependency":"postgres","instance_id":"app-02",
"timestamp":"2026-08-20T11:20:07.540Z"}


**Successful (retried after upstream failure), `request_id: lab-000130`:**

access.log: {"request_id":"lab-000130","path":"/instance","status":200,
"upstream":"172.23.0.12:8080, 172.23.0.11:8080",
"upstream_status":"502, 200","timestamp":"2026-08-20T11:05:22.620Z"}

(First attempt against 172.23.0.12 failed with 502; nginx retried against
172.23.0.11, which succeeded; client received 200.)

## Conclusions and limits

### Q9 — Proxy/connectivity vs. dependency/application errors

- **Proxy/connectivity issues** (Incident 1, and the connect-phase failures
  behind Incidents 2/3's initial attempts): proven by `error.log`'s
  `connect() failed (111: Connection refused)` entries, which occur at the
  nginx-to-upstream network layer, before any application code runs. No
  matching `dependency_error` or even `http_request` entry exists in
  application.log for these specific failed attempts, since the app
  container was never reached.
- **Dependency/application issues** (Incidents 2 and 3's actual failures):
  proven by application.log's `dependency_error` events, which are logged
  by the Flask app itself, with an explicit `dependency` field
  (`redis`/`postgres`) — the app was reached and ran its code, but a
  downstream call failed.
- **A third category, proxy timeout masking application success**
  (Incident 4): proven by the direct contradiction between access.log
  (504, implying failure) and application.log (200, confirming success)
  for the same `request_id` — the proxy layer reported a failure that did
  not reflect the application's actual outcome.

### Q10 — What the logs do not prove, and what to check next in a running environment

- The logs do not prove **why** app-02 became unreachable during Incident 1
  (OS-level network issue? container restart? resource exhaustion?) — only
  that it was unreachable. In a running environment, this would be checked
  via `docker inspect app-02` for restart count/exit codes, and host-level
  resource metrics (CPU/memory) at that timestamp.
- The logs do not prove the underlying cause of the Redis (Incident 2) or
  Postgres (Incident 3) failures — only that the app's connection attempts
  failed. In a running environment: check `docker logs redis`/`docker logs
  postgres` directly for the same time window, and container health/restart
  history.
- The logs do not explain why `proxy_next_upstream off;` (per the
  historical nginx config, if unchanged from what we reviewed) appears to
  have allowed retries for `/ready` and `/instance` but not other endpoints
  during Incident 1 — this would require inspecting the actual nginx config
  version in effect during this historical incident, which is not available
  to us (only the current, repaired repo config is).
- The logs do not fully explain Incident 4's ~2.0s cutoff against a
  configured 3s `proxy_read_timeout` — in a running environment, this would
  be checked by reproducing sustained Postgres latency (e.g. via a
  deliberate slow query or `pg_sleep`) and observing the actual nginx
  behavior and exact timeout that fires, rather than inferring it from
  historical logs alone.
- These logs represent a **separate historical incident**, explicitly
  distinct from the live environment repaired in this project (per
  `APPLICATION.md`: "The three historical logs are a separate training
  incident, not a complete list of current faults") — findings here inform
  configuration decisions (e.g. timeout tuning, per `decisions.md`) but are
  not evidence about the current, live environment's health.
