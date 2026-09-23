# Gesamtkonzept: ein Werkzeug für die ganze Hausverwaltung

Ausgangslage: 200–300 Einheiten, ein Eigentümer, eine Angestellte mit rund
20 Stunden pro Woche. Ziel ist **eine** Datenbank, in der jeder Vorgang des
Unternehmens abgebildet ist, und die möglichst viel Routine selbst erledigt,
damit die 20 Stunden für die Dinge bleiben, die einen Menschen brauchen.

Grundregel für jede Automatik: **Das Programm bereitet vor, der Mensch gibt
frei**, wo Geld, Fristen oder Rechte von Mietern berührt sind (Mahnung,
Kündigung, Kautionsabrechnung). Wo nichts schiefgehen kann (Zahlung erkennen,
Interessenten benachrichtigen, Erinnerungen), läuft sie von allein.

---

## 1. Die Prozesse im Unternehmen

| # | Prozess | Auslöser | Was automatisch passieren kann |
|---|---|---|---|
| 1 | **Mieteingang prüfen** | Monatsanfang | Kontoauszug einlesen, Zahlungen Mietern zuordnen, Liste „wer fehlt“ ✅ *gebaut* |
| 2 | **Mahnwesen** | Miete nach Fälligkeit + Karenz offen | Erinnerung → 1. Mahnung → 2. Mahnung vorbereiten; ab 2 Monatsmieten Rückstand Hinweis auf § 543 BGB |
| 3 | **Kündigung durch Mieter** | Brief/E-Mail geht ein | Frist berechnen (§ 573c BGB: 3 Monate, Zugang bis 3. Werktag), Bestätigung erzeugen, Einheit „frei ab …“ setzen |
| 4 | **Neuvermietung** | Einheit wird frei | passende Interessenten aus dem Pool **automatisch anschreiben**, Besichtigungstermine anbieten |
| 5 | **Interessenten verwalten** | Anfrage über Portal, Telefon, Website | Anfrage erfassen (später per E-Mail-Import), Suchprofil, Status, Löschung nach 6 Monaten |
| 6 | **Mieterwechsel** | Vertrag unterschrieben | Checkliste: Übergabeprotokoll, Zählerstände, Schlüssel, Kaution-Eingang, Wohnungsgeberbestätigung (§ 19 BMG, 2 Wochen), Zähler ummelden |
| 7 | **Auszug & Kaution** | Mietende | Abnahmetermin, Protokoll, Kautionsabrechnung vorbereiten (Einbehalt für ausstehende NK-Abrechnung) |
| 8 | **Nebenkostenabrechnung** | jährlich, Frist 12 Monate (§ 556 Abs. 3 BGB) | Kosten je Objekt aus den Abbuchungen, Umlageschlüssel, Vorauszahlungen aus dem Mieteingang, Anpassung der Vorauszahlung |
| 9 | **Schäden & Reparaturen** | Meldung vom Mieter | Ticket, Handwerker beauftragen, Termin, Rechnung, Kosten dem Objekt zuordnen |
| 10 | **Wiederkehrende Pflichten** | Kalender | Rauchmelder, Heizungswartung, Gasprüfung, Trinkwasser, Schornsteinfeger, Winterdienst – Erinnerung vorab |
| 11 | **Mieterhöhung** | Staffel/Index/Mietspiegel | Termine berechnen (§ 558 BGB: 15 Monate, Kappungsgrenze), Schreiben vorbereiten |
| 12 | **Buchhaltung & Auswertung** | monatlich/jährlich | Soll/Ist, Leerstand, Rendite je Objekt, Export für den Steuerberater |

Die Angestellte arbeitet dann nicht mehr Listen ab, sondern ein **Cockpit**:
„Heute zu tun: 3 Mahnungen freigeben, 1 Kündigung bestätigen, 2 Übergaben
diese Woche, Rauchmelder Musterstr. 5 in 14 Tagen fällig.“

---

## 2. Die Datenbank

Alles hängt an wenigen Stammdaten – deshalb wurden die zuerst sauber gebaut:

```
Objekt ──< Einheit ──< Mietvertrag >── Person (Mieter)
  │           │            │
  │           │            ├──< Sollmiete (Staffel, Erhöhungen)     ✅
  │           │            ├──< Zahlung >── Bankbuchung             ✅
  │           │            ├──< Mahnung                              (2)
  │           │            ├──< Kündigung                            (3)
  │           │            └──< Dokument / Notiz                     (9)
  │           ├──< Zähler, Ausstattung                               (6)
  │           └──< Leerstand / Vermietungsvorgang >── Interessent    (4,5)
  ├──< Wartung / Prüfpflicht                                         (10)
  ├──< Ticket >── Handwerker                                         (9)
  └──< Kosten (aus Abbuchungen) ──> Nebenkostenabrechnung            (8)

Aufgabe / Frist  ← wird von allen Modulen erzeugt                    (Cockpit)
Protokoll        ← jede Änderung, wer/was/wann                       ✅
```

