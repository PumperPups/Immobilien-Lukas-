# Wie gerechnet wird

Alle Werte stehen in `config.json` (Vorlage: `config.example.json`) und sind
Startannahmen. Wer echte Angebote hat, trägt sie ein – der Rest der Pipeline
rechnet damit weiter.

## Kostenseite

| Position | Standard | Bemerkung |
| --- | --- | --- |
| `unit_build_eur` | 75.000 € | Tiny House schlüsselfertig, je Einheit |
| `foundation_eur` | 8.000 € | Punktfundament/Bodenplatte, je Einheit |
| `connection_eur` | 12.000 € | Hausanschlüsse, je Einheit |
| `development_eur` | 15.000 € | Erschließung, einmalig, nur wenn nicht erschlossen |
| `permit_eur` | 4.500 € | Bauantrag, Statik, Vermessung, je Einheit |
| `notary_rate` | 1,5 % | Notar und Grundbuch, vom Kaufpreis |
| `broker_rate` | 3,57 % | nur bei gewerblichem Anbieter |
| Grunderwerbsteuer | 3,5–6,5 % | je Bundesland, siehe `config.py` |
| `contingency_rate` | 10 % | Puffer auf Bau, Erschließung, Genehmigung |
| `subdivision_eur` | 6.000 € | Teilung/WEG, **nur** beim Verkauf |

Unbekannte Erschließung wird wie „nicht erschlossen" gerechnet. Lieber zu
vorsichtig kalkuliert als eine Überraschung nach dem Notartermin.

## Wie viele Häuser passen drauf?

`Fläche / area_per_unit_sqm` (Standard 350 m² je Einheit inklusive Abstand und
Stellplatz), gedeckelt auf `max_units`. Das ist eine grobe Schätzung – was
wirklich zulässig ist, sagt der Bebauungsplan, nicht diese Formel.

## Miete

```
Kosten je Einheit × Zielrendite / 12
-----------------------------------  +  Bewirtschaftungskosten
        (1 − Leerstandsquote)
```

Bei 7 % Zielrendite, 5 % Leerstand und 80 € nicht umlagefähigen Kosten ergibt
eine Einheit für 133.000 € rund 900 € Kaltmiete im Monat.

## Kaufpreis

```
(Kosten je Einheit + Teilungskosten) × (1 + Zielmarge)
```

## Maximalgebot – die eigentlich wichtige Zahl

`tinyhaus verhandlung <key>` rechnet die Mietformel rückwärts: Gegeben die
Miete, die Interessenten **tatsächlich** genannt haben – was darf das
Grundstück dann noch kosten?

Beispiel aus den Demodaten: Grundstück für 44.500 € inseriert, kalkulierte
Miete 900 €. Die Anfragen ergeben im Schnitt 800 €. Damit sinkt das
Maximalgebot auf 14.500 €. Das Grundstück ist zu diesem Preis kein Geschäft –
entweder Preis verhandeln oder bleiben lassen.

Fällt die Zahlungsbereitschaft unter die reinen Baukosten, ist das Maximalgebot
0 €: Dann trägt sich das Projekt selbst bei geschenktem Grundstück nicht.

## Bewertung der Grundstücke

100 Punkte, verteilt auf acht Kriterien:

| Kriterium | Punkte | Logik |
| --- | ---: | --- |
| Quadratmeterpreis | 20 | Abstand zur eigenen Obergrenze |
| Gesamtpreis | 10 | weniger Kapitaleinsatz, weniger Risiko |
| Kapazität | 15 | mehrere Einheiten verteilen die Fixkosten |
| Baurecht | 15 | Bauland voll, Bauerwartungsland 30 % |
| Erschließung | 10 | erschlossen voll, unklar 40 %, unerschlossen 0 |
| Anbieter | 5 | privat: keine Courtage, mehr Spielraum |
| Standzeit | 5 | was 90 Tage liegt, lässt sich drücken |
| **Nachfrage** | **20** | gemessene qualifizierte Anfragen je Test |

Ungetestete Regionen bekommen bei der Nachfrage die halbe Punktzahl – sonst
käme nie eine neue Region auf die Liste, und das System würde sich in den
bereits getesteten Gegenden im Kreis drehen.
