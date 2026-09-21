import unittest

from tinyhaus.config import Config
from tinyhaus.fmt import eur
from tinyhaus.demand import (
    build_market_test, next_label, outreach_message, render_ads, VARIANT_BUY,
    VARIANT_RENT,
)
from tinyhaus.models import LAND_BAULAND, Plot
from tinyhaus.pricing import calculate


def sample_plot() -> Plot:
    return Plot(
        source="demo", source_id="1", url="https://x.invalid/1",
        title="Baugrundstück 820 m²", price_eur=44_500.0, area_sqm=820.0,
        postal_code="34633", city="Fuldabrück", state="Hessen",
        land_type=LAND_BAULAND, developed=True,
    )


class TestLabels(unittest.TestCase):
    def test_labels_are_unique_per_region(self):
        self.assertEqual(next_label(set(), "34"), "TH-34-01")
        self.assertEqual(next_label({"TH-34-01"}, "34"), "TH-34-02")


class TestAds(unittest.TestCase):
    def setUp(self):
        cfg = Config()
        plot = sample_plot()
        calc = calculate(plot, cfg)
        self.test = build_market_test(plot, calc, cfg, "TH-34-01")
        self.ads = render_ads(self.test)

    def test_two_variants(self):
        self.assertEqual(set(self.ads), {VARIANT_RENT, VARIANT_BUY})

    def test_rent_ad_shows_monthly_price(self):
        ad = self.ads[VARIANT_RENT]
        self.assertIn("Monat", ad.title)
        self.assertEqual(ad.price_eur, self.test.rent_eur_month)

    def test_buy_ad_shows_total_price(self):
        ad = self.ads[VARIANT_BUY]
        self.assertEqual(ad.price_eur, self.test.buy_price_eur)
        self.assertGreater(ad.price_eur, 10 * (self.test.rent_eur_month or 0))

    def test_both_ads_carry_the_tracking_label(self):
        for ad in self.ads.values():
            self.assertIn("TH-34-01", ad.body)

    def test_ads_declare_the_project_as_planned(self):
        """Pflicht, nicht Kuer: keine Anzeige fuer ein Objekt, das es nicht gibt."""
        for ad in self.ads.values():
            self.assertIn("Planung", ad.body)
            self.assertIn("kein Vertragsangebot", ad.body)

    def test_ads_ask_the_price_question(self):
        self.assertIn("welche Miete", self.ads[VARIANT_RENT].body)
        self.assertIn("Mieten lieber", self.ads[VARIANT_BUY].body)

    def test_german_thousand_separator_without_breaking_prose(self):
        body = self.ads[VARIANT_BUY].body
        self.assertIn(eur(self.test.buy_price_eur), body)
        self.assertRegex(body, r"\d{1,3}\.\d{3} EUR")
        self.assertIn("Erschliessung und", body)
        # Fliesstext-Kommas duerfen nicht zu Punkten geworden sein
        self.assertIn("Kaufnebenkosten (Notar, Grunderwerbsteuer)", body)


class TestOutreach(unittest.TestCase):
    def test_message_asks_the_three_dealbreaker_questions(self):
        cfg = Config()
        plot = sample_plot()
        text = outreach_message(plot, calculate(plot, cfg), cfg)
        self.assertIn("Bebauungsplan", text)
        self.assertIn("erschlossen", text)
        self.assertIn("Grundbuch", text)
        self.assertIn(plot.url, text)
        self.assertIn("44.500 EUR", text)


if __name__ == "__main__":
    unittest.main()
