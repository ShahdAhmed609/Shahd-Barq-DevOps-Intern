# Evidence and Submission Index

- **Repository URL:** https://github.com/ShahdAhmed609/Shahd-Barq-DevOps-Intern
- **Final commit:** *(fill in after video — the last commit pushed once Part 5 is complete)*
- **Matching CI run:** *(fill in after final commit — link to the GitHub Actions run for the final commit)*
- **Continuous 12–18 minute video URL:** *(fill in after recording/uploading)*
- **Challenge receipt ID:** *(fill in from `.assessment/challenge.json` after running `./video_challenge.sh` during the video)*
- **Starting video commit:** *(fill in — the commit HEAD is on immediately before recording begins)*
- **Later documentation-only commits, if any:** *(fill in if any docs are touched after the video, with a one-line explanation each — e.g. filling in this index's video-timestamp column)*

This index matches the final README, diagram, GitHub code, and video to
the final three-instance, port-8090 configuration reached at the end of
the recording.

---

## Requirement → file/output → commit → video timestamp

| Requirement | File / Output | Commit | Video timestamp |
|---|---|---|---|
| Baseline kept, unmodified, before technical changes | Full repo state | `8442da3` | TBD |
| Healthcheck targets correct path (/health) | `docker-compose.yml` | `ba5785c` | TBD |
| Flask binds to 0.0.0.0 (reachable from other containers) | `docker-compose.yml` | `9363cdb` | TBD |
| nginx listen port matches Docker's port mapping | `nginx/nginx.conf` | `93c6dcb` | TBD |
| nginx upstream port for app-01 corrected | `nginx/nginx.conf` | `9babb60` | TBD |
| app-02 reports correct instance identity | `docker-compose.yml` | `a2a0450` | TBD |
| Secrets excluded from git; safe .env.example provided | `.gitignore`, `config/app.env.example` | `ae31e6b` | TBD |
| Postgres data directory persists (volume/tmpfs fix) | `docker-compose.yml` | `7a1cfd8` | TBD |
| Postgres/Redis ports not published to host | `docker-compose.yml` | `c172ead` | TBD |
| nginx removed from backend network (isolation) | `docker-compose.yml` | `ba33455` | TBD |
| DATABASE_URL/REDIS_URL port + password corrected | `config/app.env` (git-ignored; see `troubleshooting.md` Entry 9) | `ae31e6b` (indirect — no diff by design) | TBD |
| Log analysis: all 10 required questions answered | `log_analysis.md`, `log_analysis/analyze.py` | `9fd9fb8` | TBD |
| `validate.py`: bounded checks, PASS/FAIL, non-zero exit | `validate.py` | `02f06a8` | TBD |
| `validate.py`: 10/10 checks passing (local) | `validate.py` output | `02f06a8` | TBD |
| `failure_test.py`: stop/measure/restore/verify | `failure_test.py` | `f651294` | TBD |
| nginx failover enabled; test client timeout corrected | `nginx/nginx.conf`, `failure_test.py` | `762f9c6` | TBD |
| Failure/recovery proof: 20/20 succeed during outage, full recovery confirmed | `failure_test.py` output | `762f9c6` | TBD |
| `backup.sh` / `restore.sh` implemented | `backup.sh`, `restore.sh` | `4714a41` | TBD |
| Persistence proof: record survives full container + volume recreation via backup/restore | `backup.sh`/`restore.sh` output, `troubleshooting.md` Entry 11 | `4714a41` | TBD |
| `.github/workflows/ci.yml` created, runs on push/PR | `.github/workflows/ci.yml` | `840a025` | TBD |
| CI run #1: first real run, red (DNS-hang failure found) | GitHub Actions run for `840a025` | `840a025` | TBD |
| CI fix: network isolation check made resilient to DNS hang | `validate.py` | `10a0105` | TBD |
| CI run #2: green, all steps pass | GitHub Actions run for `10a0105` | `10a0105` | TBD |
| `troubleshooting.md`: investigation journal, 12 entries | `troubleshooting.md` | `df9f360` | TBD |
| `decisions.md`: 7 decisions with required fields | `decisions.md` | `f05c2d8` | TBD |
| `security_review.md`: 10 findings with required fields | `security_review.md` | `d845ea9` | TBD |
| `AI_USAGE.md`: itemized AI usage disclosure | `AI_USAGE.md` | `00c2754` | TBD |
| `architecture.png`: request flow, ports, networks, storage, health | `architecture.png` | `052674e` | TBD |
| `README.md`: copyable setup/build/run/test/failure/backup/cleanup | `README.md` | `6488a39` | TBD |
| Repository, starting commit, clean git status shown live | Live terminal | starting video commit (above) | TBD |
| Environment built/started from stopped state; service health shown | Live terminal | — | TBD |
| `/`, `/health`, `/ready`, `/records`, `/counter` tested live | Live terminal | — | TBD |
| Both backends proven via `/instance` through nginx | Live terminal | — | TBD |
| One backend stopped live; continued traffic/errors shown; recovered | Live terminal, `failure_test.py` | *(commit if any made live)* | TBD |
| Created record shown surviving app + Postgres container recreation | Live terminal | — | TBD |
| Validation and failure test run live; one historical-log finding demonstrated | Live terminal, `log_analysis.md` | — | TBD |
| `./video_challenge.sh` run once (first time in this working copy) | Live terminal, `.assessment/challenge.json` | — | TBD |
| Runtime fault diagnosed and fixed live, without full-stack reset | Live terminal | *(commit made live, if any)* | TBD |
| Public port changed live 8080 → 8090; nginx proven on 8090 | Live terminal, `docker-compose.yml`/`.env` | *(commit made live)* | TBD |
| Third app instance added live; all three respond; validation rerun | Live terminal, `docker-compose.yml` | *(commit made live)* | TBD |
| `git status`/`git diff` shown; changes explained; commit hashes shown on screen | Live terminal | *(commits made live)* | TBD |
| Video commits pushed; linked to commit and video timestamp | GitHub | *(commits made live)* | TBD |
