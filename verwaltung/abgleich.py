"""Abgleich: welche Gutschrift gehoert zu welchem Mieter und welchem Monat?

Jede offene Gutschrift wird gegen alle in Frage kommenden Vertraege
gepunktet. Die Punkte stehen im Klartext daneben, damit jede Entscheidung
nachvollziehbar ist:

    bekanntes Konto des Mieters        +60   (Sammelzahler wie Jobcenter: 0 - sagt nichts ueber den Mieter)
    Mieternummer / Referenz im Zweck   +60   (auch gelernte, z.B. die BG-Nummer beim Jobcenter)
    Nachname im Namen oder Zweck       +25   (Vorname zusaetzlich +20)
    Adresse im Zweck                   +10
    Betrag = Sollmiete                 +20   (genau 2 oder 3 Monatsmieten: +10)

Automatisch zugeordnet wird nur, wenn der Beste mindestens 45 Punkte hat
UND mindestens 20 Punkte vor dem Zweitbesten liegt. Alles andere landet
unter "Zu pruefen" - mit den besten Vorschlaegen, ein Klick genuegt.

Wird eine Zahlung sicher erkannt (auch ohne Konto), merkt sich das
Programm das Konto des Zahlers. Ab dem zweiten Monat laeuft der Grossteil
also ueber das bekannte Konto. Bei Sammelzahlern (Jobcenter, Sozialamt)
merkt es sich stattdessen die Kennung aus dem Zweck (BG-Nummer o. ae.).

Laeuft komplett lokal, ohne KI und ohne Internet.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from . import geld
from .db import Datenbank
from .miete import Vertrag, lade_vertraege, offen_im_monat
from .schutz import falten, woerter

AUTO_MINDESTENS = 45
AUTO_ABSTAND = 20
VORMONAT_AB_TAG = 25          # Zahlung ab dem 25. gilt fuer den Folgemonat

MONATSWOERTER = {
    "januar": 1, "februar": 2, "feb": 2, "marz": 3, "mrz": 3, "april": 4, "apr": 4, "mai": 5,
    "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9,
    "sept": 9, "oktober": 10, "okt": 10, "oct": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
}   # "jan" fehlt absichtlich: Jan ist auch ein Vorname
NICHT_AUTOMATISCH = ("kaution", "mietsicherheit")


@dataclass
class Vorschlag:
    vertrag: Vertrag
    punkte: int
    gruende: list[str] = field(default_factory=list)
    ohne_konto: int = 0            # Punkte ohne das bekannte Konto (fuers Lernen)
    signal: bool = True            # mehr als nur ein passender Betrag


@dataclass
class Ergebnis:
    automatisch: int = 0
    zu_pruefen: int = 0
    ignoriert: int = 0
    gelernt: int = 0

    def text(self) -> str:
        return (f"{self.automatisch} automatisch zugeordnet, {self.zu_pruefen} zu prüfen, "
                f"{self.ignoriert} ignoriert, {self.gelernt} Zahlerkonten neu gelernt")


# ------------------------------------------------------------------ Monat

def _jahr_fuer(monat: int, bezug: dt.date) -> int:
    """Das Jahr, in dem dieser Monat dem Buchungsdatum am naechsten liegt."""
    return min((bezug.year - 1, bezug.year, bezug.year + 1),
               key=lambda j: abs((j * 12 + monat) - (bezug.year * 12 + bezug.month)))


def monate_aus_zweck(zweck: str, bezug: dt.date) -> list[str]:
    text = falten(zweck)
    gefunden: set[str] = set()
    for tag, mon, jahr in re.findall(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(20\d{2}|\d{2})(?!\d)", text):
        gefunden.add((int(mon), int(jahr)))
        text = text.replace(f"{tag}.{mon}.{jahr}", " ")
    for mon, jahr in re.findall(r"(?<![\d.,])(0?[1-9]|1[0-2])\s*[./-]\s*(20\d{2}|\d{2})(?![\d.,])", text):
        gefunden.add((int(mon), int(jahr)))
    for wort in woerter(text):
        if wort in MONATSWOERTER:
            gefunden.add((MONATSWOERTER[wort], None))
    aus = set()
    for mon, jahr in gefunden:
        if not 1 <= mon <= 12:
            continue
        if jahr is None:
            jahr = _jahr_fuer(mon, bezug)
        elif jahr < 100:
            jahr += 2000
        if abs((jahr * 12 + mon) - (bezug.year * 12 + bezug.month)) <= 12:
            aus.add(f"{jahr:04d}-{mon:02d}")
    return sorted(aus)


def monate_fuer(zweck: str, datum: dt.date) -> tuple[list[str], str]:
    """(Monate, woher). Aus dem Zweck, sonst aus dem Datum."""
    genannt = monate_aus_zweck(zweck, datum)
    if genannt:
        return genannt, "laut Verwendungszweck"
    if datum.day >= VORMONAT_AB_TAG:
        return [geld.monat_plus(geld.monat(datum), 1)], "Zahlung Ende Vormonat"
    return [geld.monat(datum)], "laut Buchungsdatum"


# ------------------------------------------------------------------ Punkte

class Bewerter:
    def __init__(self, db: Datenbank, vertraege: list[Vertrag] | None = None):
        self.db = db
        self.vertraege = vertraege if vertraege is not None else lade_vertraege(db)
        self.zahler = db.zahler_je_kennung()
        self._muster = {v.id: v.muster() for v in self.vertraege}
        self._namen = {v.id: v.namen_woerter() for v in self.vertraege}
        self._adresse = {v.id: v.adresse() for v in self.vertraege}

    def kandidaten(self, monate: list[str]) -> list[Vertrag]:
        frueh = geld.monat_plus(monate[0], -6)          # Nachzahlung nach Auszug
        spaet = geld.monat_plus(monate[-1], 1)          # Einzug naechsten Monat
        return [v for v in self.vertraege
                if v.erster_monat <= spaet and (v.letzter_monat is None or v.letzter_monat >= frueh)]

    def bewerte(self, buchung, monate: list[str]) -> list[Vorschlag]:
        zweck_text = falten(buchung["zweck"])
        zweck_woerter = set(woerter(buchung["zweck"]))
        namen_woerter = set(woerter(buchung["name"])) | zweck_woerter
        # Bank ersetzt Zeichen ausserhalb ihres Zeichensatzes durch "?" (Testoğlu -> Testo?lu)
        for text in (buchung["name"], buchung["zweck"]):
            if text and "?" in text:
                namen_woerter |= set(woerter(text.replace("?", "")))
        kennung = buchung["iban_kennung"]
        konto_vertraege = self.zahler.get(kennung, set()) if kennung else set()
        betrag = buchung["betrag_cent"]

        vorschlaege = []
        for v in self.kandidaten(monate):
            punkte, gruende, konto_punkte = 0, [], 0
            if v.id in konto_vertraege:
                if len(konto_vertraege) == 1:
                    konto_punkte = 60
                    gruende.append(f"bekanntes Konto …{buchung['iban_ende']}")
                else:
                    gruende.append(f"Sammelzahler-Konto ({len(konto_vertraege)} Verträge)")
            if any(m.search(zweck_text) for m in self._muster[v.id]):
                punkte += 60
                gruende.append("Mieternummer/Referenz im Zweck")
            nach, vor = self._namen[v.id]
            if nach & namen_woerter:
                punkte += 25
                gruende.append("Nachname")
                if vor & namen_woerter:
                    punkte += 20
                    gruende.append("Vorname")
            adr = self._adresse[v.id]
            if adr and adr[0] in zweck_text and adr[1] in zweck_woerter:
                punkte += 10
                gruende.append("Adresse")
            soll = v.soll(monate[0]) or v.soll(geld.monat_plus(monate[0], -1))
            signal = punkte + konto_punkte
            if soll and betrag == soll * len(monate):
                punkte += 20
                gruende.append("Betrag = Sollmiete")
            elif soll and betrag in (2 * soll, 3 * soll):
                punkte += 10
                gruende.append(f"Betrag = {betrag // soll} Monatsmieten")
            if signal == 0 and punkte == 0:
                continue
            vorschlaege.append(Vorschlag(v, punkte + konto_punkte, gruende, ohne_konto=punkte, signal=signal > 0))
        vorschlaege.sort(key=lambda s: (-s.punkte, s.vertrag.nummer))
        # passt nur der Betrag, ist das bei vielen gleich hohen Mieten wertlos
        mit_signal = [s for s in vorschlaege if s.signal]
        nur_betrag = [s for s in vorschlaege if not s.signal]
        return mit_signal + (nur_betrag if len(nur_betrag) <= 3 else [])

    @staticmethod
    def sicher(vorschlaege: list[Vorschlag]) -> bool:
        if not vorschlaege or vorschlaege[0].punkte < AUTO_MINDESTENS:
            return False
        return len(vorschlaege) == 1 or vorschlaege[0].punkte - vorschlaege[1].punkte >= AUTO_ABSTAND


# ------------------------------------------------------------------ Verteilen

def verteilen(v: Vertrag, monate: list[str], betrag: int, ist: dict[tuple[int, str], int],
              ab: str) -> list[tuple[str, int]]:
    """Betrag auf Monate verteilen: erst die genannten, dann aeltere offene
    Monate (aeltester zuerst), ein Rest bleibt als Ueberzahlung im letzten."""
    teile: dict[str, int] = {}
    rest = betrag

    def nimm(m: str) -> None:
        nonlocal rest
        offen = offen_im_monat(v, m, ist) - teile.get(m, 0)
        menge = min(rest, max(offen, 0))
        if menge > 0:
            teile[m] = teile.get(m, 0) + menge
            rest -= menge

    for m in monate:
        nimm(m)
    start = max(ab, v.erster_monat)
    for m in geld.monate(start, geld.monat_plus(monate[0], -1)):
        if rest <= 0:
            break
        nimm(m)
    if rest > 0:
        ziel = monate[-1]
        teile[ziel] = teile.get(ziel, 0) + rest
    return sorted(teile.items())


# ------------------------------------------------------------------ Ablauf

def zuordnen(db: Datenbank, buchung_id: int, vertrag: Vertrag, monate: list[str] | None = None,
             art: str = "hand", grund: str = "", merken: bool = False,
             ist: dict[tuple[int, str], int] | None = None) -> list[tuple[str, int]]:
    b = db.buchung(buchung_id)
    if monate is None:
        monate, _ = monate_fuer(b["zweck"] or "", geld.datum(b["datum"]))
    if ist is None:
        ist = db.ist_je_vertrag_monat()
    # eigene alte Zuordnung dieser Buchung nicht doppelt zaehlen
    for alt in db.q("SELECT * FROM zahlungen WHERE buchung_id = ?", (buchung_id,)):
        schluessel = (alt["vertrag_id"], alt["monat"])
        ist[schluessel] = ist.get(schluessel, 0) - alt["betrag_cent"]
    teile = verteilen(v=vertrag, monate=monate, betrag=b["betrag_cent"], ist=ist, ab=db.monat_seit())
    db.zahlung_buchen(buchung_id, [(vertrag.id, m, c) for m, c in teile], art, grund)
    for m, c in teile:
        ist[(vertrag.id, m)] = ist.get((vertrag.id, m), 0) + c
    if merken and b["iban_kennung"]:
        db.zahler_merken(vertrag.id, b["iban_kennung"], b["iban_ende"], b["name"] or "", "hand")
    if merken or art == "auto":
        referenz_lernen(db, vertrag, b)
    if art == "hand":
        db.protokolliere("zuordnen", f"Buchung {buchung_id} -> {vertrag.nummer} {teile}")
    db.con.commit()
    return teile


def sammelzahler(db: Datenbank, kennung: str | None) -> bool:
    if not kennung:
        return False
    row = db.eins("SELECT COUNT(*) AS n FROM zahler WHERE iban_kennung = ?", (kennung,))
    return row["n"] > 1


def referenz_lernen(db: Datenbank, vertrag: Vertrag, buchung) -> str | None:
    """Zahlt ein Sammelzahler (Jobcenter), steht der Mieter meist nur ueber eine
    Kennung im Zweck fest ("KdU 12345BG0012345 ..."). Die wird sich gemerkt.
    Nur Kennungen aus Buchstaben UND mind. 5 Ziffern - keine Datumsangaben."""
    if not sammelzahler(db, buchung["iban_kennung"]):
        return None
    for wort in re.findall(r"[A-Za-z0-9]{8,}", buchung["zweck"] or ""):
        if sum(z.isdigit() for z in wort) >= 5 and any(z.isalpha() for z in wort):
            if wort.lower() in (r.lower() for r in vertrag.referenzen):
                return None
            vertrag.referenzen.append(wort)
            db.con.execute("UPDATE vertraege SET referenzen = ? WHERE id = ?",
                           ("; ".join(vertrag.referenzen), vertrag.id))
            return wort
    return None


def ignorieren(db: Datenbank, buchung_id: int, grund: str = "", zahler_immer: bool = False) -> None:
    b = db.buchung(buchung_id)
    db.con.execute("DELETE FROM zahlungen WHERE buchung_id = ?", (buchung_id,))
    db.con.execute("UPDATE buchungen SET status = 'ignoriert', notiz = ? WHERE id = ?",
                   (grund or "keine Miete", buchung_id))
    if zahler_immer and b["iban_kennung"]:
        db.con.execute("INSERT OR IGNORE INTO zahler_ignoriert VALUES (?, ?, ?, ?)",
                       (b["iban_kennung"], b["iban_ende"], b["name"], dt.date.today().isoformat()))
    db.protokolliere("ignorieren", f"Buchung {buchung_id}: {grund}")
    db.con.commit()


def abgleichen(db: Datenbank) -> Ergebnis:
    """Alle offenen Gutschriften durchgehen, sichere Faelle zuordnen."""
    erg = Ergebnis()
    bewerter = Bewerter(db)
    ignoriert = db.ignorierte_zahler()
    ist = db.ist_je_vertrag_monat()
    offene = db.q("SELECT * FROM buchungen WHERE status = 'offen' ORDER BY datum, id")
    for b in offene:
        if b["iban_kennung"] and b["iban_kennung"] in ignoriert:
            db.con.execute("UPDATE buchungen SET status = 'ignoriert', notiz = 'Zahler wird ignoriert' "
                           "WHERE id = ?", (b["id"],))
            erg.ignoriert += 1
            continue
        datum = geld.datum(b["datum"])
        monate, woher = monate_fuer(b["zweck"] or "", datum)
        vorschlaege = bewerter.bewerte(b, monate)
        kaution = any(w in falten(b["zweck"]) for w in NICHT_AUTOMATISCH)
        if kaution or not bewerter.sicher(vorschlaege):
            if kaution:
                db.con.execute("UPDATE buchungen SET notiz = 'Kaution? Bitte von Hand prüfen' WHERE id = ?",
                               (b["id"],))
            erg.zu_pruefen += 1
            continue
        bester = vorschlaege[0]
        zuordnen(db, b["id"], bester.vertrag, monate, art="auto",
                 grund=", ".join(bester.gruende) + f" ({bester.punkte} P.; Monat {woher})", ist=ist)
        erg.automatisch += 1
        if b["iban_kennung"] and bester.ohne_konto >= AUTO_MINDESTENS:
            if db.zahler_merken(bester.vertrag.id, b["iban_kennung"], b["iban_ende"], b["name"] or "", "gelernt"):
                erg.gelernt += 1
                bewerter.zahler = db.zahler_je_kennung()
    db.protokolliere("abgleich", erg.text())
    db.con.commit()
    return erg
