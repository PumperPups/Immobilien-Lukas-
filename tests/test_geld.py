import datetime as dt
import tempfile
import unittest
from pathlib import Path

from verwaltung import geld
from verwaltung.schutz import Schluessel, falten, iban_bauen, iban_ende, iban_gueltig


class GeldTest(unittest.TestCase):
    def test_betraege(self):
        self.assertEqual(geld.cent("1.234,56"), 123456)
        self.assertEqual(geld.cent("-12,5"), -1250)
        self.assertEqual(geld.cent("1234.56"), 123456)
        self.assertEqual(geld.cent("1.234"), 123400)
        self.assertEqual(geld.cent(" 695,00 EUR"), 69500)
        self.assertEqual(geld.cent("100,00-"), -10000)
        self.assertIsNone(geld.cent(""))
        self.assertIsNone(geld.cent("abc"))
        self.assertEqual(geld.eur(123456), "1.234,56 €")
        self.assertEqual(geld.eur(-500, False), "-5,00")

    def test_datum(self):
        self.assertEqual(geld.datum("01.10.26"), dt.date(2026, 10, 1))
        self.assertEqual(geld.datum("2026-10-01T08:00:00"), dt.date(2026, 10, 1))
        self.assertIsNone(geld.datum("Summe"))

    def test_monate(self):
        self.assertEqual(geld.monat_plus("2026-12", 1), "2027-01")
        self.assertEqual(geld.monat_plus("2026-01", -1), "2025-12")
        self.assertEqual(geld.monate("2026-11", "2027-02"), ["2026-11", "2026-12", "2027-01", "2027-02"])
        self.assertEqual(geld.letzter("2028-02"), dt.date(2028, 2, 29))

    def test_ostern_und_faelligkeit(self):
        self.assertEqual(geld._ostersonntag(2026), dt.date(2026, 4, 5))
        self.assertEqual(geld._ostersonntag(2025), dt.date(2025, 4, 20))
        # Samstag zaehlt nicht, Feiertage auch nicht
        self.assertEqual(geld.faellig_am("2026-10"), dt.date(2026, 10, 5))     # Do, Fr, (Sa 3.10.), Mo
        self.assertEqual(geld.faellig_am("2026-04"), dt.date(2026, 4, 7))      # Karfreitag + Ostermontag
        self.assertEqual(geld.faellig_am("2026-05"), dt.date(2026, 5, 6))      # 1. Mai
        self.assertEqual(geld.faellig_am("2027-01"), dt.date(2027, 1, 6))


class SchutzTest(unittest.TestCase):
    def test_iban(self):
        self.assertTrue(iban_gueltig("DE89 3704 0044 0532 0130 00"))
        self.assertFalse(iban_gueltig("DE88 3704 0044 0532 0130 00"))
        self.assertTrue(iban_gueltig(iban_bauen("DE", "000000000000123456")))
        self.assertEqual(iban_ende("DE89 3704 0044 0532 0130 00"), "3000")

    def test_kennung_stabil_und_geheim(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            k1, k2 = Schluessel(Path(a)), Schluessel(Path(b))
            self.assertEqual(k1.kennung("DE89370400440532013000"), k1.kennung("de89 3704 0044 0532 0130 00"))
            self.assertEqual(k1.kennung("DE89370400440532013000"), Schluessel(Path(a)).kennung("DE89370400440532013000"))
            self.assertNotEqual(k1.kennung("DE89370400440532013000"), k2.kennung("DE89370400440532013000"))
            self.assertNotIn("0532013000", k1.kennung("DE89370400440532013000"))
            self.assertIsNone(k1.kennung(""))

    def test_falten(self):
        self.assertEqual(falten("Müller"), falten("Mueller"))
        self.assertEqual(falten("Müller"), falten("Muller"))
        self.assertEqual(falten("Größe"), falten("Groesse"))


if __name__ == "__main__":
    unittest.main()
