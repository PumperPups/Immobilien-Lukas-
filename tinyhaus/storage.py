"""Persistenz auf SQLite - keine Server, keine Abhaengigkeiten.

Die Datenbank ist das Gedaechtnis der Pipeline: was schon gesehen wurde
(damit nicht dieselbe Anzeige dreimal gemeldet wird), was bewertet wurde,
welche Test-Anzeigen laufen und welche Anfragen darauf eingegangen sind.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from pathlib import Path
from typing import Any, Iterable

from .models import DemandSignal, Lead, MarketTest, Plot, Score, region_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS plots (
    key           TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    fingerprint   TEXT,
    url           TEXT,
    title         TEXT,
    price_eur     REAL,
    area_sqm      REAL,
    city          TEXT,
    postal_code   TEXT,
    state         TEXT,
    region        TEXT,
    description   TEXT,
    seller_type   TEXT,
    seller_name   TEXT,
    seller_contact TEXT,
    land_type     TEXT,
    has_building  INTEGER,
    teardown      INTEGER,
    developed     INTEGER,
    listed_on     TEXT,
    first_seen    TEXT,
    last_seen     TEXT,
    status        TEXT,
    notes         TEXT,
    raw           TEXT
);
CREATE INDEX IF NOT EXISTS idx_plots_region ON plots(region);
CREATE INDEX IF NOT EXISTS idx_plots_fingerprint ON plots(fingerprint);

CREATE TABLE IF NOT EXISTS scores (
    plot_key      TEXT PRIMARY KEY,
    total         REAL,
    units         INTEGER,
    rejected      INTEGER,
    reject_reason TEXT,
    reasons       TEXT,
    breakdown     TEXT,
    computed_at   TEXT
);

CREATE TABLE IF NOT EXISTS market_tests (
    label          TEXT PRIMARY KEY,
    region         TEXT NOT NULL,
    plot_key       TEXT,
    city           TEXT,
    rent_eur_month REAL,
    buy_price_eur  REAL,
    unit_sqm       REAL,
    channel        TEXT,
    status         TEXT,
    published_at   TEXT,
    ad_rent_path   TEXT,
    ad_buy_path    TEXT,
    created_at     TEXT,
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_tests_region ON market_tests(region);

CREATE TABLE IF NOT EXISTS leads (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    label          TEXT NOT NULL,
    interest       TEXT,
    name           TEXT,
    contact        TEXT,
    message        TEXT,
    accepted_rent  REAL,
    accepted_price REAL,
    received_at    TEXT,
    qualified      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_leads_label ON leads(label);
"""


