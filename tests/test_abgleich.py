import datetime as dt
import unittest

from hilfe_verwaltung import JOBCENTER, DbTest, iban, u
from verwaltung import abgleich, uebersicht
from verwaltung.miete import lade_vertraege


class MonatTest(unittest.TestCase):
    def test_monat_aus_zweck(self):
        tag = dt.date(2026, 10, 2)
        self.assertEqual(abgleich.monate_aus_zweck("Miete September", tag), ["2026-09"])
        self.assertEqual(abgleich.monate_aus_zweck("Miete 10/2026", tag), ["2026-10"])
        self.assertEqual(abgleich.monate_aus_zweck("KdU 11.26", tag), ["2026-11"])
        self.assertEqual(abgleich.monate_aus_zweck("Miete Sept + Okt", tag), ["2026-09", "2026-10"])
        self.assertEqual(abgleich.monate_aus_zweck("Miete Dezember", dt.date(2027, 1, 3)), ["2026-12"])
        self.assertEqual(abgleich.monate_aus_zweck("Jan Mustermann Miete", tag), [])     # Jan = Vorname
        self.assertEqual(abgleich.monate_aus_zweck("Kundennr 12345BG0012345", tag), [])

    def test_monat_aus_datum(self):
        self.assertEqual(abgleich.monate_fuer("Miete", dt.date(2026, 9, 28))[0], ["2026-10"])
        self.assertEqual(abgleich.monate_fuer("Miete", dt.date(2026, 10, 3))[0], ["2026-10"])
        self.assertEqual(abgleich.monate_fuer("Miete September", dt.date(2026, 10, 3))[0], ["2026-09"])


