"""Gemeinsame Bausteine fuer die Tests der Hausverwaltung - nur erfundene Daten."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from verwaltung import einlesen, stammdaten
from verwaltung.bank import Umsatz
from verwaltung.db import Datenbank
from verwaltung.schutz import iban_bauen


def iban(nr: int) -> str:
    return iban_bauen("DE", "00000000" + f"{nr:010d}")


JOBCENTER = iban(999999)

STAMM = f"""Mieternummer;Objekt;Strasse;PLZ;Ort;Einheit;Vorname;Nachname;Mitmieter;Mietbeginn;Mietende;Kaltmiete;Nebenkosten;IBAN Zahler;IBAN Zahler 2;Referenzen
M-0001;Musterstr. 5;Musterstraße 5;12345;Musterstadt;WE 1;Max;Mustermann;;01.01.2020;;500,00;150,00;{iban(1)};;
M-0002;Musterstr. 5;Musterstraße 5;12345;Musterstadt;WE 2;Moritz;Mustermann;;01.01.2021;;400,00;120,00;;;
M-0003;Beispielweg 3;Beispielweg 3;12345;Musterstadt;WE 1;Erika;Beispiel;Hans Beispiel;01.06.2019;;610,00;190,00;;;
M-0004;Beispielweg 3;Beispielweg 3;12345;Musterstadt;WE 2;Anna;Probe;;01.01.2018;;450,00;130,00;;{JOBCENTER};
M-0005;Beispielweg 3;Beispielweg 3;12345;Musterstadt;WE 3;Paul;Probe;;01.01.2018;;455,00;135,00;;{JOBCENTER};
M-0006;Testring 1;Testring 1;12345;Musterstadt;WE 1;Lena;Testmann;;01.01.2015;31.07.2026;300,00;100,00;;;
M-0007;Testring 1;Testring 1;12345;Musterstadt;Garage 1;Otto;Vorlage;;01.03.2022;;60,00;0;;;
"""


class DbTest:
    """Mixin: frische Datenbank mit sieben erfundenen Vertraegen, Erfassung ab Juli 2026."""

    def setUp(self):  # noqa: N802
        self._tmp = tempfile.TemporaryDirectory()
        self.ordner = Path(self._tmp.name)
        self.db = Datenbank(self.ordner)
        erg = stammdaten.einlesen_text(self.db, STAMM)
        assert not erg.fehler, erg.fehler
        self.db.setze_meta("erfassung_ab", "2026-07")

    def tearDown(self):  # noqa: N802
        self.db.close()
        self._tmp.cleanup()

    def buchen(self, *umsaetze: Umsatz) -> None:
        einlesen.speichern(self.db, list(umsaetze), "test.csv", "Test")

    def vertrag_von(self, buchung_zweck: str) -> list[tuple[str, str, int]]:
        """[(Mieternummer, Monat, Cent)] fuer die Buchung mit diesem Zweck."""
        return [(r["nummer"], r["monat"], r["betrag_cent"]) for r in self.db.q(
            "SELECT v.nummer, z.monat, z.betrag_cent FROM zahlungen z JOIN buchungen b ON b.id = z.buchung_id "
            "JOIN vertraege v ON v.id = z.vertrag_id WHERE b.zweck = ? ORDER BY z.monat", (buchung_zweck,))]

    def status(self, zweck: str) -> str:
        return self.db.eins("SELECT status FROM buchungen WHERE zweck = ?", (zweck,))["status"]


def u(tag: str, betrag: float, name: str = "", iban_: str = "", zweck: str = "") -> Umsatz:
    d = dt.date.fromisoformat(tag)
    return Umsatz(datum=d, betrag_cent=round(betrag * 100), name=name, iban=iban_, zweck=zweck, konto=iban(100001))
