import json
import random
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from service.__main__ import main
from service.agents.player import build_team
from service.agents.roster import PlayerProfile, Squad, load_squad
from service.core.config import MatchConfig
from service.core.types import Team
from service.engine.state_machine import ServiceMatch
from service.recording import record_match

SQUADS_DIR = Path(__file__).resolve().parent.parent / "squads"


def flat_squad(name: str, rating: int) -> Squad:
    return Squad(name, tuple(PlayerProfile(f"{name}{i}", i + 1, rating, rating, rating, rating, rating)
                             for i in range(6)))


class ProfileTests(unittest.TestCase):
    def test_validation(self):
        for bad in (dict(name="", shirt=1), dict(name="X", shirt=0), dict(name="X", shirt=100),
                    dict(name="X", shirt=True), dict(name="X", shirt=1, pace=0),
                    dict(name="X", shirt=1, power=100), dict(name="X", shirt=1, reach=50.5),
                    dict(name="X", shirt=1, accuracy=True)):
            with self.assertRaises(ValueError, msg=str(bad)):
                PlayerProfile(**bad)

    def test_ratings_map_in_the_right_direction(self):
        lo, hi = PlayerProfile("Lo", 1, 1, 1, 1, 1, 1), PlayerProfile("Hi", 2, 99, 99, 99, 99, 99)
        self.assertLess(lo.max_speed, hi.max_speed)
        self.assertLess(lo.strength, hi.strength)
        self.assertLess(lo.reach_m, hi.reach_m)
        self.assertGreater(lo.drain_mult, hi.drain_mult)      # more endurance drains less
        self.assertGreater(lo.mishit_mult, hi.mishit_mult)    # more accuracy mishits less
        self.assertGreater(lo.aim_mult, hi.aim_mult)
        self.assertEqual((lo.overall, hi.overall), (1, 99))

    def test_an_average_player_is_close_to_the_old_defaults(self):
        p = PlayerProfile("Mid", 5)
        self.assertAlmostEqual(p.max_speed, 6.75, delta=0.02)
        self.assertAlmostEqual(p.strength, 1.0, delta=0.01)
        self.assertAlmostEqual(p.reach_m, 1.3, delta=0.01)
        for m in (p.drain_mult, p.mishit_mult, p.aim_mult):
            self.assertAlmostEqual(m, 1.0, delta=0.01)

    def test_from_dict_rejects_typos_and_missing_fields(self):
        with self.assertRaises(ValueError):
            PlayerProfile.from_dict({"name": "X", "shirt": 1, "pac": 80})
        with self.assertRaises(ValueError):
            PlayerProfile.from_dict({"name": "X"})
        with self.assertRaises(ValueError):
            PlayerProfile.from_dict("X")  # type: ignore[arg-type]


