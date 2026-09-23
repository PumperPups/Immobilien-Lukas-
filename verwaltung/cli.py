"""Kommandozeile: python -m verwaltung <befehl>

Der Alltag laeuft ueber die Browser-Oberflaeche (`web`). Die Befehle hier
sind fuer Einrichtung, Automatisierung (Aufgabenplanung) und Fehlersuche.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from . import abgleich, einlesen, geld, stammdaten, uebersicht
from .db import Datenbank
from .schutz import DEMO_ORDNER, daten_ordner, im_projekt


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="verwaltung", description="Hausverwaltung - Mieteingang und Stammdaten")
    p.add_argument("--daten", help="Datenordner (Standard: ~/Hausverwaltung-Daten oder $VERWALTUNG_DATEN)")
    p.add_argument("--demo", action="store_true", help="mit den erfundenen Demo-Daten arbeiten")
    sub = p.add_subparsers(dest="befehl", required=True)

    s = sub.add_parser("init", help="Datenordner und Datenbank anlegen")
    s.add_argument("--ab", help="Zahlungen ab diesem Monat fuehren, z.B. 2026-10")

    s = sub.add_parser("demo", help="erfundene Demo-Daten erzeugen und einlesen (daten_demo/)")
    s.add_argument("--nicht-einlesen", action="store_true", help="nur Dateien erzeugen")

    sub.add_parser("vorlage", help="Stammdaten-Vorlage (CSV) in den Datenordner schreiben")

    s = sub.add_parser("stammdaten", help="Objekte, Mieter und Vertraege aus CSV einlesen")
    s.add_argument("datei")

    s = sub.add_parser("import", help="Kontoauszuege einlesen und abgleichen")
    s.add_argument("dateien", nargs="*", help="ohne Angabe: alles aus <daten>/bank/eingang")

    sub.add_parser("abgleich", help="offene Gutschriften erneut abgleichen")

    s = sub.add_parser("monat", help="Monatsuebersicht: wer hat bezahlt?")
    s.add_argument("monat", nargs="?", help="z.B. 2026-10 (Standard: aktueller Monat)")
    s.add_argument("--offen", action="store_true", help="nur nicht bezahlte")
    s.add_argument("--csv", help="als CSV speichern (Datei im Datenordner/export)")

    s = sub.add_parser("pruefen", help="nicht zugeordnete Gutschriften mit Vorschlaegen")
    s.add_argument("--alle", action="store_true", help="auch Vorschlaege ausfuehrlich")

    s = sub.add_parser("zuordnen", help="Gutschrift von Hand einem Vertrag zuordnen")
    s.add_argument("buchung", type=int)
    s.add_argument("mieternummer")
    s.add_argument("--monat", action="append", help="Monat(e), sonst automatisch")
    s.add_argument("--nicht-merken", action="store_true", help="Zahlerkonto nicht merken")

    s = sub.add_parser("ignorieren", help="Gutschrift ist keine Miete")
    s.add_argument("buchung", type=int)
    s.add_argument("--grund", default="")
    s.add_argument("--immer", action="store_true", help="diesen Zahler kuenftig immer ignorieren")

    s = sub.add_parser("aufheben", help="Zuordnung einer Gutschrift rueckgaengig machen")
    s.add_argument("buchung", type=int)

    s = sub.add_parser("anonymisieren", help="Kontoauszug ohne echte Namen/IBANs kopieren (zum Weitergeben)")
    s.add_argument("datei")
    s.add_argument("--ziel")

    s = sub.add_parser("web", help="Oberflaeche im Browser starten")
    s.add_argument("--port", type=int, default=8780)
    s.add_argument("--kein-browser", action="store_true")
    return p


def _warnung_projektordner(ordner: Path) -> None:
    if im_projekt(ordner):
        print("ACHTUNG: Der Datenordner liegt im Projektordner. Echte Mieterdaten gehoeren\n"
              "         nach ausserhalb (Standard ~/Hausverwaltung-Daten) - siehe docs/DATENSCHUTZ.md.\n")


def main(argv: list[str] | None = None) -> int:
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="replace")
        except AttributeError:
            pass
    args = _parser().parse_args(argv)

    if args.befehl == "demo":
        from . import demo
        info = demo.erzeugen()
        print(f"Demo-Daten erzeugt in {DEMO_ORDNER}: {info['vertraege']} Verträge, "
              f"{info['buchungen']} Gutschriften, Monate {', '.join(info['monate'])}")
        print("Zahlertypen:", ", ".join(f"{k} {v}" for k, v in info["typen"].items()))
        if args.nicht_einlesen:
            return 0
        db = Datenbank(DEMO_ORDNER)
        print("Stammdaten:", stammdaten.einlesen(db, DEMO_ORDNER / "stammdaten_demo.csv").text())
        for erg in einlesen.eingang_verarbeiten(db):
            print(" ", erg.text())
        print("Abgleich:", abgleich.abgleichen(db).text())
        print("\nWeiter mit:  python -m verwaltung --demo web")
        return 0

    if args.befehl == "anonymisieren":
        from .anonym import anonymisieren
        ordner = daten_ordner(args.daten, args.demo)
        namen = []
        if (ordner / Datenbank.DATEI).exists():
            db = Datenbank(ordner)
            namen = [(r["vorname"] or "", r["nachname"]) for r in db.q("SELECT vorname, nachname FROM personen")]
        ziel = anonymisieren(Path(args.datei), Path(args.ziel) if args.ziel else None, namen)
        print(f"Pseudonymisierte Kopie: {ziel}")
        print("Bitte vor dem Weitergeben einmal selbst durchsehen.")
        return 0

    ordner = daten_ordner(args.daten, args.demo)
    _warnung_projektordner(ordner)
    db = Datenbank(ordner)

    if args.befehl == "init":
        einlesen.eingang_ordner(db)
        if args.ab:
            if not geld.gueltiger_monat(args.ab):
                print("--ab bitte als JJJJ-MM, z.B. 2026-10")
                return 2
            db.setze_meta("erfassung_ab", args.ab)
        print(f"Datenordner: {ordner}")
        print(f"  Datenbank:        {ordner / Datenbank.DATEI}")
        print(f"  Kontoauszuege ->  {ordner / 'bank' / 'eingang'}")
        print(f"  Schluessel:       {ordner / 'schluessel.key'}  (mit ins Backup!)")
        print(f"  Erfassung ab:     {db.erfassung_ab or 'erster eingelesener Monat'}")
        return 0

    if args.befehl == "vorlage":
        ziel = ordner / "stammdaten_vorlage.csv"
        ziel.write_text(stammdaten.vorlage(), encoding="utf-8-sig")
        print(f"Vorlage geschrieben: {ziel}")
        return 0

    if args.befehl == "stammdaten":
        print(stammdaten.einlesen(db, Path(args.datei)).text())
        return 0

    if args.befehl == "import":
        if args.dateien:
            ergebnisse = [einlesen.datei_einlesen(db, Path(d)) for d in args.dateien]
        else:
            ergebnisse = einlesen.eingang_verarbeiten(db)
            if not ergebnisse:
                print(f"Keine Dateien in {einlesen.eingang_ordner(db)}")
        for erg in ergebnisse:
            print(erg.text())
        print("Abgleich:", abgleich.abgleichen(db).text())
        return 1 if any(e.fehler for e in ergebnisse) else 0

    if args.befehl == "abgleich":
        print(abgleich.abgleichen(db).text())
        return 0

    if args.befehl == "monat":
        return _monat(db, args)

    if args.befehl == "pruefen":
        return _pruefen(db)

    if args.befehl == "zuordnen":
        from .miete import lade_vertraege
        v = next((x for x in lade_vertraege(db) if x.nummer.lower() == args.mieternummer.lower()), None)
        if not v or not db.buchung(args.buchung):
            print("Buchung oder Mieternummer unbekannt.")
            return 2
        teile = abgleich.zuordnen(db, args.buchung, v, args.monat, merken=not args.nicht_merken)
        print(f"Zugeordnet an {v.nummer} {v.name}: " + ", ".join(f"{m} {geld.eur(c)}" for m, c in teile))
        return 0

    if args.befehl == "ignorieren":
        abgleich.ignorieren(db, args.buchung, args.grund, args.immer)
        print("Ignoriert.")
        return 0

    if args.befehl == "aufheben":
        db.zuordnung_aufheben(args.buchung)
        print("Zuordnung aufgehoben - die Gutschrift steht wieder unter 'Zu prüfen'.")
        return 0

    if args.befehl == "web":
        from .web import starten
        return starten(db, args.port, browser=not args.kein_browser)
    return 0


def _monat(db: Datenbank, args) -> int:
    m = args.monat or geld.monat(dt.date.today())
    if not geld.gueltiger_monat(m):
        print("Monat bitte als JJJJ-MM")
        return 2
    mon = uebersicht.monat_berechnen(db, m)
    if args.csv:
        ziel = db.ordner / "export" / args.csv
        ziel.parent.mkdir(exist_ok=True)
        ziel.write_text(uebersicht.als_csv(mon, args.offen), encoding="utf-8-sig")
        print(f"Gespeichert: {ziel}")
        return 0
    print(f"{geld.monat_name(m)} - fällig am {geld.datum_de(mon.faellig)}")
    print(f"Soll {geld.eur(mon.summe('soll'))}  Ist {geld.eur(mon.summe('ist'))}  "
          f"({mon.quote:.0%})  |  " + ", ".join(f"{s} {mon.anzahl(s)}" for s in uebersicht.REIHENFOLGE))
    print()
    for z in mon.zeilen:
        if args.offen and z.status in (uebersicht.BEZAHLT, uebersicht.ZU_VIEL):
            continue
        v = z.vertrag
        print(f"{z.status:<11} {v.nummer:<8} {v.objekt[:22]:<22} {v.einheit[:9]:<9} {v.name[:26]:<26} "
              f"Soll {geld.eur(z.soll):>12}  Ist {geld.eur(z.ist):>12}  Rückstand {geld.eur(z.saldo):>12}")
    return 0


def _pruefen(db: Datenbank) -> int:
    offene = db.q("SELECT * FROM buchungen WHERE status = 'offen' ORDER BY datum")
    if not offene:
        print("Nichts zu prüfen.")
        return 0
    bewerter = abgleich.Bewerter(db)
    for b in offene:
        monate, woher = abgleich.monate_fuer(b["zweck"] or "", geld.datum(b["datum"]))
        print(f"#{b['id']}  {geld.datum_de(b['datum'])}  {geld.eur(b['betrag_cent']):>12}  {b['name']}"
              f"{'  (Konto …' + b['iban_ende'] + ')' if b['iban_ende'] else ''}")
        print(f"      Zweck: {b['zweck'] or '-'}   -> Monat {', '.join(monate)} ({woher})"
              + (f"   [{b['notiz']}]" if b["notiz"] else ""))
        for s in bewerter.bewerte(b, monate)[:3]:
            print(f"      ? {s.vertrag.nummer} {s.vertrag.name} ({s.vertrag.objekt}, {s.vertrag.einheit}) "
                  f"{s.punkte} P.: {', '.join(s.gruende)}")
    print(f"\n{len(offene)} offen. Zuordnen: python -m verwaltung zuordnen <#> <Mieternummer>")
    return 0
