# Tiny-House-Scout

Unbebaute Grundstücke finden, bewerten – und **vor dem Kauf** messen, ob in
dieser Gegend überhaupt jemand in ein Tiny House ziehen will. Zur Miete oder
zum Kauf.

Die Idee dahinter: Man kennt die Gegend nicht, in der das günstige Grundstück
liegt. Also wird nicht geraten, sondern getestet. Für jede Region gehen zwei
Anzeigen raus – eine **Mietanzeige** (X € im Monat) und eine **Kaufanzeige**
(Festpreis Y €). Wer sich meldet, wird erfasst. Aus den Anfragen entsteht ein
Nachfrage-Index je Region, der zwei Dinge steuert:

1. welche Grundstücke oben auf der Liste landen, und
2. was man für das Grundstück überhaupt noch bieten darf.

Damit dreht sich die übliche Reihenfolge um: erst die Nachfrage, dann der Kauf.

```
Portale/CSV  ──▶  scan  ──▶  Bewertung  ──▶  Shortlist
                                                 │
                                                 ▼
                                        Anzeigen Miete + Kauf
                                                 │
                                          Anfragen (Leads)
                                                 │
                        ┌────────────────────────┴───────────────┐
                        ▼                                        ▼
              Nachfrage-Index je Region              Maximalgebot fürs Grundstück
                        │                                        │
                        └──────────▶ zurück in die Bewertung ◀───┘
```

## Schnellstart

Es wird nichts installiert, keine Fremdpakete, nur Python 3.11+.

```bash
python3 -m tinyhaus init                 # config.json + Datenbank anlegen
python3 -m tinyhaus scan --bericht       # Inserate holen, bewerten, Bericht schreiben
python3 -m tinyhaus test --auto 3        # Anzeigen für 3 ungetestete Regionen bauen
python3 -m tinyhaus veroeffentlicht TH-34-01
python3 -m tinyhaus lead TH-34-01 --interesse miete --miete 780 --qualifiziert
python3 -m tinyhaus nachfrage            # was der Markt tatsächlich sagt
python3 -m tinyhaus verhandlung demo:demo-001
```

Ohne Konfiguration läuft die Quelle `demo` mit zwölf Beispielinseraten – die
komplette Kette lässt sich damit durchspielen, bevor ein echtes Portal
angebunden ist.

## Die Befehle

| Befehl | Was er tut |
| --- | --- |
| `init` | Beispielkonfiguration und Datenbank anlegen |
| `scan [--quelle X] [--bericht]` | Inserate holen, unbebaute Bauplätze filtern, bewerten |
| `liste [--min N] [--bericht]` | Shortlist der besten Grundstücke |
| `zeige <key>` | Details, Score-Aufschlüsselung, volle Kalkulation |
| `kontakt <key> [--markieren]` | Anschreiben an den Verkäufer erzeugen |
| `status <key> <status>` | neu / shortlist / kontaktiert / abgelehnt / gekauft |
| `test <key>` \| `test --auto N` | Miet- und Kaufanzeige erzeugen |
| `veroeffentlicht <label>` | Anzeige als live markieren (ab jetzt zählt sie) |
| `lead <label> --interesse ...` | Anfrage erfassen |
| `nachfrage` | gemessene Nachfrage je PLZ-Gebiet |
| `verhandlung <key>` | Maximalgebot aus echter Zahlungsbereitschaft |
| `bericht` | HTML-Übersicht unter `out/report.html` |
| `stand` | Kennzahlen der Pipeline |

## Was gefiltert wird

Gesucht sind **Grundstücke ohne Haus**. Der Filter wirft raus:

* bebaute Grundstücke (Einfamilienhaus, Hof, Halle) und – sofern nicht
  ausdrücklich erlaubt – Abrissobjekte,
* Ackerland, Wald, Garten- und Freizeitgrundstücke (dort darf niemand wohnen),
* Bauerwartungsland, solange `allow_bauerwartungsland` aus ist,
* zu kleine, zu große, zu teure Flächen (alles in `config.json`),
* Regionen außerhalb des Suchgebiets.

Inserate ohne Preis („Preis auf Anfrage") fliegen nicht weg, sondern werden
als *manuell prüfen* markiert – da steckt oft das beste Geschäft drin.

Bewertet wird danach mit acht Kriterien (Quadratmeterpreis, Gesamtpreis,
Kapazität, Baurecht, Erschließung, Anbieter, Standzeit, gemessene Nachfrage).
Jede Teilnote steht im Klartext daneben – `zeige <key>` zeigt sie.

## Woher die Grundstücke kommen

| Quelle | Status |
| --- | --- |
| `demo` | Beispieldaten, immer verfügbar |
| `csv` | eigene Exporte/Listen, `data/import/*.csv`, deutsche Spaltennamen |
| `kleinanzeigen` | HTML-Suche, robots.txt-konform, **nicht** standardmäßig aktiv |
| `immoscout24` | offizielle API, braucht Partnervertrag |

**Wichtig:** Automatisiertes Abrufen und vor allem automatisiertes *Einstellen*
von Anzeigen verstößt gegen die AGB der großen Portale und kostet im Zweifel
den Account – mitsamt allen laufenden Anzeigen. Deshalb:

* Der Scanner hält sich an robots.txt und bricht bei 403/429 ab, statt zu tricksen.
* Anzeigen werden **nicht** automatisch eingestellt. `test` erzeugt fertige
  Texte plus Einstell-Checkliste unter `out/anzeigen/<LABEL>/` – Copy-Paste,
  zwei Minuten pro Anzeige. Sobald ein offizieller Zugang vorliegt, tritt an
  diese Stelle ein API-Publisher; die Schnittstelle dafür steht schon.

Details: [docs/RECHTLICHES.md](docs/RECHTLICHES.md).

## Was die Zahlen bedeuten

Aus Grundstückspreis, Baukosten, Erschließung, Nebenkosten und Puffer entsteht
eine Gesamtkalkulation. Daraus zwei Preise:

* **Miete** = Zielrendite auf das eingesetzte Kapital, korrigiert um
  Leerstand, plus nicht umlagefähige Kosten.
* **Kaufpreis** = Kosten je Einheit + Teilungskosten + Zielmarge.

Und rückwärts, sobald Anfragen vorliegen: Wenn der Markt nur 800 € Miete
zahlt, wie viel darf das Grundstück dann noch kosten? Genau diese Zahl liefert
`verhandlung` – das ist der Betrag, mit dem man in das Gespräch geht.

Alle Annahmen stehen in `config.json` und sind dokumentiert in
[docs/KALKULATION.md](docs/KALKULATION.md). Sie sind Startwerte, keine
Wahrheiten – wer echte Angebote von Tiny-House-Herstellern hat, trägt sie ein.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Aufbau

```
tinyhaus/
  models.py     Grundstück, Score, Markttest, Lead, Nachfrage-Signal
  config.py     alle Annahmen, per config.json überschreibbar
  classify.py   deutsche Inseratstexte -> Baurecht, Bebauung, Erschließung
  scoring.py    Ausschlusskriterien + acht gewichtete Teilnoten
  pricing.py    Kalkulation und Maximalgebot (rückwärts gerechnet)
  demand.py     Anzeigentexte Miete/Kauf + Verkäufer-Anschreiben
  pipeline.py   der Ablauf: scan -> bewerten -> testen -> verhandeln
  storage.py    SQLite
  report.py     HTML- und Konsolenbericht
  sources/      demo, csv, kleinanzeigen, immoscout24
  publish/      entwurf (Dateien), api (Platzhalter)
```

Nächste Schritte: [docs/ROADMAP.md](docs/ROADMAP.md).
