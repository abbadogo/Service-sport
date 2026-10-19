"""Balance test: python scripts/balance.py [matches] [minutes]"""
import sys
from collections import Counter
from multiprocessing import Pool

from service.core.config import MatchConfig
from service.engine.events import PointScored, StrikeMade
from service.engine.state_machine import ServiceMatch


def one(args):
    seed, minutes = args
    r = ServiceMatch(MatchConfig(duration_minutes=minutes, seed=seed)).run()
    pts = [e for e in r.events if isinstance(e, PointScored)]
    return dict(a=r.score_a, b=r.score_b, win=r.winner.value if r.winner else "-", sd=r.overtime_s > 0,
                reasons=Counter(e.reason.name for e in pts),
                chaser=Counter("none" if e.chaser_id is None else ("exhausted" if e.chaser_stamina < 0.15 else "tired" if e.chaser_stamina < 0.45 else "fresh") for e in pts),
                conceded=Counter(e.conceded_by.value for e in pts),
                strikes=sum(isinstance(e, StrikeMade) for e in r.events), live=r.live_time_s)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    mins = float(sys.argv[2]) if len(sys.argv) > 2 else 2
    with Pool() as p:
        R = p.map(one, [(s, mins) for s in range(100, 100 + n)])
    def tot(k):
        return sum((r[k] for r in R), Counter())
    pts = sum(r["a"] + r["b"] for r in R)
    print(f"matches={n} minutes={mins}")
    print("wins:", Counter(r["win"] for r in R), "sudden death:", sum(r["sd"] for r in R))
    print("avg points/match: %.2f  (A %.2f, B %.2f)" % (pts / n, sum(r["a"] for r in R) / n, sum(r["b"] for r in R) / n))
    print("points lost by side:", dict(tot("conceded")))
    print("how points end:", dict(tot("reasons")))
    print("chaser state when point lost:", dict(tot("chaser")))
    print("avg strikes/match: %.0f, avg seconds per point: %.1f" % (sum(r["strikes"] for r in R) / n, sum(r["live"] for r in R) / max(pts, 1)))
    print("scoreless matches:", sum(1 for r in R if r["a"] + r["b"] == 0))
