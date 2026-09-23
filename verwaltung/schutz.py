"""Datenschutz-Bausteine: wo die echten Daten liegen, IBAN nur als Kennung.

Grundsatz: echte Mieterdaten liegen NIE im Projektordner, sondern in einem
eigenen Datenordner (Standard: ~/Hausverwaltung-Daten, per Umgebungsvariable
VERWALTUNG_DATEN oder --daten anders waehlbar). Der Projektordner - und damit
alles, was ein KI-Assistent beim Programmieren sieht - enthaelt nur Code und
erfundene Demo-Daten (daten_demo/, Max Mustermann & Co.).

IBANs werden gar nicht erst gespeichert: in der Datenbank steht nur eine
Kennung (HMAC-SHA256 mit einem Schluessel aus dem Datenordner) und die
letzten vier Stellen fuer die Anzeige ("…4711"). Wiedererkennen geht damit
trotzdem: dieselbe IBAN ergibt immer dieselbe Kennung.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
DEMO_ORDNER = PROJEKT / "daten_demo"
STANDARD_ORDNER = Path.home() / "Hausverwaltung-Daten"


def daten_ordner(angabe: str | None = None, demo: bool = False) -> Path:
    if demo:
        return DEMO_ORDNER
    if angabe:
        return Path(angabe).expanduser().resolve()
    umgebung = os.environ.get("VERWALTUNG_DATEN")
    return Path(umgebung).expanduser().resolve() if umgebung else STANDARD_ORDNER


def im_projekt(ordner: Path) -> bool:
    """Liegt der Ordner im Projekt (und damit im Blickfeld des KI-Assistenten)?"""
    try:
        ordner.resolve().relative_to(PROJEKT)
    except ValueError:
        return False
    return ordner.resolve() != DEMO_ORDNER.resolve()


# ------------------------------------------------------------------ IBAN

def iban_normal(text: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()


def iban_gueltig(text: str | None) -> bool:
    s = iban_normal(text)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[0-9A-Z]{10,30}", s):
        return False
    umgestellt = s[4:] + s[:4]
    zahl = "".join(str(int(z, 36)) for z in umgestellt)
    return int(zahl) % 97 == 1


def iban_ende(text: str | None) -> str:
    s = iban_normal(text)
    return s[-4:] if len(s) >= 4 else ""


def iban_bauen(land: str, bban: str) -> str:
    """Pruefziffer rechnen - fuer Demo- und Ersatz-IBANs."""
    umgestellt = bban + land + "00"
    zahl = int("".join(str(int(z, 36)) for z in umgestellt))
    return f"{land}{98 - zahl % 97:02d}{bban}"


class Schluessel:
    """Geheimer Schluessel im Datenordner fuer die IBAN-Kennungen.

    Geht er verloren, erkennt das Programm bekannte Zahler nicht mehr
    automatisch (Zuordnungen muessen neu gelernt werden) - deshalb gehoert
    er mit ins Backup. Ohne Datenordner ist er wertlos.
    """

    DATEI = "schluessel.key"

    def __init__(self, ordner: Path):
        pfad = ordner / self.DATEI
        if not pfad.exists():
            ordner.mkdir(parents=True, exist_ok=True)
            pfad.write_text(secrets.token_hex(32), encoding="ascii")
        self._geheim = bytes.fromhex(pfad.read_text(encoding="ascii").strip())

    def kennung(self, iban: str | None) -> str | None:
        s = iban_normal(iban)
        if len(s) < 8:
            return None
        return hmac.new(self._geheim, s.encode(), hashlib.sha256).hexdigest()[:32]


# ------------------------------------------------------------------ Texte

_UMLAUTE = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})


def falten(text: str | None) -> str:
    """Fuer Vergleiche: klein, Umlaute weg, Akzente weg.

    Banken schreiben Umlaute mal als ae, mal als a, mal richtig. Deshalb
    wird beides auf den Grundbuchstaben gefaltet: Müller = Mueller = Muller.
    """
    s = (text or "").lower().translate(_UMLAUTE)
    s = s.replace("ae", "a").replace("oe", "o").replace("ue", "u")
    s = unicodedata.normalize("NFKD", s)
    return "".join(z for z in s if not unicodedata.combining(z))


def woerter(text: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", falten(text))
