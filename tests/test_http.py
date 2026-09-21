import unittest
from urllib.robotparser import RobotFileParser

from tinyhaus.sources.http import PoliteFetcher, RobotsDisallowed

ROBOTS = """
User-agent: *
Disallow: /s-anzeige/
Allow: /
"""


class RobotsTest(unittest.TestCase):
    def fetcher(self, robots: str | None) -> PoliteFetcher:
        fetcher = PoliteFetcher("TestBot/1.0", delay_seconds=0)
        parser = None
        if robots is not None:
            parser = RobotFileParser()
            parser.parse(robots.splitlines())
        fetcher._robots["https://portal.invalid"] = parser
        return fetcher

    def test_disallowed_path_is_blocked(self):
        fetcher = self.fetcher(ROBOTS)
        self.assertFalse(fetcher.allowed("https://portal.invalid/s-anzeige/1"))
        with self.assertRaises(RobotsDisallowed):
            fetcher.get("https://portal.invalid/s-anzeige/1")

    def test_allowed_path_passes_the_check(self):
        self.assertTrue(self.fetcher(ROBOTS).allowed("https://portal.invalid/s-grundstuecke/"))

    def test_unreadable_robots_means_no_crawling(self):
        """Im Zweifel nicht crawlen - nicht im Zweifel crawlen."""
        self.assertFalse(self.fetcher(None).allowed("https://portal.invalid/irgendwas"))

    def test_opt_out_is_explicit(self):
        fetcher = PoliteFetcher("TestBot/1.0", delay_seconds=0, respect_robots=False)
        self.assertTrue(fetcher.allowed("https://portal.invalid/s-anzeige/1"))


if __name__ == "__main__":
    unittest.main()
