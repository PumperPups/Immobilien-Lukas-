"""Quelle: Kleinanzeigen-Suchergebnisseiten.

WICHTIG - vor dem Aktivieren lesen (docs/RECHTLICHES.md):
Die AGB von Kleinanzeigen untersagen automatisierten Abruf. Diese Quelle
haelt sich deshalb strikt an robots.txt und bricht ab, sobald der Abruf
untersagt oder gedrosselt wird. Sie ist NICHT in der Standardkonfiguration
aktiv. Der saubere Weg ist ein Partner-/API-Zugang oder der CSV-Import.

Konfiguration (config.json):
    "scan": {
      "sources": ["kleinanzeigen"],
      "options": {"kleinanzeigen": {
          "search_urls": ["<deine gefilterte Suche aus dem Browser>"]
      }}
    }
"""

from __future__ import annotations

from typing import Iterable
from urllib.parse import urljoin

from ..classify import enrich, parse_area, parse_location, parse_price
from ..config import Config
from ..models import Plot
from .base import Source, SourceError
from .htmlparse import parse_listings
from .http import PoliteFetcher

BASE_URL = "https://www.kleinanzeigen.de"

CAPTURE = {
    "location": "aditem-main--top--left",
    "title": "text-module-begin",
    "description": "--description",
    "price": "--price-shipping--price",
    "tags": "simpletag",
}


def parse_search_page(html: str, base_url: str = BASE_URL) -> list[Plot]:
    """Wandelt eine Suchergebnisseite in Plots. Ohne Netz testbar."""
    plots: list[Plot] = []
    for item in parse_listings(html, "article", "data-adid", CAPTURE):
        plz, city = parse_location(item.get("location"))
        href = item.get("href", "")
        plot = Plot(
            source="kleinanzeigen",
            source_id=item.get("id", ""),
            url=urljoin(base_url, href) if href else "",
            title=item.get("title", ""),
            description=item.get("description", ""),
            price_eur=parse_price(item.get("price")),
            area_sqm=parse_area(item.get("tags")) or parse_area(item.get("title")),
            postal_code=plz,
            city=city,
            raw=item,
        )
        enrich(plot)
        plots.append(plot)
    return plots


def page_url(search_url: str, page: int) -> str:
    """Kleinanzeigen paginiert ueber ein /seite:N/-Segment im Pfad."""
    if page <= 1:
        return search_url
    marker = "/s-"
    index = search_url.find(marker)
    if index == -1:
        separator = "&" if "?" in search_url else "?"
        return f"{search_url}{separator}page={page}"
    return f"{search_url[:index]}/s-seite:{page}{search_url[index + len(marker) - 1:]}"


class KleinanzeigenSource(Source):
    name = "kleinanzeigen"

    def __init__(self, fetcher: PoliteFetcher | None = None):
        self._fetcher = fetcher

    def fetcher(self, cfg: Config) -> PoliteFetcher:
        if self._fetcher is None:
            self._fetcher = PoliteFetcher(
                user_agent=cfg.scan.user_agent,
                delay_seconds=cfg.scan.request_delay_seconds,
                timeout=cfg.scan.timeout_seconds,
                respect_robots=cfg.scan.respect_robots,
            )
        return self._fetcher

    def fetch(self, cfg: Config) -> Iterable[Plot]:
        options = cfg.scan.options.get(self.name, {})
        search_urls: list[str] = options.get("search_urls", [])
        if not search_urls:
            raise SourceError(
                "Keine 'search_urls' fuer die Quelle 'kleinanzeigen' konfiguriert. "
                "Suche im Browser nach Grundstuecken mit deinen Filtern, kopiere die "
                "URL und trage sie in config.json unter scan.options.kleinanzeigen.search_urls ein."
            )
        fetcher = self.fetcher(cfg)
        for search_url in search_urls:
            for page in range(1, cfg.scan.max_pages_per_source + 1):
                html = fetcher.get(page_url(search_url, page))
                plots = parse_search_page(html)
                if not plots:
                    break
                yield from plots
