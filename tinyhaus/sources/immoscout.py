"""Quelle: ImmobilienScout24 ueber die offizielle Schnittstelle.

IS24 bietet eine Such-API nur mit Partnervertrag und OAuth-Zugangsdaten.
Ohne diese Daten bricht die Quelle bewusst mit einer Erklaerung ab, statt
die Webseite zu scrapen - das waere ein AGB-Verstoss und fliegt auf.

Die Umwandlung der API-Antwort in unsere Plots steckt in
``parse_api_result`` und ist unabhaengig vom Zugang testbar: sobald der
Vertrag steht, muss nur noch ``fetch`` den Request absetzen.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

from ..classify import enrich
from ..config import Config
from ..models import Plot
from .base import Source, SourceError

ENV_CLIENT_ID = "IS24_CLIENT_ID"
ENV_CLIENT_SECRET = "IS24_CLIENT_SECRET"


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def parse_api_result(payload: dict[str, Any]) -> list[Plot]:
    """Wandelt eine IS24-Suchantwort (resultlist) in Plots."""
    entries = (
        payload.get("resultlist.resultlistEntry")
        or payload.get("resultlistEntry")
        or payload.get("results")
        or []
    )
    if isinstance(entries, dict):
        entries = [entries]

    plots: list[Plot] = []
    for entry in entries:
        item = entry.get("resultlist.realEstate") or entry.get("realEstate") or entry
        address = item.get("address") or {}
        plot = Plot(
            source="immoscout24",
            source_id=str(_first(entry, "@id", "id") or _first(item, "@id", "id") or ""),
            url=str(_first(entry, "url", "@url") or ""),
            title=str(_first(item, "title") or ""),
            description=str(_first(item, "descriptionNote", "description") or ""),
            price_eur=_as_float((item.get("price") or {}).get("value")),
            area_sqm=_as_float(_first(item, "plotArea", "livingSpace")),
            city=_first(address, "city"),
            postal_code=_first(address, "postcode"),
            state=_first(address, "quarter", "state"),
            seller_name=str(_first(item, "contactDetails") or "") or None,
            raw=item if isinstance(item, dict) else {},
        )
        enrich(plot)
        plots.append(plot)
    return plots


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ImmoScoutSource(Source):
    name = "immoscout24"
    requires_credentials = True

    def fetch(self, cfg: Config) -> Iterable[Plot]:
        client_id = os.environ.get(ENV_CLIENT_ID)
        client_secret = os.environ.get(ENV_CLIENT_SECRET)
        if not client_id or not client_secret:
            raise SourceError(
                "ImmobilienScout24 braucht einen Partnerzugang. Setze "
                f"{ENV_CLIENT_ID} und {ENV_CLIENT_SECRET}, nachdem der "
                "API-Vertrag steht (https://api.immobilienscout24.de). "
                "Bis dahin: Quelle 'csv' nutzen und Exporte importieren."
            )
        raise SourceError(
            "Zugangsdaten gefunden, aber der API-Aufruf ist noch nicht "
            "freigeschaltet: den konkreten Suchendpunkt und das OAuth-Verfahren "
            "gibt IS24 mit dem Vertrag vor. parse_api_result() ist fertig - "
            "hier nur noch den Request einsetzen."
        )
