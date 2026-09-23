"""Waechter fuer Claude Code: kein Zugriff auf echte Mieterdaten.

Laeuft vor jedem Werkzeug-Aufruf (PreToolUse, eingetragen in
.claude/settings.json). Zeigt ein Pfad oder Befehl auf den echten
Datenordner, auf Datenbank, Schluessel oder Kontoauszuege ausserhalb von
daten_demo/, wird der Aufruf blockiert (Exit-Code 2) und Claude bekommt
die Begruendung zu sehen.

Das ist die zweite Sicherung. Die erste: echte Daten liegen gar nicht im
Projektordner (Standard ~/Hausverwaltung-Daten), und die deny-Regeln in
.claude/settings.json sperren Lesen/Schreiben dort.
"""

import json
import os
import re
import sys

MELDUNG = ("Blockiert (Datenschutz): Dieser Zugriff zielt auf echte Mieter- oder Bankdaten. "
           "Arbeite mit den Demo-Daten (python -m verwaltung demo, Ordner daten_demo/). "
           "Braucht es ein echtes Beispiel, soll der Nutzer selbst 'python -m verwaltung anonymisieren <datei>' "
           "ausfuehren und nur die pseudonymisierte Kopie weitergeben.")

MUSTER = [
    r"hausverwaltung-daten",                         # Standard-Datenordner
    r"verwaltung_daten",                             # Umgebungsvariable
    r"(?<!daten_demo[/\\])verwaltung\.db",           # echte Datenbank
    r"(?<!daten_demo[/\\])schluessel\.key",          # Schluessel fuer IBAN-Kennungen
    r"(?<!daten_demo[/\\])bank[/\\](eingang|archiv)",
    r"stammdaten(?!_demo|_vorlage|\.py)[\w-]*\.csv",
    r"-m\s+verwaltung\b(?![^\n]*--demo)",           # CLI gegen echte Daten druckt echte Namen aus
]


def pfade(eingabe: dict) -> str:
    """Nur die Felder, die auf Dateien zeigen - nicht den Inhalt, der geschrieben wird."""
    teile = []
    for feld in ("file_path", "path", "pattern", "glob", "command", "notebook_path", "url"):
        wert = eingabe.get(feld)
        if isinstance(wert, str):
            teile.append(wert)
    return "\n".join(teile)


def main() -> int:
    try:
        daten = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    text = pfade(daten.get("tool_input") or {}).lower()
    if not text:
        return 0
    eigener = os.environ.get("VERWALTUNG_DATEN", "").strip().lower()
    if eigener and eigener in text:
        print(MELDUNG, file=sys.stderr)
        return 2
    for muster in MUSTER:
        if re.search(muster, text):
            print(MELDUNG, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
