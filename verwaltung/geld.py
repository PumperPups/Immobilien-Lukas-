"""Betraege, Monate, Faelligkeit.

Geld wird ueberall als ganze Cent gefuehrt (int) - nie als float, sonst
stimmt die Summe von 300 Mieten am Ende um ein paar Cent nicht.
Monate sind Texte im Format "2026-10".
"""

from __future__ import annotations

import datetime as dt
import re

MONATSNAMEN = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
               "August", "September", "Oktober", "November", "Dezember"]


# ------------------------------------------------------------------ Betraege

def cent(text: str | int | float | None) -> int | None:
    """'1.234,56' / '-1234.56' / '1234,5 EUR' / 1234.5 -> Cent. Leer -> None."""
    if text is None:
        return None
    if isinstance(text, int):
        return text * 100
    if isinstance(text, float):
        return round(text * 100)
    s = str(text).strip().replace(" ", "").replace(" ", "")
    s = re.sub(r"(?i)(eur|€)", "", s)
    if not s:
        return None
    negativ = s.startswith("-") or s.endswith("-")
    s = s.strip("+-")
    if "," in s and "." in s:
        # der hintere Trenner ist das Dezimalzeichen
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) == 3:
        s = s.replace(".", "")              # "1.234" = Tausenderpunkt
    try:
        wert = round(float(s) * 100)
    except ValueError:
        return None
    return -wert if negativ else wert


def eur(betrag: int | None, zeichen: bool = True) -> str:
    """Cent -> '1.234,56 €'."""
    if betrag is None:
        return "–"
    text = f"{abs(betrag) / 100:,.2f}".translate(str.maketrans({",": ".", ".": ","}))
    text = ("-" if betrag < 0 else "") + text
    return f"{text} €" if zeichen else text


# ------------------------------------------------------------------ Datum

def datum(text: str | dt.date | None) -> dt.date | None:
    """'01.10.2026' / '01.10.26' / '2026-10-01' -> date."""
    if text is None or isinstance(text, dt.date):
        return text
    s = str(text).strip()
    for form in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s[:10] if form == "%Y-%m-%d" else s, form).date()
        except ValueError:
            continue
    return None


def datum_de(d: dt.date | str | None) -> str:
    d = datum(d)
    return d.strftime("%d.%m.%Y") if d else ""


# ------------------------------------------------------------------ Monate

def monat(d: dt.date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def monat_plus(m: str, n: int) -> str:
    jahr, mon = int(m[:4]), int(m[5:7])
    index = jahr * 12 + (mon - 1) + n
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def monate(von: str, bis: str) -> list[str]:
    """Alle Monate von..bis einschliesslich."""
    aus, m = [], von
    while m <= bis:
        aus.append(m)
        m = monat_plus(m, 1)
    return aus


def monat_name(m: str) -> str:
    return f"{MONATSNAMEN[int(m[5:7]) - 1]} {m[:4]}"


def erster(m: str) -> dt.date:
    return dt.date(int(m[:4]), int(m[5:7]), 1)


def letzter(m: str) -> dt.date:
    return erster(monat_plus(m, 1)) - dt.timedelta(days=1)


def gueltiger_monat(text: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", text or ""))


# ------------------------------------------------------------------ Faelligkeit

def _ostersonntag(jahr: int) -> dt.date:
    """Gauss'sche Osterformel (gregorianisch)."""
    a, b, c = jahr % 19, jahr // 100, jahr % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mon = (h + l_ - 7 * m + 114) // 31
    tag = (h + l_ - 7 * m + 114) % 31 + 1
    return dt.date(jahr, mon, tag)


def feiertage(jahr: int) -> set[dt.date]:
    """Bundesweite Feiertage. Landesfeiertage verschieben die Faelligkeit
    hoechstens um einen Tag - dafuer gibt es die Karenztage."""
    ostern = _ostersonntag(jahr)
    tage = {dt.date(jahr, 1, 1), dt.date(jahr, 5, 1), dt.date(jahr, 10, 3),
            dt.date(jahr, 12, 25), dt.date(jahr, 12, 26)}
    for versatz in (-2, 1, 39, 50):       # Karfreitag, Ostermontag, Himmelfahrt, Pfingstmontag
        tage.add(ostern + dt.timedelta(days=versatz))
    return tage


def faellig_am(m: str, werktag: int = 3) -> dt.date:
    """Miete ist faellig am 3. Werktag (§ 556b BGB). Samstag zaehlt dabei
    nicht mit (BGH VIII ZR 129/09), Feiertage auch nicht."""
    frei = feiertage(int(m[:4]))
    d, gezaehlt = erster(m), 0
    while True:
        if d.weekday() < 5 and d not in frei:
            gezaehlt += 1
            if gezaehlt == werktag:
                return d
        d += dt.timedelta(days=1)
