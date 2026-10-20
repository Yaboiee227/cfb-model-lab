import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from cfb_week8_schedule import eastern_game_date, parse_dt, team_display


class TestWeek8Schedule(unittest.TestCase):
    def test_team_display_prefers_location(self):
        self.assertEqual(team_display({'location':'Florida International','displayName':'FIU Panthers'}),'Florida International')

    def test_team_display_falls_back(self):
        self.assertEqual(team_display({'displayName':'Delaware Fightin Blue Hens'}),'Delaware Fightin Blue Hens')

    def test_team_display_requires_name(self):
        with self.assertRaises(ValueError):
            team_display({'id':'1'})

    def test_evening_game_uses_eastern_date_not_next_utc_date(self):
        # 8 PM ET Wednesday is 00:00 UTC Thursday; the game belongs to Wednesday.
        self.assertEqual(eastern_game_date(parse_dt('2026-10-22T00:00:00Z')),'2026-10-21')


if __name__=='__main__':
    unittest.main()
