import tempfile
import unittest

from service.agents.roster import list_squads, load_squad_by_id

RATINGS = ("pace", "power", "accuracy", "endurance", "reach")


class ListSquadsTests(unittest.TestCase):
    def test_lists_shipped_squads_sorted_with_ids(self) -> None:
        ids = [s["id"] for s in list_squads()]
        self.assertEqual(ids, sorted(ids))
        self.assertIn("kano_stars", ids)
        self.assertIn("gwale_maestros", ids)

    def test_squad_has_six_players_and_an_overall(self) -> None:
        for squad in list_squads():
            self.assertEqual(len(squad["players"]), 6, squad["id"])
            self.assertTrue(1 <= squad["overall"] <= 99, squad["id"])

    def test_player_entries_carry_name_shirt_ratings_and_overall(self) -> None:
        player = list_squads()[0]["players"][0]
        for key in ("name", "shirt", "overall", *RATINGS):
            self.assertIn(key, player)

    def test_empty_directory_gives_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(list_squads(d), [])


class LoadByIdTests(unittest.TestCase):
    def test_loads_a_shipped_squad(self) -> None:
        self.assertEqual(len(load_squad_by_id("kano_stars").players), 6)

    def test_unknown_or_unsafe_ids_raise_key_error(self) -> None:
        for bad in ("nobody", "../README", "kano_stars.json", "KANO_STARS", ""):
            with self.subTest(bad=bad), self.assertRaises(KeyError):
                load_squad_by_id(bad)


if __name__ == "__main__":
    unittest.main()
