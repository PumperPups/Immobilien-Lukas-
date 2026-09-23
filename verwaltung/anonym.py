"""Kontoauszug pseudonymisieren - bevor ihn irgendjemand sonst zu sehen bekommt.

Wofuer: Die Bank aendert ihr Exportformat, eine neue Bank kommt dazu, eine
Zahlung wird nicht erkannt. Dann braucht der Helfer (Mensch oder KI) eine
Beispieldatei - aber nie die echte. Dieses Modul erzeugt eine Kopie, in der

  * jeder Name durch einen erfundenen ersetzt ist (Max Mustermann, Erika
    Beispiel ...) - derselbe echte Name wird innerhalb der Datei immer zum
    selben erfundenen, damit Zusammenhaenge erhalten bleiben,
  * jede IBAN durch eine erfundene (Bankleitzahl 00000000) ersetzt ist,
  * im Verwendungszweck nur bekannte, unpersoenliche Woerter stehen bleiben
    (Miete, Oktober, KdU, WE ...); alles andere wird zu "xxxx",
  * lange Ziffernfolgen (Kundennummern, BG-Nummern) durch andere Ziffern
    gleicher Laenge ersetzt sind,
  * alle Spalten, die nicht gebraucht werden (BIC, Mandat, Glaeubiger-ID,
    Saldo, Kopfzeilen mit dem Kontoinhaber), geleert sind.

Die Zuordnung echt -> erfunden wird nirgends gespeichert und ist bei jedem
Lauf neu zufaellig. Aus der Kopie fuehrt kein Weg zurueck.

Betraege und Daten bleiben, weil ohne sie kein Abgleich zu pruefen ist.
"""

from __future__ import annotations

import csv
import io
import random
import re
import secrets
from pathlib import Path

from .bank import lese_datei
from .bank.csv_bank import _dekodieren, _kopf_finden, _norm, _trenner
from .schutz import falten, iban_bauen

VORNAMEN = ["Max", "Erika", "Hans", "Anna", "Paul", "Lena", "Karl", "Marie", "Felix", "Sophie", "Otto",
            "Clara", "Emil", "Greta", "Theo", "Ida", "Oskar", "Frieda", "Jakob", "Luise"]
NACHNAMEN = ["Mustermann", "Musterfrau", "Beispiel", "Probe", "Muster", "Testmann", "Vorlage", "Platzhalter",
             "Exempel", "Modell", "Schablone", "Entwurf", "Fiktiv", "Erfunden", "Namenlos", "Irgendwer",
             "Jedermann", "Niemand", "Dummy", "Attrappe"]

ORGANISATION = {"jobcenter", "bundesagentur", "agentur", "arbeit", "sozialamt", "wohngeld", "stadtwerke",
                "landkreis", "kreis", "stadt", "gemeinde", "gmbh", "ag", "ev", "kg", "versicherung",
                "finanzamt", "kasse", "bank", "sparkasse", "volksbank", "hausverwaltung", "rentenversicherung",
                "familienkasse", "amt", "sozialhilfe", "grundsicherung"}

ERLAUBT = {falten(w) for w in """
    miete mieten monatsmiete kaltmiete warmmiete grundmiete nebenkosten nk bk betriebskosten heizkosten
    vorauszahlung nachzahlung rueckstand rückstand kaution mietsicherheit gutschrift ueberweisung überweisung
    dauerauftrag sepa lastschrift einzug wohnung whg we app str strasse straße weg nr hausnr haus
    fuer für von und plus rest teilzahlung abschlag erstattung rate raten kdu bg leistungen unterkunft
    kosten der des die das zum zur im in am an mieter mieterin mieternummer mieternr kundennr vertrag
    vertragsnr einheit objekt garage stellplatz zinsen entgelt euro eur referenz end to notprovided
    datum svwz eref kref mref cred abwa iban bic januar februar märz maerz april mai juni juli august
    september oktober november dezember jan feb mrz apr jun jul aug sep sept okt nov dez monat monate
    mietzahlung zahlung bezahlt restzahlung teil anteil ok danke gruss gruß eg og dg links rechts mitte
    vorderhaus hinterhaus gutschr ueberw überw dauerauftr lastschr sammler echtzeit
    echtzeitueberweisung sepaueberweisung""".split()} | ORGANISATION

BEHALTEN = {"datum", "valuta", "betrag", "haben", "soll", "status"}
TEXTSPALTEN = {"zweck", "buchungstext"}
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")


