"""Fast scoring-rate probe: python scripts/quick_rate.py SKILL [seeds] [sim_seconds]"""
import random
import sys
from collections import Counter

from service.agents.policies import DefaultStrikePolicy
from service.core.config import MatchConfig
from service.engine import ServiceMatch
from service.engine.events import PointScored, StrikeMade

skill = float(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
sim = float(sys.argv[3]) if len(sys.argv) > 3 else 240
reasons, chaser, conceded, pts, live, strikes = Counter(), Counter(), Counter(), 0, 0.0, 0
for seed in range(500, 500 + n):
    m = ServiceMatch(MatchConfig(duration_minutes=15, seed=seed, max_sim_seconds=sim))
    m.strike_policy = DefaultStrikePolicy(random.Random(seed), m.strike_cfg, m.engine, curve_skill=skill)
    r = m.run(); live += r.live_time_s
    for e in r.events:
        if isinstance(e, StrikeMade): strikes += 1
        if isinstance(e, PointScored):
            pts += 1; reasons[e.reason.name] += 1; conceded[e.conceded_by.value] += 1
            chaser["none" if e.chaser_id is None else "exhausted" if e.chaser_stamina < .15 else "fresh/tired"] += 1
print(f"skill={skill} points={pts} per live minute={pts/(live/60):.2f} strikes/min={strikes/(live/60):.0f}", dict(reasons), dict(chaser), dict(conceded))