class AbgleichTest(DbTest, unittest.TestCase):
    def test_bekanntes_konto(self):
        self.buchen(u("2026-07-01", 650, "M. Mustermann", iban(1), "Dauerauftrag"))
        erg = abgleich.abgleichen(self.db)
        self.assertEqual(erg.automatisch, 1)
        self.assertEqual(self.vertrag_von("Dauerauftrag"), [("M-0001", "2026-07", 65000)])

    def test_mieternummer_und_konto_lernen(self):
        self.buchen(u("2026-07-02", 800, "Hans Beispiel", iban(33), "Miete M 3 Juli"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("Miete M 3 Juli"), [("M-0003", "2026-07", 80000)])
        # im naechsten Monat reicht das gelernte Konto, auch ohne jeden Hinweis
        self.buchen(u("2026-08-01", 800, "HB", iban(33), "Danke"))
        self.assertEqual(abgleich.abgleichen(self.db).automatisch, 1)
        self.assertEqual(self.vertrag_von("Danke"), [("M-0003", "2026-08", 80000)])

    def test_mitmieter_zahlt(self):
        self.buchen(u("2026-07-02", 800, "Hans Beispiel", "", "Miete"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("Miete"), [("M-0003", "2026-07", 80000)])

    def test_gleicher_nachname_bleibt_zur_pruefung(self):
        self.buchen(u("2026-07-02", 600, "Mustermann", "", "Miete Mustermann"))
        erg = abgleich.abgleichen(self.db)
        self.assertEqual(erg.zu_pruefen, 1)
        self.assertEqual(self.status("Miete Mustermann"), "offen")
        vorschlaege = abgleich.Bewerter(self.db).bewerte(self.db.q("SELECT * FROM buchungen")[0], ["2026-07"])
        self.assertEqual({s.vertrag.nummer for s in vorschlaege[:2]}, {"M-0001", "M-0002"})

    def test_voller_name_schlaegt_nachnamen(self):
        self.buchen(u("2026-07-02", 520, "Moritz Mustermann", iban(55), "Miete"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("Miete"), [("M-0002", "2026-07", 52000)])

    def test_jobcenter_sammelzahler(self):
        # Konto gehoert zu zwei Vertraegen -> Konto allein entscheidet nichts, der Name schon
        self.buchen(u("2026-06-29", 580, "Jobcenter Musterstadt", JOBCENTER, "KdU 99999BG0000001 Probe, Anna 07.2026"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("KdU 99999BG0000001 Probe, Anna 07.2026"), [("M-0004", "2026-07", 58000)])
        # BG-Nummer gelernt: naechster Monat ohne Namen geht trotzdem
        v = next(x for x in lade_vertraege(self.db) if x.nummer == "M-0004")
        self.assertIn("99999BG0000001", v.referenzen)
        self.buchen(u("2026-07-30", 580, "Jobcenter Musterstadt", JOBCENTER, "KdU 99999BG0000001 08.2026"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("KdU 99999BG0000001 08.2026"), [("M-0004", "2026-08", 58000)])

    def test_jobcenter_ohne_namen_wird_nicht_geraten(self):
        self.buchen(u("2026-06-29", 590, "Jobcenter Musterstadt", JOBCENTER, "KdU 07.2026"))
        self.assertEqual(abgleich.abgleichen(self.db).zu_pruefen, 1)

    def test_zahlung_ende_vormonat(self):
        self.buchen(u("2026-07-29", 650, "Max Mustermann", iban(1), "Miete"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("Miete"), [("M-0001", "2026-08", 65000)])

    def test_nachzahlung_fuellt_alten_monat(self):
        self.buchen(u("2026-07-02", 650, "Max Mustermann", iban(1), "Miete Juli"))
        self.buchen(u("2026-09-03", 1300, "Max Mustermann", iban(1), "Miete + Rueckstand"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("Miete + Rueckstand"),
                         [("M-0001", "2026-08", 65000), ("M-0001", "2026-09", 65000)])

    def test_ueberzahlung_bleibt_im_monat(self):
        self.buchen(u("2026-07-02", 650, "Max Mustermann", iban(1), "Miete"),
                    u("2026-07-03", 650, "Max Mustermann", iban(1), "Miete nochmal"))
        abgleich.abgleichen(self.db)
        m = uebersicht.monat_berechnen(self.db, "2026-07", dt.date(2026, 7, 20))
        zeile = next(z for z in m.zeilen if z.vertrag.nummer == "M-0001")
        self.assertEqual((zeile.ist, zeile.status, zeile.saldo), (130000, uebersicht.ZU_VIEL, -65000))

    def test_kaution_nie_automatisch(self):
        self.buchen(u("2026-07-02", 1500, "Max Mustermann", iban(1), "Kaution WE 1"))
        self.assertEqual(abgleich.abgleichen(self.db).zu_pruefen, 1)
        self.assertIn("Kaution", self.db.eins("SELECT notiz FROM buchungen")["notiz"])

    def test_zahler_ignorieren(self):
        self.buchen(u("2026-07-14", 45.12, "Stadtwerke Musterstadt", iban(777), "Erstattung"))
        abgleich.abgleichen(self.db)
        b = self.db.eins("SELECT id FROM buchungen")["id"]
        abgleich.ignorieren(self.db, b, "keine Miete", zahler_immer=True)
        self.buchen(u("2026-08-14", 12.00, "Stadtwerke Musterstadt", iban(777), "Erstattung 2"))
        self.assertEqual(abgleich.abgleichen(self.db).ignoriert, 1)
        self.assertEqual(self.status("Erstattung 2"), "ignoriert")

    def test_hand_zuordnen_und_aufheben(self):
        self.buchen(u("2026-07-05", 590, "Unbekannt", iban(88), "Ueberweisung"))
        abgleich.abgleichen(self.db)
        b = self.db.eins("SELECT id FROM buchungen")["id"]
        v = next(x for x in lade_vertraege(self.db) if x.nummer == "M-0005")
        abgleich.zuordnen(self.db, b, v, merken=True)
        self.assertEqual(self.vertrag_von("Ueberweisung"), [("M-0005", "2026-07", 59000)])
        self.assertIn(v.id, self.db.zahler_je_kennung()[self.db.schluessel.kennung(iban(88))])
        self.db.zuordnung_aufheben(b)
        self.assertEqual(self.status("Ueberweisung"), "offen")
        self.assertEqual(self.vertrag_von("Ueberweisung"), [])

    def test_nachzahlung_nach_auszug(self):
        self.buchen(u("2026-09-10", 400, "Lena Testmann", iban(66), "Restmiete Juli"))
        abgleich.abgleichen(self.db)
        self.assertEqual(self.vertrag_von("Restmiete Juli"), [("M-0006", "2026-07", 40000)])


class EinlesenTest(DbTest, unittest.TestCase):
    def test_doppelter_import_und_echte_zwillinge(self):
        a = u("2026-07-01", 650, "Max Mustermann", iban(1), "Miete")
        b = u("2026-07-01", 650, "Max Mustermann", iban(1), "Miete")      # wirklich zweimal ueberwiesen
        self.buchen(a, b)
        self.buchen(a, b, u("2026-07-02", 60, "Otto Vorlage", "", "Garage"))
        self.assertEqual(self.db.eins("SELECT COUNT(*) AS n FROM buchungen")["n"], 3)
        imp = self.db.q("SELECT neu, doppelt FROM importe ORDER BY id")
        self.assertEqual([(r["neu"], r["doppelt"]) for r in imp], [(2, 0), (1, 2)])

    def test_iban_wird_nicht_gespeichert(self):
        self.buchen(u("2026-07-01", 650, "Max Mustermann", iban(1), "Miete"))
        dump = "\n".join(self.db.con.iterdump())
        self.assertNotIn(iban(1), dump)
        self.assertNotIn(iban(1)[4:], dump)
        self.assertIn(iban(1)[-4:], dump)                   # nur die letzten vier Stellen

    def test_erfassungsbeginn_automatisch(self):
        self.db.con.execute("DELETE FROM meta WHERE schluessel = 'erfassung_ab'")
        self.buchen(u("2026-06-28", 650, "Max Mustermann", iban(1), "Miete"))
        self.assertEqual(self.db.erfassung_ab, "2026-07")


class UebersichtTest(DbTest, unittest.TestCase):
    def test_status_und_rueckstand(self):
        self.buchen(u("2026-07-01", 650, "Max Mustermann", iban(1), "a"),
                    u("2026-07-02", 300, "Moritz Mustermann", "", "M-0002 Teil"),
                    u("2026-08-01", 650, "Max Mustermann", iban(1), "b"))
        abgleich.abgleichen(self.db)
        m = uebersicht.monat_berechnen(self.db, "2026-08", dt.date(2026, 8, 2))
        z = {x.vertrag.nummer: x for x in m.zeilen}
        self.assertEqual(z["M-0001"].status, uebersicht.BEZAHLT)
        self.assertEqual(z["M-0002"].status, uebersicht.OFFEN)                 # vor Faelligkeit
        self.assertEqual(z["M-0002"].saldo, 52000 - 30000 + 52000)
        self.assertNotIn("M-0006", z)                                          # ausgezogen
        spaeter = uebersicht.monat_berechnen(self.db, "2026-08", dt.date(2026, 8, 20))
        self.assertEqual({x.vertrag.nummer: x for x in spaeter.zeilen}["M-0002"].status, uebersicht.UEBERFAELLIG)
        juli = uebersicht.monat_berechnen(self.db, "2026-07", dt.date(2026, 8, 20))
        self.assertEqual({x.vertrag.nummer: x for x in juli.zeilen}["M-0002"].status, uebersicht.UEBERFAELLIG)
        self.assertIn("M-0002", uebersicht.als_csv(spaeter, nur_offen=True))
        self.assertNotIn("M-0001", uebersicht.als_csv(spaeter, nur_offen=True))


if __name__ == "__main__":
    unittest.main()
