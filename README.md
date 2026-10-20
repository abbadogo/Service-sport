# Sabis ("Service"): street-game simulation engine

A deterministic, headless simulation of **Sabis** (also called "Service"), a street game from Kano, northern Nigeria: a custom
slipper-cut disc (bevelled with a Peak Milk can lid) is rolled like a tyre and kept upright by
stick strikes. When it falls flat, a point is scored against the side it fell on. Written in
standard-library Python, with no GUI.

## Features

- **Gyroscopic tyre-roll physics**: bevel-induced steering bias, precession that tightens as the ball
  slows, grass-friction decay, and a 0 to 90 degree tilt that ends the rally (the "flat slap").
- **Court referee**: team zones with a hard midline ban, serve legality (launch height Z = 0,
  crouched, inside own half, direction, speed), strike legality, out-of-bounds, hand-pickup transition.
- **Match clock**: optional duration, clamped to a 15-minute cap, paused during hand pickups,
  tied matches go to sudden death.
- **Match lifecycle**: serve, rally, score, hand pickup, next serve; the conceding side serves from where it picked the ball up.
- **Players**: 6 per side, a nearest-player "cursor" that chases the ball (automatic, slightly random
  hand-off), stamina and exhaustion, a hold-to-charge strike power bar.
- **Reproducible**: a fixed 120 Hz step and seeded randomness; the same seed replays the same match.

## Rules as implemented

The full, living rulebook is in [`docs/RULES.md`](docs/RULES.md); the table below is a summary.

| Rule | Behaviour |
|---|---|
| Score | The side the ball falls flat on concedes; the other side scores. |
| Out of bounds | The ball leaving the pitch counts against the side it left on. |
| Serve | The conceding side serves from anywhere in its own half, launched at Z = 0. The picker serves from where they picked the ball up (kept 0.5 m back from the midline); the opening serve is from the centre of the half. Default serves scale their speed to the distance and always cross the midline. |
| Lazy serve | A serve that dies on the server's own side with no strike is a point against the server (no re-do). |
| Strikes | A ball may only be struck while it is on the striker's own side. A team may not strike twice in a row until the ball has crossed the midline. A swing can mishit (a weak, misdirected dribble), more often when tired or when the ball is fast. A bar at 90% or more is a long hit: the disc is sent deep, aimed to die short of the far baseline, at extra stamina cost. |
| Rotation | After a point the team that conceded rotates one position slot (volleyball style). Can be switched off. |
| Clock | Runs only while the ball is live. Paused during hand pickup. |
| Sudden death | Tied at 00:00: the next point wins. A leader at 00:00 wins immediately. |

## Requirements

- Python 3.11 or newer (developed and run on 3.12).
- No runtime dependencies, no external accounts, services, API keys or paid tools.

## Setup (fresh clone)

```bash
git clone <repository-url>
cd service_engine
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .                 # installs the engine (no third-party packages)
pip install -r requirements-dev.txt   # only needed for lint, type check, build, audit
```

### GitHub Codespaces / dev container

Opening the repository in a Codespace (or VS Code "Reopen in Container") uses
`.devcontainer/devcontainer.json`: Python 3.12, then `pip install -e .` and
`pip install -r requirements-dev.txt` run automatically, with the Python, Ruff and mypy
extensions. Nothing else is needed. (This configuration has not been opened in a Codespace by the
author yet; report any problems.)

## Sabis Lab (web app)

A browser app to run a match, watch it on the pitch, change the rules and physics from a settings panel, and
run it again. The Python engine stays the single source of truth: a small standard-library server runs matches
and the React + TypeScript app (in `web/`) displays them.

```bash
# terminal 1: the engine API (http://127.0.0.1:8000)
python -m service.api

# terminal 2: the web app (http://localhost:5173), forwards /api to the server
cd web
npm install        # first time only; commit the generated package-lock.json
npm run dev
```

API (JSON): `GET /api/health`, `GET /api/settings` (the editable settings, with ranges and defaults),
`POST /api/matches` with `{"minutes", "seed", "opening_server", "settings": {...}}` returning a replay. All input is
validated on the server; unknown or out-of-range values return a 400 with a message. To make another rule or
physics value editable, add one entry to `service/api/settings.py`; the panel in the web app picks it up.

## Usage

```bash
python -m service                          # one 15-minute match, seed 1
python -m service --minutes 5 --seed 7 --events
python -m service --help
```

`--minutes` must satisfy 0 < m <= 15. Larger values are clamped to 15 and reported; zero,
negative or non-numeric values are rejected with an error and exit code 2.

