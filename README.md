# Sabis ("Service"): street-game simulation engine

A deterministic, headless simulation of **Sabis** (also called "Service"), a street game from Kano, northern Nigeria: a custom
slipper-cut disc (bevelled with a Peak Milk can lid) is rolled like a tyre and kept upright by
stick strikes. When it falls flat, a point is scored against the side it fell on. Written in
standard-library Python; the engine has no GUI. An optional browser app, Sabis Lab, sits on top of it (see below).

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
pip install -r requirements-dev.lock.txt   # pinned dev tools (what CI uses): lint, type check, build, audit
python -m unittest discover -s tests  # run the tests (about 40 s)
python -m service --minutes 2 --events   # play a simulated match
```

### GitHub Codespaces / dev container

Opening the repository in a Codespace (or VS Code "Reopen in Container") uses
`.devcontainer/devcontainer.json`: Python 3.12, then `pip install -e .` and
`pip install -r requirements-dev.txt` run automatically, with the Python, Ruff and mypy
extensions. Nothing else is needed.

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
| Tests with coverage (CI fails below 90%) | `coverage run -m unittest discover -s tests && coverage report` |
| Lint | `ruff check .` |
| Type check | `mypy` |
| Build package | `python -m build` |
| Dependency audit | `pip-audit -r requirements-dev.txt` |
| Web: install | `cd web && npm ci` |
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

## Playing a live match

The **Play** tab in Sabis Lab lets you play Team A against the computer, in real time.

- You drive the player **nearest the disc** (the ringed one); control passes to whoever is closest as the disc moves.
  The computer plays everyone else.
- **Move:** WASD, the arrow keys, or the on-screen stick (phones and tablets). You still cannot cross the center line.
- **Strike:** hold SPACE or the HOLD button to fill the power bar, release to hit. The disc goes straight at the other
  team; push the stick up or down (W/S) as you release to angle it, up to about 35 degrees. A bar at 90% or more is a long hit.
  Swings are forgiving (your reach grows with the disc's speed) and a straight hit is corrected for the bevel's curve; both
  are adjustable under "Playing yourself" in the settings. Swinging when the disc is out of reach is a miss, and your swings can mishit
  (more often when tired).
- Serves are automatic in this version, for both teams.

How it works: `POST /api/play` starts a session; the browser then calls `POST /api/play/<id>/step` about 20 times a
second with `{move, aim, charge}`. Each call advances the match by the real time since the previous call (at most 0.25 s),
so the game keeps its pace whatever the network delay, and returns the newest frame. Sessions expire after 5 idle minutes
and at most 8 run at once. Engine side: `ServiceMatch(..., human_team=Team.A)` and `step(HumanInput(...))`.

### Logs and metrics

Each request gets an id (response header `X-Request-Id`, repeated as `request_id` in error bodies) and is logged with its
method, route, status and time. Session ids are secrets, so they are never logged (the route appears as
`/api/play/{id}/step`). `python -m service.api --log-format json` prints one JSON object per line. `GET /api/metrics`
returns in-process counters (reset on restart); it exposes counts only.

## Sabis Lab (web app)

A browser app to run a match, watch it on the pitch, change the rules and physics from a settings panel, and
run it again. The Python engine stays the single source of truth: a small standard-library server runs matches
and the React + TypeScript app (in `web/`) displays them.

```bash
# terminal 1: the engine API (http://127.0.0.1:8000)
python -m service.api

# terminal 2: the web app (http://localhost:5173), forwards /api to the server
cd web
npm ci   # installs exactly what package-lock.json pins
npm run dev
```

API (JSON): `GET /api/health`, `GET /api/metrics` (request counts, latency, matches run, live sessions),
`GET /api/settings` (the editable settings, with ranges and defaults),
`POST /api/matches` with `{"minutes", "seed", "opening_server", "settings": {...}}` returning a replay. All input is
validated on the server; unknown or out-of-range values return a 400 with a message. To make another rule or
physics value editable, add one entry to `service/api/settings.py`; the panel in the web app picks it up.

## Verification status

What has actually been run, and where.

- **GitHub Actions (CI workflow), on pushes to `main`, as of commit `4b6d585` (run #65, 2026-10-30): passing.**
  - Python 3.11 and 3.12: `ruff check .`, `mypy`, 99 unit tests, `python -m build`, `pip-audit`.
  - Web (Node 22): `npm ci`, `eslint`, `tsc --noEmit`, 120 Vitest tests, `vite build`, `npm audit` (0 vulnerabilities).
- **Run by hand in a GitHub Codespace:** the same Python and web checks, the API server (`python -m service.api`)
  and the Sabis Lab web app in a browser.
- **One red run in the history (#46, 2026-10-22):** a documentation-only commit failed at `npm audit` with an error from
  the npm registry (`400 Invalid package tree`) after every other step passed. The same lockfile passed in the runs
  before and after, so it was treated as a transient registry fault; the audit step now retries up to three times (a real
  vulnerability still fails it) and each job has a 15-minute limit.
- **Live play:** covered by the CI run above (20 Python tests for the engine control code, session manager and API; web
  tests for the input logic, API client and strike button). A real-time check against a live server kept pace with the
  wall clock (5.4 s of play simulated 5.3 s). The Play screen has been played informally on a phone browser by the
  author, but there has been no structured playtest.
- **Not covered by automated tests:** the browser UI end to end (there are tests for the logic, the API client and the
  settings panel, but none that drive the whole app), and the game's balance (see below).
- **Python dev tools are pinned** in `requirements-dev.lock.txt` (generated from `requirements-dev.txt` with
  `pip-compile`; regenerate it to upgrade). The engine itself has no runtime dependencies.
- **Dependabot** (`.github/dependabot.yml`) groups minor and patch updates and holds back major upgrades of React,
  eslint and TypeScript until they are done deliberately.

## Known limitations

- **Where points come from.** In the latest balance run (16 two-minute matches, seed range 100-115) all 39 points
  were flat slaps, about one every 49 s, wins split 9 to 7, 3 of 16 matches reached sudden death. But in 32 of the
  39 points the losing side had no chaser: the ball died after that side's own mishit. Only 6 came from an exhausted
  chaser. The rules say tiredness should decide points; in the current model mishits do most of the work.
- Mishit rates, the strike-aim habits and the bevel strength are tuning guesses, not measurements from real play.
- The full test suite takes about 40 s because several tests play whole matches.
- Live play uses plain HTTP polling (about 20 requests a second), so it feels best on a fast, low-latency connection; a
  WebSocket connection would be smoother. You play Team A only, serves are automatic, and there is no sound.
- Single process only; no accounts, persistence or online play against other people yet.
- Balance statistics came from small samples (8 to 30 matches), so treat them as indicative.

## Troubleshooting

- `ValueError: duration must satisfy ...`: pass minutes in (0, 15].
- A match ends `ABORTED`: it hit `--max-sim-seconds`, usually a very long sudden death. Raise the
  limit or try another seed.
- `ModuleNotFoundError: service`: run from the repository root, or `pip install -e .`.
