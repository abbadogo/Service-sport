"""Record a match to JSON: python scripts/record_replay.py MINUTES SEED OUT.json"""
import json
import sys

from service.core.config import MatchConfig
from service.engine.state_machine import ServiceMatch
from service.recording import record_match

if __name__ == "__main__":
    replay = record_match(ServiceMatch(MatchConfig(duration_minutes=float(sys.argv[1]), seed=int(sys.argv[2]))))
    with open(sys.argv[3], "w") as fh:
        json.dump(replay, fh, separators=(",", ":"))
    print(len(replay["frames"]), "frames", len(replay["events"]), "events", replay["result"])
