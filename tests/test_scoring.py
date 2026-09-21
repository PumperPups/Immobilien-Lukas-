import unittest

from tinyhaus.config import Config
from tinyhaus.models import (
    DemandSignal, LAND_AGRAR, LAND_BAUERWARTUNG, LAND_BAULAND, Plot,
    SELLER_COMMERCIAL, SELLER_PRIVATE,
)
from tinyhaus.scoring import check_hard_criteria, score_plot


def plot(**kwargs) -> Plot:
    base = dict(
        source="t", source_id="1", url="", title="Bauland", price_eur=45_000.0,
        area_sqm=800.0, state="Hessen", postal_code="34117",
        land_type=LAND_BAULAND, developed=True, seller_type=SELLER_PRIVATE,
    )
    base.update(kwargs)
    return Plot(**base)


class TestHardCriteria(unittest.TestCase):
    def test_accepts_good_plot(self):
        self.assertIsNone(check_hard_criteria(plot(), Config()))

    def test_rejects_plot_with_house(self):
        # Kernanforderung der Idee: nur Grundstuecke ohne Haus.
        reason = check_hard_criteria(plot(has_building=True), Config())
        self.assertIn("bebaut", reason)

    def test_rejects_farmland_and_garden(self):
        self.assertIsNotNone(check_hard_criteria(plot(land_type=LAND_AGRAR), Config()))

    def test_bauerwartungsland_only_when_allowed(self):
        cfg = Config()
        self.assertIsNotNone(check_hard_criteria(plot(land_type=LAND_BAUERWARTUNG), cfg))
        cfg.criteria.allow_bauerwartungsland = True
        self.assertIsNone(check_hard_criteria(plot(land_type=LAND_BAUERWARTUNG), cfg))

    def test_rejects_too_small_too_big_too_pricey(self):
        cfg = Config()
        self.assertIn("zu klein", check_hard_criteria(plot(area_sqm=100), cfg))
        self.assertIn("zu gross", check_hard_criteria(plot(area_sqm=50_000), cfg))
        self.assertIn("zu teuer", check_hard_criteria(plot(price_eur=500_000), cfg))

    def test_unknown_price_needs_manual_check(self):
        self.assertIn("Preis unbekannt", check_hard_criteria(plot(price_eur=None), Config()))

    def test_region_filter(self):
        cfg = Config()
        cfg.criteria.regions = ["17", "23"]
        self.assertIn("nicht im Suchgebiet", check_hard_criteria(plot(), cfg))
        cfg.criteria.regions = ["34"]
        self.assertIsNone(check_hard_criteria(plot(), cfg))

    def test_exclude_region(self):
        cfg = Config()
        cfg.criteria.exclude_regions = ["34"]
        self.assertIn("ausgeschlossen", check_hard_criteria(plot(), cfg))


class TestScore(unittest.TestCase):
    def test_rejected_plots_score_zero(self):
        score = score_plot(plot(has_building=True), Config())
        self.assertTrue(score.rejected)
        self.assertEqual(score.total, 0.0)

    def test_cheaper_plot_scores_higher(self):
        cfg = Config()
        cheap = score_plot(plot(price_eur=25_000), cfg)
        pricey = score_plot(plot(price_eur=100_000), cfg)
        self.assertGreater(cheap.total, pricey.total)

    def test_private_seller_beats_broker(self):
        cfg = Config()
        self.assertGreater(
            score_plot(plot(seller_type=SELLER_PRIVATE), cfg).total,
            score_plot(plot(seller_type=SELLER_COMMERCIAL), cfg).total,
        )

    def test_measured_demand_lifts_score(self):
        """Der Rueckkanal: gemessene Nachfrage macht eine Region attraktiver."""
        cfg = Config()
        cold = DemandSignal(region="34", tests=2, leads=1, qualified_leads=0)
        hot = DemandSignal(region="34", tests=2, leads=14, qualified_leads=12)
        self.assertGreater(
            score_plot(plot(), cfg, hot).total, score_plot(plot(), cfg, cold).total
        )

    def test_reasons_are_human_readable(self):
        score = score_plot(plot(), Config())
        self.assertTrue(all(isinstance(r, str) and r for r in score.reasons))
        self.assertAlmostEqual(sum(score.breakdown.values()), score.total, places=0)


if __name__ == "__main__":
    unittest.main()
