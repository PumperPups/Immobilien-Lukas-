"""Konfiguration: alle Annahmen an einer Stelle, per JSON ueberschreibbar.

Jede Zahl hier ist eine Geschaeftsannahme, keine Naturkonstante. Wer die
Kalkulation anzweifelt, aendert die Werte in config.json - nicht den Code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Grunderwerbsteuer je Bundesland in Prozent.
# ACHTUNG: Stand der Recherche, Laender aendern die Saetze regelmaessig.
# Vor jedem Kauf beim Finanzamt/Notar gegenpruefen (siehe docs/RECHTLICHES.md).
GRUNDERWERBSTEUER: dict[str, float] = {
    "Baden-Wuerttemberg": 5.0,
    "Bayern": 3.5,
    "Berlin": 6.0,
    "Brandenburg": 6.5,
    "Bremen": 5.0,
    "Hamburg": 5.5,
    "Hessen": 6.0,
    "Mecklenburg-Vorpommern": 6.0,
    "Niedersachsen": 5.0,
    "Nordrhein-Westfalen": 6.5,
    "Rheinland-Pfalz": 5.0,
    "Saarland": 6.5,
    "Sachsen": 5.5,
    "Sachsen-Anhalt": 5.0,
    "Schleswig-Holstein": 6.5,
    "Thueringen": 5.0,
}
DEFAULT_GRUNDERWERBSTEUER = 6.0  # konservativ, wenn Bundesland unbekannt


@dataclass
class PlotCriteria:
    """Was ein Grundstueck mitbringen muss, damit es uns interessiert."""

    max_price_eur: float = 120_000.0
    max_price_per_sqm: float = 180.0
    min_area_sqm: float = 300.0
    max_area_sqm: float = 5_000.0
    area_per_unit_sqm: float = 350.0   # Flaechenbedarf je Tiny House inkl. Abstand
    max_units: int = 6                 # mehr wird zum Bauprojekt, nicht mehr "tiny"
    allow_bauerwartungsland: bool = False
    allow_teardown: bool = False       # Abrissobjekte kosten Zeit und Geld
    require_developed: bool = False    # nur erschlossene Grundstuecke
    regions: list[str] = field(default_factory=list)  # PLZ-Praefixe, leer = ueberall
    exclude_regions: list[str] = field(default_factory=list)


@dataclass
class BuildCosts:
    """Kostenseite je Tiny House."""

    unit_build_eur: float = 75_000.0        # Haus schluesselfertig
    foundation_eur: float = 8_000.0         # Punktfundament/Bodenplatte
    connection_eur: float = 12_000.0        # Hausanschluesse je Einheit
    development_eur: float = 15_000.0       # Erschliessung, wenn nicht erschlossen
    permit_eur: float = 4_500.0             # Bauantrag, Statik, Vermessung
    notary_rate: float = 1.5                # Notar + Grundbuch in % vom Kaufpreis
    broker_rate: float = 3.57               # Maklercourtage in % (falls Makler)
    contingency_rate: float = 10.0          # Puffer in % der Baukosten
    subdivision_eur: float = 6_000.0        # Teilung/WEG-Aufteilung je Einheit,
                                            # faellt nur beim Verkauf an


@dataclass
class Targets:
    """Was wir verdienen wollen."""

    sale_margin_rate: float = 20.0      # Zielmarge auf Gesamtkosten in %
    gross_yield_rate: float = 7.0       # Ziel-Bruttomietrendite p.a. in %
    vacancy_rate: float = 5.0           # Leerstands-/Ausfallannahme in %
    operating_cost_eur_month: float = 80.0  # nicht umlagefaehige Kosten je Einheit
    unit_sqm: float = 45.0              # Wohnflaeche je Tiny House


@dataclass
class ScanConfig:
    """Verhalten der Scanner - defensiv voreingestellt."""

    sources: list[str] = field(default_factory=lambda: ["demo"])
    request_delay_seconds: float = 3.0
    max_pages_per_source: int = 3
    respect_robots: bool = True
    user_agent: str = (
        "TinyHausScout/0.1 (+Kontakt im Impressum; respektiert robots.txt)"
    )
    timeout_seconds: float = 20.0
    #: Quellenspezifische Optionen, z.B.
    #: {"kleinanzeigen": {"search_urls": ["https://..."]}}
    options: dict[str, dict] = field(default_factory=dict)


@dataclass
class Config:
    criteria: PlotCriteria = field(default_factory=PlotCriteria)
    costs: BuildCosts = field(default_factory=BuildCosts)
    targets: Targets = field(default_factory=Targets)
    scan: ScanConfig = field(default_factory=ScanConfig)
    db_path: str = "data/tinyhaus.db"
    output_dir: str = "out"
    shortlist_min_score: float = 60.0

    # --- Laden/Speichern ---

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        cfg = cls()
        if path is None:
            path = Path("config.json")
        path = Path(path)
        if not path.exists():
            return cfg
        data = json.loads(path.read_text(encoding="utf-8"))
        return cfg.merged(data)

    def merged(self, data: dict[str, Any]) -> "Config":
        """Flaches Ueberschreiben je Sektion - unbekannte Keys fliegen raus."""
        out = Config(
            criteria=PlotCriteria(**{**asdict(self.criteria), **_sub(data, "criteria", PlotCriteria)}),
            costs=BuildCosts(**{**asdict(self.costs), **_sub(data, "costs", BuildCosts)}),
            targets=Targets(**{**asdict(self.targets), **_sub(data, "targets", Targets)}),
            scan=ScanConfig(**{**asdict(self.scan), **_sub(data, "scan", ScanConfig)}),
            db_path=data.get("db_path", self.db_path),
            output_dir=data.get("output_dir", self.output_dir),
            shortlist_min_score=data.get("shortlist_min_score", self.shortlist_min_score),
        )
        return out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _sub(data: dict[str, Any], key: str, cls: type) -> dict[str, Any]:
    section = data.get(key) or {}
    allowed = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
    return {k: v for k, v in section.items() if k in allowed}


def grunderwerbsteuer_rate(state: str | None) -> float:
    if not state:
        return DEFAULT_GRUNDERWERBSTEUER
    return GRUNDERWERBSTEUER.get(state.strip(), DEFAULT_GRUNDERWERBSTEUER)
