# Handover: Sabis ("Service") project, 2026-10-26

**For the next Claude.** Read this first. Source of truth is the GitHub repo `abbadogo/Service-sport`, branch `main`
(not this zip). The user works from a PHONE in a GitHub Codespace: give short copy-paste commands, one step at a time,
and ask for screenshots. They do not read code. Never claim anything "passes" without seeing output.

## What it is
Sabis ("Service") is a street game from Kano, Nigeria: 6v6, a beveled slipper-disc rolled like a tyre and kept upright
with sticks; it scores against the side it falls flat on. Python engine in `service/` (stdlib only), React+TS web app
in `web/` (Sabis Lab: Watch/tune and a live Play tab). Rules: `docs/RULES.md`. Built to the user's "DataFactor
blueprint": small focused commits that include their tests, honest docs, green CI, no fake history.

## State
- CI (GitHub Actions: Python 3.11+3.12, web job) was green through the lockfile and observability commits; the last
  pushed commit `6c716bf` (test hygiene) was still running when last seen. Ask for `gh run list --limit 4`.
- Latest DataFactor score 69.8 (offer line is 70; email is sales-y, payout estimate is only $30-90). Do not pad commits.
- Python 3.14 in the Codespace; lockfile `requirements-dev.lock.txt` (pip-compile) is what CI installs.
- Coverage of `service/` alone: 95% (2003 statements, 108 missed). Weakest: logging_setup 65%, types 87%.

## PENDING: apply this zip (verified here: 99 Python tests OK, run under -W error::ResourceWarning)
1. **Race fix** in `service/api/server.py`: requests are now logged/counted BEFORE the reply is sent (before, a client
   reading the log/metrics right after a reply could miss it; one flaky failure was seen in
   `test_requests_are_logged_with_fields_but_never_with_a_session_id`). Plus tests in `tests/test_observability.py`
   (a regression test for the ordering, and `configure_logging`/traceback tests). Three concurrent full-suite runs
   passed 99/99 before the sandbox reset.
2. **Coverage gate**: `python add_coverage.py` edits ci.yml (Test step -> `coverage run ... && coverage report`),
   pyproject.toml (`fail_under = 90`, source = service), requirements-dev.txt, README, CHANGELOG. Idempotent.
   It does NOT regenerate the lockfile; the user must: `pip-compile --output-file=requirements-dev.lock.txt
   requirements-dev.txt`, then check `grep -i '^coverage==' requirements-dev.lock.txt` (CI installs from the lock!).

Steps to give the user (unzip name may arrive with "(1)": quote it):
`unzip -o <zip>` at repo root -> `ruff check . --fix`, `ruff check .`, `mypy | tail -3`, unittest ->
**commit 1** `git add service tests` "fix: log and count a request before replying" -> `python add_coverage.py`,
`pip-compile ...`, grep check, `coverage run -m unittest discover -s tests && coverage report` (must be >= 90) ->
**commit 2** ci.yml pyproject.toml requirements-dev.txt requirements-dev.lock.txt README.md CHANGELOG.md
"ci: enforce 90% coverage of the service package" -> push -> read the Actions run.
Then delete the zip and `add_coverage.py` (`*.zip` is gitignored; the script is not: do not commit it).

## Next after that
- Web coverage: measure first (`npm i -D @vitest/coverage-v8`, `npx vitest run --coverage`), set a threshold a few
  points below the measured value, not a guessed 70.
- **Ask the user how the Play tab feels** (they never answered): straight hits? easier to hit? lag? Last fix made hits
  go straight at the other team (stick up/down at release angles them), swing reach grows with disc speed (0.25 s),
  bevel aim assist 0.9, normal hits can't go out of the far end. They were stuck forwarding port 5173 in the Ports tab.
- Open design questions: far-baseline overhit currently scores for the hitter (long hit is range-limited to avoid it);
  points come mostly from mishits not tired chasers; serves are automatic; Play uses HTTP polling (WebSocket later).
- When Play feels right: a real `v0.1.0` tag/release (only then).

## Habits that matter
Small commits with their tests; `git status --short` before every commit; never weaken a check; explain failures from
the actual log (`gh run view $(gh run list --status failure --limit 1 --json databaseId -q '.[0].databaseId')
--log-failed | tail -40`; `gh run rerun` is NOT permitted by the Codespace token); the sandbox has no network, no
ruff/mypy, cannot run npm: React changes stay unverified until the user runs lint/typecheck/test/build.
