# Technical Decisions

Each entry: choice made, why, alternative considered, trade-off, evidence/commit, and a production improvement beyond this lab's scope.

---

## Decision 1: Base image — pinned Alpine variants for Postgres/Redis, slim Debian for app

- **Choice:** Kept `postgres:16-alpine@sha256:...` and
  `redis:7.4-alpine@sha256:...` (pinned by digest, not tag), and
  `python:3.12-slim-bookworm` for the app image.
- **Why:** Alpine images are small and fast to pull, which matters for
  CI runtime; pinning by digest guarantees the exact same image bytes
  are used every time, regardless of what `:latest` might later resolve
  to. `slim-bookworm` (Debian-based, not Alpine) was kept for the app
  specifically because it uses glibc, avoiding potential musl-related
  compatibility issues with Python C-extension dependencies (e.g.
  `psycopg`).
- **Alternative:** Use `:latest` tags for simplicity/readability, or
  switch the app image to `python:3.12-alpine` for consistency with the
  other services.
- **Trade-off:** Pinned digests are more reproducible but less
  human-readable in the compose file, and don't auto-update with
  security patches. A full Alpine app image would be smaller than
  slim-bookworm but risks subtle musl/glibc compatibility issues with
  compiled Python dependencies.
- **Evidence / commit:** Base images unchanged from starter pack except
  where directly modified (see Decision 3); confirmed working via
  `docker compose -p barq-assessment ps -a` showing all 5 containers
  healthy throughout the project.
- **Production improvement:** Add automated dependency-update tooling
  (Dependabot/Renovate) to track new digests for security patches,
  rather than a one-time manual pin.

---

## Decision 2: Health checks — separate liveness (/health) from readiness (/ready)

- **Choice:** Kept the app contract's separation between `/health`
  (process liveness only, no dependency checks) and `/ready` (checks
  real Postgres and Redis connectivity), and used `/health` for Docker's
  own `HEALTHCHECK`, not `/ready`.
- **Why:** If Docker's healthcheck used `/ready` instead, a temporary
  Postgres/Redis blip would make Docker think the whole app process had
  crashed and restart it unnecessarily — even though the process itself
  was fine and just needed the dependency to recover. Separating the two
  concerns avoids unnecessary restarts while still allowing `/ready` to
  be checked independently (by `validate.py` and nginx-level routing
  decisions, if extended).
- **Alternative:** Use a single combined health/readiness endpoint for
  simplicity.
- **Trade-off:** Two endpoints instead of one adds a small amount of API
  surface, but prevents the failure mode described above. This was
  already the intended design per `APPLICATION.md`, not a change we
  introduced — but the healthcheck path bug (troubleshooting.md Entry 1)
  shows how easy it is to accidentally point a healthcheck at the wrong
  one of the two.
- **Evidence / commit:** `ba5785c` — fixed healthcheck to correctly
  target `/health`.
- **Production improvement:** Add a third endpoint or metric exposing
  *why* `/ready` is failing (which specific dependency), surfaced to a
  monitoring system, rather than only a binary ready/not-ready signal.

---

## Decision 3: Networks — two-network isolation (frontend/backend), nginx restricted to frontend only

- **Choice:** `app-01`/`app-02` are attached to both `frontend` and
  `backend` networks; `nginx` is attached to `frontend` only; `postgres`
  and `redis` are attached to `backend` only.
- **Why:** This ensures nginx can reach the app instances (shared
  `frontend`) but cannot reach Postgres/Redis directly (no shared
  network with `backend`), satisfying the brief's requirement to block
  direct NGINX access to the data layer. Docker Compose networks provide
  genuine L3 isolation — a container simply cannot resolve or connect to
  another container unless they share a network, which is a stronger
  guarantee than an application-level firewall rule.
- **Alternative:** Use a single flat network for all 5 services and rely
  on Postgres/Redis not exposing ports to the host as the only
  isolation layer.
- **Trade-off:** Two networks add a small amount of configuration
  complexity but provide defense-in-depth: even if nginx were
  compromised, it has no network path to the database layer at all,
  not even blocked by an ACL that a determined attacker inside the
  container might bypass.
- **Evidence / commit:** `ba33455` — removed nginx from `backend`;
  verified via `docker network inspect barq-assessment_backend` showing
  membership `{postgres, redis, app-01, app-02}` (nginx absent), and via
  `nc -zv postgres 5432` from inside nginx failing with DNS resolution
  failure (`bad address`), not just a connection refusal.
- **Production improvement:** In a larger deployment, add a third
  network tier separating `app-01`/`app-02` from each other (no
  east-west communication needed between them), and use Kubernetes
  NetworkPolicies or equivalent for more granular, auditable rules than
  Compose's network model allows.

---

## Decision 4: Timeouts/retries — nginx proxy_next_upstream enabled (error, timeout)

- **Choice:** Set `proxy_next_upstream error timeout;` in `nginx.conf`,
  enabling nginx to automatically retry a different upstream server when
  the first attempt fails to connect or times out.
- **Why:** With this disabled (`off`, the starter default),
  `failure_test.py` showed only 10/20 requests succeeding during a
  single-backend outage — nginx returned an error to the client instead
  of trying the healthy instance. Enabling retries makes the two-instance
  setup actually resilient to a single backend failure, which is the
  entire point of running two instances behind a load balancer.
