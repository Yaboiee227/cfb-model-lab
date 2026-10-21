import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class TestStaticIntegrityPages(unittest.TestCase):
    def test_ratings_page_is_explicitly_benchmark_only(self):
        text = (ROOT / "ratings.html").read_text(encoding="utf-8")
        self.assertIn("Benchmark only — not a CB canonical power rating.", text)
        self.assertIn("cfb/benchmarks/week-08-sagarin-full.json", text)
        self.assertIn("data/model-registry.json", text)
        self.assertIn("canonicalInfluence", text)
        self.assertNotIn("Sagarin is the CB canonical", text)

    def test_recap_page_reads_audited_sources(self):
        text = (ROOT / "recap.html").read_text(encoding="utf-8")
        self.assertIn("cfb/record-summary.json", text)
        self.assertIn("cfb/projections/week-08-status.json", text)
        self.assertIn("data/model-registry.json", text)
        self.assertIn("Week 8 is not a completed canonical recap.", text)

    def test_pages_cross_link(self):
        ratings = (ROOT / "ratings.html").read_text(encoding="utf-8")
        recap = (ROOT / "recap.html").read_text(encoding="utf-8")
        self.assertIn('href="recap.html"', ratings)
        self.assertIn('href="ratings.html"', recap)
        self.assertIn('href="week-8.html"', ratings)
        self.assertIn('href="week-8.html"', recap)


if __name__ == "__main__":
    unittest.main()
