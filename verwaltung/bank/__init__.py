"""Kontoauszuege einlesen: CSV (alle gaengigen Banken) und CAMT.052/053 (XML).

CAMT ist das Standardformat, das jede deutsche Bank im Online-Banking als
"Umsaetze exportieren" anbietet - wenn es die Wahl gibt, ist es die beste,
weil Name, IBAN und Verwendungszweck sauber getrennt sind.

Alle Leser liefern dieselbe Form (Umsatz). Was danach mit einem Umsatz
passiert (speichern, IBAN nur als Kennung), entscheidet import_.py.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path


class FormatFehler(Exception):
    """Datei ist kein bekannter Kontoauszug."""


@dataclass
class Umsatz:
    datum: dt.date
    betrag_cent: int                  # Gutschrift positiv, Abbuchung negativ
    name: str = ""                    # Auftraggeber / Zahlungspflichtiger
    iban: str = ""                    # IBAN des Auftraggebers
    zweck: str = ""                   # Verwendungszweck
    konto: str = ""                   # eigenes Konto (IBAN oder Bezeichnung)
    roh: dict = field(default_factory=dict, repr=False)


def lese_datei(pfad: Path) -> tuple[str, list[Umsatz]]:
    """(Formatname, Umsaetze). Erkennt das Format am Inhalt, nicht an der Endung."""
    from . import camt, csv_bank

    daten = Path(pfad).read_bytes()
    kopf = daten[:2000].lstrip(b"\xef\xbb\xbf \r\n\t")
    if kopf.startswith(b"<") or b"<Document" in kopf:
        return "CAMT", camt.lese(daten)
    return csv_bank.lese(daten)
