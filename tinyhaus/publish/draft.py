"""Entwurfs-Publisher: erzeugt fertige Anzeigen zum Einstellen.

Warum nicht vollautomatisch einstellen? Weil die AGB von Kleinanzeigen
automatisiertes Einstellen untersagen und der Account dafuer gesperrt
wird - mitsamt allen laufenden Anzeigen. Der Entwurfs-Weg kostet zwei
Minuten Copy-Paste je Anzeige und haelt das Konto am Leben.

Sobald ein offizieller Zugang (Kleinanzeigen-Partnerschnittstelle,
IS24-API) vorliegt, tritt an diese Stelle ein ApiPublisher - die
Schnittstelle ist dieselbe.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import Config
from ..demand import Ad
from ..fmt import eur
from ..models import MarketTest
from .base import PublishResult, Publisher

CHECKLIST = """# Einstell-Checkliste {label}

Region: {region} ({city})
Kanal: {channel}

1. Anzeige "Vermieten" einstellen -> Text aus `miete.md`
   - Kategorie: Immobilien > Haeuser zur Miete (bzw. Mietwohnungen)
   - Ort: {city}
   - Preis: {rent} (Preistyp: Festpreis/VB)
2. Anzeige "Verkaufen" einstellen -> Text aus `kauf.md`
   - Kategorie: Immobilien > Haeuser zum Kauf
   - Ort: {city}
   - Preis: {buy}
3. Beide Anzeigen tragen die Kennung {label}. Anfragen damit erfassen:
   `python3 -m tinyhaus lead {label} --interesse miete --miete 780 --name "..." --kontakt "..."`
4. Nach 14 Tagen auswerten:
   `python3 -m tinyhaus nachfrage`

Hinweis: Anzeigen ehrlich als Projekt in Planung kennzeichnen (steht im Text).
Keine Bilder verwenden, die ein fertiges Objekt vorspiegeln - Symbolbilder als
solche kennzeichnen.
"""


class DraftPublisher(Publisher):
    name = "entwurf"

    def publish(self, test: MarketTest, ads: dict[str, Ad], cfg: Config) -> PublishResult:
        target = Path(cfg.output_dir) / "anzeigen" / test.label
        target.mkdir(parents=True, exist_ok=True)

        paths: dict[str, str] = {}
        for variant, ad in ads.items():
            path = target / f"{variant}.md"
            path.write_text(ad.as_text(), encoding="utf-8")
            paths[variant] = str(path)

        (target / "anzeigen.json").write_text(
            json.dumps(
                {
                    "label": test.label,
                    "region": test.region,
                    "city": test.city,
                    "channel": test.channel,
                    "ads": [
                        {
                            "variante": ad.variant,
                            "titel": ad.title,
                            "text": ad.body,
                            "preis_eur": ad.price_eur,
                            "preistyp": ad.price_type,
                        }
                        for ad in ads.values()
                    ],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths["json"] = str(target / "anzeigen.json")

        checklist = CHECKLIST.format(
            label=test.label,
            region=test.region,
            city=test.city or "-",
            channel=test.channel,
            rent=eur(test.rent_eur_month) + " / Monat",
            buy=eur(test.buy_price_eur),
        )
        (target / "checkliste.md").write_text(checklist, encoding="utf-8")
        paths["checkliste"] = str(target / "checkliste.md")

        return PublishResult(
            published=False,
            message=f"Entwuerfe fuer {test.label} liegen in {target} - bitte manuell einstellen.",
            paths=paths,
        )
