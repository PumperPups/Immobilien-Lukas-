# Rechtliche Punkte, die das Projekt kippen können

Keine Rechtsberatung – eine Liste der Stellen, an denen dieses Geschäftsmodell
in Deutschland typischerweise scheitert, damit sie früh geklärt werden. Vor dem
ersten Kauf gehört das mit Anwalt, Steuerberater und Bauamt durchgesprochen.

## 1. Anzeigen automatisch einstellen: geht nicht

Die AGB von Kleinanzeigen und der großen Immobilienportale untersagen
automatisiertes Auslesen **und** automatisiertes Einstellen von Anzeigen.
Konsequenz bei Verstoß ist in der Regel die Sperre des Kontos – inklusive aller
laufenden Anzeigen und der bereits eingegangenen Anfragen.

Deshalb erzeugt `python3 -m tinyhaus test` nur **Entwürfe** (`out/anzeigen/<LABEL>/`)
mit fertigem Text, Preis, Kategorie-Vorschlag und Checkliste. Das Einstellen
selbst dauert pro Anzeige rund zwei Minuten.

Der saubere Weg zur Automatisierung:

* gewerbliches Konto plus Partner-/Importschnittstelle beim Portal,
* OpenImmo-Export über eine Maklersoftware,
* ImmobilienScout24-API mit Partnervertrag (`IS24_CLIENT_ID`, `IS24_CLIENT_SECRET`).

Für das Einsammeln von Inseraten gilt dasselbe in Grün: Die Quelle
`kleinanzeigen` prüft robots.txt und bricht bei 403/429 ab. Wer robots.txt
abschaltet (`scan.respect_robots = false`), handelt auf eigenes Risiko.

## 2. Werbung für ein Objekt, das es noch nicht gibt

Genau das ist der Zweck des Nachfrage-Tests – und genau hier droht der Vorwurf
der irreführenden Werbung (§ 5 UWG). Deshalb steht in jeder erzeugten Anzeige,
dass das Projekt in Planung ist, der Bau von der Nachfrage abhängt und die
Anzeige kein Vertragsangebot darstellt. Diesen Absatz nicht herauslöschen.

Dazu:

* keine Fotos verwenden, die ein fertiges Objekt vorspiegeln; Symbolbilder als
  solche kennzeichnen,
* keine Reservierungsgebühren oder Anzahlungen einsammeln,
* gewerbliche Anzeigen als gewerblich kennzeichnen (Impressumspflicht, § 5 DDG).

## 3. Darf da überhaupt ein Tiny House stehen?

Ein dauerhaft bewohntes Tiny House ist baurechtlich ein Gebäude – auch auf
Rädern, sobald es ortsfest genutzt wird. Zu klären, **bevor** ein Kaufvertrag
unterschrieben wird:

* **Bebauungsplan (§ 30 BauGB):** Art der Nutzung, Baufenster, Grundflächenzahl,
  häufig Vorgaben zu Geschossen, Dachform, Mindestgröße. Ein B-Plan kann mehrere
  Kleinhäuser auf einer Parzelle faktisch ausschließen.
* **Ohne B-Plan (§ 34 BauGB):** Einfügen in die Umgebungsbebauung. Zwei bis
  sechs Minihäuser neben lauter Einfamilienhäusern „fügen sich" oft nicht ein.
* **Außenbereich (§ 35 BauGB):** Wohnen ist dort praktisch nicht
  genehmigungsfähig. Günstige Grundstücke liegen auffällig oft genau dort.
* **Landesbauordnung:** Abstandsflächen, Stellplatzpflicht, Brandschutz.
* **Erschließung:** Anschluss an Straße, Wasser, Abwasser, Strom; kommunale
  Erschließungsbeiträge können fünfstellig werden.

Die drei Fragen aus `tinyhaus kontakt` (B-Plan, Erschließung, Grundbuchlasten)
sind die Kurzfassung. Verbindlich ist nur eine **Bauvoranfrage** beim Bauamt.

## 4. Verkaufen statt vermieten: zusätzliche Hürde

Sollen einzelne Häuser verkauft werden, braucht es Eigentum, das verkauft
werden kann:

* **Grundstücksteilung** (in einigen Ländern genehmigungspflichtig), oder
* **WEG-Aufteilung** mit Teilungserklärung und Abgeschlossenheitsbescheinigung, oder
* **Erbbaurecht** – Haus verkaufen, Grundstück behalten.

Die Kalkulation rechnet dafür pauschal `costs.subdivision_eur` je Einheit in den
Kaufpreis. Das ist ein Platzhalter, keine Kostenschätzung des Notars.

Wer Häuser baut und verkauft, ist **Bauträger**: Erlaubnis nach § 34c GewO,
Makler- und Bauträgerverordnung (MaBV), Sicherheiten für Käufergelder. Wer nur
vermietet, fällt nicht darunter – ein Grund, den Mietpfad ernst zu nehmen.

## 5. Steuern

* **Grunderwerbsteuer:** 3,5 % bis 6,5 % je Bundesland. Die Sätze in
  `tinyhaus/config.py` sind Rechercheständer und ändern sich – vor dem Kauf beim
  Notar oder Finanzamt bestätigen lassen.
* **Gewerblicher Grundstückshandel:** mehr als drei verkaufte Objekte in fünf
  Jahren machen aus privater Vermögensverwaltung ein Gewerbe (Einkommen- und
  Gewerbesteuer). Bei mehreren Tiny Houses schnell erreicht.
* **Umsatzsteuer:** Vermietung zu Wohnzwecken ist umsatzsteuerfrei – damit
  entfällt auch der Vorsteuerabzug auf die Baukosten.

## 6. Daten der Interessenten (DSGVO)

Die SQLite-Datei enthält Namen und Kontaktdaten echter Menschen.

* `data/*.db` steht in `.gitignore` – nicht committen, nicht ins Repo schieben.
* Zweck ist die Beantwortung der Anfrage; wer nur auf die Anzeige geantwortet
  hat, hat keiner Werbung zugestimmt.
* Informationspflicht (Art. 13 DSGVO) bei der ersten Antwort erfüllen,
  Löschfrist festlegen und einhalten.
* Anfragen zu Projekten, die nicht kommen, danach löschen – nicht „für später"
  aufheben.
