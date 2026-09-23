"""Hausverwaltung: eine Datenbank fuer Objekte, Mieter, Vertraege und Zahlungen.

Erster Baustein ist der Mieteingang: Kontoauszug der Bank einlesen, jede
Gutschrift automatisch dem richtigen Mietvertrag und Monat zuordnen und
auf einen Blick zeigen, wer bezahlt hat und wer nicht.

Alle echten Daten bleiben in einem eigenen Ordner ausserhalb des Projekts
(siehe docs/DATENSCHUTZ.md). Der Code arbeitet ohne Internet und ohne KI.
"""

__version__ = "0.1.0"