class Pseudonymisierer:
    def __init__(self, bekannte_namen: list[tuple[str, str]] = ()):
        self._zufall = random.Random(secrets.randbits(64))
        self._personen: dict[str, str] = {}
        self._woerter: dict[str, str] = {}
        self._ibans: dict[str, str] = {}
        self._ziffern: dict[str, str] = {}
        for vor, nach in bekannte_namen:
            self.person(f"{vor} {nach}")

    # ------------------------------------------------------------ Bausteine
    def person(self, name: str) -> str:
        if not name.strip():
            return name
        schluessel = " ".join(falten(name).split())
        worte = re.findall(r"[^\W\d_]+", name)
        if set(map(falten, worte)) & ORGANISATION:
            return self.text(name)            # Jobcenter & Co.: Art bleibt erkennbar, Ort nicht
        if schluessel not in self._personen:
            n = len(self._personen)
            vor = VORNAMEN[n % len(VORNAMEN)]
            nach = NACHNAMEN[(n // len(VORNAMEN)) % len(NACHNAMEN)]
            if n >= len(VORNAMEN) * len(NACHNAMEN):
                nach += str(n)
            self._personen[schluessel] = f"{vor} {nach}"
            # "Mustermann, Max" -> Nachname vorn, sonst hinten
            if "," in name:
                nachteil, vorteil = name.split(",", 1)
            else:
                vorteil, _, nachteil = name.strip().rpartition(" ")
            for w in re.findall(r"[^\W\d_]+", nachteil):
                if len(w) >= 3:
                    self._woerter[falten(w)] = nach
            for w in re.findall(r"[^\W\d_]+", vorteil):
                if len(w) >= 3:
                    self._woerter.setdefault(falten(w), vor)
        return self._personen[schluessel]

    def iban(self, iban: str) -> str:
        s = re.sub(r"\s", "", iban or "")
        if not s:
            return ""
        if s not in self._ibans:
            konto = f"{self._zufall.randrange(10**9, 10**10):010d}"
            self._ibans[s] = iban_bauen("DE", "00000000" + konto)
        return self._ibans[s]

    def _zahl(self, ziffern: str) -> str:
        if ziffern not in self._ziffern:
            self._ziffern[ziffern] = "".join(str(self._zufall.randrange(10)) for _ in ziffern)
        return self._ziffern[ziffern]

    def text(self, text: str) -> str:
        if not text:
            return text
        text = _IBAN.sub(lambda m: self.iban(m.group(0)), text)

        def ersetze(m: re.Match) -> str:
            wort = m.group(0)
            if wort.isdigit():
                return self._zahl(wort) if len(wort) >= 5 else wort
            gefaltet = falten(wort)
            if gefaltet in self._woerter:
                return self._woerter[gefaltet]
            if gefaltet in ERLAUBT or len(wort) <= 2:
                return wort
            return "xxxx"

        return re.sub(r"\d+|[^\W\d_]+", ersetze, text)


# ------------------------------------------------------------------ Dateien

def _csv(daten: bytes, p: Pseudonymisierer) -> str:
    text = _dekodieren(daten)
    trenner = _trenner(text.splitlines())
    zeilen = list(csv.reader(io.StringIO(text), delimiter=trenner))
    gefunden = _kopf_finden(zeilen)
    if not gefunden:
        raise ValueError("Keine Kopfzeile gefunden - Datei wird nicht verarbeitet.")
    kopf_nr, sp = gefunden
    rolle_je_spalte = {i: feld for feld, i in sp.items()}

    # erst alle Namen einsammeln, damit sie auch im Zweck anderer Zeilen ersetzt werden
    for zeile in zeilen[kopf_nr + 1:]:
        for feld in ("name", "dkb_empfaenger"):
            if feld in sp and sp[feld] < len(zeile):
                p.person(zeile[sp[feld]])

    aus = io.StringIO()
    w = csv.writer(aus, delimiter=trenner, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    for zeile in zeilen[:kopf_nr]:                       # Vorspann: Kontoinhaber, IBAN, Zeitraum ...
        w.writerow([zeile[0]] + ["xxxx" if z.strip() else "" for z in zeile[1:]] if zeile else [])
    w.writerow(zeilen[kopf_nr])
    for zeile in zeilen[kopf_nr + 1:]:
        neu = []
        for i, wert in enumerate(zeile):
            rolle = rolle_je_spalte.get(i)
            spalte = _norm(zeilen[kopf_nr][i]) if i < len(zeilen[kopf_nr]) else ""
            if rolle in BEHALTEN or spalte in ("waehrung", "wahrung", "currency"):
                neu.append(wert)
            elif rolle in ("name", "dkb_empfaenger"):
                neu.append(p.person(wert))
            elif rolle in ("iban", "konto"):
                neu.append(p.iban(wert) if wert.strip() else "")
            elif rolle in TEXTSPALTEN:
                neu.append(p.text(wert))
            else:
                neu.append("")                               # alles andere: leeren
        w.writerow(neu)
    return aus.getvalue()


def _neutral(daten_pfad: Path, p: Pseudonymisierer) -> str:
    """CAMT & Co. -> einfache CSV im neutralen Format."""
    _, umsaetze = lese_datei(daten_pfad)
    for u in umsaetze:
        p.person(u.name)
    aus = io.StringIO()
    w = csv.writer(aus, delimiter=";", lineterminator="\n")
    w.writerow(["Buchungstag", "Betrag", "Name", "IBAN", "Verwendungszweck", "Auftragskonto"])
    for u in umsaetze:
        w.writerow([u.datum.strftime("%d.%m.%Y"), f"{u.betrag_cent / 100:.2f}".replace(".", ","),
                    p.person(u.name), p.iban(u.iban), p.text(u.zweck), p.iban(u.konto)])
    return aus.getvalue()


def anonymisieren(quelle: Path, ziel: Path | None = None,
                  bekannte_namen: list[tuple[str, str]] = ()) -> Path:
    quelle = Path(quelle)
    daten = quelle.read_bytes()
    p = Pseudonymisierer(bekannte_namen)
    kopf = daten[:2000].lstrip(b"\xef\xbb\xbf \r\n\t")
    if kopf.startswith(b"<"):
        inhalt = _neutral(quelle, p)
    else:
        inhalt = _csv(daten, p)
    ziel = Path(ziel) if ziel else quelle.with_name(quelle.stem + "_anonym.csv")
    ziel.write_text(inhalt, encoding="utf-8")
    return ziel

