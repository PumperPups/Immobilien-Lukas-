"""Ablauf: scannen -> bewerten -> Nachfrage testen -> nachverhandeln.

Diese Datei verdrahtet die Bausteine. Die Reihenfolge ist die
Geschaeftslogik der Idee:

  1. scan()            Inserate einsammeln, unbebaute Grundstuecke filtern
  2. rescore()         alles neu bewerten, inkl. gemessener Nachfrage
  3. create_tests()    fuer aussichtsreiche Regionen Miet- + Kaufanzeige bauen
  4. record_lead()     Anfragen erfassen -> Nachfrage-Signal der Region
  5. negotiation()     aus der echten Zahlungsbereitschaft das Maximalgebot
                       fuer das Grundstueck ableiten
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .demand import Ad, build_market_test, next_label, render_ads
from .models import Lead, MarketTest, Plot, Score
from .pricing import Calculation, calculate, max_bid_for
from .publish import get_publisher
from .scoring import score_plot
from .sources import SourceError, get_source
from .storage import Storage


@dataclass
class ScanReport:
    fetched: int = 0
    new: int = 0
    updated: int = 0
    duplicates: int = 0
    accepted: int = 0
    rejected: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    reject_reasons: dict[str, int] = field(default_factory=dict)
    new_keys: list[str] = field(default_factory=list)


def scan(cfg: Config, storage: Storage, sources: list[str] | None = None) -> ScanReport:
    """Holt Inserate aller konfigurierten Quellen und bewertet sie sofort."""
    report = ScanReport()
    demand = storage.all_demand_signals()

    for name in sources or cfg.scan.sources:
        try:
            source = get_source(name)
            plots = list(source.fetch(cfg))
        except SourceError as exc:
            report.errors[name] = str(exc)
            continue
        except Exception as exc:  # pragma: no cover - unerwartete Quellfehler
            report.errors[name] = f"unerwarteter Fehler: {exc}"
            continue

        report.per_source[name] = len(plots)
        for plot in plots:
            report.fetched += 1
            duplicate = storage.duplicate_of(plot)
            if duplicate:
                report.duplicates += 1
            is_new = storage.upsert_plot(plot)
            if is_new:
                report.new += 1
                report.new_keys.append(plot.key)
            else:
                report.updated += 1

            score = score_plot(plot, cfg, demand.get(plot.region))
            storage.save_score(score)
            if score.rejected:
                report.rejected += 1
                reason = score.reject_reason.split(" (")[0]
                report.reject_reasons[reason] = report.reject_reasons.get(reason, 0) + 1
            else:
                report.accepted += 1
    return report


def rescore(cfg: Config, storage: Storage) -> int:
    """Alles neu bewerten - noetig, wenn Kriterien oder Nachfrage sich aendern."""
    demand = storage.all_demand_signals()
    count = 0
    for plot in storage.list_plots():
        storage.save_score(score_plot(plot, cfg, demand.get(plot.region)))
        count += 1
    return count


@dataclass
class Candidate:
    plot: Plot
    score: Score
    calc: Calculation


def shortlist(cfg: Config, storage: Storage, limit: int = 20) -> list[Candidate]:
    out: list[Candidate] = []
    for plot, score in storage.shortlist(cfg.shortlist_min_score, limit=limit):
        out.append(Candidate(plot, score, calculate(plot, cfg, score.units or None)))
    return out


# --- Nachfrage-Tests ---------------------------------------------------


@dataclass
class TestCreation:
    test: MarketTest
    ads: dict[str, Ad]
    paths: dict[str, str]
    message: str


def create_test(
    cfg: Config,
    storage: Storage,
    plot_key: str,
    publisher_name: str = "entwurf",
    channel: str = "kleinanzeigen",
) -> TestCreation:
    """Baut fuer ein Grundstueck die beiden Anzeigen (Miete + Kauf)."""
    plot = storage.get_plot(plot_key)
    if plot is None:
        raise KeyError(f"Grundstueck {plot_key} nicht in der Datenbank")

    score = storage.get_score(plot_key)
    calc = calculate(plot, cfg, score.units if score and score.units else None)

    existing = {t.label for t in storage.list_market_tests()}
    test = build_market_test(plot, calc, cfg, next_label(existing, plot.region), channel)
    ads = render_ads(test)

    result = get_publisher(publisher_name).publish(test, ads, cfg)
    test.ad_rent_path = result.paths.get("miete")
    test.ad_buy_path = result.paths.get("kauf")
    if result.published:
        test.status = "veroeffentlicht"
    storage.save_market_test(test)
    return TestCreation(test, ads, result.paths, result.message)


def auto_tests(
    cfg: Config, storage: Storage, limit: int = 3, publisher_name: str = "entwurf"
) -> list[TestCreation]:
    """Erzeugt Tests fuer die besten Grundstuecke in noch ungetesteten Regionen.

    Eine Anzeige je Region reicht: getestet wird der Markt, nicht die Parzelle.
    """
    tested = storage.tested_regions()
    created: list[TestCreation] = []
    for candidate in shortlist(cfg, storage, limit=100):
        if len(created) >= limit:
            break
        region = candidate.plot.region
        if region in tested:
            continue
        created.append(create_test(cfg, storage, candidate.plot.key, publisher_name))
        tested.add(region)
    return created


def mark_published(storage: Storage, label: str, when: str | None = None) -> MarketTest:
    from datetime import datetime

    test = storage.get_market_test(label)
    if test is None:
        raise KeyError(f"Kein Test mit Kennung {label}")
    test.status = "veroeffentlicht"
    test.published_at = when or datetime.utcnow().isoformat(timespec="seconds")
    storage.save_market_test(test)
    return test


def record_lead(storage: Storage, lead: Lead) -> tuple[int, MarketTest]:
    test = storage.get_market_test(lead.label)
    if test is None:
        raise KeyError(
            f"Kein Test mit Kennung {lead.label}. Vorhandene: "
            + ", ".join(t.label for t in storage.list_market_tests()) or "keine"
        )
    lead_id = storage.add_lead(lead)
    return lead_id, test


# --- Verhandlung -------------------------------------------------------


@dataclass
class Negotiation:
    plot: Plot
    asking_price: float
    observed_rent: float | None
    max_bid: float
    verdict: str


def negotiation(cfg: Config, storage: Storage, plot_key: str) -> Negotiation:
    """Was darf das Grundstueck kosten - gemessen an der echten Nachfrage?

    Solange keine Leads vorliegen, wird mit der kalkulierten Zielmiete
    gerechnet; sobald Interessenten Preise genannt haben, zaehlt deren
    Zahlungsbereitschaft.
    """
    plot = storage.get_plot(plot_key)
    if plot is None:
        raise KeyError(f"Grundstueck {plot_key} nicht in der Datenbank")

    score = storage.get_score(plot_key)
    units = score.units if score and score.units else None
    calc = calculate(plot, cfg, units)

    signal = storage.demand_signal(plot.region)
    observed = signal.avg_accepted_rent
    rent = observed or calc.rent_eur_month
    bid = max_bid_for(plot, cfg, rent, units)

    asking = plot.price_eur or 0.0
    if bid <= 0:
        verdict = (
            "Rechnet sich nicht: zu dieser Miete traegt das Projekt nicht einmal "
            "die Baukosten. Grundstueck nur sinnvoll, wenn Baukosten sinken oder "
            "die Miete hoeher liegt."
        )
    elif bid >= asking:
        verdict = "Angebotspreis liegt im Rahmen - Kauf zum aufgerufenen Preis vertretbar."
    else:
        gap = asking - bid
        verdict = (
            f"Zu teuer: der Preis muesste um {gap:,.0f} EUR sinken. "
            "Mit dem Maximalgebot in die Verhandlung gehen."
        ).replace(",", ".")
    return Negotiation(plot, asking, observed, bid, verdict)
