"""Was muss ein Vertrag in welchem Monat zahlen?"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import geld
from .db import Datenbank
from .schutz import falten, woerter


@dataclass
class Vertrag:
    id: int
    nummer: str
    vorname: str
    nachname: str
    mitmieter: str
    objekt: str
    einheit: str
    strasse: str
    beginn: str                       # YYYY-MM-DD
    ende: str | None
    startsaldo: int
    referenzen: list[str]
    stufen: list[tuple[str, int, int]] = field(default_factory=list)   # (ab, kalt, nk)

    @property
    def name(self) -> str:
        return f"{self.vorname} {self.nachname}".strip()

    @property
    def erster_monat(self) -> str:
        return self.beginn[:7]

    @property
    def letzter_monat(self) -> str | None:
        return self.ende[:7] if self.ende else None

    def aktiv(self, monat: str) -> bool:
        return self.erster_monat <= monat and (self.letzter_monat is None or monat <= self.letzter_monat)

    def soll(self, monat: str) -> int:
        """Gesamtmiete (kalt + Nebenkosten) fuer den Monat, 0 wenn nicht aktiv."""
        if not self.aktiv(monat):
            return 0
        passend = [s for s in self.stufen if s[0] <= monat]
        stufe = passend[-1] if passend else (self.stufen[0] if self.stufen else None)
        return stufe[1] + stufe[2] if stufe else 0

    # ------------------------------------------------------------ fuer den Abgleich
    def namen_woerter(self) -> tuple[set[str], set[str]]:
        """(Nachnamen-Teile, Vornamen) aller Mieter, gefaltet, mind. 3 Zeichen."""
        nach, vor = set(), set()
        personen = [(self.vorname, self.nachname)]
        for weitere in (self.mitmieter or "").split(";"):
            teile = weitere.strip().split()
            if len(teile) >= 2:
                personen.append((" ".join(teile[:-1]), teile[-1]))
            elif teile:
                personen.append(("", teile[0]))
        for v, n in personen:
            for name, ziel in ((n, nach), (v, vor)):
                ziel.update(w for w in woerter(name) if len(w) >= 3)
                # so, wie die Bank den Namen ohne Sonderzeichen schreibt (Testoğlu -> Testolu)
                ohne = name.encode("cp1252", errors="ignore").decode("cp1252")
                ziel.update(w for w in woerter(ohne) if len(w) >= 3)
        return nach, vor

    def muster(self) -> list[re.Pattern]:
        """Mieternummer und weitere Referenzen als tolerante Suchmuster:
        "M-0042" findet auch "M 42", "m0042", "M/0042"."""
        aus = []
        for ref in [self.nummer, *self.referenzen]:
            teile = re.findall(r"[a-z]+|\d+", falten(ref))
            if not teile or sum(len(t) for t in teile) < 3:
                continue
            stuecke = [("0*" + t.lstrip("0")) if t.isdigit() and t.lstrip("0") else re.escape(t) for t in teile]
            aus.append(re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(stuecke) + r"(?![0-9])"))
        return aus

    def adresse(self) -> tuple[str, str] | None:
        """(Strassen-Stamm, Hausnummer) - "Musterstraße 5" -> ("muster", "5")."""
        m = re.match(r"(.+?)\s*(\d+\s*[a-z]?)\s*$", falten(self.strasse or ""))
        if not m:
            return None
        stamm = re.sub(r"(strasse|str\.?|weg|allee|platz|ring|gasse)$", "", m.group(1).strip()).strip(" -.")
        return (stamm, m.group(2).replace(" ", "")) if len(stamm) >= 4 else None


def lade_vertraege(db: Datenbank) -> list[Vertrag]:
    stufen = db.sollmieten()
    aus = []
    for r in db.vertraege():
        aus.append(Vertrag(
            id=r["id"], nummer=r["nummer"], vorname=r["vorname"] or "", nachname=r["nachname"],
            mitmieter=r["mitmieter"] or "", objekt=r["objekt"], einheit=r["einheit"], strasse=r["strasse"] or "",
            beginn=r["beginn"], ende=r["ende"], startsaldo=r["startsaldo_cent"] or 0,
            referenzen=[x.strip() for x in (r["referenzen"] or "").split(";") if x.strip()],
            stufen=stufen.get(r["id"], []),
        ))
    return aus


def offen_im_monat(v: Vertrag, monat: str, ist: dict[tuple[int, str], int]) -> int:
    return v.soll(monat) - ist.get((v.id, monat), 0)


def saldo(v: Vertrag, bis: str, ab: str, ist: dict[tuple[int, str], int]) -> int:
    """Rueckstand (+) oder Guthaben (-) von Erfassungsbeginn bis einschliesslich Monat."""
    summe = v.startsaldo
    for m in geld.monate(ab, bis):
        summe += offen_im_monat(v, m, ist)
    return summe
