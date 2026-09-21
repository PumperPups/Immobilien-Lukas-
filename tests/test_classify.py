import unittest

from tinyhaus.classify import (
    classify_land, detect_building, detect_developed, detect_seller, enrich,
    parse_area, parse_location, parse_price,
)
from tinyhaus.models import (
    LAND_AGRAR, LAND_BAUERWARTUNG, LAND_BAULAND, LAND_GARTEN, LAND_UNKNOWN,
    Plot, SELLER_COMMERCIAL, SELLER_PRIVATE,
)


class TestParsing(unittest.TestCase):
    def test_price_variants(self):
        self.assertEqual(parse_price("44.500 € VB"), 44500.0)
        self.assertEqual(parse_price("1,2 Mio. €"), 1_200_000.0)
        self.assertEqual(parse_price("21000"), 21000.0)

    def test_price_on_request_is_unknown(self):
        # Lieber None als eine erfundene Zahl - die Bewertung behandelt das
        # explizit als "manuell pruefen".
        self.assertIsNone(parse_price("Preis auf Anfrage"))
        self.assertIsNone(parse_price(""))

    def test_area(self):
        self.assertEqual(parse_area("Baugrundstück ca. 1.250 qm"), 1250.0)
        self.assertEqual(parse_area("820 m²"), 820.0)
        self.assertIsNone(parse_area(None))

    def test_location(self):
        self.assertEqual(parse_location("34117 Kassel"), ("34117", "Kassel"))
        self.assertEqual(parse_location("Kassel"), (None, "Kassel"))


class TestClassification(unittest.TestCase):
    def test_land_types(self):
        self.assertEqual(classify_land("Baugrundstück, B-Plan"), LAND_BAULAND)
        self.assertEqual(classify_land("Bauerwartungsland"), LAND_BAUERWARTUNG)
        self.assertEqual(classify_land("Gartengrundstück mit Laube"), LAND_GARTEN)
        self.assertEqual(classify_land("Ackerland, verpachtet"), LAND_AGRAR)
        self.assertEqual(classify_land("Schönes Objekt"), LAND_UNKNOWN)

    def test_garden_beats_bauland_keyword(self):
        # "Freizeitgrundstueck, bebaubar mit Laube" darf nicht als Bauland
        # durchrutschen - dort darf niemand wohnen.
        self.assertEqual(classify_land("Freizeitgrundstück, bebaubar"), LAND_GARTEN)

    def test_buildings(self):
        self.assertEqual(detect_building("Einfamilienhaus"), (True, False))
        self.assertEqual(detect_building("Abrissobjekt, Bauland"), (True, True))
        self.assertEqual(detect_building("Unbebautes Grundstück"), (False, False))

    def test_developed(self):
        self.assertTrue(detect_developed("voll erschlossen"))
        self.assertFalse(detect_developed("nicht erschlossen"))
        self.assertIsNone(detect_developed("ruhige Lage"))

    def test_seller(self):
        self.assertEqual(detect_seller("provisionsfrei von privat"), SELLER_PRIVATE)
        self.assertEqual(detect_seller("Courtage 3,57%"), SELLER_COMMERCIAL)

    def test_enrich_fills_gaps(self):
        plot = Plot(
            source="t", source_id="1", url="", title="Baugrundstück 900 m²",
            description="voll erschlossen, von privat",
        )
        enrich(plot)
        self.assertEqual(plot.land_type, LAND_BAULAND)
        self.assertEqual(plot.area_sqm, 900.0)
        self.assertTrue(plot.developed)
        self.assertEqual(plot.seller_type, SELLER_PRIVATE)
        self.assertFalse(plot.has_building)


if __name__ == "__main__":
    unittest.main()
