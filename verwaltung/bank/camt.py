"""CAMT.053 (Tagesauszug) und CAMT.052 (Umsatzinformation), ISO 20022.

Namensraum-unabhaengig gelesen: die Banken liefern Versionen von 001.02 bis
001.08 - die Feldnamen sind dieselben geblieben, nur der Namensraum wechselt.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .. import geld
from . import FormatFehler, Umsatz


def _lokal(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kind(el, *pfad):
    """Erstes Element entlang des Pfads (lokale Namen), sonst None."""
    aktuell = [el]
    for name in pfad:
        naechste = []
        for e in aktuell:
            naechste.extend(k for k in e if _lokal(k.tag) == name)
        if not naechste:
            return None
        aktuell = naechste
    return aktuell[0]


def _alle(el, name):
    return [k for k in el.iter() if _lokal(k.tag) == name]


def _text(el, *pfad) -> str:
    k = _kind(el, *pfad) if pfad else el
    return (k.text or "").strip() if k is not None else ""


def lese(daten: bytes) -> list[Umsatz]:
    try:
        wurzel = ET.fromstring(daten)
    except ET.ParseError as fehler:
        raise FormatFehler(f"XML nicht lesbar: {fehler}") from None
    berichte = [e for e in wurzel.iter() if _lokal(e.tag) in ("Stmt", "Rpt")]
    if not berichte:
        raise FormatFehler("Kein CAMT-Auszug (weder Stmt noch Rpt gefunden)")

    aus: list[Umsatz] = []
    for bericht in berichte:
        konto = _text(bericht, "Acct", "Id", "IBAN")
        for eintrag in (k for k in bericht if _lokal(k.tag) == "Ntry"):
            if _text(eintrag, "Sts") in ("PDNG", "INFO") or _text(eintrag, "Sts", "Cd") in ("PDNG", "INFO"):
                continue                                  # vorgemerkt, noch nicht gebucht
            vorzeichen = -1 if _text(eintrag, "CdtDbtInd") == "DBIT" else 1
            datum = geld.datum(_text(eintrag, "BookgDt", "Dt") or _text(eintrag, "BookgDt", "DtTm")[:10]
                               or _text(eintrag, "ValDt", "Dt"))
            if datum is None:
                continue
            gesamt = geld.cent(_text(eintrag, "Amt")) or 0
            details = _alle(eintrag, "TxDtls") or [None]
            for tx in details:
                quelle = tx if tx is not None else eintrag
                betrag = geld.cent(_text(tx, "Amt")) if tx is not None and len(details) > 1 else None
                if betrag is None and tx is not None and len(details) > 1:
                    betrag = geld.cent(_text(tx, "AmtDtls", "TxAmt", "Amt"))
                betrag = betrag if betrag is not None else gesamt
                gutschrift = vorzeichen > 0
                seite = "Dbtr" if gutschrift else "Cdtr"
                name = (_text(quelle, "RltdPties", seite, "Nm")
                        or _text(quelle, "RltdPties", seite, "Pty", "Nm"))
                iban = _text(quelle, "RltdPties", seite + "Acct", "Id", "IBAN")
                zweck = " ".join(_text(u) for u in _alle(quelle, "Ustrd")).strip()
                letzter = _text(quelle, "RltdPties", "Ultmt" + seite, "Nm") or \
                    _text(quelle, "RltdPties", "Ultmt" + seite, "Pty", "Nm")
                if letzter and letzter != name:
                    zweck = f"{zweck} (für {letzter})".strip()   # z.B. Jobcenter zahlt fuer Mieter
                if not zweck:
                    zweck = _text(eintrag, "AddtlNtryInf")
                aus.append(Umsatz(datum=datum, betrag_cent=vorzeichen * abs(betrag), name=name,
                                  iban=iban, zweck=zweck, konto=konto))
    return aus
