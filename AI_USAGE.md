# AI Usage Disclosure

AI (Claude, Anthropic) was used interactively throughout this
assessment. Each significant use is recorded below individually.

---

## Use 1: Diagnostic strategy for the broken environment

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Suggest diagnostic commands (`docker inspect`,
  `docker compose logs`, `docker network inspect`, etc.) to isolate each
  bug's root cause after I reported a symptom and pasted real command
  output.
- **Files or decisions affected:** `docker-compose.yml`,
  `nginx/nginx.conf`, `config/app.env` — every Part 2 fix listed in
  troubleshooting.md.
- **What you changed or rejected:** Accepted the diagnostic approach in
  general, but the fix cycle was iterative — e.g. for the nginx port
  issue, an initial `up -d --build` retest after editing the config
  still failed; I reported this back and we identified that bind-mounted
  config changes require `docker compose restart`, not just `up -d`.
- **How you independently verified it:** Ran every suggested command
  myself against my real Docker environment; retested each fix with
  `curl`/`docker compose ps -a`/log inspection before accepting it as
  working. All retest output shown in troubleshooting.md is genuine.
- **Related commit:** `ba5785c`, `9363cdb`, `93c6dcb`, `9babb60`,
  `a2a0450`, `7a1cfd8`, `c172ead`, `ba33455`

---

## Use 2: Log analysis script and correlation methodology

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Write the Python script (`log_analysis/analyze.py`) to
  parse the three JSON-lines/plain-text logs, and suggest correlating
  entries across logs via the shared `request_id` field.
- **Files or decisions affected:** `log_analysis/analyze.py`,
  `log_analysis.md`.
- **What you changed or rejected:** Rejected the AI's initial framing of
  Incident 1 as a clean, continuous app-02 outage — I ran a follow-up
  check (`grep` for app-02 activity during that exact window) that
  revealed one request succeeded mid-outage, which changed the
  conclusion to "connectivity flapping" rather than a clean binary
  outage. Also caught a discrepancy the AI's first pass missed (error.log
  showing 59 connection-refused events vs. access.log showing only 40
  client-facing 502s) by asking for the per-path breakdown directly,
  which led to discovering nginx's retry-masking behavior.
- **How you independently verified it:** Re-ran the script after every
  change; manually inspected raw log lines for specific `request_id`s
  (e.g. `lab-000238`, `lab-000606`) via `grep` before accepting any
  correlation claim, rather than trusting the script's summary output
  alone.
- **Related commit:** `9fd9fb8`

---

## Use 3: validate.py implementation

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Draft the structure and checks for `validate.py` (bounded
  wait, PASS/FAIL per check, endpoint/network isolation checks) based
  on the brief's requirements.
- **Files or decisions affected:** `validate.py`.
- **What you changed or rejected:** After the first GitHub Actions run
  (CI #1) failed on the network-isolation check with a 10-second hang
  (not the fast failure seen locally), I reported this back rather than
  assuming the check itself was wrong; the fix (wrapping the check in
  `timeout 3`) was then applied and verified in a second CI run.
- **How you independently verified it:** Ran locally (10/10 passing)
  and, critically, in GitHub Actions on a clean machine unrelated to my
  local setup — this caught a real environment-dependent bug that local
  testing alone did not reveal.
- **Related commit:** `02f06a8`, `10a0105`

---

## Use 4: failure_test.py implementation

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Draft `failure_test.py` (stop a backend, measure
  traffic/errors, restore, verify recovery) per Part 3's requirements.
- **Files or decisions affected:** `failure_test.py`.
- **What you changed or rejected:** Initial run showed only 10/20
  requests succeeding during the outage. I did not accept this as
  expected behavior and asked why; investigation traced it to
  `nginx.conf`'s `proxy_next_upstream off;` setting. After fixing that,
  a result of 17/20 (not the expected 20/20) was also not accepted at
  face value — further investigation via nginx's own access log showed
  the remaining 3 failures were a bug in the test script's own
  `REQUEST_TIMEOUT` value, not the environment, which I confirmed by
  requesting the debug output be un-suppressed to see the real
  exception.
- **How you independently verified it:** Ran the script against the
  real, live environment at each stage (before fix, after nginx fix,
  after both fixes) and compared the actual pass counts (10/20, 17/20,
  20/20) rather than accepting a single claimed result.
- **Related commit:** `f651294`, `762f9c6`

---

## Use 5: backup.sh / restore.sh implementation

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Draft `backup.sh`/`restore.sh` using `pg_dump`/`psql`.
- **Files or decisions affected:** `backup.sh`, `restore.sh`.
- **What you changed or rejected:** Rejected the first version's
  `restore.sh` as broken, even though it printed "PASS" — the visible
  `psql` output alongside it showed real SQL errors
  (`relation "records" already exists`, etc.), and I independently
  confirmed via `GET /records` that the test record was genuinely not
  restored. This was reported back, leading to two fixes: `pg_dump
  --clean --if-exists` in `backup.sh`, and explicit exit-code checking
  via `psql -v ON_ERROR_STOP=1` in `restore.sh`.
- **How you independently verified it:** Ran a full end-to-end test from
  a completely wiped Postgres volume (not just a container restart):
  created a record, backed it up, destroyed the volume, recreated from
  scratch, confirmed only seed data present, restored, confirmed the
  test record was back — verified via direct `curl` output at each
  step, not by trusting the script's own success message.
- **Related commit:** `4714a41`

---

## Use 6: CI pipeline (.github/workflows/ci.yml)

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Draft the GitHub Actions workflow, including handling the
  git-ignored `config/app.env` file needed for a clean CI checkout to
  actually run.
- **Files or decisions affected:** `.github/workflows/ci.yml`.
- **What you changed or rejected:** Accepted the initial structure; the
  first real run (CI #1) failed for a reason not anticipated in the
  draft (the DNS-hang issue covered in Use 3) — this was diagnosed and
  fixed based on the actual CI log output, not assumed in advance.
- **How you independently verified it:** Watched both runs execute live
  in GitHub's Actions tab; confirmed CI #2 genuinely passed on a fresh,
  independent machine before considering the pipeline complete.
- **Related commit:** `840a025`, `10a0105`

---

## Use 7: Documentation drafting (log_analysis.md, troubleshooting.md, decisions.md, security_review.md, this file)

- **Tool/model:** Claude (Anthropic)
- **Purpose:** Structure and draft the required documentation files from
  the real commands, output, and commit history already generated
  during the hands-on work, matching the exact templates required by
  the assessment.
- **Files or decisions affected:** `log_analysis.md`,
  `troubleshooting.md`, `decisions.md`, `security_review.md`,
  `AI_USAGE.md`.
- **What you changed or rejected:** Requested restructuring multiple
  times to match the exact required field templates (the first draft of
  each document used a different, looser structure than what the
  assessment templates actually specify) — final versions follow the
  provided templates exactly.
- **How you independently verified it:** Cross-checked every commit hash
  and timestamp cited in these documents against my own
  `git log --format="%h %ad %s" --date=iso` output before accepting the
  final text; corrected/confirmed hashes where placeholders had been
  left in earlier drafts.
- **Related commit:** `9fd9fb8` (log_analysis.md), and the commits for
  troubleshooting.md, decisions.md, security_review.md, and this file
  once committed.
