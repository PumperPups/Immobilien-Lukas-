"""Textanalyse deutscher Immobilieninserate.

Die Portale liefern Fliesstext. Hier wird daraus das, was die Bewertung
braucht: Preis, Flaeche, Baurecht, Bebauung, Erschliessung, Anbieter.
"""

from __future__ import annotations

import re

from .models import (
    LAND_AGRAR,
    LAND_BAUERWARTUNG,
    LAND_BAULAND,
    LAND_GARTEN,
    LAND_UNKNOWN,
    SELLER_COMMERCIAL,
    SELLER_PRIVATE,
    SELLER_UNKNOWN,
)

# Erst die Gruppenschreibweise (45.500), dann die einfache (21000) -
# umgekehrt wuerde aus "21000" die 210 herausgelesen.
_NUM = r"\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:,\d+)?"


def parse_number(text: str | None) -> float | None:
    """'45.000,50' -> 45000.5 ; '1,2 Mio' -> 1200000.0"""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    m = re.search(_NUM, s)
    if not m:
        return None
    raw = m.group(0).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    lowered = s.lower()
    if re.search(r"\bmio|million", lowered):
        value *= 1_000_000
    elif re.search(r"\btsd|tausend\b", lowered):
        value *= 1_000
    return value


def parse_price(text: str | None) -> float | None:
    if text is None:
        return None
    lowered = str(text).lower()
    if any(w in lowered for w in ("auf anfrage", "vb ohne", "preis auf", "vhb ohne")):
        # 'Preis auf Anfrage' -> bewusst unbekannt lassen, nicht raten.
        if not re.search(r"\d", lowered):
            return None
    return parse_number(text)


def parse_area(text: str | None) -> float | None:
    """Zieht die Grundstuecksflaeche aus Text wie '800 m²' oder 'ca. 1.250 qm'."""
    if text is None:
        return None
    m = re.search(rf"({_NUM})\s*(?:m²|m2|qm|quadratmeter)", str(text), re.I)
    if not m:
        return parse_number(text)
    return parse_number(m.group(1))


def parse_location(text: str | None) -> tuple[str | None, str | None]:
    """'34117 Kassel' -> ('34117', 'Kassel')"""
    if not text:
        return None, None
    m = re.search(r"\b(\d{5})\b[\s,-]*([A-Za-zÄÖÜäöüß .\-]+)?", text)
    if m:
        city = (m.group(2) or "").strip(" ,.-") or None
        return m.group(1), city
    return None, text.strip() or None


# --- Baurecht ----------------------------------------------------------

_BAULAND = (
    "baugrundstück", "baugrundstueck", "bauland", "bauplatz", "baugelände",
    "bebaubar", "b-plan", "bebauungsplan", "§ 34", "paragraph 34",
    "wohnbaugrundstück", "wohnbauland", "grundstück zum bauen",
)
_BAUERWARTUNG = ("bauerwartungsland", "bauerwartung", "künftiges bauland", "im flächennutzungsplan")
_GARTEN = ("gartengrundstück", "freizeitgrundstück", "kleingarten", "schrebergarten", "wochenendgrundstück", "erholungsgrundstück")
_AGRAR = ("ackerland", "landwirtschaftliche fläche", "waldgrundstück", "forstfläche", "grünland", "weideland", "ackerfläche")


def classify_land(*texts: str | None) -> str:
    """Grobe Einstufung des Baurechts. Im Zweifel: unbekannt statt Wunschdenken."""
    blob = " ".join(t.lower() for t in texts if t)
    if any(w in blob for w in _AGRAR):
        return LAND_AGRAR
    if any(w in blob for w in _GARTEN):
        return LAND_GARTEN
    if any(w in blob for w in _BAUERWARTUNG):
        return LAND_BAUERWARTUNG
    if any(w in blob for w in _BAULAND):
        return LAND_BAULAND
    return LAND_UNKNOWN


# --- Bebauung ----------------------------------------------------------

_BUILDING = (
    "einfamilienhaus", "mehrfamilienhaus", "doppelhaushälfte", "reihenhaus",
    "bungalow", "bestandsimmobilie", "wohnhaus", "bauernhaus", "hofstelle",
    "mit haus", "bebaut mit", "villa", "gewerbehalle", "scheune",
)
_TEARDOWN = ("abriss", "abrissobjekt", "abbruchobjekt", "abrissreif", "zum abriss")
_EXPLICIT_EMPTY = ("unbebaut", "unbebautes", "nicht bebaut", "freies grundstück", "leerstehendes grundstück")


def detect_building(*texts: str | None) -> tuple[bool, bool]:
    """(hat_gebaeude, ist_abrissobjekt)"""
    blob = " ".join(t.lower() for t in texts if t)
    teardown = any(w in blob for w in _TEARDOWN)
    if teardown:
        return True, True
    if any(w in blob for w in _EXPLICIT_EMPTY):
        return False, False
    has = any(w in blob for w in _BUILDING)
    return has, False


# --- Erschliessung -----------------------------------------------------

_DEVELOPED = ("voll erschlossen", "vollerschlossen", "erschlossen", "erschließung vorhanden", "anschlüsse vorhanden", "strom und wasser liegen an")
_UNDEVELOPED = ("nicht erschlossen", "unerschlossen", "erschließung nicht", "ohne erschließung", "erschließungskosten fallen an")


def detect_developed(*texts: str | None) -> bool | None:
    blob = " ".join(t.lower() for t in texts if t)
    if any(w in blob for w in _UNDEVELOPED):
        return False
    if any(w in blob for w in _DEVELOPED):
        return True
    return None


# --- Anbieter ----------------------------------------------------------

_COMMERCIAL = ("makler", "immobilien gmbh", "gewerblich", "provisionspflichtig", "courtage", "maklerprovision", "immobilienbüro")
_PRIVATE = ("privat", "von privat", "provisionsfrei", "ohne makler", "privatverkauf")


def detect_seller(*texts: str | None) -> str:
    blob = " ".join(t.lower() for t in texts if t)
    if any(w in blob for w in _COMMERCIAL):
        return SELLER_COMMERCIAL
    if any(w in blob for w in _PRIVATE):
        return SELLER_PRIVATE
    return SELLER_UNKNOWN


def enrich(plot) -> None:
    """Fuellt fehlende Felder eines Plots aus Titel und Beschreibung nach."""
    texts = (plot.title, plot.description)
    if plot.land_type == LAND_UNKNOWN:
        plot.land_type = classify_land(*texts)
    has, teardown = detect_building(*texts)
    plot.has_building = plot.has_building or has
    plot.teardown = plot.teardown or teardown
    if plot.developed is None:
        plot.developed = detect_developed(*texts)
    if plot.seller_type == SELLER_UNKNOWN:
        plot.seller_type = detect_seller(*texts)
    if plot.area_sqm is None:
        plot.area_sqm = parse_area(plot.title) or parse_area(plot.description)
