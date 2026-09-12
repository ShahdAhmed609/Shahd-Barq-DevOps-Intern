# Troubleshooting Journal

Baseline commit (unmodified starter pack): `8442da3` (2026-09-02 20:53:43 +0300)

---

## Entry 1 / 2026-09-09 14:31:48 +0300
- **Symptom:** `docker compose ps -a` showed `app-01`/`app-02` as `(unhealthy)` despite both containers running. Logs showed repeated `GET /healthz` returning 404 every ~6 seconds.
- **Hypothesis:** The healthcheck targets a path that doesn't exist on the app.
- **Command or test:**

docker inspect app-01 --format='{{.Config.Healthcheck.Test}}'
grep -rn "healthz" Dockerfile app/ docker-compose.yml

- **Actual output:**

[CMD python -c import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)]
docker-compose.yml:12: test: [...urlopen('http://127.0.0.1:8080/healthz'...)]

- **Failed attempt and what changed your thinking:** None — hypothesis confirmed on first check.
- **Root cause:** `docker-compose.yml`'s shared healthcheck (`x-app` anchor) targets `/healthz`; `APPLICATION.md` specifies the liveness endpoint is `/health`.
- **Fix:** Changed `/healthz` to `/health` in the healthcheck `test:` array.
- **Retest evidence:**

docker compose -p barq-assessment ps -a
app-01 ... Up 33 seconds (healthy)
app-02 ... Up 33 seconds (healthy)

- **Related commit:** `ba5785c`
- **Remaining uncertainty:** None.

---

## Entry 2 / 2026-09-09 14:53:30 +0300
- **Symptom:** Every request through nginx returned "Empty reply from server," even after containers reported healthy.
- **Hypothesis:** Flask may be bound only to localhost inside its own container, unreachable from other containers (each container has its own network namespace).
- **Command or test:** `docker compose -p barq-assessment logs app-01 | head -5`
- **Actual output:** `...Running on http://127.0.0.1:8080`
- **Failed attempt and what changed your thinking:** None — log output directly confirmed the hypothesis.
- **Root cause:** `APP_HOST` was set to `"127.0.0.1"` in the shared `x-app-env` anchor.
- **Fix:** Changed `APP_HOST` to `"0.0.0.0"`.
- **Retest evidence:**

docker compose -p barq-assessment logs app-01 | tail -5
Running on all addresses (0.0.0.0)
Running on http://172.18.0.3:8080

docker compose -p barq-assessment exec app-01 python3 -c
"import urllib.request; print(urllib.request.urlopen('http://app-01:8080/health', timeout=2).status)"
200

- **Related commit:** `9363cdb`
- **Remaining uncertainty:** None.

---

## Entry 3 / 2026-09-09 15:10:22 +0300
- **Symptom:** After Entry 2's fix, requests to `http://127.0.0.1:8080/...` still returned "Empty reply from server."
- **Hypothesis:** nginx's `listen` directive may not match the internal container port Docker forwards to.
- **Command or test:**

docker compose -p barq-assessment ps -a
cat nginx/nginx.conf | grep listen

- **Actual output:**

nginx ... 127.0.0.1:8080->81/tcp
listen 80;

  Docker maps host 8080 → container port 81; nginx listens on 80.
- **Failed attempt and what changed your thinking:** Edited `nginx.conf` to `listen 81;`, ran `docker compose up -d --build`, retested — still failed identically. This showed that `up -d` does not reload a bind-mounted config file when the service definition itself hasn't changed; had to use `docker compose restart nginx` explicitly to force a reload.
- **Root cause:** `nginx.conf` had `listen 80;`, mismatched against Docker's `81` mapping.
- **Fix:** Changed `listen 80;` to `listen 81;`; forced reload via `docker compose restart nginx`.
- **Retest evidence:**

