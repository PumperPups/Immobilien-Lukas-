"""SQLite-Datenbank: eine Datei im Datenordner, kein Server.

Aufbau (Stufe 1 = Mieteingang; weitere Module haengen sich an dieselben
Stammdaten, siehe docs/GESAMTKONZEPT.md):

    objekte ──< einheiten ──< vertraege >── personen
                                 │
                                 ├──< sollmieten        (Miete je Zeitraum)
                                 ├──< zahler            (bekannte Konten, nur Kennung)
                                 └──< zahlungen >── buchungen ──> importe
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from . import geld
from .schutz import Schluessel

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT
);

-- ---------------------------------------------------------------- Stammdaten
CREATE TABLE IF NOT EXISTS objekte (
    id          INTEGER PRIMARY KEY,
    kuerzel     TEXT NOT NULL UNIQUE,      -- z.B. "Musterstr. 5"
    strasse     TEXT,
    plz         TEXT,
    ort         TEXT,
    notiz       TEXT
);

CREATE TABLE IF NOT EXISTS einheiten (
    id          INTEGER PRIMARY KEY,
    objekt_id   INTEGER NOT NULL REFERENCES objekte(id),
    bezeichnung TEXT NOT NULL,             -- z.B. "WE 3" oder "EG links"
    art         TEXT,                      -- Wohnung, Gewerbe, Stellplatz ...
    flaeche_qm  REAL,
    notiz       TEXT,
    UNIQUE (objekt_id, bezeichnung)
);

CREATE TABLE IF NOT EXISTS personen (
    id          INTEGER PRIMARY KEY,
    vorname     TEXT,
    nachname    TEXT NOT NULL,
    email       TEXT,
    telefon     TEXT,
    notiz       TEXT
);

CREATE TABLE IF NOT EXISTS vertraege (
    id          INTEGER PRIMARY KEY,
    nummer      TEXT NOT NULL UNIQUE,      -- Mieternummer, z.B. "M-0042"
    einheit_id  INTEGER NOT NULL REFERENCES einheiten(id),
    person_id   INTEGER NOT NULL REFERENCES personen(id),
    mitmieter   TEXT,                      -- weitere Namen, mit ; getrennt
    beginn      TEXT NOT NULL,             -- YYYY-MM-DD
    ende        TEXT,
    kaution_cent INTEGER,
    startsaldo_cent INTEGER NOT NULL DEFAULT 0,  -- Rueckstand (+) / Guthaben (-) bei Erfassungsbeginn
    referenzen  TEXT,                      -- weitere Kennungen im Verwendungszweck (BG-Nummer ...), ; getrennt
    notiz       TEXT
);

CREATE TABLE IF NOT EXISTS sollmieten (
    vertrag_id  INTEGER NOT NULL REFERENCES vertraege(id) ON DELETE CASCADE,
    gueltig_ab  TEXT NOT NULL,             -- YYYY-MM
    kalt_cent   INTEGER NOT NULL,
    nk_cent     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (vertrag_id, gueltig_ab)
);

-- ---------------------------------------------------------------- Bank
CREATE TABLE IF NOT EXISTS importe (
    id          INTEGER PRIMARY KEY,
    datei       TEXT,
    format      TEXT,
    am          TEXT,
    neu         INTEGER,
    doppelt     INTEGER,
    abbuchungen INTEGER
);

CREATE TABLE IF NOT EXISTS buchungen (
    id          INTEGER PRIMARY KEY,
    konto       TEXT,                      -- eigenes Konto, nur "…1234"
    datum       TEXT NOT NULL,
    betrag_cent INTEGER NOT NULL,
    name        TEXT,                      -- Auftraggeber laut Bank
    iban_kennung TEXT,                     -- HMAC, nie die IBAN selbst
    iban_ende   TEXT,
    zweck       TEXT,
    fingerabdruck TEXT NOT NULL UNIQUE,
    import_id   INTEGER REFERENCES importe(id),
    status      TEXT NOT NULL DEFAULT 'offen',   -- offen / zugeordnet / ignoriert
    notiz       TEXT
);
CREATE INDEX IF NOT EXISTS idx_buchungen_status ON buchungen(status);
CREATE INDEX IF NOT EXISTS idx_buchungen_datum ON buchungen(datum);

CREATE TABLE IF NOT EXISTS zahler (
    iban_kennung TEXT NOT NULL,
    vertrag_id  INTEGER NOT NULL REFERENCES vertraege(id) ON DELETE CASCADE,
    iban_ende   TEXT,
    bezeichnung TEXT,                      -- z.B. "Jobcenter" oder "Mutter"
    quelle      TEXT,                      -- stammdaten / gelernt / hand
    PRIMARY KEY (iban_kennung, vertrag_id)
);

CREATE TABLE IF NOT EXISTS zahler_ignoriert (
    iban_kennung TEXT PRIMARY KEY,
    iban_ende   TEXT,
    bezeichnung TEXT,
    am          TEXT
);

CREATE TABLE IF NOT EXISTS zahlungen (
    id          INTEGER PRIMARY KEY,
    buchung_id  INTEGER NOT NULL REFERENCES buchungen(id) ON DELETE CASCADE,
    vertrag_id  INTEGER NOT NULL REFERENCES vertraege(id),
    monat       TEXT NOT NULL,             -- YYYY-MM, fuer den gezahlt wurde
    betrag_cent INTEGER NOT NULL,
    art         TEXT NOT NULL,             -- auto / hand
    grund       TEXT,
    am          TEXT
);
CREATE INDEX IF NOT EXISTS idx_zahlungen_vertrag ON zahlungen(vertrag_id, monat);
CREATE INDEX IF NOT EXISTS idx_zahlungen_buchung ON zahlungen(buchung_id);

-- ---------------------------------------------------------------- Protokoll
CREATE TABLE IF NOT EXISTS protokoll (
    id          INTEGER PRIMARY KEY,
    am          TEXT NOT NULL,
    aktion      TEXT NOT NULL,
    details     TEXT
);
"""