def _b(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _ob(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


class Storage:
    def __init__(self, db_path: str | Path = "data/tinyhaus.db"):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- Grundstuecke --------------------------------------------------

    def upsert_plot(self, plot: Plot) -> bool:
        """Speichert das Grundstueck. Rueckgabe: True, wenn es neu ist."""
        existing = self.conn.execute(
            "SELECT key, first_seen, status, notes FROM plots WHERE key = ?", (plot.key,)
        ).fetchone()
        is_new = existing is None
        first_seen = plot.first_seen if is_new else existing["first_seen"]
        status = plot.status if is_new else existing["status"]
        notes = plot.notes if is_new else (existing["notes"] or plot.notes)

        self.conn.execute(
            """
            INSERT INTO plots (key, source, source_id, fingerprint, url, title,
                price_eur, area_sqm, city, postal_code, state, region, description,
                seller_type, seller_name, seller_contact, land_type, has_building,
                teardown, developed, listed_on, first_seen, last_seen, status, notes, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                url=excluded.url, title=excluded.title, price_eur=excluded.price_eur,
                area_sqm=excluded.area_sqm, city=excluded.city,
                postal_code=excluded.postal_code, state=excluded.state,
                region=excluded.region, description=excluded.description,
                seller_type=excluded.seller_type, seller_name=excluded.seller_name,
                seller_contact=excluded.seller_contact, land_type=excluded.land_type,
                has_building=excluded.has_building, teardown=excluded.teardown,
                developed=excluded.developed, listed_on=excluded.listed_on,
                last_seen=excluded.last_seen, fingerprint=excluded.fingerprint,
                raw=excluded.raw
            """,
            (
                plot.key, plot.source, plot.source_id, plot.fingerprint, plot.url,
                plot.title, plot.price_eur, plot.area_sqm, plot.city, plot.postal_code,
                plot.state, plot.region, plot.description, plot.seller_type,
                plot.seller_name, plot.seller_contact, plot.land_type,
                _b(plot.has_building), _b(plot.teardown), _b(plot.developed),
                plot.listed_on, first_seen, plot.last_seen, status, notes,
                json.dumps(plot.raw, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return is_new

    def duplicate_of(self, plot: Plot) -> str | None:
        """Findet dasselbe Grundstueck unter anderer Quelle (Portal-Doppler)."""
        row = self.conn.execute(
            "SELECT key FROM plots WHERE fingerprint = ? AND key != ? LIMIT 1",
            (plot.fingerprint, plot.key),
        ).fetchone()
        return row["key"] if row else None

    def get_plot(self, key: str) -> Plot | None:
        row = self.conn.execute("SELECT * FROM plots WHERE key = ?", (key,)).fetchone()
        return self._row_to_plot(row) if row else None

    def list_plots(
        self, status: str | None = None, region: str | None = None
    ) -> list[Plot]:
        sql = "SELECT * FROM plots WHERE 1=1"
        args: list[Any] = []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if region:
            sql += " AND region = ?"
            args.append(region)
        sql += " ORDER BY last_seen DESC"
        return [self._row_to_plot(r) for r in self.conn.execute(sql, args)]

    def set_status(self, key: str, status: str, note: str | None = None) -> bool:
        cur = self.conn.execute(
            "UPDATE plots SET status = ?, notes = COALESCE(?, notes) WHERE key = ?",
            (status, note, key),
        )
        self.conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_plot(row: sqlite3.Row) -> Plot:
        allowed = {f.name for f in fields(Plot)}
        data = {k: row[k] for k in row.keys() if k in allowed}
        data["has_building"] = bool(row["has_building"])
        data["teardown"] = bool(row["teardown"])
        data["developed"] = _ob(row["developed"])
        data["raw"] = json.loads(row["raw"] or "{}")
        data["description"] = row["description"] or ""
        data["notes"] = row["notes"] or ""
        return Plot(**data)

    # --- Bewertungen ---------------------------------------------------

    def save_score(self, score: Score) -> None:
        self.conn.execute(
            """INSERT INTO scores (plot_key,total,units,rejected,reject_reason,
                   reasons,breakdown,computed_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(plot_key) DO UPDATE SET
                   total=excluded.total, units=excluded.units,
                   rejected=excluded.rejected, reject_reason=excluded.reject_reason,
                   reasons=excluded.reasons, breakdown=excluded.breakdown,
                   computed_at=excluded.computed_at""",
            (
                score.plot_key, score.total, score.units, _b(score.rejected),
                score.reject_reason, json.dumps(score.reasons, ensure_ascii=False),
                json.dumps(score.breakdown, ensure_ascii=False), score.computed_at,
            ),
        )
        self.conn.commit()

    def get_score(self, plot_key: str) -> Score | None:
        row = self.conn.execute(
            "SELECT * FROM scores WHERE plot_key = ?", (plot_key,)
        ).fetchone()
        return self._row_to_score(row) if row else None

    @staticmethod
    def _row_to_score(row: sqlite3.Row) -> Score:
        return Score(
            plot_key=row["plot_key"],
            total=row["total"],
            units=row["units"],
            rejected=bool(row["rejected"]),
            reject_reason=row["reject_reason"] or "",
            reasons=json.loads(row["reasons"] or "[]"),
            breakdown=json.loads(row["breakdown"] or "{}"),
            computed_at=row["computed_at"],
        )

    def shortlist(self, min_score: float = 0.0, limit: int = 50) -> list[tuple[Plot, Score]]:
        rows = self.conn.execute(
            """SELECT p.key FROM plots p JOIN scores s ON s.plot_key = p.key
               WHERE s.rejected = 0 AND s.total >= ?
               ORDER BY s.total DESC LIMIT ?""",
            (min_score, limit),
        ).fetchall()
        out: list[tuple[Plot, Score]] = []
        for row in rows:
            plot = self.get_plot(row["key"])
            score = self.get_score(row["key"])
            if plot and score:
                out.append((plot, score))
        return out

    # --- Nachfrage-Tests -----------------------------------------------

    def save_market_test(self, test: MarketTest) -> None:
        self.conn.execute(
            """INSERT INTO market_tests (label,region,plot_key,city,rent_eur_month,
                   buy_price_eur,unit_sqm,channel,status,published_at,ad_rent_path,
                   ad_buy_path,created_at,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(label) DO UPDATE SET
                   rent_eur_month=excluded.rent_eur_month,
                   buy_price_eur=excluded.buy_price_eur, status=excluded.status,
                   published_at=excluded.published_at,
                   ad_rent_path=excluded.ad_rent_path,
                   ad_buy_path=excluded.ad_buy_path, notes=excluded.notes""",
            (
                test.label, test.region, test.plot_key, test.city, test.rent_eur_month,
                test.buy_price_eur, test.unit_sqm, test.channel, test.status,
                test.published_at, test.ad_rent_path, test.ad_buy_path,
                test.created_at, test.notes,
            ),
        )
        self.conn.commit()

    def get_market_test(self, label: str) -> MarketTest | None:
        row = self.conn.execute(
            "SELECT * FROM market_tests WHERE label = ?", (label,)
        ).fetchone()
        if not row:
            return None
        return MarketTest(**{k: row[k] for k in row.keys()})

    def list_market_tests(self, region: str | None = None) -> list[MarketTest]:
        sql = "SELECT * FROM market_tests"
        args: list[Any] = []
        if region:
            sql += " WHERE region = ?"
            args.append(region)
        sql += " ORDER BY created_at DESC"
        return [MarketTest(**{k: r[k] for k in r.keys()}) for r in self.conn.execute(sql, args)]

    def tested_regions(self) -> set[str]:
        return {
            r["region"]
            for r in self.conn.execute("SELECT DISTINCT region FROM market_tests")
        }

    # --- Leads ---------------------------------------------------------

    def add_lead(self, lead: Lead) -> int:
        cur = self.conn.execute(
            """INSERT INTO leads (label,interest,name,contact,message,accepted_rent,
                   accepted_price,received_at,qualified) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                lead.label, lead.interest, lead.name, lead.contact, lead.message,
                lead.accepted_rent, lead.accepted_price, lead.received_at,
                _b(lead.qualified),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def leads_for(self, label: str) -> list[Lead]:
        rows = self.conn.execute(
            "SELECT * FROM leads WHERE label = ? ORDER BY received_at", (label,)
        ).fetchall()
        return [
            Lead(
                label=r["label"], interest=r["interest"], name=r["name"],
                contact=r["contact"], message=r["message"] or "",
                accepted_rent=r["accepted_rent"], accepted_price=r["accepted_price"],
                received_at=r["received_at"],
                qualified=bool(r["qualified"]),
            )
            for r in rows
        ]

    # --- Nachfrage-Aggregation -----------------------------------------

    def demand_signal(self, region: str) -> DemandSignal:
        tests = self.conn.execute(
            "SELECT COUNT(*) c FROM market_tests WHERE region = ? AND status != 'entwurf'",
            (region,),
        ).fetchone()["c"]
        rows = self.conn.execute(
            """SELECT l.interest, l.qualified, l.accepted_rent, l.accepted_price
               FROM leads l JOIN market_tests t ON t.label = l.label
               WHERE t.region = ?""",
            (region,),
        ).fetchall()

        signal = DemandSignal(region=region, tests=tests)
        rent_prices: list[float] = []
        buy_prices: list[float] = []
        for r in rows:
            interest = r["interest"] or ""
            if interest == "kein_interesse":
                continue
            signal.leads += 1
            if interest in ("miete", "beides"):
                signal.rent_leads += 1
                if r["accepted_rent"]:
                    rent_prices.append(r["accepted_rent"])
            if interest in ("kauf", "beides"):
                signal.buy_leads += 1
                if r["accepted_price"]:
                    buy_prices.append(r["accepted_price"])
            if r["qualified"]:
                signal.qualified_leads += 1
        if rent_prices:
            signal.avg_accepted_rent = round(sum(rent_prices) / len(rent_prices), 2)
        if buy_prices:
            signal.avg_accepted_price = round(sum(buy_prices) / len(buy_prices), 2)
        return signal

    def all_demand_signals(self) -> dict[str, DemandSignal]:
        regions = {r["region"] for r in self.conn.execute("SELECT DISTINCT region FROM market_tests")}
        return {r: self.demand_signal(r) for r in regions}

    def stats(self) -> dict[str, int]:
        def count(sql: str, args: Iterable[Any] = ()) -> int:
            return int(self.conn.execute(sql, tuple(args)).fetchone()[0])

        return {
            "grundstuecke": count("SELECT COUNT(*) FROM plots"),
            "bewertet": count("SELECT COUNT(*) FROM scores"),
            "shortlist": count("SELECT COUNT(*) FROM scores WHERE rejected = 0"),
            "kontaktiert": count("SELECT COUNT(*) FROM plots WHERE status = 'kontaktiert'"),
            "tests": count("SELECT COUNT(*) FROM market_tests"),
            "tests_live": count("SELECT COUNT(*) FROM market_tests WHERE status = 'veroeffentlicht'"),
            "leads": count("SELECT COUNT(*) FROM leads"),
            "leads_qualifiziert": count("SELECT COUNT(*) FROM leads WHERE qualified = 1"),
        }
