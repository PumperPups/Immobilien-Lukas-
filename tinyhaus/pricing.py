"""Kalkulation: vom Grundstueckspreis zu Mietpreis und Kaufpreis.

Zwei Zahlen fallen hinten raus, und genau die beiden testen wir am Markt:
  - Miete pro Monat  (Bruttomietrendite-Ansatz)
  - Kaufpreis        (Gesamtkosten + Zielmarge)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import Config, grunderwerbsteuer_rate
from .fmt import de_number, eur
from .models import Plot, SELLER_COMMERCIAL


@dataclass
class Calculation:
    units: int
    plot_price: float
    acquisition_extra: float      # Notar, Grundbuch, GrESt, ggf. Makler
    build_total: float
    development_total: float
    permit_total: float
    contingency: float
    total_cost: float
    cost_per_unit: float
    sale_price_eur: float      # Verkaufspreis je Einheit (inkl. Teilungskosten)
    rent_eur_month: float      # Monatsmiete je Einheit
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def total_revenue_sale(self) -> float:
        return round(self.sale_price_eur * self.units, 2)

    @property
    def profit_sale(self) -> float:
        return round(self.total_revenue_sale - self.total_cost, 2)

    @property
    def payback_years_rent(self) -> float | None:
        """Wie lange bis sich das Ganze ueber Miete traegt (ohne Finanzierung)."""
        annual = self.rent_eur_month * 12 * self.units
        if annual <= 0:
            return None
        return round(self.total_cost / annual, 1)

    def explain(self) -> list[str]:
        lines = [
            f"Einheiten: {self.units}",
            f"Grundstueck: {eur(self.plot_price)}",
            f"Kaufnebenkosten: {eur(self.acquisition_extra)}",
            f"Bau ({self.units}x): {eur(self.build_total)}",
            f"Erschliessung/Anschluesse: {eur(self.development_total)}",
            f"Genehmigung/Planung: {eur(self.permit_total)}",
            f"Puffer: {eur(self.contingency)}",
            f"Gesamtkosten: {eur(self.total_cost)} ({eur(self.cost_per_unit)} je Einheit)",
            f"-> Kaufangebot: {eur(self.sale_price_eur)} je Einheit",
            f"-> Mietangebot: {eur(self.rent_eur_month)}/Monat je Einheit",
        ]
        payback = self.payback_years_rent
        if payback:
            lines.append(f"Amortisation ueber Miete: ca. {de_number(payback, 1)} Jahre")
        return lines


def units_for(plot: Plot, cfg: Config) -> int:
    """Wie viele Tiny Houses passen realistisch auf das Grundstueck?"""
    crit = cfg.criteria
    if not plot.area_sqm or plot.area_sqm <= 0:
        return 0
    raw = math.floor(plot.area_sqm / crit.area_per_unit_sqm)
    return max(0, min(raw, crit.max_units))


def acquisition_cost(plot: Plot, cfg: Config) -> tuple[float, dict[str, float]]:
    """Kaufpreis + Nebenkosten. Makler nur bei gewerblichem Anbieter."""
    price = plot.price_eur or 0.0
    grest_rate = grunderwerbsteuer_rate(plot.state)
    grest = price * grest_rate / 100.0
    notary = price * cfg.costs.notary_rate / 100.0
    broker = (
        price * cfg.costs.broker_rate / 100.0
        if plot.seller_type == SELLER_COMMERCIAL
        else 0.0
    )
    extra = grest + notary + broker
    detail = {
        "grunderwerbsteuer": round(grest, 2),
        "grunderwerbsteuer_satz": grest_rate,
        "notar_grundbuch": round(notary, 2),
        "makler": round(broker, 2),
    }
    return round(extra, 2), detail


def calculate(plot: Plot, cfg: Config, units: int | None = None) -> Calculation:
    """Vollkalkulation fuer ein Grundstueck."""
    costs, targets = cfg.costs, cfg.targets
    n = units if units is not None else units_for(plot, cfg)
    n = max(n, 1)  # fuer die Kalkulation immer mindestens eine Einheit rechnen

    plot_price = plot.price_eur or 0.0
    extra, extra_detail = acquisition_cost(plot, cfg)

    build_total = costs.unit_build_eur * n + costs.foundation_eur * n
    development_total = costs.connection_eur * n
    if plot.developed is not True:
        # Nicht erschlossen (oder unbekannt) -> Erschliessung einplanen.
        development_total += costs.development_eur
    permit_total = costs.permit_eur * n

    contingency = (build_total + development_total + permit_total) * (
        costs.contingency_rate / 100.0
    )
    total = plot_price + extra + build_total + development_total + permit_total + contingency
    per_unit = total / n

    # Wer einzelne Einheiten verkauft, muss das Grundstueck teilen oder
    # WEG-Miteigentum bilden - Kosten, die beim Vermieten nicht anfallen.
    sale_price = (per_unit + costs.subdivision_eur) * (1 + targets.sale_margin_rate / 100.0)

    # Miete: Zielrendite auf das eingesetzte Kapital, korrigiert um
    # Leerstandsrisiko, plus nicht umlagefaehige Bewirtschaftungskosten.
    yield_monthly = per_unit * (targets.gross_yield_rate / 100.0) / 12.0
    occupancy = max(1e-6, 1 - targets.vacancy_rate / 100.0)
    rent = yield_monthly / occupancy + targets.operating_cost_eur_month

    breakdown = {
        "grundstueck": round(plot_price, 2),
        **extra_detail,
        "bau": round(build_total, 2),
        "erschliessung": round(development_total, 2),
        "genehmigung": round(permit_total, 2),
        "puffer": round(contingency, 2),
    }

    return Calculation(
        units=n,
        plot_price=round(plot_price, 2),
        acquisition_extra=extra,
        build_total=round(build_total, 2),
        development_total=round(development_total, 2),
        permit_total=round(permit_total, 2),
        contingency=round(contingency, 2),
        total_cost=round(total, 2),
        cost_per_unit=round(per_unit, 2),
        sale_price_eur=round_to(sale_price, 500),
        rent_eur_month=round_to(rent, 10),
        breakdown=breakdown,
    )


def round_to(value: float, step: float) -> float:
    """Marktuebliche Rundung - 78.500 EUR verkauft sich besser als 78.437 EUR."""
    if step <= 0:
        return round(value, 2)
    return round(round(value / step) * step, 2)


def max_bid_for(plot: Plot, cfg: Config, target_rent: float, units: int | None = None) -> float:
    """Rueckwaerts: Was darf das Grundstueck kosten, wenn der Markt nur
    ``target_rent`` pro Monat zahlt? Das ist die Zahl fuer die Verhandlung.
    """
    n = units if units is not None else max(units_for(plot, cfg), 1)
    targets, costs = cfg.targets, cfg.costs

    occupancy = max(1e-6, 1 - targets.vacancy_rate / 100.0)
    # Miete -> zulaessige Kosten je Einheit (Umkehrung von calculate()).
    yield_monthly = (target_rent - targets.operating_cost_eur_month) * occupancy
    if yield_monthly <= 0:
        return 0.0
    allowed_per_unit = yield_monthly * 12.0 / (targets.gross_yield_rate / 100.0)
    allowed_total = allowed_per_unit * n

    build_total = costs.unit_build_eur * n + costs.foundation_eur * n
    development_total = costs.connection_eur * n
    if plot.developed is not True:
        development_total += costs.development_eur
    permit_total = costs.permit_eur * n
    fixed = build_total + development_total + permit_total
    fixed_with_buffer = fixed * (1 + costs.contingency_rate / 100.0)

    # Restbetrag deckt Kaufpreis inkl. Nebenkosten (die am Preis haengen).
    rest = allowed_total - fixed_with_buffer
    if rest <= 0:
        return 0.0
    grest_rate = grunderwerbsteuer_rate(plot.state)
    broker_rate = (
        costs.broker_rate if plot.seller_type == SELLER_COMMERCIAL else 0.0
    )
    multiplier = 1 + (grest_rate + costs.notary_rate + broker_rate) / 100.0
    return round_to(rest / multiplier, 500)
