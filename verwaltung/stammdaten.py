"""Stammdaten aus einer Tabelle einlesen: eine Zeile je Mietvertrag.

Die 200-300 Einheiten stehen meistens schon irgendwo in Excel. In Excel
"Speichern unter -> CSV UTF-8 (durch Trennzeichen getrennt)" und hier
einlesen. Spaltennamen sind tolerant, Reihenfolge egal. Erneutes Einlesen
aktualisiert (Schluessel ist die Mieternummer) - es entsteht nichts doppelt.

IBANs aus der Tabelle werden sofort in Kennungen umgewandelt und nicht
gespeichert. Nach dem Einlesen kann die CSV geloescht werden.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass, field
from pathlib import Path

from . import geld
from .bank.csv_bank import _dekodieren, _norm
from .db import Datenbank
from .schutz import iban_bauen, iban_ende, iban_gueltig

SPALTEN = {
    "nummer": ("mieternummer", "mieternr", "vertragsnummer", "nummer", "nr", "referenz"),
    "objekt": ("objekt", "haus", "liegenschaft", "gebaeude"),
    "strasse": ("strasse", "adresse", "anschrift"),
    "plz": ("plz", "postleitzahl"),
    "ort": ("ort", "stadt"),
    "einheit": ("einheit", "wohnung", "whg", "we", "lage"),
    "art": ("art", "nutzung", "typ"),
    "flaeche": ("flaeche", "wohnflaeche", "qm", "m2"),
    "vorname": ("vorname",),
    "nachname": ("nachname", "name", "mieter"),
    "mitmieter": ("mitmieter", "weiteremieter"),
    "email": ("email", "mail"),
    "telefon": ("telefon", "tel", "handy", "mobil"),
    "beginn": ("mietbeginn", "beginn", "einzug", "vertragsbeginn"),
    "ende": ("mietende", "ende", "auszug", "vertragsende"),
    "kalt": ("kaltmiete", "grundmiete", "nettokaltmiete", "kalt"),
    "nk": ("nebenkosten", "nk", "betriebskosten", "nebenkostenvorauszahlung", "vorauszahlung"),
    "gesamt": ("gesamtmiete", "warmmiete", "miete", "sollmiete"),
    "gueltig_ab": ("mietegueltigab", "gueltigab"),
    "kaution": ("kaution",),
    "rueckstand": ("rueckstand", "startsaldo", "offenerrueckstand"),
    "iban1": ("ibanzahler", "iban", "ibanmieter", "ibanzahler1"),
    "iban2": ("ibanzahler2", "iban2", "ibanjobcenter"),
    "referenzen": ("referenzen", "bgnummer", "weiterereferenzen"),
    "notiz": ("notiz", "bemerkung", "hinweis"),
}
SPALTEN = {k: tuple(_norm(a) for a in v) for k, v in SPALTEN.items()}

VORLAGE_KOPF = ["Mieternummer", "Objekt", "Strasse", "PLZ", "Ort", "Einheit", "Art", "Flaeche",
                "Vorname", "Nachname", "Mitmieter", "E-Mail", "Telefon", "Mietbeginn", "Mietende",
                "Kaltmiete", "Nebenkosten", "Kaution", "Rueckstand", "IBAN Zahler", "IBAN Zahler 2",
                "Referenzen", "Notiz"]


@dataclass
class StammErgebnis:
    neu: int = 0
    geaendert: int = 0
    mietaenderungen: int = 0
    konten: int = 0
    fehler: list[str] = field(default_factory=list)

    def text(self) -> str:
        t = (f"{self.neu} Verträge neu, {self.geaendert} aktualisiert, {self.mietaenderungen} Mieten geändert, "
             f"{self.konten} Zahlerkonten hinterlegt")
        if self.fehler:
            t += f", {len(self.fehler)} Zeilen mit Fehlern:\n  " + "\n  ".join(self.fehler)
        return t


def _zeilen(text: str) -> list[dict[str, str]]:
    trenner = max(";,\t", key=lambda t: text[:3000].count(t))
    leser = csv.reader(io.StringIO(text), delimiter=trenner)
    kopf = [_norm(k) for k in next(leser, [])]
    index = {}
    for feld, aliase in SPALTEN.items():
        for a in aliase:
            if a in kopf and kopf.index(a) not in index.values():
                index[feld] = kopf.index(a)
                break
    aus = []
    for zeile in leser:
        if any(z.strip() for z in zeile):
            aus.append({f: zeile[i].strip() for f, i in index.items() if i < len(zeile)})
    return aus


def einlesen(db: Datenbank, pfad: Path) -> StammErgebnis:
    return einlesen_text(db, _dekodieren(Path(pfad).read_bytes()))


def einlesen_text(db: Datenbank, text: str) -> StammErgebnis:
    erg = StammErgebnis()
    for nr, z in enumerate(_zeilen(text), start=2):
        try:
            _zeile(db, z, erg)
        except ValueError as fehler:
            erg.fehler.append(f"Zeile {nr}: {fehler}")
    db.protokolliere("stammdaten", erg.text())
    db.con.commit()
    return erg


def _monat_von(text: str) -> str | None:
    """'01.10.2026' oder '2026-10' -> '2026-10'."""
    if geld.gueltiger_monat(text.strip()):
        return text.strip()
    d = geld.datum(text) if text else None
    return geld.monat(d) if d else None


def _zeile(db: Datenbank, z: dict[str, str], erg: StammErgebnis) -> None:
    nachname = z.get("nachname", "")
    if not nachname:
        raise ValueError("Nachname fehlt")
    vorname = z.get("vorname", "")
    if not vorname and " " in nachname and "," not in nachname:
        vorname, nachname = nachname.rsplit(" ", 1)
    elif "," in nachname and not vorname:
        nachname, vorname = (t.strip() for t in nachname.split(",", 1))
    for feld in ("iban1", "iban2"):                   # erst pruefen, dann schreiben
        if z.get(feld) and not iban_gueltig(z[feld]):
            raise ValueError(f"IBAN ungültig (Prüfziffer) - endet auf {iban_ende(z[feld])}")
    strasse = z.get("strasse", "")
    objekt = z.get("objekt") or strasse
    if not objekt:
        raise ValueError("Objekt oder Strasse fehlt")
    einheit = z.get("einheit") or "1"
    beginn = geld.datum(z.get("beginn"))
    if not beginn:
        raise ValueError(f"Mietbeginn fehlt/unlesbar ({z.get('beginn', '')!r})")
    ende = geld.datum(z.get("ende")) if z.get("ende") else None
    kalt, nk, gesamt = geld.cent(z.get("kalt")), geld.cent(z.get("nk")) or 0, geld.cent(z.get("gesamt"))
    if kalt is None:
        if gesamt is None:
            raise ValueError("weder Kaltmiete noch Gesamtmiete angegeben")
        kalt, nk = gesamt - nk, nk
    flaeche = geld.cent(z.get("flaeche"))

    objekt_id = db.objekt_id(objekt, strasse, z.get("plz", ""), z.get("ort", ""))
    einheit_id = db.einheit_id(objekt_id, einheit, z.get("art", ""), flaeche / 100 if flaeche else None)

    nummer = z.get("nummer", "").strip()
    alt = db.vertrag_nach_nummer(nummer) if nummer else None
    if alt is None and not nummer:
        # ohne Mieternummer: gleicher Vertrag = gleiche Einheit, gleicher Beginn, gleicher Nachname
        row = db.eins("SELECT v.nummer FROM vertraege v JOIN personen p ON p.id = v.person_id "
                      "WHERE v.einheit_id = ? AND v.beginn = ? AND p.nachname = ?",
                      (einheit_id, beginn.isoformat(), nachname))
        alt = db.vertrag_nach_nummer(row["nummer"]) if row else None
    werte = dict(mitmieter=z.get("mitmieter", ""), beginn=beginn.isoformat(),
                 ende=ende.isoformat() if ende else None, kaution_cent=geld.cent(z.get("kaution")),
                 startsaldo_cent=geld.cent(z.get("rueckstand")) or 0,
                 referenzen=z.get("referenzen", ""), notiz=z.get("notiz", ""))
    if alt:
        vertrag_id = alt["id"]
        db.con.execute("UPDATE personen SET vorname = ?, nachname = ?, email = COALESCE(NULLIF(?, ''), email), "
                       "telefon = COALESCE(NULLIF(?, ''), telefon) WHERE id = ?",
                       (vorname, nachname, z.get("email", ""), z.get("telefon", ""), alt["person_id"]))
        db.con.execute("UPDATE vertraege SET einheit_id = ?, mitmieter = ?, beginn = ?, ende = ?, "
                       "kaution_cent = ?, startsaldo_cent = ?, referenzen = ?, notiz = ? WHERE id = ?",
                       (einheit_id, *werte.values(), vertrag_id))
        erg.geaendert += 1
        ab = _monat_von(z.get("gueltig_ab", "")) or max(geld.monat(beginn), geld.monat(dt.date.today()))
    else:
        person_id = db.con.execute("INSERT INTO personen (vorname, nachname, email, telefon) VALUES (?, ?, ?, ?)",
                                   (vorname, nachname, z.get("email", ""), z.get("telefon", ""))).lastrowid
        vertrag_id = db.con.execute(
            "INSERT INTO vertraege (nummer, einheit_id, person_id, mitmieter, beginn, ende, kaution_cent, "
            "startsaldo_cent, referenzen, notiz) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (nummer or f"NEU-{einheit_id}-{beginn:%Y%m}", einheit_id, person_id, *werte.values())).lastrowid
        if not nummer:
            db.con.execute("UPDATE vertraege SET nummer = ? WHERE id = ?", (f"M-{vertrag_id:04d}", vertrag_id))
        erg.neu += 1
        ab = geld.monat(beginn)
    if db.setze_sollmiete(vertrag_id, ab, kalt, nk) and alt:
        erg.mietaenderungen += 1
    for feld, bezeichnung in (("iban1", "Mieter"), ("iban2", "Zahler 2")):
        roh = z.get(feld, "")
        if roh and db.zahler_merken(vertrag_id, db.schluessel.kennung(roh), iban_ende(roh), bezeichnung, "stammdaten"):
            erg.konten += 1


def vorlage() -> str:
    beispiel = ["M-0001", "Musterstr. 5", "Musterstraße 5", "12345", "Musterstadt", "WE 1", "Wohnung", "62,5",
                "Max", "Mustermann", "Erika Mustermann", "max@example.org", "", "01.03.2021", "",
                "520,00", "180,00", "1560,00", "0", iban_bauen("DE", "000000000000123456"), "", "", ""]
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";")
    w.writerow(VORLAGE_KOPF)
    w.writerow(beispiel)
    return puffer.getvalue()

