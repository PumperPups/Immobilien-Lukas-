"""Oberflaeche im Browser - laeuft nur auf diesem Rechner (127.0.0.1).

    python -m verwaltung web          oder Doppelklick auf "Mieteingang starten.cmd"

Reiter:
  Übersicht     Monat fuer Monat: wer hat bezahlt, wer nicht, Rueckstand gesamt
  Zu prüfen     Gutschriften, die nicht sicher zugeordnet werden konnten -
                mit Vorschlaegen, ein Klick ordnet zu und merkt sich den Zahler
  Mieter        alle Vertraege, je Vertrag Zahlungsverlauf und bekannte Konten
  Import        Kontoauszug hochladen oder Eingangsordner einlesen
  Einstellungen Stammdaten einlesen, Erfassungsbeginn, Karenztage

Beim Start wird der Eingangsordner automatisch eingelesen und abgeglichen.
Kein Internet, keine KI, keine Fremdpakete.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import http.server
import json
import threading
import traceback
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import abgleich, einlesen, geld, stammdaten, uebersicht
from .bank.csv_bank import _dekodieren
from .db import Datenbank
from .miete import lade_vertraege, saldo
from .schutz import DEMO_ORDNER

e = html.escape

STIL = """
:root { --bg:#f5f6f8; --karte:#fff; --text:#1d2330; --leise:#667085; --linie:#e3e6ec; --akzent:#2f6fed;
        --ok:#15803d; --ok-bg:#dcfce7; --warn:#b45309; --warn-bg:#fef3c7; --rot:#b91c1c; --rot-bg:#fee2e2;
        --grau-bg:#eef0f3; --lila:#6d28d9; --lila-bg:#ede9fe; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#15171b; --karte:#1e2127; --text:#e8e9ec; --leise:#9aa0aa; --linie:#2e323a; --akzent:#5b8dff;
          --ok:#86efac; --ok-bg:#14532d55; --warn:#fcd34d; --warn-bg:#78350f55; --rot:#fca5a5; --rot-bg:#7f1d1d55;
          --grau-bg:#2a2e36; --lila:#c4b5fd; --lila-bg:#4c1d9555; }
}
* { box-sizing:border-box; }
body { margin:0; font:15px/1.5 system-ui, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }
header { display:flex; flex-wrap:wrap; gap:.4rem 1.2rem; align-items:center; padding:.7rem 1.2rem;
         background:var(--karte); border-bottom:1px solid var(--linie); position:sticky; top:0; z-index:5; }