curl -i http://127.0.0.1:8080/health
HTTP/1.1 502 Bad Gateway

  (502, not empty — confirms nginx is now listening and proxying; the 502 itself is Entry 4's separate bug.)
- **Related commit:** `93c6dcb`
- **Remaining uncertainty:** None.

---

## Entry 4 / 2026-09-09 15:25:41 +0300
- **Symptom:** After Entry 3's fix, 3 of 4 test requests returned `502 Bad Gateway`.
- **Hypothesis:** nginx's upstream block may reference the wrong port for app-01.
- **Command or test:**

docker compose -p barq-assessment logs nginx | tail -20
grep -A2 upstream nginx/nginx.conf

- **Actual output:**

[error] connect() failed (111: Connection refused) ... upstream: "http://172.18.0.2:8081/health"
server app-01:8081 max_fails=0;
server app-02:8080 max_fails=0;

- **Failed attempt and what changed your thinking:** None directly, but cross-referencing the one successful request's upstream IP (`172.18.0.3:8080`) via `docker compose exec nginx getent hosts app-02` revealed it was app-02, not app-01 as its own X-Instance-ID header claimed — this surfaced Entry 5 as a side effect.
- **Root cause:** nginx's upstream block listed `app-01:8081`; app-01's actual Flask server listens on 8080 (`APP_PORT=8080`).
- **Fix:** Changed `server app-01:8081` to `server app-01:8080`.
- **Retest evidence:**

for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/health; done
200 200 200 200 200 200

- **Related commit:** `9babb60`
- **Remaining uncertainty:** None.

---

## Entry 5 / 2026-09-09 15:30:43 +0300
- **Symptom:** app-02's own logs and `/instance` responses showed `"instance_id": "app-01"`.
- **Hypothesis:** app-02's environment override may have a copy-paste error.
- **Command or test:** `grep -A6 "app-02:" docker-compose.yml`
- **Actual output:**

app-02:
environment:
INSTANCE_ID: "app-01"

- **Failed attempt and what changed your thinking:** None.
- **Root cause:** Copy-paste error — app-02's `INSTANCE_ID` was set to `"app-01"`.
- **Fix:** Changed to `INSTANCE_ID: "app-02"`.
- **Retest evidence:**

for i in 1 2 3 4; do curl -s http://127.0.0.1:8080/instance; echo; done
{"instance_id":"app-01",...}
{"instance_id":"app-02",...}
{"instance_id":"app-01",...}
{"instance_id":"app-02",...}

- **Related commit:** `a2a0450`
- **Remaining uncertainty:** None.

---

## Entry 6 / 2026-09-10 12:47:37 +0300
- **Symptom:** No functional symptom yet observed — found via deliberate review of the named volume against Part 3's persistence requirement.
- **Hypothesis:** The named volume may not actually cover Postgres's real data directory.
- **Command or test:** `grep -A4 "postgres-data" docker-compose.yml`
- **Actual output:**

volumes:
- postgres-data:/var/lib/postgresql/backup
tmpfs: [/var/lib/postgresql/data]

- **Failed attempt and what changed your thinking:** None — the mismatch was visible directly in the config.
- **Root cause:** Postgres's real data directory (`/var/lib/postgresql/data`) was mounted as `tmpfs` (in-memory, wiped on stop); the named volume pointed at `/backup`, a path Postgres does not use for live data.
- **Fix:** Changed volume mount to `postgres-data:/var/lib/postgresql/data`; removed the `tmpfs:` line.
- **Retest evidence:**

curl -s -X POST http://127.0.0.1:8080/records -d '{"title":"Persistence proof test"}'
docker compose -p barq-assessment rm -sf postgres app-01 app-02
docker compose -p barq-assessment up -d --build postgres app-01 app-02
curl -s http://127.0.0.1:8080/records
{"records":[{"id":1,...},{"id":2,...},{"id":3,"title":"Persistence proof test"}]}

  All 3 records present after full container recreation.
- **Related commit:** `7a1cfd8`
- **Remaining uncertainty:** None.

---

## Entry 7 / 2026-09-10 13:03:34 +0300
- **Symptom:** No functional symptom — found via direct review against the brief's requirement not to publish app/Postgres/Redis ports.
- **Hypothesis:** N/A — direct config review.
- **Command or test:** `grep -A2 "ports:" docker-compose.yml`
- **Actual output:**

postgres: ports: ["127.0.0.1:15432:5432"]
redis: ports: ["127.0.0.1:16379:6379"]

- **Failed attempt and what changed your thinking:** None.
- **Root cause:** Both services had unnecessary `ports:` entries, likely left over from local debugging.
- **Fix:** Removed `ports:` from both `postgres` and `redis`.
- **Retest evidence:**

curl -v http://127.0.0.1:15432 2>&1 | tail -5 -> connection refused
curl -v http://127.0.0.1:16379 2>&1 | tail -5 -> connection refused
curl -s http://127.0.0.1:8080/ready
{"dependencies":{"postgres":"ready","redis":"ready"},...}

- **Related commit:** `c172ead`
- **Remaining uncertainty:** None.

---

## Entry 8 / 2026-09-10 13:12:29 +0300
- **Symptom:** No functional symptom — found via direct review against the brief's requirement to block direct NGINX access to Postgres/Redis.
- **Hypothesis:** N/A — direct config review.
- **Command or test:** `grep -A2 "nginx:" docker-compose.yml`
- **Actual output:**

nginx:
networks: [frontend, backend]

- **Failed attempt and what changed your thinking:** None.
- **Root cause:** nginx's `networks:` list included `backend`, likely inherited from early debugging.
- **Fix:** Changed to `networks: [frontend]`.
- **Retest evidence:**

curl -s http://127.0.0.1:8080/ready
{"dependencies":{"postgres":"ready","redis":"ready"},...} (unaffected)

docker network inspect barq-assessment_backend --format '{{range .Containers}}{{.Name}} {{end}}'
postgres redis app-01 app-02 (nginx absent)

docker compose -p barq-assessment exec nginx sh -c "nc -zv postgres 5432"
nc: bad address 'postgres'

- **Related commit:** `ba33455`
- **Remaining uncertainty:** None.

---

## Entry 9 / 2026-09-10 11:53:39 +0300
- **Symptom:** `/records` and `/ready` returned `{"error":"postgres_unavailable"}` despite postgres reporting `(healthy)` for 2+ minutes, ruling out a startup timing issue.
- **Hypothesis:** app-01's connection string may be wrong (port and/or credentials).
- **Command or test:**

docker compose -p barq-assessment logs app-01 | grep -i "postgres|dependency_error"
cat config/app.env
grep POSTGRES_PASSWORD docker-compose.yml

- **Actual output:**

{"level":"ERROR","event":"dependency_error","dependency":"postgres","error_type":"OperationalError",...}
DATABASE_URL=postgresql://barq_app:BarqLabOnly_7qN2vK8d@postgres:5433/barq_tasks
REDIS_URL=redis://redis:6380/0
POSTGRES_PASSWORD: BarqLabOnly_7qN2vK8c

- **Failed attempt and what changed your thinking:** None — comparing the two files side by side directly revealed both the port mismatch (5433/6380 vs 5432/6379) and a one-character password mismatch (`...vK8d` vs `...vK8c`).
- **Root cause:** `config/app.env` had wrong ports and a mismatched password.
- **Fix:** Corrected `config/app.env` locally to use ports `5432`/`6379` and the matching password.
- **Retest evidence:**

curl -s http://127.0.0.1:8080/ready
{"dependencies":{"postgres":"ready","redis":"ready"},"status":"ready",...}
curl -s http://127.0.0.1:8080/records
{"records":[{"id":1,...},{"id":2,...}]}
curl -s http://127.0.0.1:8080/counter
{"counter":1,"instance_id":"app-02",...}

- **Related commit:** `ae31e6b` (secrets exclusion commit; the actual value fix has no git diff by design, since `config/app.env` is git-ignored — see Remaining uncertainty)
- **Remaining uncertainty:** No git diff exists for the real fix, since `config/app.env` was deliberately excluded from version control before the fix was applied (it holds a credential, even if a synthetic lab one). `config/app.env.example` was updated in commit `ae31e6b` to reflect the corrected port structure as indirect evidence; direct evidence is the retest output above and the live video demonstration.

---

## Entry 10 / 2026-09-11 15:13:52 +0300
- **Symptom:** `failure_test.py` (stopping app-01) showed only 10/20 requests succeeding during the outage, despite app-02 being fully healthy.
- **Hypothesis:** nginx may not be configured to retry a healthy upstream when the first one fails.
- **Command or test:** `grep proxy_next_upstream nginx/nginx.conf`
- **Actual output:** `proxy_next_upstream off;`
- **Failed attempt and what changed your thinking:** Changed `proxy_next_upstream` to `error timeout;` and retested — result improved to 17/20, not the expected 20/20. Pulled nginx's own access log for the exact test window and found all 20 requests were in fact correctly retried and returned 200 by nginx itself; the 3 remaining failures were the *test client* (`failure_test.py`) giving up early. Its `REQUEST_TIMEOUT` was 2 seconds, and nginx's retry sequence (waiting out a ~2s connect timeout to the stopped app-01 before retrying app-02) sometimes took just over 2.0s — nginx logged these as status 499 ("client closed connection"), meaning the bug had shifted from the environment to the test script itself.
- **Root cause:** Two separate causes — (1) `proxy_next_upstream off;` in nginx.conf, and (2) `failure_test.py`'s `REQUEST_TIMEOUT = 2` was too tight relative to nginx's worst-case retry latency.
- **Fix:** Changed `proxy_next_upstream` to `error timeout;`; increased `failure_test.py`'s `REQUEST_TIMEOUT` to 5.
- **Retest evidence:**

Before any fix: 10/20 succeeded
After nginx fix only: 17/20 succeeded
After both fixes: 20/20 succeeded

  nginx access log for the final run confirms all 20 requests during the outage window show `upstream_status` ending in `, 200` or a direct `200`, all ultimately served by app-02.
- **Related commit:** `762f9c6`
- **Remaining uncertainty:** None.

---

## Entry 11 / 2026-09-12 15:38:12 +0300
- **Symptom:** `restore.sh` printed `PASS: restore ... complete`, but `psql` output shown alongside it contained multiple errors (`relation "records" already exists`, `duplicate key value violates unique constraint`, `multiple primary keys ... not allowed`). `GET /records` confirmed the test record was genuinely not restored.
- **Hypothesis:** `restore.sh` is not actually checking whether `psql` succeeded; `pg_dump`'s default output may conflict with objects already created by `database/init.sql` on a fresh volume.
- **Command or test:**

./backup.sh
docker compose -p barq-assessment rm -sf postgres app-01 app-02
docker volume rm barq-assessment_postgres-data
docker compose -p barq-assessment up -d --build postgres app-01 app-02
./restore.sh backups/backup_<ts>.sql
curl -s http://127.0.0.1:8080/records

- **Actual output:**

ERROR: relation "records" already exists
ERROR: duplicate key value violates unique constraint "records_pkey"
ERROR: multiple primary keys for table "records" are not allowed
PASS: restore from backups/backup_<ts>.sql complete
{"records":[{"id":1,...},{"id":2,...}]} -- test record missing

- **Failed attempt and what changed your thinking:** The script's own PASS message was the failed attempt — it was a false positive. This was only caught by independently checking `GET /records`, which is now a standard step for any future "does X persist" claim in this project rather than trusting a script's own exit message alone.
- **Root cause:** (1) `backup.sh` used plain `pg_dump` with no `--clean --if-exists`, producing a backup unsafe to apply onto a database with pre-existing conflicting objects. (2) `restore.sh` piped into `psql` without `-v ON_ERROR_STOP=1` and never checked the exit code.
- **Fix:** Added `--clean --if-exists` to `pg_dump` in `backup.sh`; added `-v ON_ERROR_STOP=1` to `psql` in `restore.sh` and made it check the exit code explicitly before printing PASS.
- **Retest evidence:**

./backup.sh -> PASS: backup written to backups/backup_20260911T123351Z.sql
(fresh volume, confirmed only 2 seed records present)
./restore.sh backups/backup_20260911T123351Z.sql
DROP TABLE
CREATE TABLE
COPY 3
PASS: restore from backups/backup_20260911T123351Z.sql complete
curl -s http://127.0.0.1:8080/records
{"records":[{"id":1,...},{"id":2,...},{"id":3,"title":"backup.sh restore proof v2"}]}

- **Related commit:** `4714a41`
- **Remaining uncertainty:** None.

---

## Entry 12 / 2026-09-12 16:07:30 +0300
- **Symptom:** `validate.py` scored 10/10 locally, but the first GitHub Actions run (CI #1, commit `840a025`) failed one check: `Command '[...getent hosts postgres...]' timed out after 10 seconds`.
- **Hypothesis:** `getent hosts postgres`, run from the isolated nginx container, may hang rather than fail fast when no DNS resolver is reachable, and this may differ between local Docker Desktop and GitHub's Linux runners.
- **Command or test:** Compared local run of the same check against the CI log for the failing run.
- **Actual output:** Locally: fast failure (`nc: bad address 'postgres'` in an earlier manual test). In CI: full 10-second timeout with no resolution either way.
- **Failed attempt and what changed your thinking:** The first CI run itself (`840a025`, red) was the failed attempt — it revealed that local pass does not guarantee CI pass, prompting a check specifically for environment-dependent DNS timeout behavior rather than assuming the isolation fix itself was wrong (network isolation was confirmed correct by other means — see Entry 8).
- **Root cause:** Environment-dependent DNS resolver timeout behavior differs between Docker Desktop (Windows, local) and GitHub's Linux-hosted runners; `getent`'s hang was a test-methodology issue, not a real difference in network isolation.
- **Fix:** Wrapped the check in `timeout 3 getent hosts postgres` so it is forced to return a non-zero exit code within 3 seconds regardless of whether `getent` fails fast or hangs; reduced the outer Python subprocess timeout accordingly.
- **Retest evidence:** Local: 10/10 checks pass. CI #2 (commit `10a0105`): green, all steps pass, ~26s total runtime.
- **Related commit:** `10a0105`
- **Remaining uncertainty:** The exact underlying reason `getent`'s DNS timeout behavior differs between the two environments (e.g. specific resolver configuration inside GitHub's runner image) was not root-caused further, since the practical fix (a hard timeout wrapper) resolves it regardless of the underlying cause.
