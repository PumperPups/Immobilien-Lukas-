"""CSV-Exporte deutscher Banken.

Jede Bank baut ihre CSV anders: Sparkasse (CSV-CAMT), Volks-/Raiffeisenbank,
ING, DKB, Deutsche Bank, Commerzbank, Postbank ... Statt fuer jede Bank einen
eigenen Leser zu schreiben, wird die Kopfzeile gesucht (sie steht nicht
immer in Zeile 1) und jede Spalte ueber eine Liste bekannter Namen erkannt.

Kommt eine neue Bank dazu, die nicht erkannt wird: mit
`python -m verwaltung anonymisieren <datei>` eine Kopie ohne echte Namen
und IBANs erzeugen und die zum Nachbessern weitergeben - nie das Original.
"""

from __future__ import annotations

import csv
import io
import re

from .. import geld
from . import FormatFehler, Umsatz


def _norm(text: str) -> str:
    s = (text or "").strip().lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(alt, neu)
    return re.sub(r"[^a-z0-9]", "", s)


# Reihenfolge = Vorrang. Verglichen wird der Spaltenname ohne Sonderzeichen.
SPALTEN: dict[str, tuple[str, ...]] = {
    "datum": ("buchungstag", "buchungsdatum", "buchung", "datum", "buchungstagdatum", "date"),
    "valuta": ("valutadatum", "valuta", "wertstellung", "wertstellungsdatum", "wert"),
    "betrag": ("betrag", "betrageur", "betrag€", "umsatz", "betraginEUR", "amount"),
    "haben": ("haben", "gutschrift"),
    "soll": ("soll", "belastung"),
    "name": ("beguenstigterzahlungspflichtiger", "namezahlungsbeteiligter", "zahlungspflichtiger",
             "zahlungspflichtiger", "auftraggeberempfaenger", "beguenstigterauftraggeber",
             "auftraggeber", "empfaenger", "name", "zahlungsbeteiligter"),
    "iban": ("kontonummeriban", "ibanzahlungsbeteiligter", "iban", "gegenkontoiban", "kontonummer"),
    "zweck": ("verwendungszweck", "vwz", "zweck", "buchungsdetails"),
    "buchungstext": ("buchungstext", "umsatzart", "umsatztyp", "vorgang"),
    "konto": ("auftragskonto", "ibanauftragskonto", "ibanauftraggeberkonto", "eigeneskonto", "konto"),
    "dkb_empfaenger": ("zahlungsempfaengerin",),
    "status": ("status",),
}
SPALTEN = {k: tuple(_norm(n) for n in v) for k, v in SPALTEN.items()}


def _dekodieren(daten: bytes) -> str:
    for kodierung in ("utf-8-sig", "cp1252"):
        try:
            return daten.decode(kodierung)
        except UnicodeDecodeError:
            continue
    return daten.decode("latin-1")


def _trenner(zeilen: list[str]) -> str:
    probe = "\n".join(zeilen[:40])
    return max(";,\t", key=lambda t: probe.count(t))


def _kopf_finden(zeilen: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for nr, zeile in enumerate(zeilen[:40]):
        namen = [_norm(z) for z in zeile]
        zuordnung: dict[str, int] = {}
        for feld, aliase in SPALTEN.items():
            for alias in aliase:
                if alias in namen and namen.index(alias) not in zuordnung.values():
                    zuordnung[feld] = namen.index(alias)
                    break
        if "datum" in zuordnung and ("betrag" in zuordnung or "haben" in zuordnung):
            return nr, zuordnung
    return None


def lese(daten: bytes) -> tuple[str, list[Umsatz]]:
    text = _dekodieren(daten)
    rohzeilen = text.splitlines()
    trenner = _trenner(rohzeilen)
    zeilen = list(csv.reader(io.StringIO(text), delimiter=trenner))
    gefunden = _kopf_finden(zeilen)
    if not gefunden:
        raise FormatFehler("Keine Kopfzeile mit Buchungsdatum und Betrag gefunden - "
                           "ist das ein Umsatz-Export der Bank?")
    kopf_nr, sp = gefunden
    kopf = zeilen[kopf_nr]

    def wert(zeile: list[str], feld: str) -> str:
        i = sp.get(feld)
        return zeile[i].strip() if i is not None and i < len(zeile) else ""

    aus: list[Umsatz] = []
    for zeile in zeilen[kopf_nr + 1:]:
        if not any(z.strip() for z in zeile):
            continue
        datum = geld.datum(wert(zeile, "datum")) or geld.datum(wert(zeile, "valuta"))
        if datum is None:
            continue                                  # Summen- oder Fusszeile
        if wert(zeile, "status").lower() in ("vorgemerkt", "umsatz vorgemerkt"):
            continue
        betrag = geld.cent(wert(zeile, "betrag"))
        if betrag is None:                            # Deutsche Bank: getrennte Spalten Soll / Haben
            haben, soll = geld.cent(wert(zeile, "haben")), geld.cent(wert(zeile, "soll"))
            betrag = abs(haben) if haben else (-abs(soll) if soll else None)
        if betrag is None:
            continue
        zweck = wert(zeile, "zweck")
        if not zweck:                                 # Commerzbank: alles steht im Buchungstext
            zweck = wert(zeile, "buchungstext")
        name = wert(zeile, "name")
        if betrag < 0 and wert(zeile, "dkb_empfaenger"):
            name = wert(zeile, "dkb_empfaenger")      # DKB: zwei Namensspalten
        aus.append(Umsatz(datum=datum, betrag_cent=betrag, name=name, iban=wert(zeile, "iban"),
                          zweck=re.sub(r"\s+", " ", zweck), konto=wert(zeile, "konto"),
                          roh=dict(zip(kopf, zeile))))
    return f"CSV ({_bank_raten(sp, kopf)})", aus


def _bank_raten(sp: dict[str, int], kopf: list[str]) -> str:
    namen = {_norm(k) for k in kopf}
    if "beguenstigterzahlungspflichtiger" in namen:
        return "Sparkasse"
    if "namezahlungsbeteiligter" in namen:
        return "Volksbank/Raiffeisen"
    if "auftraggeberempfaenger" in namen:
        return "ING"
    if "zahlungspflichtiger" in namen and "zahlungsempfaengerin" in namen:
        return "DKB"
    if "haben" in sp:
        return "Deutsche Bank"
    if "ibanauftraggeberkonto" in namen:
        return "Commerzbank"
    return "allgemein"
