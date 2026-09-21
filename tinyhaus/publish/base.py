"""Schnittstelle zum Veroeffentlichen der Nachfrage-Anzeigen."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import Config
from ..demand import Ad
from ..models import MarketTest


@dataclass
class PublishResult:
    published: bool
    message: str
    paths: dict[str, str] = field(default_factory=dict)


class Publisher(ABC):
    name = "base"

    @abstractmethod
    def publish(self, test: MarketTest, ads: dict[str, Ad], cfg: Config) -> PublishResult:
        ...
