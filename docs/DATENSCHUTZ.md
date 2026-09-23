# Datenschutz: echte Daten sieht keine KI

Die Vorgabe: Das Programm wird mit Hilfe eines KI-Assistenten (Claude)
entwickelt – aber die KI bekommt **nie** echte Mieterdaten zu sehen. Keine
Namen, keine IBANs, keine Beträge echter Mieter. Die KI arbeitet nur mit
erfundenen Daten („Max Mustermann“).

Das ist nicht nur ein Versprechen, sondern mehrfach technisch abgesichert.

## Schicht 1 – Code und Daten liegen getrennt

| | Ort | enthält | in git? | KI sieht es? |
|---|---|---|---|---|
| Programm | Projektordner | nur Code, Doku, Tests | ja | ja |
| Demo | `daten_demo/` im Projekt | erfundene Daten | nein (wird erzeugt) | ja |
| **Echte Daten** | `~/Hausverwaltung-Daten` (außerhalb!) | Datenbank, Schlüssel, Kontoauszüge | **nie** | **nein** |

Der echte Datenordner liegt absichtlich **außerhalb** des Projektordners.
Ein KI-Assistent arbeitet im Projektordner; was nicht dort liegt, kommt ihm
nicht unter. Legt jemand den Datenordner doch ins Projekt, warnt das Programm
bei jedem Start. Außerdem schließt `.gitignore` alle Datenbanken,
Schlüssel und Datenordner aus.

Die KI-Sitzungen in der Cloud (wie die, in der dieses Programm entstanden
ist) haben nur Zugriff auf das GitHub-Repository – und dort liegen nie Daten.

## Schicht 2 – Sperren für Claude Code auf dem eigenen PC

Wird Claude Code einmal direkt auf dem Rechner mit den echten Daten benutzt,
greifen zwei Sperren aus `.claude/settings.json`:

1. **deny-Regeln:** Lesen/Schreiben in `~/Hausverwaltung-Daten`, von
   `verwaltung.db`, `schluessel.key` und den Bank-Ordnern ist verboten.
2. **Wächter** (`.claude/hooks/datenschutz.py`): prüft vor *jedem*
   Werkzeug-Aufruf, ob ein Pfad oder Befehl auf echte Daten zielt – auch über
   Umwege wie `cat`, `sqlite3` oder `python -m verwaltung monat` (das würde echte
   Namen ausgeben). Solche Aufrufe werden blockiert; erlaubt ist nur `--demo`.

Grenze, ehrlich gesagt: Die Sperren schützen vor versehentlichem Zugriff.
Wer selbst echte Daten in den Chat kopiert oder einen Screenshot der
Oberfläche mit echten Mietern hochlädt, umgeht sie. Deshalb: **Für Fragen und
Fehlermeldungen immer die Demo nachstellen oder pseudonymisieren** (unten).

## Schicht 3 – Datensparsamkeit im Programm

* **IBANs werden nicht gespeichert.** In der Datenbank steht nur eine Kennung
  (HMAC-SHA256 mit einem geheimen Schlüssel aus dem Datenordner) und die
  letzten vier Stellen für die Anzeige („Konto …4711“). Wiedererkennen
  funktioniert trotzdem, zurückrechnen nicht ohne den Schlüssel.
* **Keine KI, kein Internet zur Laufzeit.** Die Zuordnung ist ein
  nachvollziehbares Punktesystem, das komplett auf dem eigenen PC läuft.
  Kein Kontoauszug verlässt den Rechner.
* **Oberfläche nur lokal:** Der Webserver lauscht ausschließlich auf
  127.0.0.1 und lehnt Anfragen fremder Webseiten ab.
* **Protokoll:** Jede Zuordnung, jedes Ignorieren und jeder Import wird mit
  Zeitpunkt festgehalten.

## Schicht 4 – Pseudonymisieren, wenn doch ein Beispiel gebraucht wird

Die Bank ändert ihr Exportformat, eine Zahlung wird nicht erkannt: Dann braucht
der Helfer ein Beispiel. Nie das Original weitergeben, sondern:

```
python -m verwaltung anonymisieren C:\Pfad\zum\export.csv
```

Das erzeugt `export_anonym.csv`:

* jeder Name → erfundener Name (derselbe echte Name wird immer zum selben
  erfundenen, damit Zusammenhänge erhalten bleiben),
* jede IBAN → erfundene IBAN (Bankleitzahl 00000000),
* im Verwendungszweck bleiben nur unpersönliche Wörter (Miete, Oktober, KdU,
  WE …), alles andere wird „xxxx“; lange Nummern werden durch andere ersetzt,
* nicht benötigte Spalten (BIC, Mandat, Saldo, Kopfzeilen mit Kontoinhaber)
  werden geleert,
* die Zuordnung echt → erfunden wird nirgends gespeichert.

Beträge und Daten bleiben, weil ohne sie kein Abgleich zu prüfen ist. Die
Kopie vor dem Weitergeben einmal selbst ansehen.

## Pflichten, die beim Betreiber bleiben

* **Backup** des Datenordners (inkl. `schluessel.key`) – verschlüsselt, z. B.
  auf BitLocker-Laufwerk oder verschlüsseltem Cloud-Speicher.
* **Festplattenverschlüsselung** des PCs (BitLocker) und eigenes Windows-Konto
  für die Angestellte.
* **Aufbewahrung/Löschung:** Buchungsbelege unterliegen steuerlichen
  Aufbewahrungsfristen; Interessentendaten spätestens 6 Monate nach Abschluss
  löschen (kommt mit dem Interessenten-Modul).
* **Verzeichnis von Verarbeitungstätigkeiten** (Art. 30 DSGVO): Mietverwaltung
  und Mieteingang als Tätigkeit eintragen, Rechtsgrundlage Vertrag
  (Art. 6 Abs. 1 b DSGVO).
