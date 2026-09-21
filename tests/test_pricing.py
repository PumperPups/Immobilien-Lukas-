import unittest

from tinyhaus.config import Config
from tinyhaus.models import LAND_BAULAND, Plot, SELLER_COMMERCIAL, SELLER_PRIVATE
from tinyhaus.pricing import calculate, max_bid_for, units_for


def plot(**kwargs) -> Plot:
    base = dict(
        source="t", source_id="1", url="", title="Bauland", price_eur=45_000.0,
        area_sqm=800.0, state="Hessen", postal_code="34117",
        land_type=LAND_BAULAND, developed=True, seller_type=SELLER_PRIVATE,
    )
    base.update(kwargs)
    return Plot(**base)


class TestUnits(unittest.TestCase):
    def test_area_drives_units(self):
        cfg = Config()
        self.assertEqual(units_for(plot(area_sqm=800), cfg), 2)
        self.assertEqual(units_for(plot(area_sqm=349), cfg), 0)

    def test_cap(self):
        cfg = Config()
        self.assertEqual(units_for(plot(area_sqm=99_000), cfg), cfg.criteria.max_units)


class TestCalculation(unittest.TestCase):
    def test_costs_add_up(self):
        calc = calculate(plot(), Config())
        summed = (
            calc.plot_price + calc.acquisition_extra + calc.build_total
            + calc.development_total + calc.permit_total + calc.contingency
        )
        self.assertAlmostEqual(calc.total_cost, summed, places=2)

    def test_margin_and_subdivision_are_applied(self):
        cfg = Config()
        calc = calculate(plot(), cfg)
        expected = (calc.cost_per_unit + cfg.costs.subdivision_eur) * (
            1 + cfg.targets.sale_margin_rate / 100
        )
        self.assertLess(abs(calc.sale_price_eur - expected), 500)

    def test_sale_price_covers_more_than_pure_cost(self):
        # Verkaufen kostet Teilung/WEG-Aufteilung - das steckt nur im Kaufpreis,
        # nicht in der Miete.
        calc = calculate(plot(), Config())
        self.assertGreater(calc.sale_price_eur, calc.cost_per_unit)

    def test_undeveloped_plot_costs_more(self):
        cfg = Config()
        cheap = calculate(plot(developed=True), cfg)
        pricey = calculate(plot(developed=False), cfg)
        self.assertGreater(pricey.total_cost, cheap.total_cost)

    def test_broker_fee_only_for_commercial(self):
        cfg = Config()
        private = calculate(plot(seller_type=SELLER_PRIVATE), cfg)
        commercial = calculate(plot(seller_type=SELLER_COMMERCIAL), cfg)
        self.assertGreater(commercial.acquisition_extra, private.acquisition_extra)

    def test_grunderwerbsteuer_differs_by_state(self):
        cfg = Config()
        bayern = calculate(plot(state="Bayern"), cfg)          # 3,5 %
        nrw = calculate(plot(state="Nordrhein-Westfalen"), cfg)  # 6,5 %
        self.assertGreater(nrw.acquisition_extra, bayern.acquisition_extra)


class TestMaxBid(unittest.TestCase):
    def test_roundtrip(self):
        """Kalkulierte Miete rueckwaerts gerechnet ergibt wieder den Kaufpreis."""
        cfg = Config()
        p = plot(price_eur=45_000.0)
        calc = calculate(p, cfg)
        bid = max_bid_for(p, cfg, calc.rent_eur_month)
        self.assertLess(abs(bid - 45_000.0), 2_000.0)

    def test_lower_rent_means_lower_bid(self):
        cfg = Config()
        p = plot()
        calc = calculate(p, cfg)
        self.assertLess(
            max_bid_for(p, cfg, calc.rent_eur_month - 100),
            max_bid_for(p, cfg, calc.rent_eur_month),
        )

    def test_unpayable_rent_yields_zero(self):
        self.assertEqual(max_bid_for(plot(), Config(), 50.0), 0.0)


if __name__ == "__main__":
    unittest.main()