Programmatic use:

```python
from service.core.config import MatchConfig
from service.engine import ServiceMatch

result = ServiceMatch(MatchConfig(duration_minutes=2, seed=5)).run()
print(result.score_a, result.score_b, result.winner, result.reason)
```

## Environment variables

None. The engine has no secrets, external services or deployment target. When a networked or
persistent component is added, a `.env.example` will be added with it.

## Development commands

| Purpose | Command |
|---|---|
| Tests | `python -m unittest discover -s tests -v` |
| Lint | `ruff check .` |
| Type check | `mypy` |
| Build package | `python -m build` |
| Dependency audit | `pip-audit -r requirements-dev.txt` |
| Web: install | `cd web && npm install` (then `npm ci` once the lockfile is committed) |
| Web: lint / types / tests / build | `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` (in `web/`) |

The same checks run in GitHub Actions (`.github/workflows/ci.yml`) on every push and pull request,
on Python 3.11 and 3.12. Dependabot (`.github/dependabot.yml`) watches pip and Actions weekly.

## Architecture

```
service/
  core/      Team, Vec2, pitch constants; validated config objects
  court/     boundary_referee.py: zones, midline ban, serve/strike/out-of-bounds rules, hand pickup
  physics/   gyroscopic_engine.py: tyre-roll model; forecast.py: cached ball predictions
  agents/    player.py (stamina), chase_controller.py (cursor), formation.py,
             policies.py (serve/strike AI), power_bar.py
  engine/    match_clock.py, state_machine.py (lifecycle), events.py
  api/       server.py (JSON API), settings.py (editable-settings table)
  recording.py  turns a match into a compact replay for the API and scripts
  __main__.py  command-line entry point
web/         Sabis Lab: React + TypeScript + Vite front end (src/lib has the logic, src/components the UI)
tests/       unit, rule, regression and CLI tests
scripts/     developer tools: balance.py, quick_rate.py, record_replay.py (not part of the package)
```

Layers depend downwards: `engine` uses `agents`, `court` and `physics`; `court` uses only `core`.
Serve and strike behaviour are plug-in policies, so AI or human controllers can be swapped in
without touching the match loop.

## Verification status

What has actually been run, and where.

- **GitHub Actions (CI workflow), on pushes to `main`, as of commit `f8e5411` (2026-10-20): passing.**
  - Python 3.11 and 3.12: `ruff check .`, `mypy`, 62 unit tests, `python -m build`, `pip-audit`.
  - Web (Node 22): `npm ci`, `eslint`, `tsc --noEmit`, 27 Vitest tests, `vite build`, `npm audit` (0 vulnerabilities).
- **Run by hand in a GitHub Codespace:** the same Python and web checks, the API server (`python -m service.api`)
  and the Sabis Lab web app in a browser.
- **Not covered by automated tests:** the browser UI end to end (there are tests for the logic, the API client and the
  settings panel, but none that drive the whole app), and the game's balance (see below).
- **No lockfile for the Python dev tools:** the engine has no runtime dependencies. Versions in
  `requirements-dev.txt` are ranges, not hashes; generate a pinned lock (for example with `pip-compile`).
- **Dependabot** (`.github/dependabot.yml`) groups minor and patch updates and holds back major upgrades of React,
  eslint and TypeScript until they are done deliberately.

## Known limitations

- **Where points come from.** In the latest balance run (16 two-minute matches, seed range 100-115) all 39 points
  were flat slaps, about one every 49 s, wins split 9 to 7, 3 of 16 matches reached sudden death. But in 32 of the
  39 points the losing side had no chaser: the ball died after that side's own mishit. Only 6 came from an exhausted
  chaser. The rules say tiredness should decide points; in the current model mishits do most of the work.
- Mishit rates, the strike-aim habits and the bevel strength are tuning guesses, not measurements from real play.
- Balance numbers come from small samples (16 matches); treat them as indicative.
- The full test suite takes about 30 s because several tests play whole matches.
- Single process only; no multiplayer, persistence or networking yet.
- Balance statistics came from small samples (8 to 30 matches), so treat them as indicative.

## Troubleshooting

- `ValueError: duration must satisfy ...`: pass minutes in (0, 15].
- A match ends `ABORTED`: it hit `--max-sim-seconds`, usually a very long sudden death. Raise the
  limit or try another seed.
- `ModuleNotFoundError: service`: run from the repository root, or `pip install -e .`.
