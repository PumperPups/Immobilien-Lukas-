"""Kommandozeile: python3 -m tinyhaus <befehl>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline, report, sources
from .config import Config
from .demand import outreach_message, render_ads
from .fmt import de_number, eur, sqm
from .models import (
    INTEREST_BOTH,
    INTEREST_BUY,
    INTEREST_NONE,
    INTEREST_RENT,
    Lead,
)
from .pricing import calculate
from .publish import available as publishers_available
from .storage import Storage

EXAMPLE_CONFIG = "config.example.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tinyhaus",
        description="Grundstuecke finden, bewerten und die Nachfrage nach Tiny Houses messen.",
    )
    parser.add_argument("--config", default="config.json", help="Pfad zur Konfiguration")
    parser.add_argument("--db", default=None, help="Pfad zur Datenbank (ueberschreibt Config)")
    sub = parser.add_subparsers(dest="befehl", required=True)

    sub.add_parser("init", help="Beispielkonfiguration und Datenbank anlegen")
    sub.add_parser("quellen", help="verfuegbare Quellen und Publisher anzeigen")

    p_scan = sub.add_parser("scan", help="Inserate einsammeln und bewerten")
    p_scan.add_argument("--quelle", action="append", help="nur diese Quelle (mehrfach moeglich)")
    p_scan.add_argument("--bericht", action="store_true", help="danach HTML-Bericht schreiben")

    p_list = sub.add_parser("liste", help="Shortlist der besten Grundstuecke")
    p_list.add_argument("--min", type=float, default=None, help="Mindest-Score")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--bericht", action="store_true", help="HTML-Bericht schreiben")

    p_show = sub.add_parser("zeige", help="Details und Kalkulation zu einem Grundstueck")
    p_show.add_argument("key", help="z.B. demo:demo-001")

    p_contact = sub.add_parser("kontakt", help="Anschreiben an den Verkaeufer erzeugen")
    p_contact.add_argument("key")
    p_contact.add_argument("--markieren", action="store_true", help="Status auf 'kontaktiert' setzen")

    p_status = sub.add_parser("status", help="Status eines Grundstuecks setzen")
    p_status.add_argument("key")
    p_status.add_argument("status", choices=["neu", "shortlist", "kontaktiert", "abgelehnt", "gekauft"])
    p_status.add_argument("--notiz", default=None)

    p_test = sub.add_parser("test", help="Nachfrage-Anzeigen (Miete + Kauf) erzeugen")
    p_test.add_argument("key", nargs="?", help="Grundstueck; ohne Angabe --auto nutzen")
    p_test.add_argument("--auto", type=int, metavar="N", help="N Tests fuer ungetestete Regionen")
    p_test.add_argument("--publisher", default="entwurf", choices=publishers_available())
    p_test.add_argument("--kanal", default="kleinanzeigen")

    p_pub = sub.add_parser("veroeffentlicht", help="Test als veroeffentlicht markieren")
    p_pub.add_argument("label", help="z.B. TH-34-01")

    p_lead = sub.add_parser("lead", help="Anfrage auf eine Anzeige erfassen")
    p_lead.add_argument("label")
    p_lead.add_argument(
        "--interesse",
        default=INTEREST_RENT,
        choices=[INTEREST_RENT, INTEREST_BUY, INTEREST_BOTH, INTEREST_NONE],
    )
    p_lead.add_argument("--miete", type=float, default=None,
                        help="Monatsmiete, die der Interessent zahlen wuerde")
    p_lead.add_argument("--kaufpreis", type=float, default=None,
                        help="Kaufpreis, den der Interessent zahlen wuerde")
    p_lead.add_argument("--name", default=None)
    p_lead.add_argument("--kontakt", default=None)
    p_lead.add_argument("--nachricht", default="")
    p_lead.add_argument("--qualifiziert", action="store_true", help="Budget und Zeitpunkt geklaert")

    sub.add_parser("nachfrage", help="gemessene Nachfrage je Region")

    p_neg = sub.add_parser("verhandlung", help="Maximalgebot fuer ein Grundstueck")
    p_neg.add_argument("key")

    sub.add_parser("bericht", help="HTML-Bericht schreiben")
    sub.add_parser("stand", help="Kennzahlen der Pipeline")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load(args.config)
    if args.db:
        cfg.db_path = args.db

    if args.befehl == "init":
        return cmd_init(cfg, args)
    if args.befehl == "quellen":
        print("Quellen:   " + ", ".join(sources.available()))
        print("Publisher: " + ", ".join(publishers_available()))
        return 0

    with Storage(cfg.db_path) as storage:
        handlers = {
            "scan": cmd_scan, "liste": cmd_list, "zeige": cmd_show,
            "kontakt": cmd_contact, "status": cmd_status, "test": cmd_test,
            "veroeffentlicht": cmd_published, "lead": cmd_lead,
            "nachfrage": cmd_demand, "verhandlung": cmd_negotiation,
            "bericht": cmd_report, "stand": cmd_stats,
        }
        return handlers[args.befehl](cfg, storage, args)


# --- Befehle -----------------------------------------------------------


def cmd_init(cfg: Config, args: argparse.Namespace) -> int:
    path = Path(args.config)
    if path.exists():
        print(f"{path} existiert bereits - nichts ueberschrieben.")
    else:
        cfg.save(path)
        print(f"Konfiguration angelegt: {path}")
    Storage(cfg.db_path).close()
    print(f"Datenbank bereit: {cfg.db_path}")
    print("Naechster Schritt: python3 -m tinyhaus scan --bericht")
    return 0


def cmd_scan(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    result = pipeline.scan(cfg, storage, args.quelle)
    print(
        f"{result.fetched} Inserate geholt | {result.new} neu | {result.updated} aktualisiert "
        f"| {result.duplicates} Doppler | {result.accepted} passend | {result.rejected} aussortiert"
    )
    for name, count in result.per_source.items():
        print(f"  Quelle {name}: {count}")
    if result.reject_reasons:
        print("Ausschlussgruende:")
        for reason, count in sorted(result.reject_reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>3}x {reason}")
    for name, error in result.errors.items():
        print(f"  FEHLER Quelle {name}: {error}", file=sys.stderr)

    candidates = pipeline.shortlist(cfg, storage)
    print()
    print(report.text_shortlist(candidates))
    if args.bericht:
        print(f"\nBericht: {report.write_report(cfg, storage, candidates)}")
    return 0 if not result.errors else 1


def cmd_list(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    if args.min is not None:
        cfg.shortlist_min_score = args.min
    candidates = pipeline.shortlist(cfg, storage, limit=args.limit)
    print(report.text_shortlist(candidates))
    if args.bericht:
        print(f"\nBericht: {report.write_report(cfg, storage, candidates)}")
    return 0


def cmd_show(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    plot = storage.get_plot(args.key)
    if plot is None:
        print(f"Unbekannt: {args.key}", file=sys.stderr)
        return 1
    score = storage.get_score(args.key)
    calc = calculate(plot, cfg, score.units if score and score.units else None)

    print(f"{plot.title}\n{plot.url}")
    print(f"Ort:        {plot.postal_code or '?'} {plot.city or '?'} ({plot.state or 'Bundesland unbekannt'})")
    print(f"Preis:      {eur(plot.price_eur)}  |  {sqm(plot.area_sqm)}  |  {eur(plot.price_per_sqm)}/m²")
    erschlossen = {True: "ja", False: "nein", None: "unbekannt"}[plot.developed]
    print(f"Baurecht:   {plot.land_type}  |  erschlossen: {erschlossen}  |  Anbieter: {plot.seller_type}")
    print(f"Status:     {plot.status}  |  gesehen: {plot.first_seen}")
    if score:
        print(f"\nScore {de_number(score.total, 1)}" + (f" (ABGELEHNT: {score.reject_reason})" if score.rejected else ""))
        for key, value in score.breakdown.items():
            print(f"  {key:<14} {de_number(value, 1):>6}")
        for reason in score.reasons:
            print(f"  - {reason}")
    print("\nKalkulation:")
    for line in calc.explain():
        print(f"  {line}")
    return 0


def cmd_contact(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    plot = storage.get_plot(args.key)
    if plot is None:
        print(f"Unbekannt: {args.key}", file=sys.stderr)
        return 1
    score = storage.get_score(args.key)
    calc = calculate(plot, cfg, score.units if score and score.units else None)
    print(outreach_message(plot, calc, cfg))
    if args.markieren:
        storage.set_status(plot.key, "kontaktiert")
        print("\n[Status auf 'kontaktiert' gesetzt]")
    return 0


def cmd_status(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    if not storage.set_status(args.key, args.status, args.notiz):
        print(f"Unbekannt: {args.key}", file=sys.stderr)
        return 1
    print(f"{args.key} -> {args.status}")
    return 0


def cmd_test(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    if args.auto:
        creations = pipeline.auto_tests(cfg, storage, args.auto, args.publisher)
        if not creations:
            print("Keine neuen Regionen zu testen - alle Shortlist-Regionen haben schon einen Test.")
            return 0
    elif args.key:
        try:
            creations = [pipeline.create_test(cfg, storage, args.key, args.publisher, args.kanal)]
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 1
    else:
        print("Bitte Grundstueck angeben oder --auto N nutzen.", file=sys.stderr)
        return 1

    for creation in creations:
        test = creation.test
        print(f"\n{test.label} | Region {test.region} | {test.city or '-'}")
        print(f"  Miete: {eur(test.rent_eur_month)}/Monat   Kauf: {eur(test.buy_price_eur)}")
        for variant, ad in creation.ads.items():
            print(f"  {variant:<6} {ad.title}")
        print(f"  {creation.message}")
    print("\nNach dem Einstellen: python3 -m tinyhaus veroeffentlicht <LABEL>")
    return 0


def cmd_published(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    try:
        test = pipeline.mark_published(storage, args.label)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{test.label} ist live seit {test.published_at}. Anfragen erfassen mit:")
    print(f"  python3 -m tinyhaus lead {test.label} --interesse miete --miete 780")
    return 0


def cmd_lead(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    lead = Lead(
        label=args.label, interest=args.interesse, name=args.name,
        contact=args.kontakt, message=args.nachricht, accepted_rent=args.miete,
        accepted_price=args.kaufpreis, qualified=args.qualifiziert,
    )
    try:
        lead_id, test = pipeline.record_lead(storage, lead)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 1
    signal = storage.demand_signal(test.region)
    print(f"Lead #{lead_id} erfasst ({lead.interest}) fuer {test.label}.")
    print(
        f"Region {signal.region}: {signal.leads} Anfragen "
        f"({signal.rent_leads} Miete / {signal.buy_leads} Kauf), "
        f"{signal.qualified_leads} qualifiziert, Index {de_number(signal.index, 2)}"
    )
    count = pipeline.rescore(cfg, storage)
    print(f"{count} Grundstuecke mit der neuen Nachfrage neu bewertet.")
    return 0


def cmd_demand(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    signals = storage.all_demand_signals()
    if not signals:
        print("Noch keine Nachfrage-Tests. Erzeugen mit: python3 -m tinyhaus test --auto 3")
        return 0
    print(f"{'Region':<8}{'Tests':>6}{'Leads':>7}{'Miete':>7}{'Kauf':>6}{'qual.':>7}"
          f"{'Ø Miete':>12}{'Ø Kaufpreis':>14}{'Index':>8}")
    print("-" * 75)
    for region, s in sorted(signals.items(), key=lambda kv: -kv[1].index):
        print(
            f"{region:<8}{s.tests:>6}{s.leads:>7}{s.rent_leads:>7}{s.buy_leads:>6}"
            f"{s.qualified_leads:>7}{eur(s.avg_accepted_rent):>12}"
            f"{eur(s.avg_accepted_price):>14}{de_number(s.index, 2):>8}"
        )
    return 0


def cmd_negotiation(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    try:
        result = pipeline.negotiation(cfg, storage, args.key)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{result.plot.title}")
    print(f"  Angebotspreis:   {eur(result.asking_price)}")
    print(
        "  Zahlungsbereitschaft: "
        + (f"{eur(result.observed_rent)}/Monat (gemessen)" if result.observed_rent
           else "noch nicht gemessen - Kalkulationsmiete verwendet")
    )
    print(f"  Maximalgebot:    {eur(result.max_bid)}")
    print(f"  {result.verdict}")
    return 0


def cmd_report(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    path = report.write_report(cfg, storage, pipeline.shortlist(cfg, storage, limit=50))
    print(f"Bericht: {path}")
    return 0


def cmd_stats(cfg: Config, storage: Storage, args: argparse.Namespace) -> int:
    for label, value in storage.stats().items():
        print(f"{label:<20} {value:>6}")
    return 0
