"""Registry der Publisher."""

from __future__ import annotations

from .api import ApiPublisher
from .base import PublishResult, Publisher
from .draft import DraftPublisher

_REGISTRY: dict[str, type[Publisher]] = {
    DraftPublisher.name: DraftPublisher,
    ApiPublisher.name: ApiPublisher,
}


def available() -> list[str]:
    return sorted(_REGISTRY)


def get_publisher(name: str = "entwurf") -> Publisher:
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(
            f"Unbekannter Publisher '{name}'. Verfuegbar: {', '.join(available())}"
        ) from None


__all__ = ["Publisher", "PublishResult", "get_publisher", "available"]
