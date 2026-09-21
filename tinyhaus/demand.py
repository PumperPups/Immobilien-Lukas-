"""Nachfrage-Test: zwei Anzeigen je Region - Miete und Kauf.

Der Kern der Idee: bevor irgendwer ein Grundstueck kauft, wird in der
Region gemessen, ob ueberhaupt jemand zu Preis X in ein Tiny House
ziehen will - und ob die Leute lieber mieten oder kaufen.

Ehrlichkeit ist hier kein Luxus, sondern Pflicht: die Anzeigen weisen
aus, dass das Projekt in Planung ist und der Bau von der Nachfrage
abhaengt. Eine Anzeige fuer ein Objekt, das es so nicht gibt, waere
irrefuehrende Werbung (UWG) - und verbrennt ausserdem das Vertrauen
genau der Leute, die spaeter einziehen sollen.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .fmt import de_number, eur, sqm
from .models import MarketTest, Plot
from .pricing import Calculation

VARIANT_RENT = "miete"
VARIANT_BUY = "kauf"


@dataclass
class Ad:
    variant: str
    title: str
    body: str
    price_eur: float
    price_type: str      # "Miete pro Monat" | "Festpreis"
    label: str

    def as_text(self) -> str:
        return f"{self.title}\n{'=' * len(self.title)}\n\n{self.body}\n"


def next_label(existing_labels: set[str], region: str) -> str:
    """Tracking-Code, der in beiden Anzeigen steht: TH-34-01."""
    for index in range(1, 100):
        label = f"TH-{region}-{index:02d}"
        if label not in existing_labels:
            return label
    raise ValueError(f"Keine freie Labelnummer mehr fuer Region {region}")


def build_market_test(
    plot: Plot, calc: Calculation, cfg: Config, label: str, channel: str = "kleinanzeigen"
) -> MarketTest:
    return MarketTest(
        region=plot.region,
        plot_key=plot.key,
        label=label,
        city=plot.city,
        rent_eur_month=calc.rent_eur_month,
        buy_price_eur=calc.sale_price_eur,
        unit_sqm=cfg.targets.unit_sqm,
        channel=channel,
        notes=f"Grundstueck: {plot.title} ({plot.url})",
    )


def _area_name(test: MarketTest) -> str:
    return test.city or f"PLZ-Gebiet {test.region}"


_FEATURES = (
    "- ca. {sqm} m² Wohnflaeche auf einer Ebene\n"
    "- Wohn-/Kochbereich, Schlafbereich, Bad mit Dusche\n"
    "- eigener Stellplatz und Aussenflaeche\n"
    "- Anschluss an Strom, Wasser und Abwasser\n"
    "- Bezug abhaengig von Genehmigung, realistisch in 9-15 Monaten"
)

_HONESTY = (
    "Wichtig und ehrlich gesagt: Das Projekt befindet sich in der Planung. "
    "Wir pruefen gerade konkrete Grundstuecke in der Region und bauen nur, "
    "wenn sich genuegend Interessenten finden. Diese Anzeige ist eine "
    "Vorab-Anfrage, noch kein fertiges Objekt und kein Vertragsangebot. "
    "Unverbindlich, kostenlos, keine Maklergebuehr."
)

_QUESTION_HINT = (
    "Bitte im Betreff die Kennung {label} angeben, dann koennen wir Ihre\n"
    "Anfrage direkt dem Standort zuordnen."
)


def render_rent_ad(test: MarketTest) -> Ad:
    area = _area_name(test)
    rent = test.rent_eur_month or 0.0
    features = _FEATURES.format(sqm=de_number(test.unit_sqm))
    title = (
        f"Tiny House mieten in {area} - ca. {de_number(test.unit_sqm)} m² "
        f"fuer {eur(rent)}/Monat"
    )
    body = f"""Wir planen in {area} einen kleinen Tiny-House-Standort und suchen Menschen,
die dort einziehen wollen.

So ist es gedacht:
{features}

Miete: {eur(rent)} pro Monat (kalt, Stellplatz inklusive).

{_HONESTY}

Zwei kurze Fragen, wenn Sie antworten:
1) Wuerden Sie zu diesem Preis einziehen - und ab wann?
2) Falls nein: welche Miete waere fuer Sie passend?

{_QUESTION_HINT.format(label=test.label)}"""
    return Ad(VARIANT_RENT, title, body, rent, "Miete pro Monat", test.label)


def render_buy_ad(test: MarketTest) -> Ad:
    area = _area_name(test)
    price = test.buy_price_eur or 0.0
    features = _FEATURES.format(sqm=de_number(test.unit_sqm))
    title = (
        f"Tiny House kaufen in {area} - ca. {de_number(test.unit_sqm)} m², {eur(price)}"
    )
    body = f"""Wir planen in {area} einen kleinen Tiny-House-Standort - und bieten die
Haeuser wahlweise zum Kauf an.

So ist es gedacht:
{features}

Kaufpreis: {eur(price)} inklusive Grundstuecksanteil, Erschliessung und
Hausanschluessen. Kaufnebenkosten (Notar, Grunderwerbsteuer) kommen wie ueblich dazu.

{_HONESTY}

Zwei kurze Fragen, wenn Sie antworten:
1) Waere der Kauf zu diesem Preis fuer Sie interessant - und wie wuerden Sie finanzieren?
2) Oder waere Ihnen Mieten lieber? Dann sagen Sie uns gern, welche Monatsmiete passen wuerde.

{_QUESTION_HINT.format(label=test.label)}"""
    return Ad(VARIANT_BUY, title, body, price, "Festpreis", test.label)


def render_ads(test: MarketTest) -> dict[str, Ad]:
    return {VARIANT_RENT: render_rent_ad(test), VARIANT_BUY: render_buy_ad(test)}


def outreach_message(plot: Plot, calc: Calculation, cfg: Config) -> str:
    """Erstkontakt zum Grundstuecksverkaeufer - kurz, konkret, ohne Blabla."""
    return f"""Guten Tag,

Ihr Inserat "{plot.title}" ({plot.url}) ist mir aufgefallen.

Wir realisieren kleine Wohnprojekte mit Tiny Houses und pruefen Ihr
Grundstueck ({sqm(plot.area_sqm)}) fuer {calc.units} Einheit(en).

Drei Fragen, die ueber alles Weitere entscheiden:
1) Liegt ein Bebauungsplan vor, und ist Wohnbebauung zulaessig?
2) Ist das Grundstueck erschlossen (Strom, Wasser, Abwasser) - oder faellt
   die Erschliessung noch an?
3) Gibt es Lasten oder Baulasten im Grundbuch?

Bei passenden Rahmenbedingungen koennen wir kurzfristig entscheiden und
zahlen ohne Finanzierungsvorbehalt. Zum aufgerufenen Preis von
{eur(calc.plot_price)} wuerde ich gern ins Gespraech kommen.

Viele Gruesse"""
