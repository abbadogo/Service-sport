# Contributing

Thanks for taking an interest in Sabis ("Service"). This is a small project, so the process is simple: keep changes small, and keep every change tested.

## Before you start

For anything bigger than a small fix, open an issue first so we can agree on the approach.

## Setup

The engine (`service/`) needs Python 3.11 or newer and has no runtime dependencies. Developer tools are locked in `uv.lock`.

~~~
git clone https://github.com/abbadogo/Service-sport && cd Service-sport
pip install uv && uv sync --frozen
source .venv/bin/activate
~~~

The optional browser app lives in `web/` and needs Node:

~~~
cd web && npm ci
~~~

## Checks to run before you push

Python (from the repository root):

~~~
ruff check .
mypy
python -m unittest discover -s tests
python -m build
~~~

Web (from `web/`):

~~~
npm run lint
npm run typecheck
CI=1 npm test
npm run build
~~~

CI runs the same steps on every push and pull request, including a coverage gate (90%) and a dependency audit. A change is ready when CI is green.

## Commits

- One change per commit: a feature or a fix, not both mixed with formatting or refactors.
- Every behavior change comes with the tests that pin it, in the same commit.
- Use conventional commit messages, for example `feat(web): show squad names on the scoreboard` or `fix: clamp the match clock at 15 minutes`.

## Dependencies

The engine stays standard-library only. If you add or change a developer tool, edit the `dev` group in `pyproject.toml`, run `uv lock`, and commit `uv.lock` together with the change.

## Docs

If you change behavior that the README describes (rules, API, setup), update the README in the same commit.

## Licence of contributions

By submitting a contribution you agree that it may be used under the repository's licence.
