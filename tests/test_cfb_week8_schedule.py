import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from cfb_week8_schedule import team_display


class TestWeek8Schedule(unittest.TestCase):
    def test_team_display_prefers_location(self):
        self.assertEqual(team_display({'location':'Florida International','displayName':'FIU Panthers'}),'Florida International')

    def test_team_display_falls_back(self):
        self.assertEqual(team_display({'displayName':'Delaware Fightin Blue Hens'}),'Delaware Fightin Blue Hens')

    def test_team_display_requires_name(self):
        with self.assertRaises(ValueError):
            team_display({'id':'1'})


if __name__=='__main__':
    unittest.main()
