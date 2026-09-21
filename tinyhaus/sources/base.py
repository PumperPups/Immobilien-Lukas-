"""Schnittstelle fuer Grundstuecks-Quellen."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from ..config import Config
from ..models import Plot


class SourceError(RuntimeError):
    """Quelle konnte nicht abgefragt werden (Netz, Sperre, Konfiguration)."""


class Source(ABC):
    """Eine Quelle liefert rohe Grundstuecksinserate.

    Regeln fuer neue Quellen:
      * nur oeffentlich zugaengliche Daten,
      * robots.txt respektieren (siehe PoliteFetcher),
      * lieber ein Feld leer lassen als raten - die Bewertung kommt mit
        Unbekanntem klar, mit erfundenen Werten nicht.
    """

    name: str = "base"
    #: Braucht diese Quelle Zugangsdaten/Partnervertrag?
    requires_credentials: bool = False

    @abstractmethod
    def fetch(self, cfg: Config) -> Iterable[Plot]:
        ...

    def __str__(self) -> str:  # pragma: no cover - Komfort
        return self.name