Technik: eine SQLite-Datei im Datenordner, Python ohne Fremdpakete, Oberfläche
im Browser auf dem eigenen Rechner. Das trägt locker 300 Einheiten und
Jahrzehnte an Buchungen.

---

## 3. Reihenfolge des Ausbaus

| Stufe | Inhalt | Warum in dieser Reihenfolge |
|---|---|---|
| **1** ✅ | Stammdaten + Mieteingang | spart jeden Monat Stunden, und die Stammdaten braucht alles Weitere |
| **2** | Mahnwesen: Vorlagen, Stufen, PDF/E-Mail, Ratenvereinbarung | baut direkt auf „wer fehlt“ auf |
| **3** | Aufgaben-Cockpit und Fristen | ab hier arbeitet die Angestellte eine Liste ab statt Zettel |
| **4** | Kündigung → Leerstand → Interessenten-Automatik | der Ablauf „Mieter kündigt, Interessenten werden angeschrieben“ |
| **5** | Mieterwechsel-Checkliste, Übergabeprotokoll, Kaution | schließt die Lücke zwischen 4 und 1 |
| **6** | Tickets und Wartungspflichten | Haftungsthemen (Verkehrssicherung) |
| **7** | Nebenkostenabrechnung | die Abbuchungen liegen ab Stufe 1 schon in der Bank-Datei vor |
| **8** | Mehrere Arbeitsplätze | siehe unten |

### Stufe 4 im Detail (der gewünschte Ablauf)

1. Kündigung wird erfasst → Programm rechnet das Mietende und schreibt die
   Eingangsbestätigung (Vorlage, Freigabe per Klick).
2. Die Einheit bekommt den Status „wird frei am …“ mit Eckdaten (Fläche,
   Zimmer, Warmmiete, Etage, Haustiere ja/nein).
3. Abgleich mit dem Interessentenpool: Ort/Objekt, Zimmer, max. Warmmiete,
   Einzugstermin, Haustiere, WBS. Ergebnis: Liste passender Interessenten,
   sortiert nach Passung und Anfragedatum.
4. Die Angestellte gibt die Liste frei → **alle erhalten automatisch eine
   E-Mail** mit Exposé und Besichtigungsterminen (Terminwahl per Link).
5. Rückmeldungen landen im Vorgang, Selbstauskunft per Formular, Auswahl,
   Vertrag aus Vorlage → weiter mit Stufe 5.

Rechtliche Leitplanken: Interessenten nur mit Einwilligung speichern und
anschreiben (Art. 6 Abs. 1 a DSGVO), Daten spätestens 6 Monate nach Abschluss
löschen, keine Auswahl nach AGG-geschützten Merkmalen – das Suchprofil fragt
deshalb nur sachliche Kriterien ab.

### Mehrere Arbeitsplätze (Stufe 8)

Solange Eigentümer und Angestellte am selben Rechner arbeiten, reicht die
lokale Lösung. Arbeiten beide von verschiedenen Orten, läuft dieselbe Oberfläche
auf einem kleinen Server (Büro-PC, NAS oder gemieteter Server in Deutschland)
mit Anmeldung und HTTPS. Die SQLite-Datei **nicht** über Dropbox/OneDrive
teilen – gleichzeitige Zugriffe beschädigen sie.

---

## 4. Offene Fragen an euch

1. **Bank:** Welche Bank(en), wie viele Konten laufen Mieten ein? (Bestimmt den
   Export und später die direkte Anbindung.)
2. **Bestand:** Wo stehen Mieter und Mieten heute – Excel, eine Software, Papier?
3. **Mieternummer:** Gibt es eine? Wenn Mieter sie im Verwendungszweck angeben,
   wird die Erkennung praktisch fehlerfrei. Ein Rundschreiben lohnt sich.
4. **Interessenten:** Über welche Portale kommen Anfragen, in welches Postfach?
5. **Rechner:** Windows? Arbeiten beide am selben PC?
6. **Mahnwesen:** Wie wird heute gemahnt (Brief, E-Mail), welche Stufen, welche
   Fristen?
