# Security and Production-Readiness Review

For each finding: risk and evidence, impact, implemented fix/commit
(or "not implemented" where applicable), production follow-up, and how
to verify. Completed work is separated from planned improvements
throughout.

---

## Finding 1: Database credentials tracked in git

- **Risk and evidence:** `config/app.env` contains `DATABASE_URL` with
  an embedded Postgres password. It was initially tracked by git
  (inherited from the starter pack) and about to be committed with a
  corrected value during a fix.
- **Impact:** Any credential in git history is effectively permanent
  and visible to anyone with repo access, even after later removal —
  in a real (non-lab) project this would require credential rotation,
  not just deletion.
- **Implemented fix / commit:** `ae31e6b` — added `config/app.env` to
  `.gitignore`, removed it from tracking (`git rm --cached`), added
  `config/app.env.example` with a `CHANGE_ME` placeholder in place of
  the real password.
- **Production follow-up:** Use a secrets manager (Docker Secrets,
  Vault, or a cloud provider's secret store) so the credential is never
  a plain environment variable at all, and rotate on a schedule.
- **How to verify:**

git status # config/app.env absent from tracking
git log --all -- config/app.env # confirm no tracked history exists
cat .gitignore | grep app.env # confirms exclusion rule


---

## Finding 2: Postgres and Redis ports published to host

- **Risk and evidence:** The starter `docker-compose.yml` published
  `postgres` on host port 15432 and `redis` on 16379, allowing any
  process on the host to connect directly to the database layer,
  bypassing the application and its access patterns entirely.
- **Impact:** Direct database access from outside the intended
  application boundary, violating the brief's explicit requirement
  ("Do not publish app, PostgreSQL or Redis ports") and increasing
  attack surface.
- **Implemented fix / commit:** `c172ead` — removed `ports:` from both
  `postgres` and `redis` service definitions.
- **Production follow-up:** None needed beyond this for the stated
  architecture — this is the correct final state.
- **How to verify:**

curl -v http://127.0.0.1:15432 # connection refused
curl -v http://127.0.0.1:16379 # connection refused
curl -s http://127.0.0.1:8080/ready # {"postgres":"ready","redis":"ready"}


---

## Finding 3: Container user — app images verified non-root, other images unverified

- **Risk and evidence:** `app-01`/`app-02`'s Dockerfile creates and uses
  a dedicated non-root user (`groupadd --gid 10001 app && useradd --uid
  10001`), already present in the starter pack. The `postgres`, `redis`,
  and `nginx` services run as whatever user their official upstream
  images default to — this was not independently checked during this
  project.
- **Impact:** If any of the three official images defaulted to root, a
  container compromise would have full root privileges inside that
  container (though still bounded by Docker's own container isolation).
- **Implemented fix / commit:** None required for the app images (already
  correct); no change made to the other three services since their
  actual runtime user was not verified as a problem.
- **Production follow-up:** Explicitly verify each official image's
  runtime user and, if needed, add `user:` overrides in Compose, plus
  `cap_drop: [ALL]` and `read_only: true` where supported, to minimize
  the blast radius of any single container compromise.
- **How to verify:**

docker compose -p barq-assessment exec app-01 whoami # non-root, confirmed
docker compose -p barq-assessment exec postgres whoami # not yet checked
docker compose -p barq-assessment exec redis whoami # not yet checked
docker compose -p barq-assessment exec nginx whoami # not yet checked


---

## Finding 4: Image selection — pinned digests vs. mutable tags

- **Risk and evidence:** `postgres`, `redis`, and `nginx` are all
  referenced by SHA256 digest (e.g.
  `postgres:16-alpine@sha256:cf78e766...`), not a mutable tag like
  `:latest`. This was already present in the starter pack and kept
  unchanged.
- **Impact:** Without digest pinning, the actual image content pulled
  could silently change between builds with no corresponding change in
  the Compose file, making bugs non-reproducible and allowing a
  compromised upstream image to be pulled without any visible signal in
  version control.
- **Implemented fix / commit:** No change needed — already correctly
  pinned in the starter pack (confirmed via `docker compose config`
  output throughout the project, e.g. in every `docker compose ps -a`
  showing the full digest for each pulled image).
- **Production follow-up:** Add automated dependency-update tooling
  (Dependabot or Renovate) to track new digests for security patches on
  a schedule, since a static pin alone means patches are never picked
  up automatically.
- **How to verify:**

grep -E "postgres:|redis:|nginx:" docker-compose.yml

confirms @sha256:... present on all three

---

## Finding 5: nginx had unrestricted access to the backend network

- **Risk and evidence:** The starter `docker-compose.yml` attached
  `nginx` to both `frontend` and `backend` networks, meaning the only
  internet-facing component in the stack could directly reach Postgres
  and Redis, collapsing the intended two-tier network isolation into
  effectively one flat network.
- **Impact:** If nginx were compromised (e.g. via a vulnerability in a
  future custom module or misconfiguration), an attacker would have a
  direct network path to the database layer, not just to the app
  instances.
- **Implemented fix / commit:** `ba33455` — removed `backend` from
  nginx's `networks:` list, leaving only `frontend`.
- **Production follow-up:** Add a third network tier separating
  `app-01` and `app-02` from each other (no legitimate reason for direct
  east-west traffic between the two app instances in this design), and
  consider a more granular, auditable network policy engine for larger
  deployments.
- **How to verify:**

docker network inspect barq-assessment_backend --format '{{range .Containers}}{{.Name}} {{end}}'

postgres redis app-01 app-02 (nginx absent)

docker compose -p barq-assessment exec nginx sh -c "nc -zv postgres 5432"

nc: bad address 'postgres' (fails at DNS resolution, not just connection)

---

## Finding 6: Persistence/backup — Postgres data was ephemeral despite a named volume

- **Risk and evidence:** The starter `docker-compose.yml` mounted
  Postgres's real data directory (`/var/lib/postgresql/data`) as
  `tmpfs` (in-memory, wiped on stop), while the named volume
  `postgres-data` was pointed at `/var/lib/postgresql/backup`, a path
  Postgres never writes live data to. Data appeared to be configured
  for persistence but was not.
- **Impact:** Any Postgres restart (planned or crash-induced) would
  silently and completely lose all data, with no error or warning —
  this is a severe, easy-to-miss risk since the config visually
  suggests persistence is handled.
- **Implemented fix / commit:** `7a1cfd8` — corrected the volume mount
  to `postgres-data:/var/lib/postgresql/data`, removed the `tmpfs:`
  line.
- **Production follow-up:** Add scheduled, automated backups (cron or
  orchestrator-native) with off-host storage (S3 or equivalent), and
  periodic automated restore-testing rather than the current manual,
  on-demand `backup.sh`/`restore.sh` process. Additionally, Redis is
  explicitly configured with no persistence (`--save "" --appendonly
  no`) — acceptable for its current role as a disposable demo counter,
  but would need `--appendonly yes` plus a volume if used for anything
  requiring recoverability in production.
- **How to verify:**

curl -s -X POST http://127.0.0.1:8080/records -d '{"title":"persistence check"}'
docker compose -p barq-assessment rm -sf postgres app-01 app-02
docker compose -p barq-assessment up -d --build postgres app-01 app-02
curl -s http://127.0.0.1:8080/records # record still present

  Full backup/restore proof documented in troubleshooting.md Entry 11,
  including a false-positive found and fixed in `restore.sh` itself
  (it originally reported success even when the restore had actually
  failed with SQL errors).

---

## Finding 7: No monitoring, metrics, or alerting

- **Risk and evidence:** The stack has Docker-level healthchecks
  (affecting container status/restart eligibility) but no external
  monitoring, metrics aggregation, or alerting. The historical log
  analysis (log_analysis.md) found a 30-minute window containing 4
  distinct incidents — including one (Incident 4) where clients received
  504 errors while the backend had, in fact, succeeded — a pattern that
  would go completely unnoticed without proper monitoring and alerting
  tuned to distinguish true failures from timeout-tuning artifacts.
- **Impact:** In the current setup, a real production incident would
  only be discovered when a user reported it, with no automated
  detection or historical trend visibility.
- **Implemented fix / commit:** Not implemented — out of scope for this
  lab's infrastructure.
- **Production follow-up:** Add structured log shipping to a log
  aggregation system (Loki, ELK, or equivalent), metrics export
  (Prometheus-style) from nginx and the app, and alerting rules on
  error rate and latency percentiles — specifically calibrated with
  enough margin to avoid the false-failure pattern identified in
  log_analysis.md.
- **How to verify:** N/A (not implemented); the false-failure pattern
  that motivates this finding can be reviewed directly in
  `log_analysis.md`, Incident 4 section.

---

## Finding 8: Availability — nginx, Postgres, and Redis remain single points of failure

- **Risk and evidence:** `failure_test.py` proves that a single **app**
  instance failure is handled gracefully (20/20 requests succeed via
  the surviving instance, after the `proxy_next_upstream` fix). However,
  nginx itself runs as a single container, and Postgres/Redis each run
  as a single, unreplicated instance.
- **Impact:** An nginx crash makes the entire system unreachable
  regardless of app-instance health. A Postgres or Redis crash/
  corruption takes down all reads/writes regardless of how many app
  instances are running — the two-app-instance redundancy does not
  extend to these components.
- **Implemented fix / commit:** Not implemented — explicitly out of
  scope for a two-app-instance lab assessment; only app-instance
  redundancy was required and tested.
- **Production follow-up:** Run nginx behind a redundant load balancer
  (or multiple nginx replicas behind a cloud LB), use managed or
  replicated Postgres (e.g. streaming replication with automatic
  failover), and Redis in a Sentinel or Cluster configuration.
- **How to verify:**

./failure_test.py # proves app-instance-level resilience only

  (No equivalent test exists for nginx/Postgres/Redis failure, since
  no redundancy exists there to test.)

---

## Finding 9: Unbounded container log growth

- **Risk and evidence:** Container logs accumulate via Docker's default
  logging driver with no configured size or rotation limit.
- **Impact:** On a long-running host, unbounded log growth can consume
  significant disk space and, in the worst case, fill the disk and
  cause unrelated failures elsewhere on the system.
- **Implemented fix / commit:** Not implemented — containers in this
  lab are short-lived and frequently rebuilt during development/testing,
  so this was not encountered as a practical problem here.
- **Production follow-up:** Configure Docker's logging driver with
  explicit `max-size`/`max-file` limits in each service's `logging:`
  block, or ship logs externally (see Finding 7) and minimize local
  retention.
- **How to verify:** N/A (not implemented); would be verified via
  `docker inspect <container> --format '{{.HostConfig.LogConfig}}'`
  showing configured limits once added.

---

## Finding 10: nginx failover behavior — now fixed, but limited to a two-instance topology

- **Risk and evidence:** The starter `nginx.conf` had
  `proxy_next_upstream off;`, meaning a single backend instance failure
  caused ~50% of requests to fail outright instead of nginx retrying the
  healthy instance. Proven via `failure_test.py`: 10/20 requests failed
  during an app-01 outage before this fix.
- **Impact:** Reduced availability during any single-instance failure —
  directly contradicts the purpose of running two app instances behind
  a load balancer.
- **Implemented fix / commit:** `762f9c6` — changed to
  `proxy_next_upstream error timeout;`. Also fixed a related false
  negative in the test script itself (`failure_test.py`'s own
  `REQUEST_TIMEOUT` was too tight relative to nginx's real retry
  latency, causing 3 additional apparent failures that were not real).
- **Production follow-up:** With only two instances, if both were down
  simultaneously, retries would not help — this is an inherent
  limitation of a two-instance topology, not something `proxy_next_upstream`
  can solve alone. Production should run more instances and add active
  health-check-based upstream removal, so a known-down instance is
  taken out of the pool entirely rather than retried-around on every
  request.
- **How to verify:**

./failure_test.py

Step 3 output: "20/20 succeeded" (was 10/20 before the fix)
