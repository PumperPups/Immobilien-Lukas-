# Mieteingang: Einrichtung und Monatsroutine

## Was das Programm macht

Kontoauszug rein → jede Gutschrift wird dem richtigen Mieter und Monat
zugeordnet → eine Liste zeigt, wer bezahlt hat, wer teilweise, wer gar nicht.
Was nicht sicher erkannt wird, landet unter **Zu prüfen** – mit Vorschlägen,
ein Klick genügt. Dabei lernt das Programm: Wer einmal zugeordnet wurde, wird
nächsten Monat automatisch erkannt.

Mit den Demo-Daten (250 Einheiten, drei Monate) werden **97 %** der
Gutschriften automatisch zugeordnet. Der Rest sind echte Zweifelsfälle
(Kaution, Stadtwerke-Erstattung, Ehepaar mit gleichem Namen).

---

## Einmalig einrichten (ca. 30 Minuten)

1. **Python installieren** (3.11 oder neuer): python.org → Download → beim
   Installieren den Haken „Add Python to PATH“ setzen.
2. **Programm holen:** Ordner von GitHub herunterladen (grüner Knopf „Code“ →
   „Download ZIP“) und entpacken – oder `git clone`.
3. **Erst mal mit Demo-Daten ausprobieren:** Doppelklick auf
   `Demo starten.cmd`. Es öffnet sich der Browser mit erfundenen Mietern
   (Max Mustermann & Co.). Alles anklicken, nichts kann kaputtgehen.
4. **Echten Datenordner anlegen:**
   ```
   python -m verwaltung init
   ```
   legt `C:\Users\<Name>\Hausverwaltung-Daten` an. Dort liegen später
   Datenbank, Schlüssel und Kontoauszüge – **nicht** im Programmordner.
   Wer einen anderen Ort will (z. B. verschlüsseltes Laufwerk): Umgebungsvariable
   `VERWALTUNG_DATEN` setzen oder `--daten <Ordner>` angeben.
5. **Stammdaten einlesen:** `Mieteingang starten.cmd` → Reiter
   *Einstellungen* → „Vorlage herunterladen“. Eine Zeile je Mietvertrag
   ausfüllen (oder die vorhandene Excel-Liste in diese Spalten bringen), als CSV
   speichern und in das Feld ziehen. Pflicht sind nur **Nachname, Objekt,
   Mietbeginn** und **Miete** – alles andere hilft der Erkennung:

   | Spalte | wofür |
   |---|---|
   | Mieternummer | Schlüssel; steht sie im Verwendungszweck, ist die Zuordnung sicher |
   | Kaltmiete, Nebenkosten | Sollmiete (oder nur „Gesamtmiete“) |
   | IBAN Zahler | Konto, von dem der Mieter zahlt – wird sofort in eine Kennung umgewandelt |
   | IBAN Zahler 2 | z. B. Jobcenter |
   | Referenzen | z. B. BG-Nummer des Jobcenters |
   | Mitmieter | Partner, der evtl. überweist |
   | Rueckstand | offener Betrag bei Start (positiv = Mieter schuldet) |
   | Mietende | bei Auszug |

   Erneutes Einlesen ändert nur, was sich geändert hat. Mieterhöhung: neue
   Miete eintragen und Spalte „Miete gueltig ab“ (z. B. `2026-11`) setzen.
6. **Erfassungsbeginn:** Unter *Einstellungen* den Monat setzen, ab dem
   geprüft wird (z. B. der aktuelle). Davor gilt nichts als offen.

Die Stammdaten-CSV enthält IBANs – nach dem Einlesen löschen.

---

## Monatsroutine (ca. 15 Minuten)

1. **Online-Banking** → Umsätze → Zeitraum ab dem letzten Export (Überschneidung
   ist egal) → **Export als CAMT** (falls angeboten, sonst CSV) → speichern in
   `Hausverwaltung-Daten\bank\eingang`.
2. **Doppelklick `Mieteingang starten.cmd`.** Die Datei wird eingelesen,
   abgeglichen und ins Archiv verschoben; der Browser zeigt den aktuellen Monat.
   (Alternativ die Datei im Reiter *Import* einfach ins Fenster ziehen.)
3. **Zu prüfen** abarbeiten: Vorschlag anklicken. Der Haken „Zahlerkonto merken“
   sorgt dafür, dass der Zahler nächsten Monat automatisch erkannt wird.
   Stadtwerke, Zinsen und Ähnliches: „Zahler immer ignorieren“.
