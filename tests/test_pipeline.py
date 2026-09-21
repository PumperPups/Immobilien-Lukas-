"""Durchstich: vom Scan bis zum Maximalgebot."""

import tempfile
import unittest
from pathlib import Path

from tinyhaus import pipeline
from tinyhaus.config import Config
from tinyhaus.models import Lead
from tinyhaus.storage import Storage

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cfg = Config()
        self.cfg.db_path = str(root / "test.db")
        self.cfg.output_dir = str(root / "out")
        self.cfg.scan.sources = ["demo"]
        self.storage = Storage(self.cfg.db_path)
        # Demo-Quelle liest relativ zum Projektverzeichnis
        self.demo_backup = None

    def tearDown(self):
        self.storage.close()
        self.tmp.cleanup()

    def scan(self):
        return pipeline.scan(self.cfg, self.storage)

    def test_scan_filters_to_empty_building_land(self):
        report = self.scan()
        self.assertEqual(report.fetched, 12)
        self.assertEqual(report.new, 12)
        self.assertEqual(report.accepted + report.rejected, report.fetched)
        keys = {p.key for p, _ in self.storage.shortlist(0, limit=99)}
        self.assertIn("demo:demo-001", keys)      # Bauland, erschlossen
        self.assertNotIn("demo:demo-003", keys)   # Einfamilienhaus
        self.assertNotIn("demo:demo-004", keys)   # Ackerland
        self.assertNotIn("demo:demo-010", keys)   # Gartengrundstueck

    def test_second_scan_updates_instead_of_duplicating(self):
        self.scan()
        report = self.scan()
        self.assertEqual(report.new, 0)
        self.assertEqual(report.updated, 12)
        self.assertEqual(len(self.storage.list_plots()), 12)

    def test_shortlist_is_sorted_and_calculated(self):
        self.scan()
        candidates = pipeline.shortlist(self.cfg, self.storage)
        self.assertTrue(candidates)
        totals = [c.score.total for c in candidates]
        self.assertEqual(totals, sorted(totals, reverse=True))
        for candidate in candidates:
            self.assertGreater(candidate.calc.rent_eur_month, 0)
            self.assertGreater(candidate.calc.sale_price_eur, candidate.calc.rent_eur_month)

    def test_create_test_writes_both_ads(self):
        self.scan()
        creation = pipeline.create_test(self.cfg, self.storage, "demo:demo-001")
        self.assertEqual(creation.test.region, "34")
        for variant in ("miete", "kauf"):
            path = Path(creation.paths[variant])
            self.assertTrue(path.exists())
            self.assertIn(creation.test.label, path.read_text(encoding="utf-8"))
        self.assertTrue(Path(creation.paths["checkliste"]).exists())
        self.assertEqual(self.storage.get_market_test(creation.test.label).status, "entwurf")

    def test_auto_tests_one_per_region(self):
        self.scan()
        created = pipeline.auto_tests(self.cfg, self.storage, limit=3)
        regions = [c.test.region for c in created]
        self.assertEqual(len(regions), len(set(regions)))
        # Ein zweiter Lauf testet nicht dieselben Regionen noch einmal
        again = pipeline.auto_tests(self.cfg, self.storage, limit=3)
        self.assertFalse({c.test.region for c in again} & set(regions))

    def test_leads_feed_back_into_the_score(self):
        self.scan()
        creation = pipeline.create_test(self.cfg, self.storage, "demo:demo-001")
        label = creation.test.label
        pipeline.mark_published(self.storage, label)

        before = self.storage.get_score("demo:demo-001").total
        for _ in range(6):
            pipeline.record_lead(
                self.storage,
                Lead(label=label, interest="beides", accepted_rent=850,
                     accepted_price=150_000, qualified=True),
            )
        pipeline.rescore(self.cfg, self.storage)
        after = self.storage.get_score("demo:demo-001").total
        self.assertGreater(after, before)

    def test_unknown_label_is_rejected(self):
        self.scan()
        with self.assertRaises(KeyError):
            pipeline.record_lead(self.storage, Lead(label="TH-99-99", interest="miete"))

    def test_negotiation_uses_measured_rent(self):
        self.scan()
        creation = pipeline.create_test(self.cfg, self.storage, "demo:demo-001")
        pipeline.mark_published(self.storage, creation.test.label)
        label = creation.test.label

        optimistic = pipeline.negotiation(self.cfg, self.storage, "demo:demo-001")
        self.assertIsNone(optimistic.observed_rent)

        # Der Markt zahlt weniger als kalkuliert -> Maximalgebot sinkt
        pipeline.record_lead(
            self.storage,
            Lead(label=label, interest="miete", accepted_rent=850, qualified=True),
        )
        measured = pipeline.negotiation(self.cfg, self.storage, "demo:demo-001")
        self.assertEqual(measured.observed_rent, 850.0)
        self.assertLess(measured.max_bid, optimistic.max_bid)
        self.assertLess(measured.max_bid, measured.asking_price)
        self.assertIn("teuer", measured.verdict.lower())

    def test_negotiation_says_stop_when_rent_cannot_carry_the_build(self):
        self.scan()
        creation = pipeline.create_test(self.cfg, self.storage, "demo:demo-001")
        pipeline.mark_published(self.storage, creation.test.label)
        pipeline.record_lead(
            self.storage,
            Lead(label=creation.test.label, interest="miete", accepted_rent=450,
                 qualified=True),
        )
        result = pipeline.negotiation(self.cfg, self.storage, "demo:demo-001")
        self.assertEqual(result.max_bid, 0.0)
        self.assertIn("rechnet sich nicht", result.verdict.lower())

    def test_missing_plot_raises(self):
        with self.assertRaises(KeyError):
            pipeline.create_test(self.cfg, self.storage, "demo:gibtsnicht")


if __name__ == "__main__":
    unittest.main()
