# Nächste Schritte

## Zuerst, weil es die Idee trägt

1. **Eine Region wirklich testen.** Zwei Anzeigen, vier Wochen, Anfragen
   erfassen. Die ersten 20 Leads sagen mehr über das Geschäftsmodell als jede
   weitere Codezeile.
2. **Baukosten hart machen.** Drei Angebote von Tiny-House-Herstellern
   einholen und `unit_build_eur` ersetzen. Die Kalkulation steht und fällt
   damit.
3. **Bauvoranfrage** für das erste ernsthafte Grundstück. Kostet wenig, klärt
   die Frage, an der sonst alles scheitert.

## Am Code

* **Leads automatisch erfassen:** Portal-Nachrichten kommen per E-Mail. Ein
  IMAP-Import, der das Label (`TH-34-01`) aus dem Betreff zieht und daraus
  einen Lead macht, spart die Handarbeit.
* **A/B-Test der Preise:** zwei Mietpreise je Region gegeneinander laufen
  lassen, statt einen zu raten. Dafür braucht `MarketTest` eine Variante und
  der Nachfrage-Index eine Auswertung je Preispunkt.
* **Bodenrichtwerte** aus den BORIS-Portalen der Länder einlesen: dann ist der
  Quadratmeterpreis nicht mehr an einer eigenen Obergrenze gemessen, sondern am
  örtlichen Marktwert.
* **Regionsdaten statt PLZ-2:** Einwohnerentwicklung, Pendeldistanz zur
  nächsten Stadt, Leerstandsquote – als zusätzliche Bewertungskriterien.
* **Portal-Zugang:** IS24-Partnervertrag oder OpenImmo-Export; dann kann der
  `ApiPublisher` das Einstellen übernehmen (Schnittstelle steht bereits).
* **Mehrere Nutzer:** aktuell eine lokale SQLite-Datei. Für ein Team wäre ein
  kleiner Webdienst der nächste Schritt – erst sinnvoll, wenn Punkt 1 oben
  positiv ausgegangen ist.

## Bewusst nicht gebaut

* **Bot, der Anzeigen automatisch einstellt.** Verstößt gegen die AGB der
  Portale und kostet den Account – siehe [RECHTLICHES.md](RECHTLICHES.md).
* **Scraper, der robots.txt umgeht.** Gleiche Begründung.
* **Automatische Verkäufer-Mails.** Das Anschreiben wird erzeugt, verschickt
  wird es von Hand: Beim Erstkontakt entscheidet sich, ob der Verkäufer
  verhandelt – dafür lohnt der Blick drauf.
