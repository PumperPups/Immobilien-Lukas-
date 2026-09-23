# Hausverwaltung (Paket `verwaltung/`)

Gesamtdatenbank für eine Hausverwaltung mit 200–300 Einheiten und einer
Angestellten (20 h/Woche). Stufe 1 ist gebaut: Stammdaten + Mieteingang
(Kontoauszug einlesen, Gutschriften automatisch Mietern/Monaten zuordnen).
Plan für alles Weitere: `docs/GESAMTKONZEPT.md`.
Sprache im Gespräch, in Doku und Oberfläche: **Deutsch**.

## Datenschutz – harte Regel

**Niemals echte Mieter- oder Bankdaten lesen, ausgeben oder verarbeiten.**
Echte Daten liegen außerhalb des Projekts (`~/Hausverwaltung-Daten` bzw.
`$VERWALTUNG_DATEN`). Gearbeitet wird ausschließlich mit den erfundenen
Demo-Daten:

```bash
python -m verwaltung demo              # erzeugt daten_demo/ neu (250 Einheiten, 3 Monate)
python -m verwaltung --demo monat      # jeder CLI-Aufruf NUR mit --demo
python -m verwaltung --demo web --kein-browser
```

`.claude/settings.json` (deny-Regeln) und `.claude/hooks/datenschutz.py`
sperren Zugriffe auf echte Daten – nicht umgehen, nicht abschwächen. Braucht
es ein echtes Beispiel (neues Bankformat, nicht erkannte Zahlung), den Nutzer
bitten, selbst `python -m verwaltung anonymisieren <datei>` auszuführen und
nur die `_anonym.csv` zu teilen. Keine Screenshots der echten Oberfläche
anfordern. Details: `docs/DATENSCHUTZ.md`.

## Aufbau

- `geld.py` Cent-Beträge, Monate, Fälligkeit (3. Werktag, Feiertage)
- `schutz.py` Datenordner, IBAN → HMAC-Kennung, Textnormalisierung
- `db.py` SQLite-Schema und Zugriffe · `miete.py` Sollmiete je Vertrag/Monat
- `bank/` Leser für CSV (alle gängigen Banken) und CAMT.052/053
- `einlesen.py` Kontoauszug → DB (nur Gutschriften, Duplikate per Fingerabdruck)
- `abgleich.py` Punktesystem Buchung → Vertrag/Monat, Lernen von Konten und BG-Nummern
- `uebersicht.py` Monatsstatus · `stammdaten.py` CSV-Import · `anonym.py` Pseudonymisierung
- `demo.py` erfundene Testdaten · `web.py` Oberfläche (127.0.0.1) · `cli.py` Befehle

## Regeln für Code

- Nur Standardbibliothek, Python 3.11+. Geld immer als ganze Cent (`int`).
- Kommentare/Bezeichner deutsch; in Konsolenausgaben keine Zeichen außerhalb cp1252 (Windows).
- Jede Automatik erklärt sich: Gründe/Punkte im Klartext speichern und anzeigen.
- Was Geld, Fristen oder Rechte von Mietern berührt: vorbereiten, Mensch gibt frei.
- Tests: `python -m unittest discover -s tests` – neue Logik bekommt Tests mit erfundenen Daten
  (`tests/hilfe_verwaltung.py`, IBANs mit BLZ 00000000 über `iban_bauen`).
