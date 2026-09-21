"""Demo-Quelle: liest Beispielinserate aus data/fixtures/demo_plots.json.

Damit laeuft die komplette Pipeline ohne Netz und ohne Portal-Zugang -
zum Ausprobieren, fuer Tests und fuer Vorfuehrungen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..classify import enrich, parse_location, parse_price
from ..config import Config
from ..models import Plot
from .base import Source

DEFAULT_FIXTURE = Path("data/fixtures/demo_plots.json")


class DemoSource(Source):
    name = "demo"

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or DEFAULT_FIXTURE)

    def fetch(self, cfg: Config) -> Iterable[Plot]:
        records = json.loads(self.path.read_text(encoding="utf-8"))
        for record in records:
            plz, city = parse_location(record.get("location"))
            plot = Plot(
                source=self.name,
                source_id=record["source_id"],
                url=record.get("url", ""),
                title=record.get("title", ""),
                description=record.get("description", ""),
                price_eur=parse_price(record.get("price")),
                city=city,
                postal_code=plz,
                state=record.get("state"),
                listed_on=record.get("listed_on"),
                raw=record,
            )
            enrich(plot)
            yield plot
