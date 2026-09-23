# Hausverwaltung

Eine Datenbank für die ganze Hausverwaltung: Objekte, Einheiten, Mieter,
Verträge, Zahlungen – und nach und nach alle Abläufe von der Mahnung bis zur
Neuvermietung. Gebaut für 200–300 Einheiten und eine Angestellte mit 20
Stunden pro Woche.

**Stufe 1 ist fertig: Mieteingang.** Kontoauszug der Bank einlesen, jede
Gutschrift wird automatisch dem richtigen Mieter und Monat zugeordnet, und
eine Liste zeigt, wer bezahlt hat und wer nicht.

```
Online-Banking ──Export (CAMT/CSV)──▶ Eingangsordner
                                          │
                                          ▼
                              Abgleich (Punktesystem, lernt dazu)
                               │                         │
                        sicher erkannt             unsicher
                               │                         │
                               ▼                         ▼
                    Monatsübersicht            „Zu prüfen“ mit Vorschlägen
               bezahlt / teilweise / überfällig     (ein Klick)
                               │
                               ▼
                    Offene Posten → Mahnwesen (Stufe 2)
```

## Ausprobieren (2 Minuten)

Python 3.11+ genügt, keine weiteren Pakete. Unter Windows: Doppelklick auf
**`Demo starten.cmd`**. Oder:

```bash
python -m verwaltung demo           # 250 erfundene Einheiten, 3 Monate Kontoauszüge
python -m verwaltung --demo web     # Oberfläche im Browser
```

Die Demo enthält alles, was im echten Leben vorkommt: pünktliche Zahler,
Zahlung am 28. für den Folgemonat, Teilzahler, Rückstände mit Nachzahlung,
Jobcenter als Sammelzahler, Eltern zahlen für ihr Kind, leerer
Verwendungszweck, Kaution, Stadtwerke-Erstattung, zwei Konten (CSV und CAMT).
**97 % werden automatisch zugeordnet.**

## Echt benutzen

Anleitung für Einrichtung und Monatsroutine: **[docs/MIETEINGANG.md](docs/MIETEINGANG.md)**

Kurz: `python -m verwaltung init` → Stammdaten-Vorlage ausfüllen und einlesen →
jeden Monat den Kontoauszug in den Eingangsordner legen → `Mieteingang starten.cmd`.

## Datenschutz

Echte Daten liegen außerhalb des Programmordners und nie in git. Ein
KI-Assistent, der am Programm mitarbeitet, sieht nur erfundene Daten; das ist
über Sperrregeln technisch abgesichert. IBANs werden nicht gespeichert, nur
eine Kennung. Zum Weitergeben von Beispielen gibt es
`python -m verwaltung anonymisieren`. Details:
**[docs/DATENSCHUTZ.md](docs/DATENSCHUTZ.md)**

## Wie es weitergeht

Alle Prozesse des Unternehmens, das Datenmodell und die Ausbaustufen (Mahnwesen,
Aufgaben-Cockpit, Kündigung → Interessenten automatisch anschreiben,
Mieterwechsel, Reparaturen, Nebenkosten): **[docs/GESAMTKONZEPT.md](docs/GESAMTKONZEPT.md)**

## Tests

```bash
python -m unittest discover -s tests
```