def jetzt() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class Datenbank:
    DATEI = "verwaltung.db"

    def __init__(self, ordner: Path):
        self.ordner = Path(ordner)
        self.ordner.mkdir(parents=True, exist_ok=True)
        self.schluessel = Schluessel(self.ordner)
        self.con = sqlite3.connect(self.ordner / self.DATEI, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SCHEMA)
        if self.meta("schema_version") is None:
            self.setze_meta("schema_version", str(SCHEMA_VERSION))

    def close(self) -> None:
        self.con.close()

    # ------------------------------------------------------------ allgemein
    def q(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.con.execute(sql, tuple(params)).fetchall()

    def eins(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.con.execute(sql, tuple(params)).fetchone()

    def meta(self, schluessel: str, standard: str | None = None) -> str | None:
        row = self.eins("SELECT wert FROM meta WHERE schluessel = ?", (schluessel,))
        return row["wert"] if row else standard

    def setze_meta(self, schluessel: str, wert: str) -> None:
        self.con.execute("INSERT INTO meta VALUES (?, ?) ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert",
                         (schluessel, wert))
        self.con.commit()

    def protokolliere(self, aktion: str, details: str = "") -> None:
        self.con.execute("INSERT INTO protokoll (am, aktion, details) VALUES (?, ?, ?)", (jetzt(), aktion, details))

    # ------------------------------------------------------------ Einstellungen
    @property
    def erfassung_ab(self) -> str | None:
        """Ab welchem Monat die Zahlungen gefuehrt werden. Davor gilt nichts als offen."""
        return self.meta("erfassung_ab")

    def einstellung(self, name: str, standard: int) -> int:
        return int(self.meta(name, str(standard)))

    # ------------------------------------------------------------ Stammdaten
    def objekt_id(self, kuerzel: str, strasse: str = "", plz: str = "", ort: str = "") -> int:
        row = self.eins("SELECT id FROM objekte WHERE kuerzel = ?", (kuerzel,))
        if row:
            self.con.execute("UPDATE objekte SET strasse = COALESCE(NULLIF(?, ''), strasse), "
                             "plz = COALESCE(NULLIF(?, ''), plz), ort = COALESCE(NULLIF(?, ''), ort) WHERE id = ?",
                             (strasse, plz, ort, row["id"]))
            return row["id"]
        return self.con.execute("INSERT INTO objekte (kuerzel, strasse, plz, ort) VALUES (?, ?, ?, ?)",
                                (kuerzel, strasse, plz, ort)).lastrowid

    def einheit_id(self, objekt_id: int, bezeichnung: str, art: str = "", flaeche: float | None = None) -> int:
        row = self.eins("SELECT id FROM einheiten WHERE objekt_id = ? AND bezeichnung = ?", (objekt_id, bezeichnung))
        if row:
            self.con.execute("UPDATE einheiten SET art = COALESCE(NULLIF(?, ''), art), "
                             "flaeche_qm = COALESCE(?, flaeche_qm) WHERE id = ?", (art, flaeche, row["id"]))
            return row["id"]
        return self.con.execute("INSERT INTO einheiten (objekt_id, bezeichnung, art, flaeche_qm) VALUES (?, ?, ?, ?)",
                                (objekt_id, bezeichnung, art, flaeche)).lastrowid

    def vertraege(self, nur_id: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT v.*, p.vorname, p.nachname, p.email, p.telefon,
                   e.bezeichnung AS einheit, e.art, o.kuerzel AS objekt, o.strasse, o.plz, o.ort
            FROM vertraege v
            JOIN personen p ON p.id = v.person_id
            JOIN einheiten e ON e.id = v.einheit_id
            JOIN objekte o ON o.id = e.objekt_id
        """
        if nur_id is not None:
            return self.q(sql + " WHERE v.id = ?", (nur_id,))
        return self.q(sql + " ORDER BY o.kuerzel, e.bezeichnung, v.beginn")

    def vertrag_nach_nummer(self, nummer: str) -> sqlite3.Row | None:
        row = self.eins("SELECT id FROM vertraege WHERE nummer = ? COLLATE NOCASE", (nummer.strip(),))
        return self.vertraege(row["id"])[0] if row else None

    def sollmieten(self) -> dict[int, list[tuple[str, int, int]]]:
        """vertrag_id -> [(gueltig_ab, kalt, nk)] aufsteigend."""
        aus: dict[int, list[tuple[str, int, int]]] = {}
        for r in self.q("SELECT * FROM sollmieten ORDER BY vertrag_id, gueltig_ab"):
            aus.setdefault(r["vertrag_id"], []).append((r["gueltig_ab"], r["kalt_cent"], r["nk_cent"]))
        return aus

    def setze_sollmiete(self, vertrag_id: int, gueltig_ab: str, kalt: int, nk: int) -> bool:
        """Neue Miete ab Monat. Gibt True zurueck, wenn sich etwas geaendert hat."""
        stufen = self.sollmieten().get(vertrag_id, [])
        aktuell = [s for s in stufen if s[0] <= gueltig_ab]
        if aktuell and aktuell[-1][1:] == (kalt, nk):
            return False
        self.con.execute("INSERT INTO sollmieten VALUES (?, ?, ?, ?) ON CONFLICT(vertrag_id, gueltig_ab) "
                         "DO UPDATE SET kalt_cent = excluded.kalt_cent, nk_cent = excluded.nk_cent",
                         (vertrag_id, gueltig_ab, kalt, nk))
        return True

    # ------------------------------------------------------------ Zahler
    def zahler_merken(self, vertrag_id: int, iban_kennung: str | None, iban_ende: str = "",
                      bezeichnung: str = "", quelle: str = "hand") -> bool:
        if not iban_kennung:
            return False
        cur = self.con.execute("INSERT OR IGNORE INTO zahler VALUES (?, ?, ?, ?, ?)",
                               (iban_kennung, vertrag_id, iban_ende, bezeichnung, quelle))
        return cur.rowcount > 0

    def zahler_je_kennung(self) -> dict[str, set[int]]:
        aus: dict[str, set[int]] = {}
        for r in self.q("SELECT iban_kennung, vertrag_id FROM zahler"):
            aus.setdefault(r["iban_kennung"], set()).add(r["vertrag_id"])
        return aus

    def ignorierte_zahler(self) -> set[str]:
        return {r["iban_kennung"] for r in self.q("SELECT iban_kennung FROM zahler_ignoriert")}

    # ------------------------------------------------------------ Buchungen
    def buchung(self, buchung_id: int) -> sqlite3.Row | None:
        return self.eins("SELECT * FROM buchungen WHERE id = ?", (buchung_id,))

    def zahlungen(self, vertrag_id: int | None = None, monat: str | None = None) -> list[sqlite3.Row]:
        sql = ("SELECT z.*, b.datum, b.name, b.zweck, b.iban_ende, b.betrag_cent AS buchung_betrag "
               "FROM zahlungen z JOIN buchungen b ON b.id = z.buchung_id WHERE 1 = 1")
        params: list[Any] = []
        if vertrag_id is not None:
            sql += " AND z.vertrag_id = ?"
            params.append(vertrag_id)
        if monat is not None:
            sql += " AND z.monat = ?"
            params.append(monat)
        return self.q(sql + " ORDER BY b.datum, z.id", params)

    def ist_je_vertrag_monat(self) -> dict[tuple[int, str], int]:
        return {(r["vertrag_id"], r["monat"]): r["summe"] for r in
                self.q("SELECT vertrag_id, monat, SUM(betrag_cent) AS summe FROM zahlungen GROUP BY vertrag_id, monat")}

    def zahlung_buchen(self, buchung_id: int, teile: list[tuple[int, str, int]], art: str, grund: str) -> None:
        """teile = [(vertrag_id, monat, cent)]; ersetzt fruehere Zuordnungen der Buchung."""
        self.con.execute("DELETE FROM zahlungen WHERE buchung_id = ?", (buchung_id,))
        for vertrag_id, monat, betrag in teile:
            self.con.execute("INSERT INTO zahlungen (buchung_id, vertrag_id, monat, betrag_cent, art, grund, am) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", (buchung_id, vertrag_id, monat, betrag, art, grund, jetzt()))
        self.con.execute("UPDATE buchungen SET status = 'zugeordnet' WHERE id = ?", (buchung_id,))

    def zuordnung_aufheben(self, buchung_id: int) -> None:
        self.con.execute("DELETE FROM zahlungen WHERE buchung_id = ?", (buchung_id,))
        self.con.execute("UPDATE buchungen SET status = 'offen', notiz = NULL WHERE id = ?", (buchung_id,))
        self.protokolliere("aufheben", f"Buchung {buchung_id}")
        self.con.commit()

    def monat_seit(self) -> str:
        """Erfassungsbeginn, sonst aeltester Buchungsmonat, sonst dieser Monat."""
        if self.erfassung_ab:
            return self.erfassung_ab
        row = self.eins("SELECT MIN(datum) AS d FROM buchungen")
        if row and row["d"]:
            return row["d"][:7]
        return geld.monat(dt.date.today())
