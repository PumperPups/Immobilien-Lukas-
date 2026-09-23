import datetime as dt
import tempfile
import unittest
from pathlib import Path

from hilfe_verwaltung import DbTest
from verwaltung import abgleich, demo, einlesen, stammdaten
from verwaltung.anonym import Pseudonymisierer, anonymisieren
from verwaltung.bank import lese_datei
from verwaltung.db import Datenbank
from verwaltung.miete import lade_vertraege


class StammdatenTest(DbTest, unittest.TestCase):
    def test_eingelesen(self):
        vs = {v.nummer: v for v in lade_vertraege(self.db)}
        self.assertEqual(len(vs), 7)
        self.assertEqual(vs["M-0001"].soll("2026-07"), 65000)
        self.assertEqual(vs["M-0006"].soll("2026-08"), 0)               # ausgezogen
        self.assertEqual(vs["M-0003"].mitmieter, "Hans Beispiel")

    def test_erneut_einlesen_aktualisiert_und_mieterhoehung(self):
        text = ("Mieternummer;Objekt;Einheit;Nachname;Vorname;Mietbeginn;Kaltmiete;Nebenkosten;Miete gueltig ab\n"
                "M-0001;Musterstr. 5;WE 1;Mustermann;Max;01.01.2020;550,00;150,00;2026-09\n")
        erg = stammdaten.einlesen_text(self.db, text)
        self.assertEqual((erg.neu, erg.geaendert, erg.mietaenderungen), (0, 1, 1))
        v = next(x for x in lade_vertraege(self.db) if x.nummer == "M-0001")
        self.assertEqual((v.soll("2026-08"), v.soll("2026-09")), (65000, 70000))

    def test_fehler_je_zeile(self):
        text = ("Name;Objekt;Mietbeginn;Miete;IBAN\n"
                "Mustermann, Erika;Probeallee 1;01.02.2024;700;\n"
                "Ohne Beginn;Probeallee 1;;700;\n"
                "Falsche Iban;Probeallee 1;01.02.2024;700;DE00123\n")
        erg = stammdaten.einlesen_text(self.db, text)
        self.assertEqual(erg.neu, 1)
        self.assertEqual(len(erg.fehler), 2)
        self.assertFalse(self.db.q("SELECT * FROM personen WHERE nachname = 'Iban'"))   # nichts halb gespeichert
        erika = next(v for v in lade_vertraege(self.db) if v.nachname == "Mustermann" and v.vorname == "Erika")
        self.assertTrue(erika.nummer.startswith("M-"))
        self.assertEqual(erika.soll("2026-07"), 70000)

    def test_vorlage_laesst_sich_einlesen(self):
        erg = stammdaten.einlesen_text(self.db, stammdaten.vorlage())
        self.assertFalse(erg.fehler)
        self.assertEqual(erg.konten, 1)            # Beispiel-IBAN der Vorlage ist neu
        self.assertEqual(erg.geaendert, 1)


ECHT_WIRKEND = ('"Auftragskonto";"Buchungstag";"Valutadatum";"Buchungstext";"Verwendungszweck";"Glaeubiger ID";'
                '"Mandatsreferenz";"Kundenreferenz (End-to-End)";"Sammlerreferenz";"Lastschrift Ursprungsbetrag";'
                '"Auslagenersatz Ruecklastschrift";"Beguenstigter/Zahlungspflichtiger";"Kontonummer/IBAN";'
                '"BIC (SWIFT-Code)";"Betrag";"Waehrung";"Info"\n'
                '"DE89370400440532013000";"01.10.26";"01.10.26";"GUTSCHR. UEBERWEISUNG";'
                '"Miete Oktober Kowalczyk Lindenallee 17 WE 3";"DE98ZZZ09999999999";"MANDAT-4711";"";"";"";"";'
                '"Kowalczyk, Jadwiga";"DE89 3704 0044 0532 0130 00";"COBADEFFXXX";"812,40";"EUR";"Umsatz gebucht"\n'
                '"DE89370400440532013000";"30.09.26";"30.09.26";"GUTSCHR. UEBERWEISUNG";'
                '"KdU 34567BG0098765 Kowalczyk Jadwiga 10.2026";"";"";"";"";"";"";'
                '"Jobcenter Hintertupfingen";"DE44500105175407324931";"X";"400,00";"EUR";""\n')


class AnonymTest(unittest.TestCase):
    def test_nichts_echtes_bleibt(self):
        with tempfile.TemporaryDirectory() as t:
            quelle = Path(t) / "export.csv"
            quelle.write_text(ECHT_WIRKEND, encoding="cp1252")
            ziel = anonymisieren(quelle)
            text = ziel.read_text(encoding="utf-8")
            for geheim in ("Kowalczyk", "Jadwiga", "Lindenallee", "0532013000", "5407324931", "34567BG0098765",
                           "Hintertupfingen", "MANDAT-4711", "DE98ZZZ", "COBADEFF"):
                self.assertNotIn(geheim, text, geheim)
            _, umsaetze = lese_datei(ziel)              # bleibt ein gueltiger Kontoauszug
            self.assertEqual([x.betrag_cent for x in umsaetze], [81240, 40000])
            a, b = umsaetze
            self.assertEqual(a.datum, dt.date(2026, 10, 1))
            nachname = a.name.split()[-1]
            self.assertIn(nachname, a.zweck)            # gleicher Name -> gleiches Pseudonym
            self.assertIn(nachname, b.zweck)
            self.assertIn("Jobcenter", b.name)
            self.assertIn("Oktober", a.zweck)
            self.assertIn("BG", b.zweck)

    def test_camt_wird_neutral(self):
        from test_bank import CAMT
        with tempfile.TemporaryDirectory() as t:
            quelle = Path(t) / "auszug.xml"
            quelle.write_bytes(CAMT)
            text = anonymisieren(quelle).read_text(encoding="utf-8")
            self.assertNotIn("Anna Probe", text)           # steht im Original nur im Zweck ("für ...")
            self.assertNotIn("DE89370400440532013000", text)
            self.assertNotIn("DE02000000000000100001", text)
            self.assertIn("650,00", text)

    def test_wortliste(self):
        p = Pseudonymisierer([("Erika", "Kaufmann")])
        self.assertEqual(p.text("Miete Oktober Kaufmann Schillerstr 5"), "Miete Oktober Mustermann xxxx 5")


class DemoTest(unittest.TestCase):
    def test_demo_komplett(self):
        with tempfile.TemporaryDirectory() as t:
            ordner = Path(t) / "demo"
            info = demo.erzeugen(ordner, heute=dt.date(2026, 10, 20))
            self.assertEqual(info["monate"], ["2026-08", "2026-09", "2026-10"])
            db = Datenbank(ordner)
            stammdaten.einlesen(db, ordner / "stammdaten_demo.csv")
            ergebnisse = einlesen.eingang_verarbeiten(db)
            self.assertFalse([x for x in ergebnisse if x.fehler])
            erg = abgleich.abgleichen(db)
            quote = erg.automatisch / (erg.automatisch + erg.zu_pruefen)
            self.assertGreater(quote, 0.9)
            self.assertFalse(list((ordner / "bank" / "eingang").iterdir()))     # alles archiviert
            db.close()
            with self.assertRaises(RuntimeError):                               # fremden Ordner nie loeschen
                (ordner / ".demo").unlink()
                demo.erzeugen(ordner)


if __name__ == "__main__":
    unittest.main()
