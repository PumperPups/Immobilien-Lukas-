"""Monatsuebersicht: wer hat bezahlt, wer nicht?"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass, field

from . import geld
from .db import Datenbank
from .miete import Vertrag, lade_vertraege, saldo

TOLERANZ_CENT = 100            # bis 1 € Differenz gilt als bezahlt (Rundung, Bankgebuehr)
KARENZ_TAGE = 3                # so lange nach Faelligkeit warten, bevor es "ueberfaellig" heisst

BEZAHLT, ZU_VIEL, TEILWEISE, OFFEN, UEBERFAELLIG = "bezahlt", "zu viel", "teilweise", "offen", "überfällig"
REIHENFOLGE = {UEBERFAELLIG: 0, TEILWEISE: 1, OFFEN: 2, ZU_VIEL: 3, BEZAHLT: 4}


@dataclass
class Zeile:
    vertrag: Vertrag
    soll: int
    ist: int
    saldo: int                      # Rueckstand gesamt seit Erfassungsbeginn (+ = schuldet)
    status: str
    zahlungen: list = field(default_factory=list)

    @property
    def differenz(self) -> int:
        return self.ist - self.soll


@dataclass
class Monat:
    monat: str
    faellig: dt.date
    zeilen: list[Zeile]

    def summe(self, attr: str) -> int:
        return sum(getattr(z, attr) for z in self.zeilen)

    def anzahl(self, status: str) -> int:
        return sum(1 for z in self.zeilen if z.status == status)

    @property
    def quote(self) -> float:
        soll = self.summe("soll")
        return min(self.summe("ist") / soll, 1.0) if soll else 1.0


def status_fuer(soll: int, ist: int, ueberfaellig: bool) -> str:
    if soll - ist <= TOLERANZ_CENT:
        return ZU_VIEL if ist - soll > TOLERANZ_CENT else BEZAHLT
    if ueberfaellig:
        return UEBERFAELLIG
    return TEILWEISE if ist > 0 else OFFEN


def monat_berechnen(db: Datenbank, monat: str, heute: dt.date | None = None) -> Monat:
    heute = heute or dt.date.today()
    faellig = geld.faellig_am(monat)
    ueberfaellig = heute > faellig + dt.timedelta(days=db.einstellung("karenz_tage", KARENZ_TAGE))
    ist = db.ist_je_vertrag_monat()
    ab = db.monat_seit()
    zahlungen: dict[int, list] = {}
    for z in db.zahlungen(monat=monat):
        zahlungen.setdefault(z["vertrag_id"], []).append(z)

    zeilen = []
    for v in lade_vertraege(db):
        soll = v.soll(monat)
        if not soll and v.id not in zahlungen:
            continue
        betrag = ist.get((v.id, monat), 0)
        zeilen.append(Zeile(vertrag=v, soll=soll, ist=betrag,
                            saldo=saldo(v, monat, ab, ist) if monat >= ab else 0,
                            status=status_fuer(soll, betrag, ueberfaellig),
                            zahlungen=zahlungen.get(v.id, [])))
    zeilen.sort(key=lambda z: (REIHENFOLGE[z.status], z.vertrag.objekt, z.vertrag.einheit))
    return Monat(monat=monat, faellig=faellig, zeilen=zeilen)


def als_csv(m: Monat, nur_offen: bool = False) -> str:
    """Offene-Posten-Liste fuer Excel (Semikolon, deutsche Zahlen)."""
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow(["Status", "Mieternummer", "Objekt", "Einheit", "Mieter", "Soll", "Ist", "Differenz",
                "Rückstand gesamt", "Zahlungen"])
    for z in m.zeilen:
        if nur_offen and z.status in (BEZAHLT, ZU_VIEL):
            continue
        w.writerow([z.status, z.vertrag.nummer, z.vertrag.objekt, z.vertrag.einheit, z.vertrag.name,
                    geld.eur(z.soll, False), geld.eur(z.ist, False), geld.eur(z.differenz, False),
                    geld.eur(z.saldo, False),
                    ", ".join(f"{geld.datum_de(p['datum'])}: {geld.eur(p['betrag_cent'], False)}" for p in z.zahlungen)])
    return puffer.getvalue()
