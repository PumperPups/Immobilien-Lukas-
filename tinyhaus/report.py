"""Berichte: Shortlist und Nachfrage als HTML-Seite und als Konsolentext."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .config import Config
from .fmt import de_number, eur, sqm
from .models import DemandSignal
from .pipeline import Candidate
from .storage import Storage

CSS = """
:root { color-scheme: light dark; --bg:#fbfaf8; --fg:#1d1b19; --muted:#6b6660;
        --line:#e3ded7; --card:#ffffff; --accent:#1f6f53; --warn:#9a5b16; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#171614; --fg:#eceae6; --muted:#a09a92; --line:#2e2c29;
          --card:#1f1e1b; --accent:#6bbd97; --warn:#d99b4e; }
}
* { box-sizing:border-box; }
body { margin:0; padding:24px 16px 64px; background:var(--bg); color:var(--fg);
       font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:1100px; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 4px; letter-spacing:-.02em; }
h2 { font-size:1.1rem; margin:32px 0 12px; }
.sub { color:var(--muted); margin:0 0 24px; }
.cards { display:flex; flex-wrap:wrap; gap:12px; margin-bottom:8px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:12px 16px; min-width:130px; flex:1 1 130px; }
.card b { display:block; font-size:1.4rem; font-weight:650; }
.card span { color:var(--muted); font-size:.82rem; }
table { width:100%; border-collapse:collapse; background:var(--card);
        border:1px solid var(--line); border-radius:10px; overflow:hidden; }
th, td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--line);
         vertical-align:top; font-size:.9rem; }
th { font-weight:600; color:var(--muted); font-size:.78rem; text-transform:uppercase;
     letter-spacing:.04em; }
tr:last-child td { border-bottom:none; }
td.num, th.num { text-align:right; white-space:nowrap; }
.score { font-weight:650; color:var(--accent); }
.reasons { color:var(--muted); font-size:.82rem; }
a { color:var(--accent); }
.note { color:var(--warn); font-size:.85rem; margin-top:8px; }
@media (max-width:720px) { table, thead, tbody, th, td, tr { display:block; }
  thead { display:none; } td { border:none; padding:4px 12px; }
  tr { border-bottom:1px solid var(--line); padding:8px 0; display:block; }
  td.num { text-align:left; } }
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_html(
    candidates: list[Candidate], demand: dict[str, DemandSignal], stats: dict[str, int]
) -> str:
    rows = []
    for c in candidates:
        signal = demand.get(c.plot.region)
        nachfrage = (
            f"{signal.qualified_leads}/{signal.leads} Leads · Index {de_number(signal.index, 2)}"
            if signal and signal.tests
            else "noch kein Test"
        )
        rows.append(
            f"""<tr>
  <td class="num"><span class="score">{de_number(c.score.total, 1)}</span></td>
  <td><a href="{_esc(c.plot.url)}" target="_blank" rel="noopener">{_esc(c.plot.title)}</a>
      <div class="reasons">{_esc(' · '.join(c.score.reasons))}</div></td>
  <td>{_esc(c.plot.postal_code or '')} {_esc(c.plot.city or '')}<br>
      <span class="reasons">{_esc(c.plot.state or '')}</span></td>
  <td class="num">{_esc(eur(c.plot.price_eur))}<br>
      <span class="reasons">{_esc(sqm(c.plot.area_sqm))}</span></td>
  <td class="num">{c.score.units}</td>
  <td class="num">{_esc(eur(c.calc.rent_eur_month))}<br>
      <span class="reasons">{_esc(eur(c.calc.sale_price_eur))} Kauf</span></td>
  <td class="reasons">{_esc(nachfrage)}</td>
</tr>"""
        )

    demand_rows = [
        f"""<tr><td>{_esc(region)}</td><td class="num">{s.tests}</td>
  <td class="num">{s.leads}</td><td class="num">{s.rent_leads}</td>
  <td class="num">{s.buy_leads}</td><td class="num">{s.qualified_leads}</td>
  <td class="num">{_esc(eur(s.avg_accepted_rent))}</td>
  <td class="num">{_esc(eur(s.avg_accepted_price))}</td>
  <td class="num">{de_number(s.index, 2)}</td></tr>"""
        for region, s in sorted(demand.items(), key=lambda kv: -kv[1].index)
    ] or ['<tr><td colspan="9" class="reasons">Noch keine Nachfrage-Tests veroeffentlicht.</td></tr>']

    cards = "".join(
        f'<div class="card"><b>{value}</b><span>{_esc(label)}</span></div>'
        for label, value in stats.items()
    )

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tiny-House-Scout</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>Tiny-House-Scout</h1>
<p class="sub">Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
<div class="cards">{cards}</div>

<h2>Shortlist: Grundstuecke</h2>
<table><thead><tr><th class="num">Score</th><th>Grundstueck</th><th>Ort</th>
<th class="num">Preis</th><th class="num">Einh.</th><th class="num">Miete / Kauf</th>
<th>Nachfrage</th></tr></thead><tbody>
{''.join(rows) or '<tr><td colspan="7" class="reasons">Keine passenden Grundstuecke.</td></tr>'}
</tbody></table>
<p class="note">Miete und Kaufpreis sind kalkuliert, nicht gemessen - erst die
Anzeigen zeigen, was der Markt zahlt.</p>

<h2>Gemessene Nachfrage je Region</h2>
<table><thead><tr><th>PLZ-Gebiet</th><th class="num">Tests</th><th class="num">Leads</th>
<th class="num">Miete</th><th class="num">Kauf</th><th class="num">qualifiziert</th>
<th class="num">Ø Miete</th><th class="num">Ø Kaufpreis</th><th class="num">Index</th>
</tr></thead><tbody>
{''.join(demand_rows)}
</tbody></table>
</div></body></html>"""


def write_report(cfg: Config, storage: Storage, candidates: list[Candidate]) -> Path:
    path = Path(cfg.output_dir) / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_html(candidates, storage.all_demand_signals(), storage.stats()),
        encoding="utf-8",
    )
    return path


def text_shortlist(candidates: list[Candidate]) -> str:
    if not candidates:
        return "Keine passenden Grundstuecke. Kriterien lockern (config.json) oder mehr Quellen scannen."
    lines = [
        f"{'Score':>5}  {'Ort':<22} {'Preis':>12} {'Flaeche':>10} {'Einh':>4} "
        f"{'Miete':>10} {'Kaufpreis':>12}  Titel",
        "-" * 118,
    ]
    for c in candidates:
        ort = f"{c.plot.postal_code or ''} {c.plot.city or ''}".strip()[:22]
        lines.append(
            f"{de_number(c.score.total, 1):>5}  {ort:<22} {eur(c.plot.price_eur):>12} "
            f"{sqm(c.plot.area_sqm):>10} {c.score.units:>4} "
            f"{eur(c.calc.rent_eur_month):>10} {eur(c.calc.sale_price_eur):>12}  "
            f"{c.plot.title[:46]}"
        )
        lines.append(f"{'':>5}  {c.plot.key}  {c.plot.url}")
    return "\n".join(lines)
