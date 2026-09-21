"""Bewertung der gefundenen Grundstuecke.

Bewusst erklaerbar: jede Teilnote hat einen Grund im Klartext. Wer ein
Grundstueck anruft, will wissen *warum* es auf der Liste steht.

Der Clou ist die letzte Komponente: die tatsaechlich gemessene Nachfrage
aus unseren Test-Anzeigen fliesst in die Bewertung neuer Grundstuecke
zurueck. Je laenger das System laeuft, desto besser weiss es, wo sich
Tiny Houses ueberhaupt vermieten lassen.
"""

from __future__ import annotations

from .config import Config
from .fmt import eur
from .models import (
    LAND_BAUERWARTUNG,
    LAND_BAULAND,
    Plot,
    Score,
    SELLER_PRIVATE,
    DemandSignal,
)
from .pricing import units_for

WEIGHTS = {
    "preis_pro_qm": 20.0,
    "budget": 10.0,
    "kapazitaet": 15.0,
    "baurecht": 15.0,
    "erschliessung": 10.0,
    "anbieter": 5.0,
    "standzeit": 5.0,
    "nachfrage": 20.0,
}


def check_hard_criteria(plot: Plot, cfg: Config) -> str | None:
    """Ausschlusskriterien. Rueckgabe = Grund, oder None wenn alles passt."""
    crit = cfg.criteria

    if plot.has_building and not plot.teardown:
        return "bebaut - es steht bereits ein Gebaeude darauf"
    if plot.teardown and not crit.allow_teardown:
        return "Abrissobjekt (per Konfiguration ausgeschlossen)"
    if plot.land_type == LAND_BAUERWARTUNG and not crit.allow_bauerwartungsland:
        return "Bauerwartungsland - Baurecht nicht gesichert"
    if not plot.is_empty_land():
        return f"kein bebaubares Bauland (Einstufung: {plot.land_type})"

    if plot.area_sqm is None:
        return "Flaeche unbekannt - nicht bewertbar"
    if plot.area_sqm < crit.min_area_sqm:
        return f"zu klein ({plot.area_sqm:.0f} m2 < {crit.min_area_sqm:.0f} m2)"
    if plot.area_sqm > crit.max_area_sqm:
        return f"zu gross ({plot.area_sqm:.0f} m2 > {crit.max_area_sqm:.0f} m2)"

    if plot.price_eur is None:
        return "Preis unbekannt (z.B. 'auf Anfrage') - manuell pruefen"
    if plot.price_eur > crit.max_price_eur:
        return f"zu teuer ({eur(plot.price_eur)} > {eur(crit.max_price_eur)})"
    ppsm = plot.price_per_sqm
    if ppsm is not None and ppsm > crit.max_price_per_sqm:
        return f"Quadratmeterpreis zu hoch ({ppsm:.0f} EUR/m2)"

    if crit.require_developed and plot.developed is not True:
        return "nicht (nachweislich) erschlossen"

    if crit.regions and plot.region not in crit.regions:
        return f"Region {plot.region} nicht im Suchgebiet"
    if plot.region in crit.exclude_regions:
        return f"Region {plot.region} ausgeschlossen"
    return None


def score_plot(plot: Plot, cfg: Config, demand: DemandSignal | None = None) -> Score:
    reject = check_hard_criteria(plot, cfg)
    units = units_for(plot, cfg)
    if reject:
        return Score(
            plot_key=plot.key,
            total=0.0,
            units=units,
            rejected=True,
            reject_reason=reject,
            reasons=[f"Ausgeschlossen: {reject}"],
        )

    crit = cfg.criteria
    parts: dict[str, float] = {}
    reasons: list[str] = []

    # 1) Quadratmeterpreis - je guenstiger gegenueber unserer Obergrenze, desto besser.
    ppsm = plot.price_per_sqm or crit.max_price_per_sqm
    ratio = max(0.0, min(1.0, 1 - ppsm / crit.max_price_per_sqm))
    parts["preis_pro_qm"] = WEIGHTS["preis_pro_qm"] * ratio
    reasons.append(f"{ppsm:.0f} EUR/m2 (Limit {crit.max_price_per_sqm:.0f})")

    # 2) Gesamtpreis - niedriger Kapitaleinsatz = geringeres Risiko.
    price_ratio = max(0.0, min(1.0, 1 - (plot.price_eur or 0) / crit.max_price_eur))
    parts["budget"] = WEIGHTS["budget"] * price_ratio
    reasons.append(f"Kaufpreis {eur(plot.price_eur)}")

    # 3) Kapazitaet - mehrere Einheiten verteilen die Fixkosten.
    cap_ratio = min(1.0, units / 3.0) if units else 0.0
    parts["kapazitaet"] = WEIGHTS["kapazitaet"] * cap_ratio
    reasons.append(f"Platz fuer {units} Tiny House(s)")

    # 4) Baurecht.
    if plot.land_type == LAND_BAULAND:
        parts["baurecht"] = WEIGHTS["baurecht"]
        reasons.append("als Bauland ausgewiesen")
    else:
        parts["baurecht"] = WEIGHTS["baurecht"] * 0.3
        reasons.append("Baurecht unsicher (Bauerwartungsland)")

    # 5) Erschliessung - unerschlossen kostet schnell 15.000 EUR extra.
    if plot.developed is True:
        parts["erschliessung"] = WEIGHTS["erschliessung"]
        reasons.append("erschlossen")
    elif plot.developed is False:
        parts["erschliessung"] = 0.0
        reasons.append("nicht erschlossen - Erschliessungskosten einkalkuliert")
    else:
        parts["erschliessung"] = WEIGHTS["erschliessung"] * 0.4
        reasons.append("Erschliessung unklar - beim Verkaeufer nachfragen")

    # 6) Anbieter - privat heisst meist mehr Verhandlungsspielraum, keine Courtage.
    if plot.seller_type == SELLER_PRIVATE:
        parts["anbieter"] = WEIGHTS["anbieter"]
        reasons.append("Privatverkauf (keine Courtage)")
    else:
        parts["anbieter"] = WEIGHTS["anbieter"] * 0.4

    # 7) Standzeit - was lange liegt, laesst sich druecken.
    days = plot.days_listed
    if days is None:
        parts["standzeit"] = WEIGHTS["standzeit"] * 0.5
    else:
        parts["standzeit"] = WEIGHTS["standzeit"] * min(1.0, days / 90.0)
        if days >= 60:
            reasons.append(f"seit {days} Tagen inseriert - Verhandlungsspielraum")

    # 8) Gemessene Nachfrage aus unseren Test-Anzeigen in der Region.
    if demand and demand.tests:
        parts["nachfrage"] = WEIGHTS["nachfrage"] * demand.index
        reasons.append(
            f"Nachfrage-Index {demand.index:.2f} "
            f"({demand.qualified_leads} qualifizierte Anfragen aus {demand.tests} Test(s))"
        )
    else:
        # Noch ungetestet: neutrale halbe Wertung, damit neue Regionen
        # ueberhaupt eine Chance auf einen Test bekommen.
        parts["nachfrage"] = WEIGHTS["nachfrage"] * 0.5
        reasons.append("Region noch ungetestet - Nachfrage-Anzeige schalten")

    total = round(sum(parts.values()), 1)
    return Score(
        plot_key=plot.key,
        total=total,
        units=units,
        reasons=reasons,
        breakdown={k: round(v, 2) for k, v in parts.items()},
    )
