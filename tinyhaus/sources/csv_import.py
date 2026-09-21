"""CSV-Import: der rechtlich unproblematische Weg in die Pipeline.

Wer eine Portal-Suche exportiert, eine Maklerliste bekommt oder selbst
Gemeinden abtelefoniert, kippt die Daten hier rein. Spaltennamen sind
tolerant (deutsch/englisch, Gross-/Kleinschreibung egal).
"""

from __future__ import annotations

import csv
import glob
from pathlib import Path
from typing import Iterable

from ..classify import enrich, parse_area, parse_location, parse_price
from ..config import Config
from ..models import Plot
from .base import Source, SourceError

ALIASES: dict[str, tuple[str, ...]] = {
    "source_id": ("id", "nr", "nummer", "source_id", "anzeigen-id", "inserat"),
    "url": ("url", "link", "webseite"),
    "title": ("titel", "title", "bezeichnung", "ueberschrift", "überschrift"),
    "description": ("beschreibung", "description", "text", "details"),
    "price": ("preis", "price", "kaufpreis", "preis_eur"),
    "area": ("flaeche", "fläche", "area", "groesse", "größe", "grundstuecksflaeche", "grundstücksfläche", "qm", "m2"),
    "location": ("ort", "location", "plz_ort", "adresse", "stadt"),
    "postal_code": ("plz", "postleitzahl", "postal_code", "zip"),
    "city": ("stadt", "gemeinde", "city"),
    "state": ("bundesland", "state", "land"),
    "listed_on": ("datum", "eingestellt", "listed_on", "inseriert_am"),
    "seller_name": ("anbieter", "verkaeufer", "verkäufer", "seller", "name"),
    "seller_contact": ("kontakt", "telefon", "email", "e-mail", "contact"),
}


def _map_row(row: dict[str, str]) -> dict[str, str]:
    normalized = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
    out: dict[str, str] = {}
    for field, names in ALIASES.items():
        for name in names:
            if normalized.get(name):
                out[field] = normalized[name]
                break
    return out


class CsvSource(Source):
    """Liest alle CSV-Dateien aus einem Verzeichnis oder Glob-Muster."""

    name = "csv"

    def __init__(self, pattern: str | None = None):
        self.pattern = pattern or "data/import/*.csv"

    def fetch(self, cfg: Config) -> Iterable[Plot]:
        options = cfg.scan.options.get(self.name, {})
        pattern = options.get("pattern", self.pattern)
        paths = sorted(glob.glob(pattern))
        if not paths:
            raise SourceError(
                f"Keine CSV-Dateien unter '{pattern}' gefunden. "
                "Lege deine Exporte dort ab (Spalten: Titel, Preis, Flaeche, PLZ/Ort, Link)."
            )
        for path in paths:
            yield from self._read_file(Path(path))

    def _read_file(self, path: Path) -> Iterable[Plot]:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel  # type: ignore[assignment]
            for index, row in enumerate(csv.DictReader(handle, dialect=dialect), start=1):
                data = _map_row(row)
                if not data.get("title") and not data.get("url"):
                    continue
                plz = data.get("postal_code")
                city = data.get("city")
                if not plz or not city:
                    parsed_plz, parsed_city = parse_location(data.get("location"))
                    plz = plz or parsed_plz
                    city = city or parsed_city
                plot = Plot(
                    source=self.name,
                    source_id=data.get("source_id") or f"{path.stem}-{index}",
                    url=data.get("url", ""),
                    title=data.get("title", ""),
                    description=data.get("description", ""),
                    price_eur=parse_price(data.get("price")),
                    area_sqm=parse_area(data.get("area")),
                    city=city,
                    postal_code=plz,
                    state=data.get("state"),
                    listed_on=data.get("listed_on"),
                    seller_name=data.get("seller_name"),
                    seller_contact=data.get("seller_contact"),
                    raw=dict(row),
                )
                enrich(plot)
                yield plot
