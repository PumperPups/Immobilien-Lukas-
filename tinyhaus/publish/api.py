"""Platzhalter fuer einen echten API-Publisher.

Hier kommt der Code hin, sobald ein offizieller Zugang vorliegt:
Kleinanzeigen-Partnerschnittstelle (fuer gewerbliche Anbieter), die
IS24-Importschnittstelle oder ein OpenImmo-Export an ein Portal.

Bewusst als Fehler implementiert: lieber ein klarer Hinweis als ein
Bot, der gegen die AGB des Portals einstellt und den Account verbrennt.
"""

from __future__ import annotations

from ..config import Config
from ..demand import Ad
from ..models import MarketTest
from .base import PublishResult, Publisher


class ApiPublisher(Publisher):
    name = "api"

    def publish(self, test: MarketTest, ads: dict[str, Ad], cfg: Config) -> PublishResult:
        raise NotImplementedError(
            "Kein offizieller Portal-Zugang hinterlegt. Optionen:\n"
            " 1. Gewerbliches Konto + Partnerschnittstelle beim Portal beantragen\n"
            " 2. OpenImmo-Export an einen Maklersoftware-Anbieter\n"
            " 3. Solange: Publisher 'entwurf' nutzen und die fertigen Texte "
            "manuell einstellen (dauert ~2 Minuten je Anzeige)."
        )
