"""Zahlenformatierung nach deutscher Schreibweise.

Eigene Funktion statt str.replace auf ganzen Texten: sonst werden auch
die Kommas im Fliesstext zu Punkten.
"""

from __future__ import annotations


def de_number(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "-"
    formatted = f"{value:,.{decimals}f}"          # 1,234,567.89
    return formatted.translate(str.maketrans({",": ".", ".": ","}))


def eur(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "k. A."
    return f"{de_number(value, decimals)} EUR"


def sqm(value: float | int | None) -> str:
    if value is None:
        return "k. A."
    return f"{de_number(value)} m²"