class SquadTests(unittest.TestCase):
    def test_needs_six_players_and_unique_shirts(self):
        five = tuple(PlayerProfile(f"P{i}", i + 1) for i in range(5))
        with self.assertRaises(ValueError):
            Squad("Short", five)
        dup = tuple(PlayerProfile(f"P{i}", 7) for i in range(6))
        with self.assertRaises(ValueError):
            Squad("Dup", dup)
        with self.assertRaises(ValueError):
            Squad("", tuple(PlayerProfile(f"P{i}", i + 1) for i in range(6)))

    def test_shipped_squads_load(self):
        for f in sorted(SQUADS_DIR.glob("*.json")):
            sq = load_squad(f)
            self.assertEqual(len(sq.players), 6, f.name)
            self.assertTrue(1 <= sq.overall <= 99)
        self.assertGreaterEqual(len(list(SQUADS_DIR.glob("*.json"))), 2)

    def test_load_errors_are_value_errors(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_squad(bad)
            with self.assertRaises(ValueError):
                load_squad(Path(d) / "missing.json")
            bad.write_text(json.dumps({"name": "X", "players": "no"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_squad(bad)
            bad.write_text(json.dumps({"name": "X", "players": [], "extra": 1}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_squad(bad)


class BuildTeamTests(unittest.TestCase):
    def test_squad_gives_names_and_ratings_in_slot_order(self):
        sq = load_squad(SQUADS_DIR / "kano_stars.json")
        team = build_team(Team.B, random.Random(1), squad=sq)
        self.assertEqual([p.name for p in team], [p.name for p in sq.players])
        self.assertEqual([p.pid for p in team], [f"B{i}" for i in range(1, 7)])
        self.assertEqual(team[5].max_speed, sq.players[5].max_speed)

    def test_without_a_squad_players_are_unnamed_and_neutral(self):
        for p in build_team(Team.A, random.Random(1)):
            self.assertEqual((p.name, p.shirt), ("", 0))
            self.assertEqual((p.drain_mult, p.mishit_mult, p.aim_mult), (1.0, 1.0, 1.0))

    def test_endurance_changes_how_fast_stamina_drains(self):
        tired = flat_squad("T", 1).players[0]
        fit = flat_squad("F", 99).players[0]
        squad_t = Squad("T", (tired,) + flat_squad("T", 1).players[1:])
        squad_f = Squad("F", (fit,) + flat_squad("F", 99).players[1:])
        a = build_team(Team.A, random.Random(1), squad=squad_t)[0]
        b = build_team(Team.A, random.Random(1), squad=squad_f)[0]
        for p in (a, b):
            p.max_speed = 6.0  # same speed for both, so only the drain differs
            for _ in range(240):
                p.move_toward(type(p.pos)(p.pos.x + 50.0, p.pos.y), 1 / 120)
        self.assertLess(a.stamina, b.stamina)


class MatchTests(unittest.TestCase):
    def test_same_seed_and_squads_replay_the_same_match(self):
        sqs = {Team.A: load_squad(SQUADS_DIR / "kano_stars.json"),
               Team.B: load_squad(SQUADS_DIR / "dala_warriors.json")}
        runs = [ServiceMatch(MatchConfig(duration_minutes=0.5, seed=4), squads=sqs).run() for _ in range(2)]
        self.assertEqual((runs[0].score_a, runs[0].score_b, runs[0].sim_time_s),
                         (runs[1].score_a, runs[1].score_b, runs[1].sim_time_s))

    def test_replay_carries_names_only_when_squads_are_used(self):
        sqs = {Team.A: load_squad(SQUADS_DIR / "kano_stars.json"),
               Team.B: load_squad(SQUADS_DIR / "dala_warriors.json")}
        named = record_match(ServiceMatch(MatchConfig(duration_minutes=0.2, seed=1), squads=sqs))
        self.assertEqual(named["squads"], {"A": "Kano Stars", "B": "Dala Warriors"})
        self.assertEqual(named["profiles"]["A1"], {"name": "Auwal Danlami", "shirt": 1})
        self.assertEqual(len(named["profiles"]), 12)
        plain = record_match(ServiceMatch(MatchConfig(duration_minutes=0.2, seed=1)))
        self.assertNotIn("profiles", plain)
        self.assertNotIn("squads", plain)

    def test_a_stronger_squad_wins_more_points(self):
        strong, weak = flat_squad("Strong", 80), flat_squad("Weak", 20)
        s_pts = w_pts = 0
        for seed in range(4):  # swap sides every match so the side cannot decide it
            s_team = Team.A if seed % 2 == 0 else Team.B
            r = ServiceMatch(MatchConfig(duration_minutes=0.5, seed=seed),
                             squads={s_team: strong, s_team.opponent: weak}).run()
            s_pts += r.score_a if s_team is Team.A else r.score_b
            w_pts += r.score_b if s_team is Team.A else r.score_a
        self.assertGreater(s_pts, w_pts)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_squad_flags_print_the_teams(self):
        code, out, _ = self.run_cli("--minutes", "0.2", "--squad-a", str(SQUADS_DIR / "kano_stars.json"),
                                    "--squad-b", str(SQUADS_DIR / "dala_warriors.json"))
        self.assertEqual(code, 0)
        self.assertIn("Team A: Kano Stars (overall", out)
        self.assertIn("Team B: Dala Warriors (overall", out)

    def test_bad_squad_file_exits_with_code_2(self):
        code, _, err = self.run_cli("--squad-a", "does-not-exist.json")
        self.assertEqual(code, 2)
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
