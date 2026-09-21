import tempfile
import unittest
from pathlib import Path

from tinyhaus.config import Config
from tinyhaus.models import LAND_BAULAND, SELLER_PRIVATE
from tinyhaus.sources import available, get_source
from tinyhaus.sources.base import SourceError
from tinyhaus.sources.csv_import import CsvSource
from tinyhaus.sources.demo import DemoSource
from tinyhaus.sources.htmlparse import parse_listings
from tinyhaus.sources.immoscout import ImmoScoutSource, parse_api_result
from tinyhaus.sources.kleinanzeigen import page_url, parse_search_page

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


class TestRegistry(unittest.TestCase):
    def test_known_sources(self):
        self.assertIn("demo", available())
        self.assertIn("kleinanzeigen", available())

    def test_unknown_source_explains(self):
        with self.assertRaises(SourceError):
            get_source("gibtsnicht")


class TestDemoSource(unittest.TestCase):
    def test_reads_and_classifies(self):
        plots = list(DemoSource(FIXTURES / "demo_plots.json").fetch(Config()))
        self.assertEqual(len(plots), 12)
        by_id = {p.source_id: p for p in plots}
        good = by_id["demo-001"]
        self.assertEqual(good.land_type, LAND_BAULAND)
        self.assertEqual(good.seller_type, SELLER_PRIVATE)
        self.assertTrue(good.developed)
        self.assertEqual(good.region, "34")
        self.assertTrue(by_id["demo-003"].has_building)
        self.assertTrue(by_id["demo-012"].teardown)


class TestHtmlParser(unittest.TestCase):
    def test_void_tags_do_not_break_nesting(self):
        html = (
            '<article data-adid="1"><div class="t">A</div><img src="x"><br>'
            '<div class="p">B</div></article>'
            '<article data-adid="2"><div class="t">C</div></article>'
        )
        items = parse_listings(html, "article", "data-adid", {"t": "t", "p": "p"})
        self.assertEqual([i["id"] for i in items], ["1", "2"])
        self.assertEqual(items[0]["t"], "A")
        self.assertEqual(items[0]["p"], "B")


class TestKleinanzeigen(unittest.TestCase):
    def setUp(self):
        self.html = (FIXTURES / "kleinanzeigen_search.html").read_text(encoding="utf-8")

    def test_parses_search_results(self):
        plots = parse_search_page(self.html)
        self.assertEqual(len(plots), 2)
        first = plots[0]
        self.assertEqual(first.source_id, "2311001")
        self.assertEqual(first.price_eur, 44_500.0)
        self.assertEqual(first.area_sqm, 820.0)
        self.assertEqual(first.postal_code, "34633")
        self.assertEqual(first.land_type, LAND_BAULAND)
        self.assertTrue(first.developed)
        self.assertTrue(first.url.startswith("https://www.kleinanzeigen.de/s-anzeige/"))

    def test_house_listing_is_recognised(self):
        plots = parse_search_page(self.html)
        self.assertTrue(plots[1].has_building)
        self.assertFalse(plots[1].is_empty_land())

    def test_pagination_url(self):
        url = "https://www.kleinanzeigen.de/s-grundstuecke/kassel/c221l1234"
        self.assertEqual(page_url(url, 1), url)
        self.assertIn("seite:2", page_url(url, 2))

    def test_requires_search_urls(self):
        with self.assertRaises(SourceError) as ctx:
            list(get_source("kleinanzeigen").fetch(Config()))
        self.assertIn("search_urls", str(ctx.exception))


class TestCsvSource(unittest.TestCase):
    def test_imports_with_german_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.csv"
            path.write_text(
                "Titel;Preis;Fläche;PLZ;Ort;Bundesland;Link;Beschreibung\n"
                "Baugrundstück;39.000 €;1.450 m²;17033;Neubrandenburg;"
                "Mecklenburg-Vorpommern;https://x.invalid/1;voll erschlossen, privat\n",
                encoding="utf-8",
            )
            cfg = Config()
            cfg.scan.options["csv"] = {"pattern": str(Path(tmp) / "*.csv")}
            plots = list(CsvSource().fetch(cfg))
        self.assertEqual(len(plots), 1)
        plot = plots[0]
        self.assertEqual(plot.price_eur, 39_000.0)
        self.assertEqual(plot.area_sqm, 1450.0)
        self.assertEqual(plot.postal_code, "17033")
        self.assertEqual(plot.state, "Mecklenburg-Vorpommern")
        self.assertTrue(plot.developed)

    def test_missing_files_explain_what_to_do(self):
        cfg = Config()
        cfg.scan.options["csv"] = {"pattern": "/nirgends/*.csv"}
        with self.assertRaises(SourceError) as ctx:
            list(CsvSource().fetch(cfg))
        self.assertIn("CSV", str(ctx.exception))


class TestImmoScout(unittest.TestCase):
    def test_without_credentials_it_explains(self):
        with self.assertRaises(SourceError) as ctx:
            list(ImmoScoutSource().fetch(Config()))
        self.assertIn("Partnerzugang", str(ctx.exception))

    def test_parses_api_payload(self):
        payload = {
            "resultlist.resultlistEntry": [
                {
                    "@id": "123",
                    "resultlist.realEstate": {
                        "title": "Baugrundstück, voll erschlossen",
                        "plotArea": 950,
                        "price": {"value": 52000},
                        "address": {"postcode": "17033", "city": "Neubrandenburg"},
                    },
                }
            ]
        }
        plots = parse_api_result(payload)
        self.assertEqual(len(plots), 1)
        self.assertEqual(plots[0].price_eur, 52000.0)
        self.assertEqual(plots[0].area_sqm, 950.0)
        self.assertEqual(plots[0].land_type, LAND_BAULAND)


if __name__ == "__main__":
    unittest.main()
