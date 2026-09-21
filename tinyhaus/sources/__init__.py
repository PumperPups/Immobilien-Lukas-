"""Registry der Grundstuecks-Quellen."""

from __future__ import annotations

from .base import Source, SourceError
from .csv_import import CsvSource
from .demo import DemoSource
from .immoscout import ImmoScoutSource
from .kleinanzeigen import KleinanzeigenSource

_REGISTRY: dict[str, type[Source]] = {
    DemoSource.name: DemoSource,
    CsvSource.name: CsvSource,
    KleinanzeigenSource.name: KleinanzeigenSource,
    ImmoScoutSource.name: ImmoScoutSource,
}


def available() -> list[str]:
    return sorted(_REGISTRY)


def get_source(name: str) -> Source:
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise SourceError(
            f"Unbekannte Quelle '{name}'. Verfuegbar: {', '.join(available())}"
        ) from None


__all__ = ["Source", "SourceError", "get_source", "available"]
