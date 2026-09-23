"""Kontoauszug -> Datenbank. Nur Gutschriften, jede genau einmal.

Die Angestellte exportiert mal den 1.-10., spaeter den 1.-15. - dieselben
Buchungen kommen also mehrfach. Jede Buchung bekommt einen Fingerabdruck
(Konto, Datum, Betrag, Zahler, Zweck); was schon da ist, wird uebersprungen.
Zwei wirklich gleiche Buchungen am selben Tag (Mieter ueberweist zweimal
dieselbe Miete) werden ueber einen Zaehler trotzdem beide erfasst.
"""

from __future__ import annotations

import hashlib
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import geld
from .bank import FormatFehler, Umsatz, lese_datei
from .db import Datenbank, jetzt
from .schutz import iban_ende, iban_gueltig, iban_normal, woerter

DATEI_ENDUNGEN = {".csv", ".txt", ".xml", ".camt", ".c53", ".c52"}


@dataclass
class ImportErgebnis:
    datei: str
    format: str = ""
    neu: int = 0
    doppelt: int = 0
    abbuchungen: int = 0
    fehler: str = ""

    def text(self) -> str:
        if self.fehler:
            return f"{self.datei}: FEHLER - {self.fehler}"
        return (f"{self.datei} [{self.format}]: {self.neu} neue Gutschriften, "
                f"{self.doppelt} schon bekannt, {self.abbuchungen} Abbuchungen übersprungen")


def konto_label(konto: str) -> str:
    if iban_gueltig(konto):
        return "…" + iban_ende(konto)
    return (konto or "").strip()[:30]


def _basis_abdruck(u: Umsatz, kennung: str | None) -> str:
    teile = [konto_label(u.konto), u.datum.isoformat(), str(u.betrag_cent), kennung or "",
             " ".join(woerter(u.name)), " ".join(woerter(u.zweck))]
    return hashlib.sha256("|".join(teile).encode()).hexdigest()[:40]


def speichern(db: Datenbank, umsaetze: list[Umsatz], datei: str, format_: str) -> ImportErgebnis:
    erg = ImportErgebnis(datei=datei, format=format_)
    import_id = db.con.execute("INSERT INTO importe (datei, format, am) VALUES (?, ?, ?)",
                               (datei, format_, jetzt())).lastrowid
    zaehler: Counter[str] = Counter()
    for u in umsaetze:
        if u.betrag_cent <= 0:
            erg.abbuchungen += 1
            continue
        kennung = db.schluessel.kennung(u.iban) if iban_normal(u.iban) else None
        basis = _basis_abdruck(u, kennung)
        abdruck = f"{basis}#{zaehler[basis]}"
        zaehler[basis] += 1
        cur = db.con.execute(
            "INSERT OR IGNORE INTO buchungen (konto, datum, betrag_cent, name, iban_kennung, iban_ende, zweck, "
            "fingerabdruck, import_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (konto_label(u.konto), u.datum.isoformat(), u.betrag_cent, u.name.strip(), kennung,
             iban_ende(u.iban) if kennung else "", u.zweck.strip(), abdruck, import_id))
        if cur.rowcount:
            erg.neu += 1
        else:
            erg.doppelt += 1
    db.con.execute("UPDATE importe SET neu = ?, doppelt = ?, abbuchungen = ? WHERE id = ?",
                   (erg.neu, erg.doppelt, erg.abbuchungen, import_id))
    if not db.erfassung_ab:
        erste = db.eins("SELECT MIN(datum) AS d FROM buchungen")["d"]
        if erste:
            d = geld.datum(erste)
            # wer am 28. ueberweist, zahlt meist schon fuer den Folgemonat
            start = geld.monat(d) if d.day < 20 else geld.monat_plus(geld.monat(d), 1)
            db.setze_meta("erfassung_ab", start)
    db.protokolliere("import", erg.text())
    db.con.commit()
    return erg


def datei_einlesen(db: Datenbank, pfad: Path) -> ImportErgebnis:
    try:
        format_, umsaetze = lese_datei(pfad)
    except FormatFehler as fehler:
        return ImportErgebnis(datei=Path(pfad).name, fehler=str(fehler))
    return speichern(db, umsaetze, Path(pfad).name, format_)


def eingang_ordner(db: Datenbank) -> Path:
    ordner = db.ordner / "bank" / "eingang"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def eingang_verarbeiten(db: Datenbank) -> list[ImportErgebnis]:
    """Alle Dateien aus bank/eingang einlesen und nach bank/archiv/<Monat> verschieben."""
    eingang = eingang_ordner(db)
    ergebnisse = []
    for pfad in sorted(p for p in eingang.iterdir() if p.is_file() and p.suffix.lower() in DATEI_ENDUNGEN):
        erg = datei_einlesen(db, pfad)
        ergebnisse.append(erg)
        if not erg.fehler:
            ziel = db.ordner / "bank" / "archiv" / jetzt()[:7]
            ziel.mkdir(parents=True, exist_ok=True)
            neu = ziel / pfad.name
            if neu.exists():
                neu = ziel / f"{pfad.stem}_{jetzt().replace(':', '')}{pfad.suffix}"
            shutil.move(str(pfad), neu)
    return ergebnisse
