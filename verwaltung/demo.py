"""Erfundene Demo-Daten: ~250 Einheiten, Max Mustermann & Co., drei Monate Bank.

Damit laesst sich alles ausprobieren und weiterentwickeln, ohne dass ein
einziger echter Mieter im Spiel ist. Die Kontoauszuege enthalten absichtlich
alles, was im echten Leben vorkommt:

  * puenktliche Zahler, manche schon am 28. des Vormonats
  * Verspaetete, Teilzahler, Mieter mit Rueckstand, die spaeter doppelt zahlen
  * Jobcenter als Sammelzahler (KdU), teils mit Restzahlung des Mieters
  * Zahlung von einem fremden Konto (Eltern) mit Namen im Zweck
  * leerer oder nichtssagender Verwendungszweck
  * Kaution eines neuen Mieters, Erstattung der Stadtwerke, Zinsen
  * Abbuchungen (Versicherung, Hausmeister), die ignoriert werden
  * zwei Konten: Sparkasse als CSV, Volksbank als CAMT-XML

Alle IBANs haben die Bankleitzahl 00000000 - die gibt es nicht.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import geld
from .anonym import NACHNAMEN as MUSTER_NACHNAMEN
from .anonym import VORNAMEN
from .schutz import DEMO_ORDNER, iban_bauen

NACHNAMEN = MUSTER_NACHNAMEN + ["Müsterle", "Größmuster", "Übermuster", "Schätzmann", "Beispielová",
                                "Testoğlu", "Probst-Muster", "von Beispiel"]
STRASSEN = ["Musterstraße", "Beispielweg", "Probeallee", "Testring", "Vorlagengasse", "Platzhalterstraße",
            "Schablonenweg", "Entwurfstraße", "Modellallee", "Exempelring"]
ORTE = [("12345", "Musterstadt"), ("12347", "Musterstadt"), ("23456", "Beispielhausen")]
KONTO_SPARKASSE = iban_bauen("DE", "00000000" + "0000100001")
KONTO_VOLKSBANK = iban_bauen("DE", "00000000" + "0000200002")
JOBCENTER_IBAN = iban_bauen("DE", "00000000" + "0000999999")


def _iban(r: random.Random) -> str:
    return iban_bauen("DE", "00000000" + f"{r.randrange(10**9, 10**10):010d}")


@dataclass
class DemoVertrag:
    nummer: str
    objekt: str
    strasse: str
    plz: str
    ort: str
    einheit: str
    art: str
    flaeche: float
    vorname: str
    nachname: str
    beginn: dt.date
    ende: dt.date | None
    kalt: int
    nk: int
    iban: str
    iban_bekannt: bool
    typ: str
    konto: str
    bg_nummer: str = ""
    mitmieter: str = ""
    verwandte_iban: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def soll(self) -> int:
        return self.kalt + self.nk


def _vertraege(r: random.Random, monate: list[str]) -> list[DemoVertrag]:
    namen = [(v, n) for n in NACHNAMEN for v in VORNAMEN]
    r.shuffle(namen)
    namen.insert(0, ("Max", "Mustermann"))
    namen.insert(5, ("Moritz", "Mustermann"))          # zwei Mustermaenner: Namensgleichheit
    letzter = geld.erster(monate[-1])
    aus: list[DemoVertrag] = []
    nr = 0
    objekt_nr = 0
    while len(aus) < 250:
        objekt_nr += 1
        strasse = f"{STRASSEN[objekt_nr % len(STRASSEN)]} {objekt_nr // len(STRASSEN) * 2 + 1 + objekt_nr % 3}"
        plz, ort = ORTE[objekt_nr % len(ORTE)]
        kuerzel = strasse.replace("straße", "str.")
        konto = KONTO_VOLKSBANK if objekt_nr % 5 == 0 else KONTO_SPARKASSE
        einheiten = r.choice([1, 1, 2, 3, 4, 6, 6, 8, 10, 12])
        for e in range(1, einheiten + 1):
            if r.random() < 0.06:
                continue                                # Leerstand
            garage = einheiten >= 6 and e == einheiten
            flaeche = 0.0 if garage else r.choice([38, 45, 52, 58, 64, 71, 78, 85, 96])
            kalt = 6000 if garage else int(flaeche * r.choice([7.5, 8, 8.5, 9, 9.5])) // 5 * 500
            nk = 0 if garage else int(flaeche * r.choice([2.2, 2.5, 2.8, 3.0])) // 5 * 500
            nr += 1
            vor, nach = namen[nr % len(namen)]
            beginn = dt.date(r.choice(range(2012, 2026)), r.randrange(1, 13), 1)
            ende = None
            wechsel = r.random()
            if wechsel < 0.03:
                ende = geld.letzter(monate[0])          # Auszug nach dem ersten Demo-Monat
            elif wechsel < 0.06:
                beginn = letzter                        # Einzug im letzten Demo-Monat
            elif wechsel < 0.08:
                beginn = geld.erster(monate[1])
            typ = r.choices(["puenktlich", "vormonat", "spaet", "teil", "saeumig", "jobcenter", "verwandt",
                             "ohne_zweck"], [52, 12, 9, 5, 4, 9, 3, 6])[0]
            v = DemoVertrag(
                nummer=f"M-{nr:04d}", objekt=kuerzel, strasse=strasse, plz=plz, ort=ort,
                einheit=f"Garage {e}" if garage else f"WE {e}", art="Stellplatz" if garage else "Wohnung",
                flaeche=flaeche, vorname=vor, nachname=nach, beginn=beginn, ende=ende, kalt=kalt, nk=nk,
                iban=_iban(r), iban_bekannt=r.random() < 0.7, typ="puenktlich" if garage else typ,
                konto=konto,
            )
            if r.random() < 0.15 and not garage:
                v.mitmieter = f"{r.choice(VORNAMEN)} {nach}"
            if v.typ == "jobcenter":
                v.bg_nummer = f"{r.randrange(10000, 99999)}BG{r.randrange(10**6, 10**7):07d}"
                v.extra["anteil"] = r.choice([1.0, 1.0, 0.8, 0.9])
            if v.typ == "verwandt":
                v.verwandte_iban = _iban(r)
            aus.append(v)
            if len(aus) >= 250:
                break
    return aus


def _zweck(r: random.Random, v: DemoVertrag, monat: str) -> str:
    kurz = geld.MONATSNAMEN[int(monat[5:7]) - 1]
    varianten = [
        f"Miete {kurz}", f"Miete {monat[5:7]}/{monat[:4]}", f"{v.nummer} Miete", f"Miete {v.strasse} {v.einheit}",
        f"{v.nachname} Miete", "Dauerauftrag Miete", "MIETE", f"Miete {kurz[:3]}. {v.vorname} {v.nachname}",
        f"Mietzahlung {v.einheit} {v.nachname}", f"Miete {v.nummer.replace('-', ' ')} {kurz}",
    ]
    return r.choice(varianten)


@dataclass
class Gutschrift:
    datum: dt.date
    betrag: int
    name: str
    iban: str
    zweck: str
    konto: str


def _buchungen(r: random.Random, vertraege: list[DemoVertrag], monate: list[str], bis: dt.date) -> list[Gutschrift]:
    aus: list[Gutschrift] = []

    def tag(monat: str, t: int) -> dt.date:
        return geld.erster(monat) + dt.timedelta(days=t - 1)

    for v in vertraege:
        rueckstand = 0
        for i, m in enumerate(monate):
            if v.beginn > geld.letzter(m) or (v.ende and v.ende < geld.erster(m)):
                continue
            name = f"{v.vorname} {v.nachname}"
            zweck = _zweck(r, v, m)
            if v.typ == "puenktlich":
                aus.append(Gutschrift(tag(m, r.randint(1, 3)), v.soll, name, v.iban, zweck, v.konto))
            elif v.typ == "vormonat":
                d = geld.erster(m) - dt.timedelta(days=r.randint(1, 4))
                aus.append(Gutschrift(d, v.soll, name, v.iban, zweck, v.konto))
            elif v.typ == "spaet":
                aus.append(Gutschrift(tag(m, r.randint(6, 16)), v.soll, name, v.iban, zweck, v.konto))
            elif v.typ == "ohne_zweck":
                aus.append(Gutschrift(tag(m, r.randint(1, 4)), v.soll, name, v.iban,
                                      r.choice(["", "Überweisung", "Danke"]), v.konto))
            elif v.typ == "teil":
                erst = v.soll // 2 // 100 * 100
                aus.append(Gutschrift(tag(m, 2), erst, name, v.iban, zweck, v.konto))
                if r.random() < 0.6:
                    aus.append(Gutschrift(tag(m, r.randint(12, 20)), v.soll - erst, name, v.iban,
                                          f"Rest {zweck}", v.konto))
            elif v.typ == "saeumig":
                if i == 1:
                    rueckstand += v.soll                 # mittlerer Monat faellt aus
                    continue
                betrag = v.soll + rueckstand
                rueckstand = 0
                aus.append(Gutschrift(tag(m, r.randint(3, 12)), betrag, name, v.iban,
                                      zweck if betrag == v.soll else f"Miete + Rückstand {v.nachname}", v.konto))
            elif v.typ == "jobcenter":
                kdu = round(v.soll * v.extra["anteil"]) // 100 * 100 if v.extra["anteil"] < 1 else v.soll
                d = geld.erster(m) - dt.timedelta(days=r.randint(0, 3))
                aus.append(Gutschrift(d, kdu, "Jobcenter Musterstadt", JOBCENTER_IBAN,
                                      f"KdU {v.bg_nummer} {v.nachname}, {v.vorname} {m[5:7]}.{m[:4]}", v.konto))
                if kdu < v.soll:
                    aus.append(Gutschrift(tag(m, r.randint(3, 8)), v.soll - kdu, name, v.iban,
                                          f"Restmiete {m[5:7]}/{m[2:4]}", v.konto))
            elif v.typ == "verwandt":
                aus.append(Gutschrift(tag(m, r.randint(1, 5)), v.soll, f"{r.choice(VORNAMEN)} {v.nachname}-Muster",
                                      v.verwandte_iban, f"Miete für {v.vorname} {v.nachname}", v.konto))

        if v.beginn == geld.erster(monate[-1]):     # neuer Mieter: Kaution vor Einzug
            aus.append(Gutschrift(geld.erster(monate[-1]) - dt.timedelta(days=10), 3 * v.kalt,
                                  f"{v.vorname} {v.nachname}", v.iban, f"Kaution {v.einheit} {v.strasse}", v.konto))

    # was sonst noch aufs Konto kommt
    for m in monate:
        aus.append(Gutschrift(tag(m, 14), r.randrange(3000, 25000), "Stadtwerke Musterstadt GmbH", _iban(r),
                              "Erstattung Abrechnung Allgemeinstrom", KONTO_SPARKASSE))
        aus.append(Gutschrift(geld.letzter(m), r.randrange(100, 900), "Sparkasse Musterstadt", "",
                              "Zinsen", KONTO_SPARKASSE))
    doppelt = next(v for v in vertraege if v.typ == "puenktlich" and v.konto == KONTO_SPARKASSE)
    aus.append(Gutschrift(tag(monate[-1], 2), doppelt.soll, f"{doppelt.vorname} {doppelt.nachname}",
                          doppelt.iban, "Miete", doppelt.konto))  # versehentlich doppelt ueberwiesen
    return [g for g in aus if g.datum <= bis]


# ------------------------------------------------------------------ Dateien

def _sparkasse_csv(buchungen: list[Gutschrift], abbuchungen: list[Gutschrift]) -> bytes:
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(["Auftragskonto", "Buchungstag", "Valutadatum", "Buchungstext", "Verwendungszweck",
                "Glaeubiger ID", "Mandatsreferenz", "Kundenreferenz (End-to-End)", "Sammlerreferenz",
                "Lastschrift Ursprungsbetrag", "Auslagenersatz Ruecklastschrift", "Beguenstigter/Zahlungspflichtiger",
                "Kontonummer/IBAN", "BIC (SWIFT-Code)", "Betrag", "Waehrung", "Info"])
    alle = sorted(buchungen + abbuchungen, key=lambda g: g.datum, reverse=True)
    for g in alle:
        w.writerow([g.konto, g.datum.strftime("%d.%m.%y"), g.datum.strftime("%d.%m.%y"),
                    "GUTSCHR. UEBERWEISUNG" if g.betrag > 0 else "FOLGELASTSCHRIFT", g.zweck, "", "",
                    "NOTPROVIDED", "", "", "", g.name, g.iban, "XXXXDEXXXXX" if g.iban else "",
                    geld.eur(g.betrag, False).replace(".", ""), "EUR", "Umsatz gebucht"])
    return puffer.getvalue().encode("cp1252", errors="replace")


def _camt(buchungen: list[Gutschrift], konto: str, von: dt.date, bis: dt.date) -> bytes:
    from xml.sax.saxutils import escape as e
    teile = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08">',
        "<BkToCstmrStmt><GrpHdr><MsgId>DEMO</MsgId><CreDtTm>" + bis.isoformat() + "T08:00:00</CreDtTm></GrpHdr>",
        f"<Stmt><Id>DEMO-{bis:%Y%m}</Id><FrToDt><FrDtTm>{von}T00:00:00</FrDtTm><ToDtTm>{bis}T23:59:59</ToDtTm>"
        f"</FrToDt><Acct><Id><IBAN>{konto}</IBAN></Id><Ccy>EUR</Ccy></Acct>",
    ]
    for g in sorted(buchungen, key=lambda g: g.datum):
        art = "CRDT" if g.betrag > 0 else "DBIT"
        seite = "Dbtr" if g.betrag > 0 else "Cdtr"
        betrag = f"{abs(g.betrag) / 100:.2f}"
        teile.append(
            f'<Ntry><Amt Ccy="EUR">{betrag}</Amt><CdtDbtInd>{art}</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts>'
            f"<BookgDt><Dt>{g.datum}</Dt></BookgDt><ValDt><Dt>{g.datum}</Dt></ValDt>"
            f"<NtryDtls><TxDtls><RltdPties><{seite}><Pty><Nm>{e(g.name)}</Nm></Pty></{seite}>"
            + (f"<{seite}Acct><Id><IBAN>{g.iban}</IBAN></Id></{seite}Acct>" if g.iban else "")
            + f"</RltdPties><RmtInf><Ustrd>{e(g.zweck)}</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>")
    teile.append("</Stmt></BkToCstmrStmt></Document>")
    return "\n".join(teile).encode("utf-8")


def _stammdaten_csv(vertraege: list[DemoVertrag]) -> str:
    from .stammdaten import VORLAGE_KOPF
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", lineterminator="\n")
    w.writerow(VORLAGE_KOPF)
    for v in vertraege:
        w.writerow([v.nummer, v.objekt, v.strasse, v.plz, v.ort, v.einheit, v.art,
                    str(v.flaeche).replace(".", ",") if v.flaeche else "", v.vorname, v.nachname, v.mitmieter,
                    "", "", v.beginn.strftime("%d.%m.%Y"), v.ende.strftime("%d.%m.%Y") if v.ende else "",
                    geld.eur(v.kalt, False), geld.eur(v.nk, False), geld.eur(3 * v.kalt, False),
                    "", v.iban if v.iban_bekannt else "", JOBCENTER_IBAN if v.typ == "jobcenter" and v.iban_bekannt else "",
                    v.bg_nummer if v.bg_nummer and v.iban_bekannt else "", ""])
    return puffer.getvalue()


def erzeugen(ordner: Path = DEMO_ORDNER, heute: dt.date | None = None, seed: int = 7) -> dict:
    """Legt den Demo-Ordner neu an. Loescht nur einen Ordner, der als Demo markiert ist."""
    heute = heute or dt.date.today()
    ordner = Path(ordner)
    if ordner.exists():
        if not (ordner / ".demo").exists():
            raise RuntimeError(f"{ordner} ist kein Demo-Ordner - wird nicht angefasst.")
        shutil.rmtree(ordner)
    (ordner / "bank" / "eingang").mkdir(parents=True)
    (ordner / ".demo").write_text("Erfundene Demo-Daten. Darf jederzeit geloescht werden.\n", encoding="utf-8")

    r = random.Random(seed)
    aktuell = geld.monat(heute)
    monate = [geld.monat_plus(aktuell, -2), geld.monat_plus(aktuell, -1), aktuell]
    vertraege = _vertraege(r, monate)
    buchungen = _buchungen(r, vertraege, monate, heute)
    (ordner / "stammdaten_demo.csv").write_text(_stammdaten_csv(vertraege), encoding="utf-8")

    for m in monate:
        von = geld.erster(m) - dt.timedelta(days=5)
        bis = min(geld.letzter(m) - dt.timedelta(days=5), heute)
        if von > heute:
            continue
        im_zeitraum = [g for g in buchungen if von <= g.datum <= bis]
        abbuchungen = [Gutschrift(geld.erster(m) + dt.timedelta(days=d), -r.randrange(5000, 90000), n,
                                  _iban(r), z, KONTO_SPARKASSE)
                       for d, n, z in ((1, "Muster Versicherung AG", "Gebäudeversicherung"),
                                       (4, "Hausmeisterservice Beispiel", "Rechnung 4711"),
                                       (14, "Beispielbank", "Darlehen Tilgung"))]
        abbuchungen = [a for a in abbuchungen if a.datum <= heute]
        (ordner / "bank" / "eingang" / f"sparkasse_{m}.csv").write_bytes(
            _sparkasse_csv([g for g in im_zeitraum if g.konto == KONTO_SPARKASSE], abbuchungen))
        (ordner / "bank" / "eingang" / f"volksbank_{m}.xml").write_bytes(
            _camt([g for g in im_zeitraum if g.konto == KONTO_VOLKSBANK], KONTO_VOLKSBANK, von, bis))
    return {"vertraege": len(vertraege), "buchungen": len(buchungen), "monate": monate,
            "typen": {t: sum(1 for v in vertraege if v.typ == t) for t in sorted({v.typ for v in vertraege})}}
