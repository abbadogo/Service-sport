# Changelog

All notable changes to this project are documented here.

## [Unreleased]

Verified on Python 3.12: `python -m unittest discover -s tests` ran 96 tests, all passing (about 40 s).

### Added (observability)
- API request logging with request ids, method, route, status and latency (session ids are never logged), an optional
  JSON log format (`--log-format json`), and `GET /api/metrics` with request, latency, match and live-session counters.
  8 new tests.

### Fixed (CI)
- The npm audit step is retried up to three times and each CI job has a 15-minute time limit, after run #46 failed once
  on a registry error (`400 Invalid package tree`) that did not recur with the same lockfile.

### Changed
- Live play hits: aim is now the stick's up/down push at release (straight at the other team by default; it used to
  follow where you last moved, which sent most hits sideways), the swing reaches farther for a faster disc, a hit is
  corrected for the bevel's pull, and a normal hit cannot leave over the far baseline.

### Added
- Live play: `human_team` / `HumanInput` in the engine (drive the nearest player, hold-to-charge strike, long hit,
  swing-and-miss), a session manager and `/api/play` endpoints, and a Play tab in the web app with keyboard and touch
  controls. 20 new Python tests and web tests for the input, API client and strike button.

### Fixed
- CI workflow was rejected by GitHub (`hashFiles` is not allowed in a job-level `if`); removed the condition.
- Web component tests leaked rendered DOM between tests (no automatic cleanup without Vitest globals); added an
  explicit cleanup.
- Ruff findings (one-line compound statements, lambda assignments, an ambiguous variable name) and two mypy errors.
- `npm audit` findings in the test tooling: upgraded vite, vitest and the React plugin (0 vulnerabilities).

### Changed
- Web CI job runs on Node 22. Dependabot groups minor/patch updates and holds back major upgrades of React, eslint and
  TypeScript.

### Added
- Position rotation (draft): after a point the conceding team rotates one slot; toggle `rotation` in the settings.
- Long hit (draft): a power bar at 90% or more sends the disc deep, aimed to die short of the far baseline, for extra
  stamina and slightly worse aim. Editable: level, depth, stamina cost. On/off rules show as checkboxes in the web panel.
- Sabis Lab: JSON API (`python -m service.api`) with server-side validation, an editable-settings table, and a
  React + TypeScript + Vite web app in `web/` with Vitest tests. `service/recording.py` is the shared replay recorder.
- Web CI job (runs once `web/package-lock.json` is committed), npm Dependabot, Node and ports in the dev container.
- `docs/RULES.md`: living rulebook for Sabis, with draft rules and open questions marked.
- Dev container for GitHub Codespaces (`.devcontainer/devcontainer.json`).
- Packaging (`pyproject.toml`), GitHub Actions workflow, Dependabot config, `.gitignore`.
- `python -m service` command-line entry point with input validation.
- Rule, regression and CLI tests (configuration validation, out-of-bounds scoring on every edge,
  strike-counter regression).

### Changed
- Scoring rework after balance testing showed rallies never ended (a fresh chaser never misses): added a mishit
  rule (draft), balls may only be struck on the striker's own side, the front line stands further back, chasers meet the
  ball about 8 m inside their half instead of scrumming at the center line, and strikers aim slightly right to allow
  for the bevel's slice. Result over 16 matches: about one point per 49 s, all flat slaps (previously mostly
  out-of-bounds exits or no points at all).
- Halved the bevel's steering strength (`taper_coupling` 0.003 to 0.0015). Measured over 300 simulated
  strikes: sideways drift over a full roll fell from about 12 m to about 7 m on average (max 25 m to 17 m).
- Project renamed in the docs to Sabis ("Service").
- Serves may now be taken from anywhere in the server's own half (previously only the baseline). The hand-pickup
  transition no longer carries the ball to the baseline; the default serve speed now depends on where the
  server stands (checked over 2,000 simulated serves, all crossed the midline).
- Removed `scripts/run_demo.py` (replaced by the CLI).
- Cleaned unused imports and over-long lines found by a manual pre-check.

## [0.1.0]

### Added
- Core engine: gyroscopic tyre-roll physics, court referee, match clock with 15-minute cap and
  sudden death, match state machine.
- Nearest-player cursor with stamina, 6 players per side, hold-to-charge strike power bar.
- Rules: serves must cross the midline, lazy serve is a point against the server, out of bounds
  counts against the side the ball left on.
- Developer scripts for balance testing and replay recording.
