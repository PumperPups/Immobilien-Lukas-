"""Domain-Modelle der Tiny-House-Pipeline.

Kette: Plot (Grundstueck gefunden) -> Score (bewertet) -> MarketTest
(Nachfrage-Anzeige fuer die Region) -> Lead (Anfrage eines Interessenten)
-> Demand (Nachfrage-Signal, fliesst zurueck in den Score).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any

# --- Grundstuecks-Klassifikation ---------------------------------------

LAND_UNKNOWN = "unbekannt"
LAND_BAULAND = "bauland"           # voll bebaubar, i.d.R. B-Plan vorhanden
LAND_BAUERWARTUNG = "bauerwartung"  # Bauerwartungsland, Risiko
LAND_GARTEN = "garten"             # Garten-/Freizeitgrundstueck, kein Wohnbau
LAND_AGRAR = "agrar"               # Acker/Wald, nicht bebaubar

SELLER_PRIVATE = "privat"
SELLER_COMMERCIAL = "gewerblich"
SELLER_UNKNOWN = "unbekannt"

INTEREST_RENT = "miete"
INTEREST_BUY = "kauf"
INTEREST_BOTH = "beides"
INTEREST_NONE = "kein_interesse"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def region_key(postal_code: str | None, city: str | None) -> str:
    """Gemeinsamer Regionsschluessel fuer Angebot und Nachfrage.

    Wir gruppieren auf PLZ-2 (z.B. '34' = Nordhessen). Feiner waere
    ueberpraezise: fuer die Frage "zieht hier jemand in ein Tiny House"
    ist der Arbeitsmarkt-/Pendelraum die richtige Aufloesung, nicht die
    einzelne Strasse.
    """
    if postal_code:
        digits = re.sub(r"\D", "", postal_code)
        if len(digits) >= 2:
            return digits[:2]
    if city:
        return city.strip().lower()[:12] or "unbekannt"
    return "unbekannt"


@dataclass
class Plot:
    """Ein zum Verkauf stehendes Grundstueck."""

    source: str
    source_id: str
    url: str
    title: str
    price_eur: float | None = None
    area_sqm: float | None = None
    city: str | None = None
    postal_code: str | None = None
    state: str | None = None          # Bundesland, fuer Grunderwerbsteuer
    description: str = ""
    seller_type: str = SELLER_UNKNOWN
    seller_name: str | None = None
    seller_contact: str | None = None
    land_type: str = LAND_UNKNOWN
    has_building: bool = False        # steht schon ein Haus drauf?
    teardown: bool = False            # Abrissobjekt -> Sonderfall
    developed: bool | None = None     # erschlossen (Strom/Wasser/Kanal)?
    listed_on: str | None = None      # Datum des Inserats (ISO)
    first_seen: str = field(default_factory=_now)
    last_seen: str = field(default_factory=_now)
    status: str = "neu"               # neu|shortlist|kontaktiert|abgelehnt|gekauft
    notes: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stabiler Primaerschluessel ueber Quellen hinweg."""
        return f"{self.source}:{self.source_id}"

    @property
    def fingerprint(self) -> str:
        """Erkennt dasselbe Grundstueck, wenn es auf zwei Portalen haengt."""
        base = "|".join(
            [
                (self.postal_code or "").strip(),
                (self.city or "").strip().lower(),
                f"{int(self.area_sqm or 0)}",
                f"{int(self.price_eur or 0)}",
            ]
        )
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    @property
    def price_per_sqm(self) -> float | None:
        if not self.price_eur or not self.area_sqm:
            return None
        return round(self.price_eur / self.area_sqm, 2)

    @property
    def region(self) -> str:
        return region_key(self.postal_code, self.city)

    @property
    def days_listed(self) -> int | None:
        if not self.listed_on:
            return None
        try:
            listed = date.fromisoformat(self.listed_on[:10])
        except ValueError:
            return None
        return max((date.today() - listed).days, 0)

    def is_empty_land(self) -> bool:
        """Kernfilter: unbebautes, bebaubares Grundstueck."""
        if self.has_building and not self.teardown:
            return False
        return self.land_type in (LAND_BAULAND, LAND_BAUERWARTUNG)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(
            key=self.key,
            region=self.region,
            price_per_sqm=self.price_per_sqm,
            days_listed=self.days_listed,
        )
        return d


@dataclass
class Score:
    """Bewertung eines Grundstuecks - bewusst erklaerbar, nicht als Blackbox."""

    plot_key: str
    total: float
    units: int                        # wie viele Tiny Houses passen drauf
    reasons: list[str] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)
    rejected: bool = False
    reject_reason: str = ""
    computed_at: str = field(default_factory=_now)


@dataclass
class MarketTest:
    """Eine Nachfrage-Anzeige fuer eine Region (Miete + Kauf parallel)."""

    region: str
    plot_key: str | None
    label: str                        # Tracking-Code, steht in der Anzeige
    city: str | None = None
    rent_eur_month: float | None = None
    buy_price_eur: float | None = None
    unit_sqm: float = 45.0
    channel: str = "kleinanzeigen"
    status: str = "entwurf"           # entwurf|veroeffentlicht|beendet
    published_at: str | None = None
    ad_rent_path: str | None = None
    ad_buy_path: str | None = None
    created_at: str = field(default_factory=_now)
    notes: str = ""


@dataclass
class Lead:
    """Anfrage eines Interessenten auf einen MarketTest."""

    label: str                        # Tracking-Code der Anzeige
    interest: str = INTEREST_NONE     # miete|kauf|beides|kein_interesse
    name: str | None = None
    contact: str | None = None
    message: str = ""
    # Getrennt, weil eine Monatsmiete und ein Kaufpreis nie dieselbe Zahl
    # sind - wer "beides" ankreuzt, nennt oft beide.
    accepted_rent: float | None = None     # Miete/Monat, die er zahlen wuerde
    accepted_price: float | None = None    # Kaufpreis, den er zahlen wuerde
    received_at: str = field(default_factory=_now)
    qualified: bool = False           # ernsthaft (Budget/Timing geklaert)?


@dataclass
class DemandSignal:
    """Aggregierte Nachfrage je Region - das Ergebnis der Marktests."""

    region: str
    tests: int = 0
    leads: int = 0
    rent_leads: int = 0
    buy_leads: int = 0
    qualified_leads: int = 0
    avg_accepted_rent: float | None = None
    avg_accepted_price: float | None = None

    @property
    def leads_per_test(self) -> float:
        return round(self.leads / self.tests, 2) if self.tests else 0.0

    @property
    def index(self) -> float:
        """0..1 Nachfrage-Index. 5 qualifizierte Leads pro Test = heiss."""
        if not self.tests:
            return 0.0
        per_test = self.qualified_leads / self.tests
        return round(min(per_test / 5.0, 1.0), 3)
