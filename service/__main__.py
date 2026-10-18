"""Command-line entry point: ``python -m service`` (or ``service-sim``)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from service.core.config import MatchConfig
from service.core.types import Team
from service.engine.events import PointScored
from service.engine.match_clock import MAX_DURATION_MINUTES, resolve_duration
from service.engine.state_machine import ServiceMatch


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="service-sim", description="Run one headless Service match.")
    cap = f"{MAX_DURATION_MINUTES:g}"
    p.add_argument("--minutes", type=float, default=None,
                   help=f"match length in minutes, 0 < m <= {cap} (default {cap}; larger values are clamped)")
    p.add_argument("--seed", type=int, default=1, help="random seed; the same seed replays the same match")
    p.add_argument("--opening-server", choices=[t.value for t in Team], default=Team.A.value)
    p.add_argument("--max-sim-seconds", type=float, default=7200.0,
                   help="safety limit on simulated time; the match is aborted past it")
    p.add_argument("--events", action="store_true", help="print every point as it was scored")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        resolution = resolve_duration(args.minutes)
        config = MatchConfig(duration_minutes=args.minutes, seed=args.seed,
                             opening_server=Team(args.opening_server),
                             max_sim_seconds=args.max_sim_seconds)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if resolution.clamped:
        print(f"note: requested {resolution.requested:g} min, "
              f"clamped to the {MAX_DURATION_MINUTES:g} min cap")
    result = ServiceMatch(config).run()
    if args.events:
        for e in result.events:
            if isinstance(e, PointScored):
                print(f"[{e.clock}] {e.scorer.value} scores ({e.reason.name}); "
                      f"{e.conceded_by.value} conceded -> {e.score_a}-{e.score_b}")
    winner = result.winner.value if result.winner else "none"
    print(f"Final score: A {result.score_a} - {result.score_b} B | winner: {winner} "
          f"| ended by: {result.reason.name}")
    print(f"Live {result.live_time_s:.1f}s, paused {result.paused_time_s:.1f}s, "
          f"sudden death {result.overtime_s:.1f}s, simulated {result.sim_time_s:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
