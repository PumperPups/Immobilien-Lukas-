import http.client
import json
import threading
import unittest

from hilfe_verwaltung import DbTest, iban, u
from verwaltung import abgleich, web


class WebTest(DbTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.buchen(u("2026-07-01", 650, "Max Mustermann", iban(1), "Miete Juli"),
                    u("2026-07-05", 590, "Unbekannt", iban(88), "Ueberweisung"))
        abgleich.abgleichen(self.db)
        self.srv = web.server(self.db, 0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def anfrage(self, methode, pfad, daten=None, kopf=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        koerper = json.dumps(daten).encode() if daten is not None else None
        k = {"Content-Type": "application/json"} if daten is not None else {}
        k.update(kopf or {})
        c.request(methode, pfad, body=koerper, headers=k)
        r = c.getresponse()
        return r.status, r.read().decode("utf-8")

    def test_seiten(self):
        for pfad in ("/", "/?monat=2026-07", "/pruefen", "/mieter", "/mieter/1", "/import", "/einstellungen",
                     "/vorlage.csv", "/export.csv?monat=2026-07&offen=1"):
            status, text = self.anfrage("GET", pfad)
            self.assertEqual(status, 200, pfad)
        status, text = self.anfrage("GET", "/pruefen")
        self.assertIn("Ueberweisung", text)
        self.assertNotIn(iban(88), text)               # IBAN taucht nirgends auf, nur …ende
        self.assertIn(iban(88)[-4:], text)

    def test_zuordnen_ueber_api(self):
        b = self.db.eins("SELECT id FROM buchungen WHERE zweck = 'Ueberweisung'")["id"]
        v = self.db.eins("SELECT id FROM vertraege WHERE nummer = 'M-0005'")["id"]
        status, text = self.anfrage("POST", "/api/zuordnen", {"buchung": b, "vertrag": v, "monat": None, "merken": True})
        self.assertEqual(status, 200, text)
        self.assertIn("M-0005", json.loads(text)["text"])
        self.assertEqual(self.status("Ueberweisung"), "zugeordnet")

    def test_schutz(self):
        status, _ = self.anfrage("GET", "/", kopf={"Host": "boese.example"})
        self.assertEqual(status, 403)
        status, _ = self.anfrage("POST", "/api/abgleich", {}, kopf={"Origin": "https://boese.example"})
        self.assertEqual(status, 403)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/api/abgleich", body=b"{}", headers={"Content-Type": "text/plain"})
        self.assertEqual(c.getresponse().status, 403)

    def test_import_nur_bankdateien(self):
        import base64
        status, text = self.anfrage("POST", "/api/import", {"name": "../../boese.exe",
                                                            "daten": base64.b64encode(b"x").decode()})
        self.assertEqual(status, 400)
        self.assertFalse((self.ordner / "boese.exe").exists())


if __name__ == "__main__":
    unittest.main()
