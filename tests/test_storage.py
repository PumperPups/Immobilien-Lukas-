import tempfile
import unittest
from pathlib import Path

from tinyhaus.models import Lead, MarketTest, Plot, Score
from tinyhaus.storage import Storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.storage.close()
        self.tmp.cleanup()

    def plot(self, source_id="1", **kwargs) -> Plot:
        base = dict(
            source="t", source_id=source_id, url="u", title="Bauland",
            price_eur=45_000.0, area_sqm=800.0, postal_code="34117", city="Kassel",
        )
        base.update(kwargs)
        return Plot(**base)

    def test_upsert_is_idempotent(self):
        plot = self.plot()
        self.assertTrue(self.storage.upsert_plot(plot))
        self.assertFalse(self.storage.upsert_plot(plot))
        self.assertEqual(len(self.storage.list_plots()), 1)

    def test_upsert_keeps_status_and_first_seen(self):
        plot = self.plot()
        self.storage.upsert_plot(plot)
        self.storage.set_status(plot.key, "kontaktiert", "angerufen")
        plot.title = "Bauland (Preis gesenkt)"
        self.storage.upsert_plot(plot)
        stored = self.storage.get_plot(plot.key)
        self.assertEqual(stored.status, "kontaktiert")
        self.assertEqual(stored.notes, "angerufen")
        self.assertEqual(stored.title, "Bauland (Preis gesenkt)")

    def test_detects_same_plot_on_other_portal(self):
        self.storage.upsert_plot(self.plot(source_id="1"))
        twin = self.plot(source_id="2")
        twin.source = "anderes-portal"
        self.assertEqual(self.storage.duplicate_of(twin), "t:1")

    def test_roundtrip_types(self):
        plot = self.plot(developed=None, has_building=False, raw={"a": 1})
        self.storage.upsert_plot(plot)
        stored = self.storage.get_plot(plot.key)
        self.assertIsNone(stored.developed)
        self.assertIs(stored.has_building, False)
        self.assertEqual(stored.raw, {"a": 1})

    def test_shortlist_orders_by_score_and_skips_rejected(self):
        for i, total in enumerate([40.0, 90.0, 70.0], start=1):
            plot = self.plot(source_id=str(i))
            self.storage.upsert_plot(plot)
            self.storage.save_score(Score(plot_key=plot.key, total=total, units=2))
        rejected = self.plot(source_id="9")
        self.storage.upsert_plot(rejected)
        self.storage.save_score(
            Score(plot_key=rejected.key, total=0.0, units=0, rejected=True,
                  reject_reason="bebaut")
        )
        results = self.storage.shortlist(min_score=50)
        self.assertEqual([s.total for _, s in results], [90.0, 70.0])

    def test_demand_signal_aggregates_leads(self):
        self.storage.save_market_test(
            MarketTest(region="34", plot_key=None, label="TH-34-01",
                       rent_eur_month=800, buy_price_eur=150_000,
                       status="veroeffentlicht")
        )
        self.storage.add_lead(Lead(label="TH-34-01", interest="miete",
                                   accepted_rent=780, qualified=True))
        self.storage.add_lead(Lead(label="TH-34-01", interest="beides",
                                   accepted_rent=820, accepted_price=140_000,
                                   qualified=True))
        self.storage.add_lead(Lead(label="TH-34-01", interest="kein_interesse"))

        signal = self.storage.demand_signal("34")
        self.assertEqual(signal.tests, 1)
        self.assertEqual(signal.leads, 2)          # Absage zaehlt nicht als Lead
        self.assertEqual(signal.rent_leads, 2)
        self.assertEqual(signal.buy_leads, 1)
        self.assertEqual(signal.avg_accepted_rent, 800.0)
        self.assertEqual(signal.avg_accepted_price, 140_000.0)

    def test_draft_tests_do_not_count_as_measured(self):
        self.storage.save_market_test(
            MarketTest(region="99", plot_key=None, label="TH-99-01")  # Status 'entwurf'
        )
        self.assertEqual(self.storage.demand_signal("99").tests, 0)
        self.assertEqual(self.storage.demand_signal("99").index, 0.0)


if __name__ == "__main__":
    unittest.main()
