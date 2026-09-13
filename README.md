[# BARQ DevOps Assessment — Shahd Ahmed

Repaired, tested, and documented deployment of a Flask API behind NGINX,
with PostgreSQL and Redis, for the BARQ Systems DevOps Internship
technical assessment.

- **Baseline commit (unmodified starter):** `8442da3`
- **Investigation, decisions, and reports:** see `troubleshooting.md`,
  `log_analysis.md`, `decisions.md`, `security_review.md`,
  `AI_USAGE.md`, `docs/EVIDENCE_INDEX.md`
- **Architecture diagram:** `architecture.png`

## Requirements

- Linux or WSL2
- Docker Desktop (Linux containers) with Docker Compose v2
- Python 3.12 (for `validate.py`, `failure_test.py`, and app-only tests)
- Git

## Setup

```bash
git clone https://github.com/ShahdAhmed609/Shahd-Barq-DevOps-Intern.git
cd Shahd-Barq-DevOps-Intern

# Create the required local secrets file (never committed — see .gitignore)
cp config/app.env.example config/app.env
# Edit config/app.env and replace CHANGE_ME with a real password matching
# POSTGRES_PASSWORD in docker-compose.yml.

# Create the public port config
cp .env.example .env
```

## Build

```bash
docker compose -p barq-assessment build
```

## Start

```bash
docker compose -p barq-assessment up -d
docker compose -p barq-assessment ps -a
```

Wait for all 5 containers (`app-01`, `app-02`, `nginx`, `postgres`,
`redis`) to report `Up ... (healthy)` before testing (postgres/redis/app
containers have explicit healthchecks; nginx has none but depends on the
apps being up first).

## Test — manual endpoint checks

```bash
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/ready
curl -i http://127.0.0.1:8080/instance
curl -H "Content-Type: application/json" -d '{"title":"example"}' http://127.0.0.1:8080/records
curl http://127.0.0.1:8080/records
curl http://127.0.0.1:8080/counter
```

## Test — automated validation

```bash
python3 validate.py
```
Runs bounded checks (readiness, all endpoints, both backends reachable,
real Postgres/Redis operations, unknown-route 404, prohibited host
ports closed, network isolation) and exits non-zero on any failure.

## Failure / recovery test

```bash
python3 failure_test.py
```
Stops `app-01`, measures traffic/errors during the outage, restarts it,
and verifies recovery. Exits non-zero if availability or recovery is not
proven.

## Backup and restore

```bash
# Create a backup
./backup.sh
# Writes a timestamped file to backups/, e.g. backups/backup_20260911T123351Z.sql

# Restore from a backup file
./restore.sh backups/backup_20260911T123351Z.sql
```

To prove persistence end-to-end (data survives full container/volume
recreation, not just a restart):
```bash
curl -s -X POST http://127.0.0.1:8080/records -d '{"title":"persistence check"}'
./backup.sh
docker compose -p barq-assessment rm -sf postgres app-01 app-02
docker volume rm barq-assessment_postgres-data
docker compose -p barq-assessment up -d --build postgres app-01 app-02
sleep 10
curl -s http://127.0.0.1:8080/records   # only seed data — confirms fresh
./restore.sh backups/<your-backup-file>.sql
curl -s http://127.0.0.1:8080/records   # test record is back
```

## App-only tests (fake dependencies, no Docker needed)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```
These check application logic in isolation; they do not prove
environment health (see `log_analysis.md`/`APPLICATION.md`).

## CI

`.github/workflows/ci.yml` runs on every push and pull request: checkout
→ recreate git-ignored config → validate Compose syntax → build → start
→ wait for readiness → run `validate.py`. The pipeline fails if
validation fails.

## Log analysis

```bash
python3 log_analysis/analyze.py
```
Full findings in `log_analysis.md`.

## Stop

```bash
docker compose -p barq-assessment down
```
Stops and removes containers, keeps the named Postgres volume (data
survives).

## Cleanup (full reset, destroys data)

```bash
docker compose -p barq-assessment down -v
```
`-v` also removes the named volume — use only when you want a
completely clean slate; do not use during persistence testing.

## Notes on public port

Before the recorded demonstration, the environment runs on host port
**8080**. During the video, the port is changed live to **8090** and a
third app instance is added. See `docs/EVIDENCE_INDEX.md` for the exact
commit/timestamp this happened at, and the final repo state reflects the
three-instance, port-8090 configuration.]