4. **Übersicht** → Filter „Nicht bezahlt“ → das ist die Liste für
   Erinnerungen/Mahnungen. „Offene Posten als CSV“ exportiert sie für Excel.

Ab dem 3. Werktag (plus 3 Karenztage, einstellbar) steht „überfällig“ statt
„offen“. Samstage und bundesweite Feiertage zählen nicht mit.

---

## Wie die Zuordnung entscheidet

Jede Gutschrift bekommt je Vertrag Punkte – die Gründe stehen immer daneben:

| Hinweis | Punkte |
|---|---|
| Konto ist als Zahler dieses Mieters bekannt | 60 |
| Mieternummer oder Referenz (BG-Nummer …) im Verwendungszweck | 60 |
| Nachname im Namen oder Zweck | 25 |
| … und Vorname dazu | +20 |
| Adresse im Zweck | 10 |
| Betrag = Sollmiete | 20 |

Automatisch zugeordnet wird nur bei **mindestens 45 Punkten und 20 Punkten
Vorsprung** vor dem Zweitbesten. Kautionen werden nie automatisch verbucht.

**Monat:** steht einer im Zweck („Miete Oktober“, „10/2026“), gilt der; sonst
das Buchungsdatum – ab dem 25. zählt die Zahlung für den Folgemonat.

**Verteilung:** Zahlt jemand mehr als die Monatsmiete, füllt der Rest zuerst
ältere offene Monate (Nachzahlung); was dann übrig ist, bleibt als Guthaben stehen.

**Jobcenter & Co.:** Ein Konto, das für mehrere Mieter zahlt, zählt nicht als
Hinweis. Entschieden wird über Name und Kennung im Zweck. Nach der ersten
Zuordnung merkt sich das Programm die BG-Nummer – danach geht es automatisch.

**Falsch zugeordnet?** In der Übersicht die Zeile anklicken → „Zuordnung
aufheben“. Die Gutschrift steht wieder unter *Zu prüfen*.

---

## Bank direkt anbinden (nächster Ausbau)

Heute: Export aus dem Online-Banking, zwei Minuten im Monat. Das ist bewusst
der erste Schritt – funktioniert mit jeder Bank sofort, ohne Verträge, und
die Zugangsdaten zur Bank bleiben, wo sie sind.

Der automatische Abruf ist der nächste Schritt. Drei Wege, in der Reihenfolge
der Empfehlung:

1. **FinTS (HBCI) direkt vom eigenen PC.** Sparkassen, Volks-/Raiffeisenbanken,
   Deutsche Bank, Commerzbank, Postbank, ING, DKB unterstützen es. Das Programm
   meldet sich mit Online-Banking-Zugang an, die Freigabe kommt per pushTAN aufs
   Handy, die Umsätze landen direkt im Abgleich. Keine Daten laufen über Dritte.
   Voraussetzung: kostenlose Produktregistrierung bei der Deutschen Kreditwirtschaft
   (dauert einige Wochen) und das Paket `python-fints`. Die Schnittstelle im
   Programm ist so gebaut, dass nur ein weiterer Leser neben CSV und CAMT dazukommt.
2. **Banking-Software mit Auto-Export** (z. B. Hibiscus, kostenlos, lokal):
   ruft per FinTS ab und legt Exporte automatisch in den Eingangsordner.
   Brücke, bis Weg 1 steht.
3. **Kontoinformationsdienst (PSD2-Anbieter)**: bequem, aber die Kontodaten
   laufen über einen Dienstleister – dann braucht es einen
   Auftragsverarbeitungsvertrag, und es kostet monatlich.

---

## Befehle (für Einrichtung und Fehlersuche)

```
python -m verwaltung init [--ab 2026-10]      Datenordner anlegen
python -m verwaltung vorlage                   Stammdaten-Vorlage erzeugen
python -m verwaltung stammdaten <datei.csv>    Stammdaten einlesen
python -m verwaltung import [dateien]          Kontoauszüge einlesen + abgleichen
python -m verwaltung monat [2026-10] [--offen] [--csv name.csv]
python -m verwaltung pruefen                   offene Gutschriften mit Vorschlägen
python -m verwaltung zuordnen <#> <Mieternr>   von Hand zuordnen
python -m verwaltung ignorieren <#> [--immer]
python -m verwaltung aufheben <#>
python -m verwaltung anonymisieren <datei>     Kopie ohne echte Namen/IBANs
python -m verwaltung web                       Oberfläche
python -m verwaltung demo                      Demo-Daten erzeugen
```

Jeder Befehl mit `--demo` davor arbeitet auf den erfundenen Daten.