header b { margin-right:.6rem; }
header a { color:var(--leise); text-decoration:none; font-weight:600; }
header a.aktiv { color:var(--akzent); }
.demo { background:var(--lila-bg); color:var(--lila); padding:.1rem .5rem; border-radius:6px; font-size:.8rem; font-weight:700; }
main { max-width:1400px; margin:1.2rem auto; padding:0 1rem; }
.karte { background:var(--karte); border:1px solid var(--linie); border-radius:12px; padding:1rem 1.2rem; margin-bottom:1rem; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.8rem; margin-bottom:1rem; }
.kpi { background:var(--karte); border:1px solid var(--linie); border-radius:12px; padding:.8rem 1rem; }
.kpi small { color:var(--leise); display:block; } .kpi strong { font-size:clamp(1.05rem, 4.2vw, 1.35rem); white-space:nowrap; }
.balken { height:10px; background:var(--grau-bg); border-radius:6px; overflow:hidden; margin:.4rem 0 0; }
.balken span { display:block; height:100%; background:var(--ok); }
.monatnav { display:flex; align-items:center; gap:1rem; margin-bottom:1rem; flex-wrap:wrap; }
.monatnav h1 { margin:0; font-size:1.4rem; }
.leise { color:var(--leise); } .klein { font-size:.85rem; }
a { color:var(--akzent); }
table { width:100%; border-collapse:collapse; font-size:.92rem; }
th, td { text-align:left; padding:.45rem .5rem; border-bottom:1px solid var(--linie); vertical-align:top; }
th { color:var(--leise); font-weight:600; font-size:.8rem; text-transform:uppercase; letter-spacing:.03em; }
td.z, th.z { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.tabelle { overflow-x:auto; }
tr.zeile { cursor:pointer; } tr.zeile:hover td { background:var(--grau-bg); }
tr.detail td { background:var(--bg); }
.status { display:inline-block; padding:.05rem .55rem; border-radius:99px; font-size:.8rem; font-weight:600; white-space:nowrap; }
.s-bezahlt { background:var(--ok-bg); color:var(--ok); } .s-zu-viel { background:var(--lila-bg); color:var(--lila); }
.s-teilweise { background:var(--warn-bg); color:var(--warn); } .s-offen { background:var(--grau-bg); color:var(--leise); }
.s-ueberfaellig { background:var(--rot-bg); color:var(--rot); }
.chips { display:flex; flex-wrap:wrap; gap:.4rem; margin:.2rem 0 .8rem; }
.chip { border:1px solid var(--linie); background:var(--karte); color:var(--text); border-radius:99px; padding:.25rem .8rem;
        cursor:pointer; font:inherit; font-size:.85rem; }
.chip.an { border-color:var(--akzent); color:var(--akzent); font-weight:600; }
input, select { padding:.45rem .6rem; border:1px solid var(--linie); border-radius:8px; background:var(--karte);
                color:var(--text); font:inherit; }
input[type=search], input.breit { width:100%; max-width:420px; }
.knopf { padding:.45rem 1rem; background:var(--akzent); color:#fff; border:0; border-radius:8px; font:inherit;
         font-weight:600; cursor:pointer; text-decoration:none; display:inline-block; }
.knopf.leise { background:var(--grau-bg); color:var(--text); }
.knopf.klein { padding:.2rem .6rem; font-size:.82rem; }
.knopf:disabled { opacity:.5; cursor:default; }
.vorschlag { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; padding:.35rem 0; border-top:1px dashed var(--linie); }
.punkte { font-size:.8rem; color:var(--leise); }
.buchung h3 { margin:0 0 .2rem; font-size:1.05rem; display:flex; gap:.8rem; flex-wrap:wrap; align-items:baseline; }
.zeilen { display:flex; gap:.6rem; flex-wrap:wrap; align-items:center; margin-top:.5rem; }
.hinweis { background:var(--warn-bg); color:var(--warn); border-radius:10px; padding:.6rem 1rem; margin-bottom:1rem; }
.hinweis a { color:inherit; font-weight:700; }
.meldung { font-size:.85rem; }
.ok { color:var(--ok); } .fehler { color:var(--rot); }
#zone { border:2px dashed var(--linie); border-radius:12px; padding:2rem; text-align:center; color:var(--leise); }
#zone.aktiv { border-color:var(--akzent); color:var(--text); }
code { background:var(--grau-bg); padding:.05rem .35rem; border-radius:5px; font-size:.88em; word-break:break-all; }
"""

SKRIPT = """
async function sende(pfad, daten) {
  const r = await fetch(pfad, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(daten)});
  const j = await r.json().catch(() => ({fehler:'Antwort unlesbar'}));
  if (!r.ok || j.fehler) throw new Error(j.fehler || ('HTTP ' + r.status));
  return j;
}
function melde(el, text, ok) { if (el) { el.textContent = text; el.className = 'meldung ' + (ok ? 'ok' : 'fehler'); } }
// Uebersicht: Filter und Suche
function filtern() {
  const an = [...document.querySelectorAll('.chip.an')].map(c => c.dataset.f);
  const q = (document.getElementById('suche')?.value || '').toLowerCase();
  document.querySelectorAll('tr.zeile').forEach(tr => {
    const passt = (an.length === 0 || an.includes('alle') || an.includes(tr.dataset.status)
                   || (an.includes('probleme') && ['überfällig','teilweise','offen'].includes(tr.dataset.status)))
                  && tr.dataset.suche.includes(q);
    tr.style.display = passt ? '' : 'none';
    const d = document.getElementById('d' + tr.dataset.id); if (d && !passt) d.style.display = 'none';
  });
}
document.addEventListener('click', ev => {
  const chip = ev.target.closest('.chip');
  if (chip) { document.querySelectorAll('.chip').forEach(c => c.classList.toggle('an', c === chip)); filtern(); return; }
  const tr = ev.target.closest('tr.zeile');
  if (tr && !ev.target.closest('a,button')) {
    const d = document.getElementById('d' + tr.dataset.id); if (d) d.style.display = d.style.display === 'none' ? '' : 'none';
  }
});
async function aufheben(knopf, id) {
  if (!confirm('Zuordnung dieser Gutschrift aufheben? Sie steht danach wieder unter "Zu prüfen".')) return;
  knopf.disabled = true;
  try { await sende('/api/aufheben', {buchung:id}); location.reload(); } catch (x) { alert(x.message); knopf.disabled = false; }
}
// Zu pruefen
async function zuordnen(knopf, id, vertrag) {
  const karte = knopf.closest('.buchung');
  const monat = karte.querySelector('select.monat').value;
  const merken = karte.querySelector('input.merken')?.checked ?? true;
  if (vertrag === null) {
    const wert = karte.querySelector('input.suche').value;
    const opt = [...document.querySelectorAll('#vertraege option')].find(o => o.value === wert);
    if (!opt) { melde(karte.querySelector('.meldung'), 'Bitte einen Vertrag aus der Liste wählen.', false); return; }
    vertrag = +opt.dataset.id;
  }
  knopf.disabled = true;
  try {
    const j = await sende('/api/zuordnen', {buchung:id, vertrag, monat: monat || null, merken});
    melde(karte.querySelector('.meldung'), '✓ ' + j.text, true);
    karte.style.opacity = .55; karte.querySelectorAll('button').forEach(b => b.disabled = true);
    zaehler(-1);
    if (j.weitere) setTimeout(() => location.reload(), 1800);
  } catch (x) { melde(karte.querySelector('.meldung'), x.message, false); knopf.disabled = false; }
}
async function ignorieren(knopf, id, grund, immer) {
  const karte = knopf.closest('.buchung');
  knopf.disabled = true;
  try {
    await sende('/api/ignorieren', {buchung:id, grund, immer});
    melde(karte.querySelector('.meldung'), '✓ als „' + grund + '“ abgelegt' + (immer ? ' – dieser Zahler wird künftig ignoriert' : ''), true);
    karte.style.opacity = .55; karte.querySelectorAll('button').forEach(b => b.disabled = true);
    zaehler(-1);
  } catch (x) { melde(karte.querySelector('.meldung'), x.message, false); knopf.disabled = false; }
}
function zaehler(d) { const z = document.getElementById('anzahl-pruefen'); if (z) z.textContent = Math.max(0, +z.textContent + d); }
// Import
function dateienLesen(liste, pfad, ausgabe) {
  const out = document.getElementById(ausgabe);
  [...liste].forEach(datei => {
    const leser = new FileReader();
    leser.onload = async () => {
      const b64 = leser.result.split(',')[1];
      try {
        const j = await sende(pfad, {name: datei.name, daten: b64});
        out.insertAdjacentHTML('beforeend', '<div class="ok">✓ ' + j.text.replace(/</g,'&lt;').replace(/\\n/g,'<br>') + '</div>');
      } catch (x) { out.insertAdjacentHTML('beforeend', '<div class="fehler">' + datei.name + ': ' + x.message + '</div>'); }
    };
    leser.readAsDataURL(datei);
  });
}
function zoneVerdrahten(id, pfad, ausgabe) {
  const zone = document.getElementById(id); if (!zone) return;
  const feld = zone.querySelector('input[type=file]');
  zone.addEventListener('dragover', ev => { ev.preventDefault(); zone.classList.add('aktiv'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('aktiv'));
  zone.addEventListener('drop', ev => { ev.preventDefault(); zone.classList.remove('aktiv'); dateienLesen(ev.dataTransfer.files, pfad, ausgabe); });
  feld.addEventListener('change', () => dateienLesen(feld.files, pfad, ausgabe));
}
"""


def _status_klasse(status: str) -> str:
    return "s-" + status.replace(" ", "-").replace("ü", "ue").replace("ä", "ae")


def _status(status: str) -> str:
    return f"<span class='status {_status_klasse(status)}'>{e(status)}</span>"


class App:
    def __init__(self, db: Datenbank):
        self.db = db
        self.sperre = threading.Lock()
        self.demo = db.ordner.resolve() == DEMO_ORDNER.resolve()

    # ------------------------------------------------------------ Rahmen
    def seite(self, titel: str, aktiv: str, inhalt: str) -> str:
        offen = self.db.eins("SELECT COUNT(*) AS n FROM buchungen WHERE status = 'offen'")["n"]
        reiter = [("/", "Übersicht"), ("/pruefen", f"Zu prüfen (<span id='anzahl-pruefen'>{offen}</span>)"),
                  ("/mieter", "Mieter"), ("/import", "Import"), ("/einstellungen", "Einstellungen")]
        nav = "".join(f"<a href='{p}' class='{'aktiv' if p == aktiv else ''}'>{t}</a>" for p, t in reiter)
        demo = "<span class='demo'>DEMO – erfundene Daten</span>" if self.demo else ""
        return (f"<!doctype html><html lang='de'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{e(titel)} – Mieteingang</title>"
                f"<style>{STIL}</style><script>{SKRIPT}</script></head><body><header><b>Mieteingang</b>{nav}{demo}</header>"
                f"<main>{inhalt}</main></body></html>")

    # ------------------------------------------------------------ Uebersicht
    def uebersicht(self, monat: str | None) -> str:
        heute = dt.date.today()
        monat = monat if monat and geld.gueltiger_monat(monat) else geld.monat(heute)
        m = uebersicht.monat_berechnen(self.db, monat, heute)
        offen_summe = sum(max(z.soll - z.ist, 0) for z in m.zeilen)
        pruefen = self.db.eins("SELECT COUNT(*) AS n FROM buchungen WHERE status = 'offen'")["n"]
        teile = [f"""
<div class='monatnav'>
  <a class='knopf leise' href='/?monat={geld.monat_plus(monat, -1)}'>‹</a>
  <h1>{geld.monat_name(monat)}</h1>
  <a class='knopf leise' href='/?monat={geld.monat_plus(monat, 1)}'>›</a>
  <span class='leise'>fällig am {geld.datum_de(m.faellig)} (3. Werktag)</span>
  <span style='flex:1'></span>
  <a class='knopf leise' href='/export.csv?monat={monat}&offen=1'>Offene Posten als CSV</a>
</div>"""]
        if pruefen:
            teile.append(f"<div class='hinweis'>{pruefen} Gutschrift(en) konnten nicht sicher zugeordnet werden – "
                         f"<a href='/pruefen'>jetzt prüfen</a>. Bis dahin können hier Zahlungen fehlen.</div>")
        teile.append(f"""
<div class='kpis'>
  <div class='kpi'><small>Soll</small><strong>{geld.eur(m.summe('soll'))}</strong></div>
  <div class='kpi'><small>Eingegangen</small><strong>{geld.eur(m.summe('ist'))}</strong>
    <div class='balken'><span style='width:{m.quote * 100:.1f}%'></span></div></div>
  <div class='kpi'><small>Noch offen</small><strong>{geld.eur(offen_summe)}</strong></div>
  <div class='kpi'><small>Mietverhältnisse</small><strong>{len(m.zeilen)}</strong></div>
</div>""")
        chips = [("probleme", f"Nicht bezahlt ({m.anzahl('überfällig') + m.anzahl('teilweise') + m.anzahl('offen')})")]
        chips += [(s, f"{s} ({m.anzahl(s)})") for s in uebersicht.REIHENFOLGE if m.anzahl(s)]
        chips.append(("alle", "Alle"))
        teile.append("<div class='karte'><input type='search' id='suche' placeholder='Suchen: Name, Objekt, Mieternummer …' "
                     "oninput='filtern()'><div class='chips' style='margin-top:.6rem'>"
                     + "".join(f"<button class='chip{' an' if f == 'probleme' else ''}' data-f='{e(f)}'>{e(t)}</button>"
                               for f, t in chips) + "</div>")
        zeilen = []
        for z in m.zeilen:
            v = z.vertrag
            suche = e(f"{v.nummer} {v.name} {v.mitmieter} {v.objekt} {v.einheit}".lower())
            zahl = "<br>".join(f"{geld.datum_de(p['datum'])} {geld.eur(p['betrag_cent'])}" for p in z.zahlungen) or "–"
            zeilen.append(
                f"<tr class='zeile' data-id='{v.id}' data-status='{e(z.status)}' data-suche='{suche}'>"
                f"<td>{_status(z.status)}</td><td>{e(v.nummer)}</td><td>{e(v.objekt)}</td><td>{e(v.einheit)}</td>"
                f"<td><a href='/mieter/{v.id}'>{e(v.name)}</a></td>"
                f"<td class='z'>{geld.eur(z.soll)}</td><td class='z'>{geld.eur(z.ist)}</td>"
                f"<td class='z'>{geld.eur(z.differenz) if z.differenz else ''}</td>"
                f"<td class='z'>{geld.eur(z.saldo) if z.saldo else ''}</td><td class='z klein'>{zahl}</td></tr>")
            details = "".join(
                f"<div class='zeilen klein'><span>{geld.datum_de(p['datum'])}</span><b>{geld.eur(p['betrag_cent'])}</b>"
                f"<span>{e(p['name'] or '')}</span><span class='leise'>„{e(p['zweck'] or '')}“</span>"
                f"<span class='leise'>{'automatisch: ' + e(p['grund'] or '') if p['art'] == 'auto' else 'von Hand'}</span>"
                f"<button class='knopf leise klein' onclick='aufheben(this,{p['buchung_id']})'>Zuordnung aufheben</button></div>"
                for p in z.zahlungen) or "<span class='leise klein'>Keine Zahlung für diesen Monat.</span>"
            zeilen.append(f"<tr class='detail' id='d{v.id}' style='display:none'><td colspan='10'>{details}</td></tr>")
        teile.append("<div class='tabelle'><table><thead><tr><th>Status</th><th>Nr.</th><th>Objekt</th><th>Einheit</th>"
                     "<th>Mieter</th><th class='z'>Soll</th><th class='z'>Ist</th><th class='z'>Differenz</th>"
                     "<th class='z'>Rückstand ges.</th><th class='z'>Zahlungen</th></tr></thead><tbody>"
                     + "".join(zeilen) + "</tbody></table></div></div>"
                     "<p class='leise klein'>Rückstand gesamt = alle Monate seit Erfassungsbeginn "
                     f"({geld.monat_name(self.db.monat_seit())}), plus Anfangsrückstand. Negativ = Guthaben. "
                     "Zeile anklicken zeigt die einzelnen Zahlungen.</p><script>filtern()</script>")
        return self.seite(geld.monat_name(monat), "/", "".join(teile))

    # ------------------------------------------------------------ Zu pruefen
    def pruefen(self) -> str:
        offene = self.db.q("SELECT * FROM buchungen WHERE status = 'offen' ORDER BY datum, id")
        vertraege = lade_vertraege(self.db)
        liste = "".join(f"<option value='{e(v.nummer)} · {e(v.name)} · {e(v.objekt)} {e(v.einheit)}' data-id='{v.id}'>"
                        for v in vertraege)
        if not offene:
            return self.seite("Zu prüfen", "/pruefen", "<div class='karte'>Alles zugeordnet – nichts zu prüfen. ✓</div>")
        bewerter = abgleich.Bewerter(self.db, vertraege)
        karten = [f"<datalist id='vertraege'>{liste}</datalist>",
                  f"<p class='leise'>{len(offene)} Gutschriften konnten nicht sicher zugeordnet werden. Vorschlag "
                  "anklicken – das Programm merkt sich das Konto des Zahlers und erkennt ihn nächsten Monat selbst.</p>"]
        for b in offene:
            datum = geld.datum(b["datum"])
            monate, woher = abgleich.monate_fuer(b["zweck"] or "", datum)
            auswahl = [f"<option value=''>Monat automatisch ({', '.join(geld.monat_name(x) for x in monate)} – {woher})</option>"]
            for n in range(-3, 2):
                x = geld.monat_plus(geld.monat(datum), n)
                auswahl.append(f"<option value='{x}'>{geld.monat_name(x)}</option>")
            vorschlaege = bewerter.bewerte(b, monate)[:4]
            vs = "".join(
                f"<div class='vorschlag'><button class='knopf klein' onclick='zuordnen(this,{b['id']},{s.vertrag.id})'>"
                f"{e(s.vertrag.nummer)} · {e(s.vertrag.name)}</button><span>{e(s.vertrag.objekt)}, {e(s.vertrag.einheit)} · "
                f"Soll {geld.eur(s.vertrag.soll(monate[0]))}</span>"
                f"<span class='punkte'>{s.punkte} Punkte: {e(', '.join(s.gruende))}</span></div>" for s in vorschlaege)
            if not vs:
                vs = "<div class='vorschlag leise klein'>Kein passender Vertrag gefunden.</div>"
            konto = f"Konto …{e(b['iban_ende'])}" if b["iban_ende"] else "ohne IBAN"
            notiz = f"<div class='hinweis' style='margin:.4rem 0'>{e(b['notiz'])}</div>" if b["notiz"] else ""
            karten.append(f"""
<div class='karte buchung'>
  <h3><span>{geld.datum_de(datum)}</span><span>{geld.eur(b['betrag_cent'])}</span><span>{e(b['name'] or '–')}</span>
      <span class='leise klein'>{konto} · Eingang auf {e(b['konto'] or '')}</span></h3>
  <div class='leise'>Verwendungszweck: „{e(b['zweck'] or '')}“</div>{notiz}
  {vs}
  <div class='zeilen'>
    <input class='suche breit' list='vertraege' placeholder='anderen Vertrag suchen: Name, Nr., Objekt …'>
    <button class='knopf leise klein' onclick='zuordnen(this,{b['id']},null)'>zuordnen</button>
  </div>
  <div class='zeilen'>
    <select class='monat'>{''.join(auswahl)}</select>
    <label class='klein'><input type='checkbox' class='merken' checked> Zahlerkonto merken</label>
    <span style='flex:1'></span>
    <button class='knopf leise klein' onclick="ignorieren(this,{b['id']},'Kaution',false)">Kaution</button>
    <button class='knopf leise klein' onclick="ignorieren(this,{b['id']},'keine Miete',false)">Keine Miete</button>
    <button class='knopf leise klein' onclick="ignorieren(this,{b['id']},'keine Miete',true)">Zahler immer ignorieren</button>
  </div>
  <div class='meldung'></div>
</div>""")
        return self.seite("Zu prüfen", "/pruefen", "".join(karten))

    # ------------------------------------------------------------ Mieter
    def mieter_liste(self) -> str:
        heute = geld.monat(dt.date.today())
        ist = self.db.ist_je_vertrag_monat()
        ab = self.db.monat_seit()
        konten = {r["vertrag_id"]: r["n"] for r in
                  self.db.q("SELECT vertrag_id, COUNT(*) AS n FROM zahler GROUP BY vertrag_id")}
        zeilen = []
        for v in lade_vertraege(self.db):
            s = saldo(v, heute, ab, ist) if heute >= ab else 0
            status = "aktiv" if v.aktiv(heute) else ("ausgezogen" if v.letzter_monat and v.letzter_monat < heute else "künftig")
            such = e(f"{v.nummer} {v.name} {v.mitmieter} {v.objekt} {v.einheit}".lower())
            zeilen.append(f"<tr class='zeile' data-id='{v.id}' data-status='{status}' data-suche='{such}' "
                          f"onclick=\"location='/mieter/{v.id}'\"><td>{e(v.nummer)}</td><td>{e(v.objekt)}</td>"
                          f"<td>{e(v.einheit)}</td><td>{e(v.name)}</td><td>{status}</td>"
                          f"<td class='z'>{geld.eur(v.soll(heute)) if v.aktiv(heute) else ''}</td>"
                          f"<td class='z'>{geld.eur(s) if s else ''}</td><td class='z'>{konten.get(v.id, 0)}</td></tr>")
        inhalt = ("<div class='karte'><input type='search' id='suche' placeholder='Suchen …' oninput='filtern()'>"
                  "<div class='chips' style='margin-top:.6rem'><button class='chip an' data-f='aktiv'>aktiv</button>"
                  "<button class='chip' data-f='künftig'>künftig</button><button class='chip' data-f='ausgezogen'>ausgezogen</button>"
                  "<button class='chip' data-f='alle'>alle</button></div><div class='tabelle'><table><thead><tr>"
                  "<th>Nr.</th><th>Objekt</th><th>Einheit</th><th>Mieter</th><th>Status</th><th class='z'>Miete</th>"
                  "<th class='z'>Rückstand</th><th class='z'>bekannte Konten</th></tr></thead><tbody>"
                  + "".join(zeilen) + "</tbody></table></div></div><script>filtern()</script>")
        return self.seite("Mieter", "/mieter", inhalt)

    def mieter(self, vertrag_id: int) -> str:
        rows = self.db.vertraege(vertrag_id)
        if not rows:
            return self.seite("Mieter", "/mieter", "<div class='karte'>Unbekannter Vertrag.</div>")
        r = rows[0]
        v = next(x for x in lade_vertraege(self.db) if x.id == vertrag_id)
        ist = self.db.ist_je_vertrag_monat()
        ab = self.db.monat_seit()
        heute = geld.monat(dt.date.today())
        bis = min(heute, v.letzter_monat or heute)
        verlauf = []
        for m in reversed(geld.monate(max(ab, v.erster_monat), bis)) if bis >= max(ab, v.erster_monat) else []:
            soll, bez = v.soll(m), ist.get((v.id, m), 0)
            st = uebersicht.status_fuer(soll, bez, dt.date.today() > geld.faellig_am(m) + dt.timedelta(
                days=self.db.einstellung("karenz_tage", uebersicht.KARENZ_TAGE)))
            verlauf.append(f"<tr><td><a href='/?monat={m}'>{geld.monat_name(m)}</a></td><td>{_status(st)}</td>"
                           f"<td class='z'>{geld.eur(soll)}</td><td class='z'>{geld.eur(bez)}</td>"
                           f"<td class='z'>{geld.eur(saldo(v, m, ab, ist))}</td></tr>")
        zahlungen = "".join(
            f"<tr><td>{geld.datum_de(p['datum'])}</td><td class='z'>{geld.eur(p['betrag_cent'])}</td><td>{p['monat']}</td>"
            f"<td>{e(p['name'] or '')}<br><span class='leise klein'>„{e(p['zweck'] or '')}“</span></td>"
            f"<td class='klein'>{'auto' if p['art'] == 'auto' else 'Hand'}</td>"
            f"<td><button class='knopf leise klein' onclick='aufheben(this,{p['buchung_id']})'>aufheben</button></td></tr>"
            for p in reversed(self.db.zahlungen(vertrag_id=vertrag_id)))
        konten = "".join(f"<li>Konto …{e(k['iban_ende'] or '????')} <span class='leise'>({e(k['bezeichnung'] or '')}, "
                         f"{e(k['quelle'])})</span></li>"
                         for k in self.db.q("SELECT * FROM zahler WHERE vertrag_id = ?", (vertrag_id,)))
        stufen = "".join(f"<li>ab {geld.monat_name(a)}: {geld.eur(k)} kalt + {geld.eur(n)} NK = <b>{geld.eur(k + n)}</b></li>"
                         for a, k, n in v.stufen)
        inhalt = f"""
<p><a href='/mieter'>‹ alle Mieter</a></p>
<div class='karte'><h2 style='margin:0'>{e(v.name)} <span class='leise'>{e(v.nummer)}</span></h2>
  <div>{e(r['objekt'])}, {e(r['einheit'])} · {e(r['strasse'] or '')} {e(r['plz'] or '')} {e(r['ort'] or '')}</div>
  <div class='leise klein'>Mietbeginn {geld.datum_de(v.beginn)}{' · Mietende ' + geld.datum_de(v.ende) if v.ende else ''}
  {' · Mitmieter: ' + e(v.mitmieter) if v.mitmieter else ''}{' · ' + e(r['email']) if r['email'] else ''}
  {' · ' + e(r['telefon']) if r['telefon'] else ''}</div>
  <div class='kpis' style='margin-top:.8rem'>
    <div class='kpi'><small>Miete</small><ul style='margin:.2rem 0;padding-left:1.1rem'>{stufen}</ul></div>
    <div class='kpi'><small>Bekannte Zahlerkonten</small><ul style='margin:.2rem 0;padding-left:1.1rem'>{konten or '<li class=leise>noch keins</li>'}</ul></div>
    <div class='kpi'><small>Referenzen im Zweck</small>{e('; '.join(v.referenzen)) or '<span class=leise>–</span>'}</div>
  </div></div>
<div class='karte'><h3 style='margin-top:0'>Verlauf</h3><div class='tabelle'><table><thead><tr><th>Monat</th><th>Status</th>
  <th class='z'>Soll</th><th class='z'>Ist</th><th class='z'>Rückstand ges.</th></tr></thead><tbody>{''.join(verlauf)}</tbody></table></div></div>
<div class='karte'><h3 style='margin-top:0'>Zahlungen</h3><div class='tabelle'><table><thead><tr><th>Datum</th><th class='z'>Betrag</th>
  <th>für</th><th>Zahler / Zweck</th><th>Zuordnung</th><th></th></tr></thead><tbody>{zahlungen}</tbody></table></div></div>"""
        return self.seite(v.name, "/mieter", inhalt)

    # ------------------------------------------------------------ Import
    def importseite(self) -> str:
        eingang = einlesen.eingang_ordner(self.db)
        wartend = [p.name for p in eingang.iterdir() if p.is_file()]
        verlauf = "".join(f"<tr><td>{e(r['am'][:16].replace('T', ' '))}</td><td>{e(r['datei'] or '')}</td>"
                          f"<td>{e(r['format'] or '')}</td><td class='z'>{r['neu'] or 0}</td><td class='z'>{r['doppelt'] or 0}</td></tr>"
                          for r in self.db.q("SELECT * FROM importe ORDER BY id DESC LIMIT 25"))
        inhalt = f"""
<div class='karte'><h3 style='margin-top:0'>Kontoauszug einlesen</h3>
  <p class='leise'>Im Online-Banking: Umsätze → Export → <b>CAMT</b> (am besten) oder <b>CSV</b>. Zeitraum darf sich
  mit dem letzten Export überschneiden – doppelte Buchungen werden erkannt.</p>
  <div id='zone'><p>Datei hierher ziehen oder</p><input type='file' multiple accept='.csv,.txt,.xml'></div>
  <div id='ausgabe' class='meldung' style='margin-top:.6rem'></div>
</div>
<div class='karte'><h3 style='margin-top:0'>Eingangsordner</h3>
  <p class='leise'>Dateien, die dort abgelegt werden, liest das Programm beim Start von selbst ein:<br><code>{e(str(eingang))}</code></p>
  <p>{len(wartend)} Datei(en) warten{': ' + e(', '.join(wartend)) if wartend else ''}.</p>
  <button class='knopf' onclick="sende('/api/eingang',{{}}).then(j=>{{document.getElementById('ausgabe2').innerHTML=j.text.replace(/\\n/g,'<br>')}}).catch(x=>alert(x.message))">Jetzt einlesen</button>
  <div id='ausgabe2' class='meldung ok' style='margin-top:.6rem'></div>
</div>
<div class='karte'><h3 style='margin-top:0'>Letzte Importe</h3><div class='tabelle'><table><thead><tr><th>Zeit</th><th>Datei</th>
  <th>Format</th><th class='z'>neu</th><th class='z'>schon da</th></tr></thead><tbody>{verlauf}</tbody></table></div></div>
<script>zoneVerdrahten('zone','/api/import','ausgabe')</script>"""
        return self.seite("Import", "/import", inhalt)

    # ------------------------------------------------------------ Einstellungen
    def einstellungen(self) -> str:
        anzahl = self.db.eins("SELECT COUNT(*) AS n FROM vertraege")["n"]
        inhalt = f"""
<div class='karte'><h3 style='margin-top:0'>Stammdaten (Objekte, Mieter, Verträge)</h3>
  <p>{anzahl} Verträge erfasst. Eine Zeile je Mietvertrag, Schlüssel ist die Mieternummer – erneutes Einlesen aktualisiert.
  IBANs werden beim Einlesen in eine Kennung umgewandelt und nicht gespeichert.</p>
  <p><a class='knopf leise' href='/vorlage.csv'>Vorlage herunterladen</a></p>
  <div id='zone'><p>Stammdaten-CSV hierher ziehen oder</p><input type='file' accept='.csv,.txt'></div>
  <div id='ausgabe' class='meldung' style='margin-top:.6rem'></div>
</div>
<div class='karte'><h3 style='margin-top:0'>Abgleich</h3>
  <div class='zeilen'><label>Zahlungen führen ab <input type='month' id='ab' value='{e(self.db.erfassung_ab or '')}'></label>
  <label>Karenztage nach Fälligkeit <input type='number' id='karenz' min='0' max='20' style='width:5rem'
     value='{self.db.einstellung("karenz_tage", uebersicht.KARENZ_TAGE)}'></label>
  <button class='knopf' onclick="sende('/api/einstellungen',{{ab:document.getElementById('ab').value,karenz:+document.getElementById('karenz').value}}).then(()=>melde(document.getElementById('m3'),'gespeichert',true)).catch(x=>melde(document.getElementById('m3'),x.message,false))">Speichern</button>
  <span id='m3' class='meldung'></span></div>
  <p class='leise klein'>Vor dem Erfassungsbeginn gilt nichts als offen. Rückstände von davor gehören als „Rueckstand“ in die Stammdaten.</p>
  <button class='knopf leise' onclick="sende('/api/abgleich',{{}}).then(j=>melde(document.getElementById('m4'),j.text,true))">Offene Gutschriften neu abgleichen</button>
  <span id='m4' class='meldung'></span>
</div>
<div class='karte'><h3 style='margin-top:0'>Datenordner</h3>
  <p><code>{e(str(self.db.ordner))}</code></p>
  <p class='leise klein'>Hier liegen Datenbank, Schlüssel und Kontoauszüge. Diesen Ordner regelmäßig sichern (ganzer Ordner,
  inklusive <code>schluessel.key</code>). Er gehört nicht in den Projektordner und nie in git.</p>
</div>
<script>zoneVerdrahten('zone','/api/stammdaten','ausgabe')</script>"""
        return self.seite("Einstellungen", "/einstellungen", inhalt)

    # ------------------------------------------------------------ Aktionen
    def aktion(self, pfad: str, d: dict) -> dict:
        db = self.db
        if pfad == "/api/zuordnen":
            v = next((x for x in lade_vertraege(db) if x.id == int(d["vertrag"])), None)
            if not v or not db.buchung(int(d["buchung"])):
                raise ValueError("Buchung oder Vertrag unbekannt")
            monat = d.get("monat")
            if monat and not geld.gueltiger_monat(monat):
                raise ValueError("Monat ungültig")
            teile = abgleich.zuordnen(db, int(d["buchung"]), v, [monat] if monat else None,
                                      merken=bool(d.get("merken", True)))
            text = f"{v.nummer} {v.name}: " + ", ".join(f"{geld.monat_name(m)} {geld.eur(c)}" for m, c in teile)
            weitere = abgleich.abgleichen(db).automatisch    # mit dem neu gelernten Konto
            if weitere:
                text += f" – dadurch {weitere} weitere Gutschrift(en) automatisch erkannt"
            return {"text": text, "weitere": weitere}
        if pfad == "/api/ignorieren":
            abgleich.ignorieren(db, int(d["buchung"]), str(d.get("grund", ""))[:100], bool(d.get("immer")))
            return {"text": "ok"}
        if pfad == "/api/aufheben":
            db.zuordnung_aufheben(int(d["buchung"]))
            return {"text": "ok"}
        if pfad == "/api/import":
            ziel = einlesen.eingang_ordner(db) / Path(str(d["name"])).name
            if ziel.suffix.lower() not in einlesen.DATEI_ENDUNGEN:
                raise ValueError(f"{ziel.name}: bitte CSV oder CAMT-XML aus dem Online-Banking")
            ziel.write_bytes(base64.b64decode(d["daten"]))
            ergebnisse = einlesen.eingang_verarbeiten(db)
            text = "\n".join(x.text() for x in ergebnisse)
            if any(x.fehler for x in ergebnisse):
                raise ValueError(text)
            return {"text": text + "\nAbgleich: " + abgleich.abgleichen(db).text()}
        if pfad == "/api/eingang":
            ergebnisse = einlesen.eingang_verarbeiten(db)
            text = "\n".join(x.text() for x in ergebnisse) or "Keine Dateien im Eingangsordner."
            return {"text": text + "\nAbgleich: " + abgleich.abgleichen(db).text()}
        if pfad == "/api/abgleich":
            return {"text": abgleich.abgleichen(db).text()}
        if pfad == "/api/stammdaten":
            text = base64.b64decode(d["daten"])
            erg = stammdaten.einlesen_text(db, _dekodieren(text))
            return {"text": erg.text() + "\nAbgleich: " + abgleich.abgleichen(db).text()}
        if pfad == "/api/einstellungen":
            if d.get("ab"):
                if not geld.gueltiger_monat(d["ab"]):
                    raise ValueError("Monat ungültig")
                db.setze_meta("erfassung_ab", d["ab"])
            db.setze_meta("karenz_tage", str(max(0, min(20, int(d.get("karenz", uebersicht.KARENZ_TAGE))))))
            return {"text": "ok"}
        raise LookupError(pfad)


class Handler(http.server.BaseHTTPRequestHandler):
    app: App
    ERLAUBTE_HOSTS = ("127.0.0.1", "localhost")

    def log_message(self, *_):
        pass

    def _host_ok(self) -> bool:
        # Schutz gegen DNS-Rebinding und fremde Webseiten, die an localhost senden
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        herkunft = self.headers.get("Origin")
        if host not in self.ERLAUBTE_HOSTS:
            return False
        if herkunft and urlparse(herkunft).hostname not in self.ERLAUBTE_HOSTS:
            return False
        return True

    def _senden(self, inhalt: str | bytes, typ: str = "text/html; charset=utf-8", code: int = 200,
                extra: dict | None = None):
        daten = inhalt.encode("utf-8") if isinstance(inhalt, str) else inhalt
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(daten)

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._senden("Nur lokal erreichbar.", "text/plain; charset=utf-8", 403)
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        app = self.app
        try:
            with app.sperre:
                if url.path == "/":
                    return self._senden(app.uebersicht(q.get("monat")))
                if url.path == "/pruefen":
                    return self._senden(app.pruefen())
                if url.path == "/mieter":
                    return self._senden(app.mieter_liste())
                if url.path.startswith("/mieter/") and url.path[8:].isdigit():
                    return self._senden(app.mieter(int(url.path[8:])))
                if url.path == "/import":
                    return self._senden(app.importseite())
                if url.path == "/einstellungen":
                    return self._senden(app.einstellungen())
                if url.path == "/export.csv":
                    monat = q.get("monat") if geld.gueltiger_monat(q.get("monat", "")) else geld.monat(dt.date.today())
                    m = uebersicht.monat_berechnen(app.db, monat)
                    return self._senden(uebersicht.als_csv(m, q.get("offen") == "1").encode("utf-8-sig"),
                                        "text/csv; charset=utf-8", extra={
                                            "Content-Disposition": f"attachment; filename=offene-posten-{monat}.csv"})
                if url.path == "/vorlage.csv":
                    return self._senden(stammdaten.vorlage().encode("utf-8-sig"), "text/csv; charset=utf-8",
                                        extra={"Content-Disposition": "attachment; filename=stammdaten_vorlage.csv"})
        except Exception:  # noqa: BLE001 - Fehler anzeigen statt Seite leer lassen
            return self._senden(f"<pre>{e(traceback.format_exc())}</pre>", code=500)
        self._senden("Nicht gefunden", "text/plain; charset=utf-8", 404)

    def do_POST(self):  # noqa: N802
        if not self._host_ok() or not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._senden(json.dumps({"fehler": "nicht erlaubt"}), "application/json", 403)
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge > 30_000_000:
            return self._senden(json.dumps({"fehler": "Datei zu groß"}), "application/json", 413)
        try:
            daten = json.loads(self.rfile.read(laenge) or b"{}")
            with self.app.sperre:
                antwort = self.app.aktion(urlparse(self.path).path, daten)
            self._senden(json.dumps(antwort), "application/json")
        except LookupError:
            self._senden(json.dumps({"fehler": "unbekannte Aktion"}), "application/json", 404)
        except (ValueError, KeyError, TypeError) as fehler:
            self._senden(json.dumps({"fehler": str(fehler)}), "application/json", 400)
        except Exception as fehler:  # noqa: BLE001
            traceback.print_exc()
            self._senden(json.dumps({"fehler": f"interner Fehler: {fehler}"}), "application/json", 500)


def server(db: Datenbank, port: int = 0) -> http.server.ThreadingHTTPServer:
    Handler.app = App(db)
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)


def starten(db: Datenbank, port: int = 8780, browser: bool = True) -> int:
    for erg in einlesen.eingang_verarbeiten(db):
        print(erg.text())
    print("Abgleich:", abgleich.abgleichen(db).text())
    for versuch in range(port, port + 20):
        try:
            srv = server(db, versuch)
            break
        except OSError:
            continue
    else:
        print("Kein freier Port gefunden.")
        return 1
    adresse = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Mieteingang läuft: {adresse}  (Beenden: Strg+C oder Fenster schließen)")
    if browser:
        threading.Timer(0.6, lambda: webbrowser.open(adresse)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
