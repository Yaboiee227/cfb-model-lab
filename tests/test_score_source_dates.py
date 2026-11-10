import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from score_sources import fetch_scores_for_projection


class ScoreDateTests(unittest.TestCase):
    def test_evening_kickoff_queries_eastern_game_date(self):
        with patch('score_sources._get', return_value={'events': []}) as get:
            fetch_scores_for_projection('cfb', {'games': [{'kickoff': '2026-11-11T00:00:00Z'}]})
        dates = {parse_qs(urlparse(call.args[0]).query)['dates'][0] for call in get.call_args_list}
        self.assertEqual(dates, {'20261110', '20261111'})
