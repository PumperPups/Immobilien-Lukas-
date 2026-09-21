# Loslegen

## Teil 1: Das Programm zum Laufen bringen (10 Minuten)

Voraussetzung ist Python 3.11 oder neuer. Prüfen mit `python3 --version`
(Windows: `py --version`). Falls nicht vorhanden: python.org, Installer, bei
Windows den Haken „Add Python to PATH" setzen.

```bash
git clone https://github.com/PumperPups/Immobilien-Lukas-.git
cd Immobilien-Lukas-
git checkout claude/epic-tesla-ktx6wm

python3 -m tinyhaus init            # legt config.json und die Datenbank an
python3 -m tinyhaus scan --bericht  # läuft mit 12 Beispielinseraten
```

Danach `out/report.html` im Browser öffnen. Wenn dort eine Shortlist steht,
läuft alles. Die komplette Kette einmal durchspielen:

```bash
python3 -m tinyhaus test --auto 2
python3 -m tinyhaus veroeffentlicht TH-34-01
python3 -m tinyhaus lead TH-34-01 --interesse miete --miete 800 --qualifiziert
python3 -m tinyhaus verhandlung demo:demo-001
```

Die Demodaten danach loswerden: `rm data/tinyhaus.db` und in `config.json`
unter `scan.sources` die `"demo"` durch `"csv"` ersetzen.

## Teil 2: Eigene Grundstücke reinbekommen

Der schnellste Weg ohne Portal-Vertrag ist der CSV-Import. Vorlage:
`data/fixtures/vorlage_import.csv` — Spaltennamen sind tolerant, Reihenfolge
egal, fehlende Spalten sind erlaubt.

```bash
mkdir -p data/import
cp data/fixtures/vorlage_import.csv data/import/meine-liste.csv
# Zeilen ersetzen durch das, was du gefunden hast
python3 -m tinyhaus scan --bericht
```

Woher die Zeilen kommen, ist dem Programm egal: Portal-Suche von Hand
durchgeklickt, Liste vom Makler, Gemeindeblatt, Zwangsversteigerungstermine.
Zwei Stunden Klicken ergeben 50 Zeilen — genug für den Anfang und rechtlich
völlig unproblematisch.

Wenn das trägt, lohnt der Weg über die Kleinanzeigen-Suche (`scan.sources` auf
`["kleinanzeigen"]`, eigene Such-URL unter `scan.options.kleinanzeigen.search_urls`)
oder ein IS24-Partnervertrag. Vorher [RECHTLICHES.md](RECHTLICHES.md) lesen.

## Teil 3: Die Annahmen auf deine Zahlen drehen

In `config.json`, in dieser Reihenfolge nach Wirkung:

| Wert | Woher die echte Zahl kommt |
| --- | --- |
| `costs.unit_build_eur` | drei Angebote von Tiny-House-Herstellern |
| `targets.gross_yield_rate` | was dein Kumpel mit 300 Objekten real erzielt |
| `criteria.regions` | PLZ-Anfänge, wo du hinfahren würdest (`["34","17"]`) |
| `criteria.max_price_eur` | was du tatsächlich flüssig hast |
| `targets.unit_sqm` | Größe des Hauses, das du bauen willst |

Nach jeder Änderung `python3 -m tinyhaus scan` — die Bewertung rechnet neu.

## Teil 4: Der erste echte Test (4 Wochen)

1. **Woche 1** — Eine Region festlegen. 30 bis 50 Grundstücke als CSV erfassen,
   scannen, die Top 5 anschauen. Für die beste Region Anzeigen erzeugen:
   `python3 -m tinyhaus test --auto 1`.
2. **Woche 1** — Beide Anzeigen einstellen (Texte liegen in
   `out/anzeigen/<LABEL>/`, Checkliste daneben). Danach
   `python3 -m tinyhaus veroeffentlicht <LABEL>`.
3. **Woche 2–4** — Jede Anfrage erfassen, auch die Absagen:
   `python3 -m tinyhaus lead <LABEL> --interesse miete --miete 750 --name "..." --kontakt "..."`.
   Die zwei Fragen aus dem Anzeigentext beantworten die Leute von selbst.
4. **Parallel** — Für die besten zwei Grundstücke `python3 -m tinyhaus kontakt <key>`
   und das Anschreiben rausschicken. Die drei Fragen darin (B-Plan,
   Erschließung, Grundbuchlasten) entscheiden alles Weitere.
5. **Woche 4** — `python3 -m tinyhaus nachfrage` und
   `python3 -m tinyhaus verhandlung <key>`.

### Die Entscheidungsregel

Nach vier Wochen und einer Region:

* **unter 5 Anfragen** → Region streichen. Nicht am Preis drehen, nicht die
  Anzeige „optimieren". Nächste Region, gleicher Test.
* **5 bis 15 Anfragen, Miete gewünscht** → das ist das Geschäft.
  `verhandlung` gibt dir das Maximalgebot, damit zum Verkäufer.
* **überwiegend Kaufinteresse** → sauberer, aber teurer Weg: erst
  § 34c GewO und Teilung klären, bevor du jemandem etwas zusagst.
* **viele Anfragen, alle wollen deutlich weniger zahlen** → das Modell trägt
  in dieser Gegend nicht. Diese Erkenntnis für rund 40 € Anzeigenkosten ist
  der eigentliche Gewinn des Tests.

Ein Test kostet zwei Anzeigen und vier Wochen Geduld. Ein falsch gekauftes
Grundstück kostet fünfstellig und ist jahrelang nicht loszuwerden.