- **Alternative:** Leave retries disabled and rely solely on Docker's
  restart policy to bring the failed container back, accepting a window
  of degraded availability until it recovers.
- **Trade-off:** Retried requests take slightly longer (nginx must first
  fail against the down instance, bounded by `proxy_connect_timeout 2s`,
  before retrying) rather than failing fast. This was judged acceptable
  since a slower-but-successful response is better than a fast failure
  for most use cases.
- **Evidence / commit:** `762f9c6` — before: 10/20 succeeded during
  outage; after: 20/20 succeeded, confirmed via nginx access log showing
  all 20 requests during the outage window routed successfully to the
  surviving instance.
- **Production improvement:** Add active health-check-based upstream
  removal (e.g. nginx Plus's or an open-source module's active health
  checks) so a known-down instance is removed from the pool entirely,
  rather than being retried-around on every single request.

---

## Decision 5: Restart policy and resource limits — restart: unless-stopped, no explicit resource caps

- **Choice:** Kept the starter pack's `restart: "no"` at the shared
  `x-app` anchor level unchanged for `app-01`/`app-02`, relying on
  Docker's healthcheck plus manual/CI-driven restarts rather than an
  automatic restart policy; did not add explicit `deploy.resources`
  limits.
- **Why:** For this assessment's scope (a local, single-machine lab
  environment, torn down and rebuilt frequently during development and
  testing), an automatic restart-on-failure policy risked masking real
  bugs during investigation — a crash-looping container due to an actual
  configuration error would have been silently retried instead of
  surfacing clearly in `docker compose ps -a`. This was a deliberate
  choice to prioritize debuggability during the investigation phase.
- **Alternative:** Set `restart: unless-stopped` or `on-failure:3` for
  automatic recovery, and add `deploy.resources.limits` (cpus/memory) to
  cap resource usage.
- **Trade-off:** Without an automatic restart policy, a genuine runtime
  crash (as opposed to the deliberate stop in `failure_test.py`) would
  require manual or CI intervention to recover, which is not acceptable
  for a production system. Without resource limits, a runaway container
  could consume the whole host's resources.
- **Evidence / commit:** Verified current behavior via
  `docker compose -p barq-assessment ps -a` throughout the project;
  `failure_test.py` explicitly uses `docker compose start/stop` rather
  than relying on an automatic restart policy to bring a stopped
  container back.
- **Production improvement:** This is an explicit, acknowledged
  limitation for production use — see `security_review.md` for the full
  risk writeup. A production deployment should set `restart:
  unless-stopped` (or an orchestrator-level restart policy) and explicit
  CPU/memory limits sized from observed real traffic, not lab defaults.

---

## Decision 6: Storage — named volume mounted directly at Postgres's real data path

- **Choice:** Fixed the named volume `postgres-data` to mount directly
  at `/var/lib/postgresql/data` (Postgres's actual, hardcoded data
  directory), replacing the starter pack's incorrect setup (volume
  pointed at `/backup`, real data directory mounted as ephemeral
  `tmpfs`).
- **Why:** This is the simplest, most standard pattern for
  Postgres-in-Docker persistence, and directly fixes the bug found in
  troubleshooting.md Entry 6, where data was silently wiped on every
  container stop despite a named volume appearing to be configured.
- **Alternative:** Keep a separate mount point and add a scheduled
  in-container sync/backup job instead of relying on the volume alone.
- **Trade-off:** Mounting the real data directory directly is simple and
  standard, but the volume's contents are Postgres's opaque internal
  file format — not human-readable or partially restorable without a
  full `pg_dump`/`psql` cycle via `backup.sh`/`restore.sh`.
- **Evidence / commit:** `7a1cfd8` — verified by creating a record,
  fully destroying and recreating `postgres`/`app-01`/`app-02`
  containers (keeping only the volume), and confirming the record
  survived via `GET /records`.
- **Production improvement:** Add scheduled, automated backups (e.g. a
  cron-triggered `backup.sh` run) with off-host backup storage (S3 or
  equivalent), rather than the current manual, on-demand backup process.

---

## Decision 7: Secrets handling — .gitignore exclusion, not committed even as "fixed" values

- **Choice:** `config/app.env` (containing `DATABASE_URL`/`REDIS_URL`
  with an embedded password) was added to `.gitignore` and removed from
  git tracking; a placeholder-only `config/app.env.example` was
  committed instead.
- **Why:** The brief explicitly requires keeping secrets out of images,
  code, and Compose, and providing a safe `.env.example`. This was
  applied even though the credential is synthetic lab data with no
  real-world value, on the principle that the correct practice should
  be followed regardless of the specific value's real-world sensitivity.
- **Alternative:** Commit the file with the corrected (synthetic)
  values, reasoning that lab data carries no real risk.
- **Trade-off:** Excluding the file from git means the DATABASE_URL/
  REDIS_URL port-and-password fix (troubleshooting.md Entry 9) has no
  git diff as direct evidence — this is explicitly documented as a
  limitation in that entry, with the retest command output serving as
  the evidence instead.
- **Evidence / commit:** `ae31e6b` — added `.gitignore` entry and
  `config/app.env.example`; confirmed via `git status` showing a clean
  tree with `config/app.env` absent from tracking.
- **Production improvement:** In production, use a secrets manager
  (Docker Secrets, Vault, or a cloud provider's secret store) instead of
  an env file at all, even a git-ignored local one, and rotate
  credentials on a schedule.
